import torch
import torch.nn as nn
import torch.optim as optim
import warnings
# from sklearn.decomposition import PCA # CPU 기반 PCA를 사용하려면 주석 해제

class RecursiveOptimizerV2:
    def __init__(self, model, loss_fn, optimizer_type='adam', lr=0.001,
                 activation_threshold=0.05, activation_max_depth=3,
                 activation_switch_trigger_grad_norm_threshold=1e-2, # 그래디언트 기반 활성화 스위칭 임계값
                 activation_switch_loss_stagnation_patience=10, # 손실 정체 기반 활성화 스위칭 (반복 횟수)
                 momentum_base=0.85, momentum_max=0.95, momentum_cycle_len=200, # For SGD
                 agc_clipping_ratio=0.02, agc_eps=1e-3, # For proper AGC
                 pca_target_dim_ratio=0.5, pca_freq=500, # PCA 관련 파라미터 (비율로 목표 차원 설정)
                 use_pca_dim_reduction=True,
                 verbose=1): # 0: 없음, 1: 에포크/주요 이벤트, 2: 상세 단계

        self.model = model
        self.loss_fn = loss_fn
        self.verbose = verbose

        # Optimizer
        if optimizer_type.lower() == 'adam':
            self.optimizer = optim.Adam(model.parameters(), lr=lr)
            if self.verbose > 0: print("[Lumina Log] Optimizer: Adam")
        elif optimizer_type.lower() == 'sgd':
            self.optimizer = optim.SGD(model.parameters(), lr=lr, momentum=momentum_base)
            if self.verbose > 0: print(f"[Lumina Log] Optimizer: SGD with base momentum {momentum_base}")
        else:
            warnings.warn(f"Unsupported optimizer_type: {optimizer_type}. Defaulting to Adam.")
            self.optimizer = optim.Adam(model.parameters(), lr=lr)
            if self.verbose > 0: print("[Lumina Log] Optimizer: Adam (defaulted)")
        self.optimizer_type = optimizer_type.lower()

        # Adaptive Activation Switching
        self.activations = [nn.ReLU(), nn.Tanh(), nn.Sigmoid(), nn.LeakyReLU(0.1), nn.GELU()]
        self.global_activation_idx = 0 # 전역적으로 선택된 주 활성화 인덱스
        self.activation_threshold = activation_threshold
        self._local_activation_recursion_depth = 0
        self.activation_max_depth = activation_max_depth
        self.last_output_mean_abs = None
        self.activation_switch_trigger_grad_norm_threshold = activation_switch_trigger_grad_norm_threshold
        self.activation_switch_loss_stagnation_patience = activation_switch_loss_stagnation_patience
        self._loss_stagnation_counter = 0
        self._last_avg_loss_for_stagnation = float('inf')


        # Cyclical Momentum Shifting (for SGD)
        self.momentum_base = momentum_base
        self.momentum_max = momentum_max
        self.momentum_cycle_len = momentum_cycle_len
        self._momentum_cycle_position = 0

        # Adaptive Gradient Clipping (AGC - parameter norm based)
        self.agc_clipping_ratio = agc_clipping_ratio
        self.agc_eps = agc_eps

        # Dimensional Reduction Scheduling (PCA for input data)
        self.use_pca_dim_reduction = use_pca_dim_reduction
        self.pca_target_dim_ratio = pca_target_dim_ratio # 원본 차원 대비 목표 차원 비율
        self.pca_freq = pca_freq # 몇 iteration 마다 PCA 적용
        self._current_pca_target_dim = None # 실제 적용될 목표 차원 수
        # self.pca_reducer = None # For sklearn PCA

        # Internal state
        self.iterations = 0
        self.current_epoch = 0
        self.last_loss = None
        self.avg_gradient_norm = None # 이전 스텝의 평균 그래디언트 놈

    def _log(self, message, level=1):
        if self.verbose >= level:
            print(f"[Lumina Log - OptimizerV2] {message}")

    def _update_global_activation_choice(self):
        """전역 활성화 함수 인덱스를 그래디언트 노름 또는 손실 정체에 따라 업데이트"""
        switched = False
        # 1. 그래디언트 노름 기반 (너무 작으면 변경 시도)
        if self.avg_gradient_norm is not None and self.avg_gradient_norm < self.activation_switch_trigger_grad_norm_threshold:
            self.global_activation_idx = (self.global_activation_idx + 1) % len(self.activations)
            switched = True
            self._log(f"Activation switched globally due to low avg grad norm ({self.avg_gradient_norm:.2e}). New global_activation_idx: {self.global_activation_idx} ({self.activations[self.global_activation_idx].__class__.__name__})", level=1)

        # 2. 손실 정체 기반 (일정 기간 손실 감소 없으면 변경 시도)
        if not switched and self.last_loss is not None:
            if self.last_loss >= self._last_avg_loss_for_stagnation * 0.999: # 거의 변화 없거나 증가하면
                self._loss_stagnation_counter += 1
            else:
                self._loss_stagnation_counter = 0 # 리셋
                self._last_avg_loss_for_stagnation = self.last_loss

            if self._loss_stagnation_counter >= self.activation_switch_loss_stagnation_patience:
                self.global_activation_idx = (self.global_activation_idx + 1) % len(self.activations)
                self._loss_stagnation_counter = 0 # 리셋
                self._last_avg_loss_for_stagnation = float('inf') # 리셋
                switched = True
                self._log(f"Activation switched globally due to loss stagnation. New global_activation_idx: {self.global_activation_idx} ({self.activations[self.global_activation_idx].__class__.__name__})", level=1)
        
        if switched: # 스위칭 발생 시 로컬 재귀 깊이 초기화
             self._local_activation_recursion_depth = 0


    def _adaptive_activation_switching(self, current_output_tensor):
        """
        선택된 전역 활성화 함수를 기준으로, 필요시 로컬에서 재귀적으로 다른 활성화 함수 시도.
        사용자님의 V1 코드 구조를 따르되, 시작점은 `global_activation_idx`가 됨.
        """
        # 시도할 활성화 함수 인덱스: 전역 인덱스 + 로컬 재귀 깊이
        try_activation_idx = (self.global_activation_idx + self._local_activation_recursion_depth) % len(self.activations)
        active_fn = self.activations[try_activation_idx]
        activated_output = active_fn(current_output_tensor)
        
        self.last_output_mean_abs = torch.abs(activated_output.detach()).mean().item()

        if self.last_output_mean_abs < self.activation_threshold and \
           self._local_activation_recursion_depth < self.activation_max_depth:
            
            self._log(f"  Local activation switch: Output mean {self.last_output_mean_abs:.2e} < threshold {self.activation_threshold}. Trying next. Depth: {self._local_activation_recursion_depth + 1}", level=2)
            self._local_activation_recursion_depth += 1
            return self._adaptive_activation_switching(current_output_tensor)
        
        # 현재 스텝에서 성공적으로 활성화 함수를 찾았거나 최대 깊이에 도달하면, 다음 step을 위해 로컬 깊이 리셋
        self._local_activation_recursion_depth = 0
        if self.verbose >=2 and self.last_output_mean_abs >= self.activation_threshold :
             self._log(f"  Activation found: {active_fn.__class__.__name__} (Output mean: {self.last_output_mean_abs:.2e})", level=2)

        return activated_output

    def _cyclical_momentum_shifting(self):
        """ 주기적 모멘텀 (SGD 옵티마이저 사용 시) """
        if self.optimizer_type == 'sgd':
            self._momentum_cycle_position += 1
            # cycle_progress: 0에서 1로 선형적으로 증가했다가 다시 0으로 (삼각파의 절반 형태)
            # 더 부드러운 주기 (예: 코사인)도 가능하나, 여기서는 단순 선형 사용
            current_cycle_point = self._momentum_cycle_position % self.momentum_cycle_len
            
            # 여기서는 단순하게 주기의 절반은 증가, 절반은 감소하는 형태로 구현 (V자 또는 ^자 형태)
            # User's V1 코드에서는 선형 증가만 있었음. 좀 더 주기적인 형태로 수정.
            # 예: 0 -> 1 (절반), 1 -> 0 (나머지 절반)
            ratio_in_cycle = current_cycle_point / self.momentum_cycle_len
            if ratio_in_cycle < 0.5: # 상승 구간
                scale = 2 * ratio_in_cycle 
            else: # 하강 구간
                scale = 2 * (1 - ratio_in_cycle)
            
            new_momentum = self.momentum_base + (self.momentum_max - self.momentum_base) * scale
            
            for param_group in self.optimizer.param_groups:
                param_group['momentum'] = new_momentum
            if self.iterations % 50 == 0: # 로그 빈도 조절
                self._log(f"  SGD Momentum updated to: {new_momentum:.4f} (Cycle pos: {current_cycle_point}/{self.momentum_cycle_len})", level=2)


    def _adaptive_gradient_clipping_agc(self):
        """
        Adaptive Gradient Clipping (AGC) - 파라미터 노름 기반.
        NFNet 등에서 사용된 방식과 유사.
        """
        total_grad_norm_before_clip = 0.0
        num_params_with_grad = 0

        for param in self.model.parameters():
            if param.grad is None:
                continue
            
            param_norm = torch.maximum(torch.linalg.norm(param.detach()), torch.tensor(self.agc_eps, device=param.device))
            grad_norm = torch.linalg.norm(param.grad.detach())
            total_grad_norm_before_clip += grad_norm.item()
            num_params_with_grad +=1
            
            max_norm = param_norm * self.agc_clipping_ratio
            
            trigger_agc = grad_norm > max_norm
            
            if trigger_agc:
                clip_coef = max_norm / (grad_norm + 1e-6) # 안정성을 위해 분모에 작은 값 추가
                param.grad.detach().mul_(clip_coef)
                self._log(f"    AGC applied to a parameter: grad_norm {grad_norm:.2e} > max_norm {max_norm:.2e}. Clipped with coef {clip_coef:.2f}", level=2)
        
        if num_params_with_grad > 0:
            self.avg_gradient_norm = total_grad_norm_before_clip / num_params_with_grad # 클리핑 전 그래디언트 노름 평균 저장
        else:
            self.avg_gradient_norm = 0.0


    def _dimensional_reduction_scheduling_pca(self, x_batch):
        """ PyTorch 연산 기반 PCA를 사용하여 입력 데이터의 차원을 축소 (스케줄링) """
        if not self.use_pca_dim_reduction or x_batch.ndim < 2 or x_batch.size(1) <= 1: # 이미 1차원이거나 더 작으면 수행 안 함
            return x_batch

        # 첫 호출 시 또는 차원 정보 없을 시 목표 차원 설정
        if self._current_pca_target_dim is None:
            self._current_pca_target_dim = int(x_batch.size(1) * self.pca_target_dim_ratio)
            self._current_pca_target_dim = max(1, self._current_pca_target_dim) # 최소 1차원
            self._log(f"PCA target dimension initialized to {self._current_pca_target_dim} (ratio: {self.pca_target_dim_ratio} of {x_batch.size(1)})", level=1)

        if self.iterations > 0 and self.iterations % self.pca_freq == 0 and x_batch.size(1) > self._current_pca_target_dim :
            self._log(f"  Applying PCA: Input dim {x_batch.size(1)} -> Target dim {self._current_pca_target_dim}", level=1)
            try:
                # 1. Center data (feature-wise mean)
                mean = torch.mean(x_batch, dim=0, keepdim=True)
                x_centered = x_batch - mean
                
                # 2. SVD on centered data (covariance matrix의 eigendecomposition 대안)
                #    U는 left singular vectors, S는 singular values, V는 right singular vectors (principal components)
                U, S, V = torch.linalg.svd(x_centered, full_matrices=False)
                
                # V의 행들이 주성분. V.T로 하면 열들이 주성분.
                # x_centered @ V.T[:, :num_components]
                components_to_keep = V[:self._current_pca_target_dim, :] # V는 (features, features) 또는 (features, min(batch, features)) 형태. 주성분은 행에 있음.
                
                # 3. Project data
                x_reduced = x_centered @ components_to_keep.T
                
                self._log(f"    PCA success. New dim: {x_reduced.size(1)}", level=2)
                return x_reduced
            except Exception as e:
                self._log(f"    PCA failed: {e}. Returning original data.", level=1)
                warnings.warn(f"PCA dimensional reduction failed: {e}")
                return x_batch
        return x_batch

    def epoch_start(self, epoch_num):
        self.current_epoch = epoch_num
        self._log(f"Epoch {self.current_epoch} started.", level=1)
        # 에포크 시작 시 전역 활성화 함수 선택 전략 업데이트
        if self.iterations > 0 : # 첫 에포크 시작 시에는 아직 정보 부족
             self._update_global_activation_choice()

    def step(self, x_batch, y_batch):
        self.model.train()
        self.optimizer.zero_grad()

        # 1. 차원 축소 (PCA)
        x_processed = self._dimensional_reduction_scheduling_pca(x_batch)
        
        # 2. 모델 순전파
        output = self.model(x_processed)
        
        # 3. 활성화 함수 스위칭 (모델 출력에 적용 - 사용자님 V1 구조 유지)
        #    _update_global_activation_choice는 epoch_start 또는 loss 계산 후 호출될 수 있음
        #    여기서는 매 스텝마다 로컬 재귀 시도 가능성을 열어둠.
        output_activated = self._adaptive_activation_switching(output)
        
        # 4. 손실 계산
        loss = self.loss_fn(output_activated, y_batch)
        
        # 5. 역전파
        loss.backward()
        
        # 6. 적응형 그래디언트 클리핑 (AGC) - 그래디언트 계산 후, 옵티마이저 스텝 전
        #    이 과정에서 self.avg_gradient_norm이 업데이트됨.
        self._adaptive_gradient_clipping_agc()
        
        # 7. 주기적 모멘텀 업데이트 (SGD 사용 시)
        if self.optimizer_type == 'sgd':
            self._cyclical_momentum_shifting()
        
        # 8. 옵티마이저 스텝
        self.optimizer.step()
        
        self.last_loss = loss.item()
        self.iterations += 1
        
        if self.iterations % 50 == 0: # 로그 빈도 조절
             self._log(f"Iter: {self.iterations}, Loss: {self.last_loss:.4f}, AvgGradNorm (before clip): {self.avg_gradient_norm if self.avg_gradient_norm else 'N/A':.2e}, Current Global Activation: {self.activations[self.global_activation_idx].__class__.__name__}", level=1)

        return self.last_loss

# --- 예시 모델 (사용자님의 V1 코드에는 없었지만, 테스트를 위해 간단히 정의) ---
class ExampleModel(nn.Module):
    def __init__(self, input_dim, output_dim):
        super().__init__()
        # 참고: RecursiveOptimizerV2의 _adaptive_activation_switching은 모델의 *출력*에 적용됩니다.
        # 모델 내부에 특정 활성화 레이어를 두는 방식(Lumina 1차 디벨롭)과는 다릅니다.
        self.fc1 = nn.Linear(input_dim, 128)
        self.intermediate_activation = nn.ReLU() # 모델 내부의 고정된 활성화
        self.fc2 = nn.Linear(128, 64)
        self.fc3 = nn.Linear(64, output_dim) # 이 레이어의 출력이 _adaptive_activation_switching의 입력이 됨

    def forward(self, x):
        x = self.fc1(x)
        x = self.intermediate_activation(x)
        x = self.fc2(x)
        x = self.intermediate_activation(x) # 예시로 중간 활성화 한번 더
        x = self.fc3(x) # 이 출력이 optimizer의 activation switching 대상
        return x

# --- 학습 및 평가 헬퍼 함수 (사용자님 피드백 반영을 위해 포함) ---
def train_model_v2(model, recursive_optimizer, train_loader, epochs=10, initial_input_dim_for_pca=None):
    if recursive_optimizer.use_pca_dim_reduction and initial_input_dim_for_pca:
        # PCA 목표 차원 초기화 (실제 차원 수는 _dimensional_reduction_scheduling_pca 내부에서 비율로 계산됨)
        # 이 부분은 옵티마이저 생성 시 pca_target_dim_ratio로 전달되도록 개선됨.
        # recursive_optimizer._current_pca_target_dim = int(initial_input_dim_for_pca * recursive_optimizer.pca_target_dim_ratio)
        pass


    for epoch in range(epochs):
        recursive_optimizer.epoch_start(epoch) # 에포크 시작 알림
        
        total_loss = 0.0
        for i, (x_batch, y_batch) in enumerate(train_loader):
            # 입력 데이터 차원 확인 (ExampleModel은 2D 입력을 가정)
            if x_batch.ndim > 2 and x_batch.size(0) > 0: # 배치 크기가 0보다 큰 경우에만 reshape
                 # PCA가 마지막 차원에 대해 작동하므로, (batch_size, features) 형태로 유지
                if x_batch.size(1) != initial_input_dim_for_pca and initial_input_dim_for_pca is not None : # Forcing consistent feature dim if needed
                    # This part might need careful handling based on data structure
                    # For now, assume dataloader provides (batch, features) or (batch, other_dims, features)
                    if x_batch.ndim == 3 and x_batch.size(2) == initial_input_dim_for_pca: # (batch, seq, features)
                        x_batch = x_batch.reshape(-1, initial_input_dim_for_pca) # (batch*seq, features)
                        y_batch = y_batch.repeat_interleave(x_batch.size(0) // y_batch.size(0)) if y_batch.size(0) < x_batch.size(0) else y_batch
                    elif x_batch.ndim > 2:
                         x_batch = x_batch.reshape(x_batch.size(0), -1)


            loss = recursive_optimizer.step(x_batch, y_batch)
            total_loss += loss
            # 로그는 optimizer 내부에서 verbose 설정에 따라 출력됨

        avg_loss = total_loss / len(train_loader) if len(train_loader) > 0 else 0
        recursive_optimizer._log(f"Epoch [{epoch + 1}/{epochs}] 완료, Average Loss: {avg_loss:.4f}", level=0) # level 0은 항상 출력 (또는 verbose > -1)


def evaluate_model_v2(model, test_loader, initial_input_dim_for_pca=None): # PCA 사용 시 입력 차원 일관성 유지
    model.eval()
    correct, total = 0, 0
    # PCA 차원 축소는 학습 중에만 적용되도록 설계되었으므로, 평가 시에는 원본 데이터 사용 가정.
    # 만약 평가 시에도 동일한 PCA를 적용해야 한다면, 별도 로직 또는 학습된 PCA 변환기 필요.
    # 여기서는 간단히 모델의 forward만 사용.
    with torch.no_grad():
        for x_batch, y_batch in test_loader:
            if x_batch.ndim > 2 and x_batch.size(0) > 0:
                if initial_input_dim_for_pca and x_batch.size(1) != initial_input_dim_for_pca:
                     if x_batch.ndim == 3 and x_batch.size(2) == initial_input_dim_for_pca:
                        x_batch = x_batch.reshape(-1, initial_input_dim_for_pca)
                        y_batch = y_batch.repeat_interleave(x_batch.size(0) // y_batch.size(0)) if y_batch.size(0) < x_batch.size(0) else y_batch
                     else:
                         x_batch = x_batch.reshape(x_batch.size(0), -1)

            outputs = model(x_batch) # Note: _adaptive_activation_switching is part of optimizer.step, not model.forward directly
                                     # For evaluation, typically the 'final' chosen activation state or a default one is used.
                                     # Here, raw model output is used. If activation switching is critical for eval, it needs careful handling.
                                     # For simplicity, we assume the model has learned to work without the optimizer's output activation switching during eval.
            _, predicted = torch.max(outputs.data, 1)
            total += y_batch.size(0)
            correct += (predicted == y_batch).sum().item()
    
    accuracy = (100 * correct / total) if total > 0 else 0
    print(f"[Lumina Log - OptimizerV2] Test Accuracy: {accuracy:.2f}%")
    return accuracy

# --- 예시 사용법 ---
if __name__ == '__main__':
    INPUT_DIM = 784
    OUTPUT_DIM = 10
    NUM_EPOCHS = 5 # 데모를 위해 짧게
    BATCH_SIZE = 64
    LR_ADAM = 0.001
    LR_SGD = 0.01 # SGD는 일반적으로 Adam보다 큰 LR 사용

    # 가상 데이터셋 (실제 사용 시에는 MNIST 등 사용)
    X_train_dummy = torch.randn(BATCH_SIZE * 10, INPUT_DIM) # 10 배치 분량
    y_train_dummy = torch.randint(0, OUTPUT_DIM, (BATCH_SIZE * 10,))
    train_dataset = torch.utils.data.TensorDataset(X_train_dummy, y_train_dummy)
    train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)

    X_test_dummy = torch.randn(BATCH_SIZE * 2, INPUT_DIM) # 2 배치 분량
    y_test_dummy = torch.randint(0, OUTPUT_DIM, (BATCH_SIZE * 2,))
    test_dataset = torch.utils.data.TensorDataset(X_test_dummy, y_test_dummy)
    test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False)

    # 모델 및 손실 함수
    example_model_adam = ExampleModel(input_dim=INPUT_DIM, output_dim=OUTPUT_DIM)
    example_model_sgd = ExampleModel(input_dim=INPUT_DIM, output_dim=OUTPUT_DIM) # SGD용 별도 모델 인스턴스
    loss_fn = nn.CrossEntropyLoss()

    print("\n--- RecursiveOptimizerV2 with Adam ---")
    optimizer_adam = RecursiveOptimizerV2(
        example_model_adam, loss_fn, optimizer_type='adam', lr=LR_ADAM,
        activation_threshold=0.02, activation_max_depth=2,
        activation_switch_trigger_grad_norm_threshold=1e-3,
        activation_switch_loss_stagnation_patience=5,
        agc_clipping_ratio=0.01,
        pca_target_dim_ratio=0.75, pca_freq=100, use_pca_dim_reduction=True,
        verbose=1 
    )
    train_model_v2(example_model_adam, optimizer_adam, train_loader, epochs=NUM_EPOCHS, initial_input_dim_for_pca=INPUT_DIM)
    evaluate_model_v2(example_model_adam, test_loader, initial_input_dim_for_pca=INPUT_DIM)

    print("\n--- RecursiveOptimizerV2 with SGD ---")
    optimizer_sgd = RecursiveOptimizerV2(
        example_model_sgd, loss_fn, optimizer_type='sgd', lr=LR_SGD,
        momentum_base=0.8, momentum_max=0.99, momentum_cycle_len=100, # SGD 관련 파라미터
        activation_threshold=0.02, activation_max_depth=2,
        activation_switch_trigger_grad_norm_threshold=1e-3,
        activation_switch_loss_stagnation_patience=5,
        agc_clipping_ratio=0.01,
        pca_target_dim_ratio=0.80, pca_freq=150, use_pca_dim_reduction=False, # SGD에서는 PCA 비활성화 테스트
        verbose=1
    )
    train_model_v2(example_model_sgd, optimizer_sgd, train_loader, epochs=NUM_EPOCHS, initial_input_dim_for_pca=INPUT_DIM)
    evaluate_model_v2(example_model_sgd, test_loader, initial_input_dim_for_pca=INPUT_DIM)
