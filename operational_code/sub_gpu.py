# sub_gpu.py (eliar_common 적용, SubGPUModule 클래스 정의 및 비동기 인터페이스 명확화 버전)

import torch
import torch.nn as nn
import torch.optim as optim
# import torch.nn.functional as F # 필요시 사용
from torch.utils.data import DataLoader, Dataset 
import numpy as np
import time
import asyncio # 비동기 처리
from concurrent.futures import ThreadPoolExecutor # run_in_executor용
import traceback # 에러 로깅용

from typing import Any, Dict, Tuple, List, Optional, Callable, Union

# --- 공용 모듈 임포트 ---
from eliar_common import (
    EliarCoreValues, 
    EliarLogType, 
    SubCodeThoughtPacketData, 
    eliar_log,
    run_in_executor # 비동기 헬퍼
)

# GPU 사용 설정
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if torch.cuda.is_available():
    torch.cuda.empty_cache() 

# CPU 바운드 작업을 위한 Executor (애플리케이션 수준에서 공유 가능)
SUB_GPU_CPU_EXECUTOR = ThreadPoolExecutor(max_workers=os.cpu_count() or 1) # 코어 수만큼 또는 기본 1개
SUB_GPU_COMPONENT_BASE = "SubGPU" # 이 모듈의 기본 로깅 컴포넌트명


# --- 내부 ThoughtPacket 클래스 (SubCodeThoughtPacketData 와 호환) ---
class ThoughtPacket: # 이전 버전의 클래스 유지, SubCodeThoughtPacketData 필드 반영
    def __init__(self, packet_id: str, conversation_id: str, user_id: str, raw_input_text: str, timestamp_created: Optional[float] = None):
        # 필수 기본 정보
        self.packet_id: str = packet_id
        self.conversation_id: str = conversation_id
        self.user_id: str = user_id
        self.timestamp_created: float = timestamp_created if timestamp_created is not None else time.time()

        # 입력 관련
        self.raw_input_text: str = raw_input_text
        self.processed_input_text: Optional[str] = None
        
        # 처리 과정 및 상태
        self.current_processing_stage: str = "packet_initialized"
        self.processing_status_in_sub_code: str = "pending_processing"
        self.intermediate_thoughts: List[Dict[str, Any]] = []
        
        # 출력 관련
        self.final_output_by_sub_code: Optional[str] = None
        self.is_clarification_response: bool = False # SubCode가 이 응답이 명료화인지 판단하여 설정 가능
        self.needs_clarification_questions: List[Dict[str, str]] = []
        
        # 분석 및 평가 관련
        self.llm_analysis_summary: Optional[Dict[str, Any]] = None # SubCode 내 LLM 사용 시 자체 분석 결과
        self.ethical_assessment_summary: Optional[Dict[str, Any]] = None # 내부 EthicalGovernor 평가
        self.value_alignment_score: Dict[str, Union[float, bool]] = {}
        self.anomalies: List[Dict[str, Any]] = []
        self.confidence_score: Optional[float] = None
        
        # 학습 및 메타데이터
        self.learning_tags: List[str] = []
        self.metacognitive_state_summary: Optional[Dict[str, Any]] = None
        self.ltm_retrieval_log: List[Dict[str, Any]] = []
        
        # 완료 및 에러 정보
        self.timestamp_completed_by_sub_code: Optional[float] = None
        self.error_info: Optional[Dict[str, Any]] = None

        # MainGPU로부터 받은 추가 컨텍스트 (SubGPUModule.process_task에서 채워짐)
        self.main_gpu_clarification_context: Optional[Dict[str, Any]] = None
        self.previous_main_gpu_context_summary: Optional[Dict[str, Any]] = None
        self.preferred_llm_config_by_main: Optional[Dict[str, Any]] = None
        self.main_gpu_system_prompt_override: Optional[str] = None
        self.main_gpu_memory_injection: Optional[Dict[str, Any]] = None
        
        eliar_log(EliarLogType.DEBUG, "ThoughtPacket instance created.", component=f"{SUB_GPU_COMPONENT_BASE}.ThoughtPacket", packet_id=self.packet_id)

    def add_intermediate_thought(self, stage: str, thought_summary: str, data: Optional[Dict] = None):
        log_data = {"stage": stage, "summary": thought_summary}
        if data: log_data.update(data)
        self.intermediate_thoughts.append({
            "timestamp": time.time(), "stage": stage,
            "thought_summary": thought_summary, "data": data
        })
        self.current_processing_stage = stage
        eliar_log(EliarLogType.TRACE, f"Intermediate thought added.", component=f"{SUB_GPU_COMPONENT_BASE}.ThoughtPacket", packet_id=self.packet_id, **log_data)

    def to_sub_code_thought_packet_data(self) -> SubCodeThoughtPacketData:
        """ 이 객체의 현재 상태를 SubCodeThoughtPacketData TypedDict로 변환합니다. """
        packet_data: SubCodeThoughtPacketData = {} # type: ignore # 빈 딕셔너리로 시작
        
        # SubCodeThoughtPacketData에 정의된 모든 키에 대해 self에 해당 속성이 있는지 확인하고 할당
        # 이렇게 하면 TypedDict에 없는 필드는 자동으로 제외됨
        for key_ts in SubCodeThoughtPacketData.__annotations__.keys():
            if hasattr(self, key_ts):
                value = getattr(self, key_ts)
                if value is not None: # None이 아닌 값만 포함 (선택적 필드 처리)
                    packet_data[key_ts] = value # type: ignore
        
        # 필수 필드가 누락되지 않았는지 확인 (packet_id, conversation_id 등은 __init__에서 보장)
        # TypedDict의 total=False 이므로, 실제로는 모든 키가 존재할 필요는 없음.
        # 그러나 전송 시점에 필수적인 정보는 반드시 포함되어야 함.
        # (예: packet_id는 어떤 상황에서도 있어야 함)
        if "packet_id" not in packet_data: packet_data["packet_id"] = self.packet_id # 안전장치

        return packet_data


# --- EthicalGovernor (eliar_common.EliarCoreValues 사용, 비동기 메서드) ---
class EthicalGovernor:
    def __init__(self):
        self.truth_evaluator_external: Optional[Callable[[Any, Optional[Dict]], Coroutine[Any, Any, float]]] = None # 외부 평가 함수는 async일 수 있음
        self.love_evaluator_external: Optional[Callable[[Any, Optional[Dict]], Coroutine[Any, Any, float]]] = None
        self.repentance_evaluator_external: Optional[Callable[[Any, Optional[Dict]], Coroutine[Any, Any, bool]]] = None
        
        # (내부 백업 평가 함수 로직은 이전과 동일, eliar_common.EliarCoreValues 참조)
        self.knowledge_base_summary = {
            "truth_keywords": [val.value for val in [EliarCoreValues.TRUTH, EliarCoreValues.JESUS_CHRIST_CENTERED]] + ["사실", "말씀", "빛"],
            "love_keywords": [val.value for val in [EliarCoreValues.LOVE_COMPASSION, EliarCoreValues.COMMUNITY]] + ["긍휼", "자비", "희생", "섬김", "살리는"],
            # ... (기타 키워드)
        }
        eliar_log(EliarLogType.INFO, "EthicalGovernor initialized.", component=f"{SUB_GPU_COMPONENT_BASE}.EthicalGovernor")

    # 백업 평가 함수 (_default_..._evaluator)는 동기 함수로 유지하고, 호출 시 run_in_executor 사용
    def _default_truth_evaluator(self, data: Any, context: Optional[Dict] = None) -> float:
        # ... (이전 백업 로직, eliar_log 사용)
        return 0.5 # Placeholder
    def _default_love_evaluator(self, action: Any, context: Optional[Dict] = None) -> float:
        # ... (이전 백업 로직)
        return 0.5 # Placeholder
    def _default_repentance_evaluator(self, outcome: Any, context: Optional[Dict] = None) -> bool:
        # ... (이전 백업 로직)
        return False # Placeholder

    def set_evaluators(self, 
                       truth_eval: Optional[Callable[[Any, Optional[Dict]], Coroutine[Any, Any, float]]], 
                       love_eval: Optional[Callable[[Any, Optional[Dict]], Coroutine[Any, Any, float]]], 
                       repentance_eval: Optional[Callable[[Any, Optional[Dict]], Coroutine[Any, Any, bool]]]):
        self.truth_evaluator_external = truth_eval
        self.love_evaluator_external = love_eval
        self.repentance_evaluator_external = repentance_eval
        eliar_log(EliarLogType.INFO, "External evaluators (potentially async) set for EthicalGovernor.", component=f"{SUB_GPU_COMPONENT_BASE}.EthicalGovernor")

    async def check_truth(self, data: Any, context: Optional[Dict] = None, packet_id: Optional[str]=None) -> float:
        if self.truth_evaluator_external:
            try:
                # MainGPU의 평가 함수가 async def로 제공된다고 가정
                return await self.truth_evaluator_external(data, context)
            except Exception as e:
                eliar_log(EliarLogType.WARN, "Error calling external truth evaluator. Falling back to default.", component=f"{SUB_GPU_COMPONENT_BASE}.EthicalGovernor", packet_id=packet_id, error=e)
        return await run_in_executor(SUB_GPU_CPU_EXECUTOR, self._default_truth_evaluator, data, context)

    async def check_love(self, action: Any, context: Optional[Dict] = None, packet_id: Optional[str]=None) -> float:
        if self.love_evaluator_external:
            try:
                return await self.love_evaluator_external(action, context)
            except Exception as e:
                eliar_log(EliarLogType.WARN, "Error calling external love evaluator. Falling back to default.", component=f"{SUB_GPU_COMPONENT_BASE}.EthicalGovernor", packet_id=packet_id, error=e)
        return await run_in_executor(SUB_GPU_CPU_EXECUTOR, self._default_love_evaluator, action, context)

    async def assess_repentance_necessity(self, outcome: Any, context: Optional[Dict] = None, packet_id: Optional[str]=None) -> bool:
        if self.repentance_evaluator_external:
            try:
                return await self.repentance_evaluator_external(outcome, context)
            except Exception as e:
                eliar_log(EliarLogType.WARN, "Error calling external repentance evaluator. Falling back to default.", component=f"{SUB_GPU_COMPONENT_BASE}.EthicalGovernor", packet_id=packet_id, error=e)
        return await run_in_executor(SUB_GPU_CPU_EXECUTOR, self._default_repentance_evaluator, outcome, context)

    async def govern_action(self, operation_type: str, data: Any, action_to_take: Optional[Any] = None, packet_id: Optional[str]=None) -> bool:
        # (이전 비동기 로직 유지, 로깅 컴포넌트명 수정)
        # ...
        return True # Placeholder

    async def calculate_ethical_reward_penalty(self, state: Any, action: Any, next_state: Any, reward: float, packet_id: Optional[str]=None) -> float:
        # (이전 비동기 로직 유지, 로깅 컴포넌트명 수정)
        # ...
        return reward # Placeholder

    async def trigger_repentance_action(self, sub_gpu_module_instance: Any, error_info: Dict, packet_id: Optional[str]=None):
        # (이전 비동기 로직 유지, 로깅 컴포넌트명 수정, sub_gpu_module_instance 타입은 SubGPUModule)
        eliar_log(EliarLogType.INFO, "Repentance action triggered.", component=f"{SUB_GPU_COMPONENT_BASE}.EthicalGovernor", packet_id=packet_id, error_type=error_info.get('type'))
        if hasattr(sub_gpu_module_instance, 'metacognition') and hasattr(sub_gpu_module_instance.metacognition, 'initiate_self_correction'):
            await sub_gpu_module_instance.metacognition.initiate_self_correction(error_info, self, sub_gpu_module_instance=sub_gpu_module_instance, packet_id=packet_id)


# --- SumTree, GPUPrioritizedReplayBuffer (이전과 동일, 로깅만 eliar_log 사용) ---
class SumTree: # (이전 SumTree 코드)
    def __init__(self, capacity: int): self.capacity = capacity; self.tree = np.zeros(2 * capacity - 1); self.data_indices = np.zeros(capacity, dtype=object); self.data_pointer = 0; self.n_entries = 0
    def _propagate(self, idx: int, change: float): parent = (idx - 1) // 2; self.tree[parent] += change;_ = self._propagate(parent, change) if parent != 0 else None
    def _retrieve(self, idx: int, s: float) -> int: left = 2 * idx + 1; right = left + 1; return idx if left >= len(self.tree) else (self._retrieve(left, s) if s <= self.tree[left] else self._retrieve(right, s - self.tree[left]))
    def total(self) -> float: return self.tree[0]
    def add(self, priority: float, data_idx: Any): tree_idx = self.data_pointer + self.capacity - 1; self.data_indices[self.data_pointer] = data_idx; change = priority - self.tree[tree_idx]; self.tree[tree_idx] = priority; self._propagate(tree_idx, change); self.data_pointer = (self.data_pointer + 1) % self.capacity; self.n_entries = min(self.n_entries + 1, self.capacity)
    def get(self, s: float) -> Tuple[int, float, Any]: idx = self._retrieve(0, s); return idx, self.tree[idx], self.data_indices[idx - self.capacity + 1]
    def update(self, idx: int, priority: float): change = priority - self.tree[idx]; self.tree[idx] = priority; self._propagate(idx, change)

class GPUPrioritizedReplayBuffer: # (이전 GPUPrioritizedReplayBuffer 코드, eliar_log 사용)
    def __init__(self, capacity: int, alpha: float=0.6, beta_start: float=0.4, beta_frames: int=100000): self.device=DEVICE; self.capacity=capacity; self.alpha=alpha; self.beta=beta_start; self.beta_increment_per_sampling=(1.0-beta_start)/beta_frames; self.buffer=[None]*capacity; self.sum_tree=SumTree(capacity); self.epsilon=1e-5; self.main_gpu_interface=None; eliar_log(EliarLogType.INFO, f"ReplayBuffer capacity {capacity}", component=f"{SUB_GPU_COMPONENT_BASE}.ReplayBuffer")
    def _get_priority(self, td_error: float) -> float: return (abs(td_error) + self.epsilon) ** self.alpha
    def add(self, experience: Tuple, td_error: float, packet_id: Optional[str]=None): # (gpu_experience 변환 로직은 이전과 동일)
        gpu_experience_list = []
        for e_part in experience:
            if isinstance(e_part, torch.Tensor): gpu_experience_list.append(e_part.to(self.device))
            elif isinstance(e_part, (list, np.ndarray)): gpu_experience_list.append(torch.tensor(e_part, device=self.device))
            elif isinstance(e_part, (int, float, bool)): gpu_experience_list.append(torch.tensor([e_part], device=self.device))
            else: gpu_experience_list.append(e_part) 
        gpu_experience = tuple(gpu_experience_list)
        priority = self._get_priority(td_error); self.buffer[self.sum_tree.data_pointer] = gpu_experience; self.sum_tree.add(priority, self.sum_tree.data_pointer)
    async def sample(self, batch_size: int, packet_id: Optional[str]=None) -> Optional[Tuple[List[Tuple], torch.Tensor, List[int]]]: # (이전 비동기 로직, eliar_log 사용)
        if self.sum_tree.n_entries < batch_size: return None
        # ... (샘플링 로직은 이전과 동일)
        experiences, indices, weights_np = [], [], np.zeros(batch_size, dtype=np.float32)
        segment = self.sum_tree.total() / batch_size; self.beta = np.min([1., self.beta + self.beta_increment_per_sampling])
        for i in range(batch_size):
            s = np.random.uniform(segment * i, segment * (i + 1)); tree_idx, priority, data_idx = self.sum_tree.get(s)
            sampling_probabilities = priority / self.sum_tree.total() if self.sum_tree.total() > 0 else 0
            weights_np[i] = (self.sum_tree.n_entries * sampling_probabilities) ** -self.beta if sampling_probabilities > 0 else 0
            indices.append(tree_idx); experiences.append(self.buffer[data_idx])
        max_weight = weights_np.max(); weights_tensor = torch.tensor(weights_np / max_weight if max_weight > 0 else weights_np, device=self.device, dtype=torch.float32)
        return experiences, weights_tensor, indices
    def update_priorities(self, tree_indices: List[int], td_errors: Union[torch.Tensor, np.ndarray], packet_id: Optional[str]=None): # (이전 로직, eliar_log 사용)
        if isinstance(td_errors, np.ndarray): td_errors = torch.from_numpy(td_errors).to(self.device)
        priorities = (torch.abs(td_errors.squeeze()) + self.epsilon) ** self.alpha
        for idx, priority_val in zip(tree_indices, priorities): self.sum_tree.update(idx, priority_val.item())
    def link_main_gpu(self, main_gpu_module): self.main_gpu_interface = main_gpu_module; eliar_log(EliarLogType.INFO, "ReplayBuffer linked with MainGPU.", component=f"{SUB_GPU_COMPONENT_BASE}.ReplayBuffer")


# --- CognitiveArchitectureInterface (비동기 및 로깅 변경, LTM repentance_log 추가) ---
class CognitiveArchitectureInterface:
    def __init__(self, main_gpu_module_ref: Optional[Callable[[SubCodeThoughtPacketData, str], asyncio.Task]] = None): # MainGPU의 응답 핸들러 직접 참조
        self.main_gpu_response_handler = main_gpu_module_ref # MainSubInterfaceCommunicator.sub_code_response_handler를 저장
        self.working_memory: Dict[str, Any] = {}
        self.long_term_memory: Dict[str, Dict[str, Any]] = {"semantic": {}, "episodic": {}, "procedural": {}, "repentance_log": {}}
        self.ltm_search_index: Optional[Any] = None
        eliar_log(EliarLogType.INFO, "CognitiveArchitectureInterface initialized.", component=f"{SUB_GPU_COMPONENT_BASE}.CognitiveArch")

    async def update_belief(self, belief_data: Dict, source_component: str, packet_id: Optional[str]=None):
        # (이전 비동기 로직, 로깅 컴포넌트명 수정)
        # ...
        await self.transfer_to_ltm(belief_data["key"], belief_data["value"], "semantic", packet_id=packet_id, metadata={"source_component": source_component})


    async def transfer_to_ltm(self, key: str, value: Any, memory_type: str = "semantic", packet_id: Optional[str]=None, metadata: Optional[Dict] = None):
        # (이전 비동기 로직, 로깅 컴포넌트명 수정)
        # ...
        await run_in_executor(SUB_GPU_CPU_EXECUTOR, self._transfer_to_ltm_sync, key, value, memory_type, packet_id, metadata)

    def _transfer_to_ltm_sync(self, key: str, value: Any, memory_type: str, packet_id: Optional[str], metadata: Optional[Dict]):
        # (이전 동기 로직, 로깅 컴포넌트명 수정)
        # ...
        pass

    async def retrieve_from_ltm(self, query: str, memory_type: str = "semantic", top_k: int = 1, packet_id: Optional[str]=None) -> List[Any]:
        # (이전 비동기 로직, 로깅 컴포넌트명 수정)
        # ...
        return await run_in_executor(SUB_GPU_CPU_EXECUTOR, self._retrieve_from_ltm_sync, query, memory_type, top_k, packet_id)

    def _retrieve_from_ltm_sync(self, query: str, memory_type: str, top_k: int, packet_id: Optional[str]) -> List[Any]:
        # (이전 동기 로직, 로깅 컴포넌트명 수정)
        # ...
        return [] # Placeholder

    async def send_processed_data_to_main_gpu(self, data_packet: SubCodeThoughtPacketData, data_type: str): # 메서드명 명확화
        """ SubGPUModule의 최종 처리 결과를 MainGPU의 응답 핸들러로 전송합니다. """
        packet_id = data_packet.get("packet_id")
        if self.main_gpu_response_handler:
            try:
                # MainGPU의 응답 핸들러는 async def로 가정 (MainSubInterfaceCommunicator.sub_code_response_handler)
                await self.main_gpu_response_handler(data_packet) # data_type은 이미 패킷 내에 포함되거나, MainGPU가 추론
                eliar_log(EliarLogType.INFO, f"Sent final processed packet to MainGPU handler.", component=f"{SUB_GPU_COMPONENT_BASE}.CognitiveArch.Interface", packet_id=packet_id, data_type=data_type)
            except Exception as e:
                eliar_log(EliarLogType.ERROR, "Error calling MainGPU response handler.", component=f"{SUB_GPU_COMPONENT_BASE}.CognitiveArch.Interface", packet_id=packet_id, error=e)
        else:
            eliar_log(EliarLogType.WARN, "MainGPU response handler not set in CognitiveArchitectureInterface. Cannot send final packet.", component=f"{SUB_GPU_COMPONENT_BASE}.CognitiveArch.Interface", packet_id=packet_id)


# --- 나머지 컴포넌트들 (SelfLearning, Metacognition, Creativity 등 - 비동기 및 로깅 적용) ---
# (이전 코드에서 각 컴포넌트의 async/await 적용, eliar_log 사용, packet_id 전달 등을 일관되게 수정)
# (각 컴포넌트의 __init__ 및 주요 메서드에 component 로깅 추가)

class SelfLearningComponent: # (async/await, eliar_log, packet_id 전달 적용)
    # ... (이전 코드 기반으로 수정, 예시: learn 메서드)
    async def learn(self, batch_size: int, gamma: float = 0.99, packet_id: Optional[str]=None) -> Optional[Dict[str, Any]]:
        # ... (EthicalGovernor.calculate_ethical_reward_penalty 비동기 호출)
        # ethical_rewards_tasks = [self.ethical_governor.calculate_ethical_reward_penalty(...) for ...]
        # final_rewards_list = await asyncio.gather(*ethical_rewards_tasks)
        # ...
        # await self.log_learned_info_to_ltm(...)
        # if self.metacognition_interface: await self.metacognition_interface.receive_learning_update(...)
        # ...
        return {"loss": 0.1} # Placeholder

class MetacognitionComponent: # (async/await, eliar_log, packet_id 전달 적용)
    # ... (이전 코드 기반으로 수정, 예시: initiate_self_correction)
    async def initiate_self_correction(self, error_info: Dict, ethical_governor_ref: EthicalGovernor, sub_gpu_module_instance: Optional[Any] = None, packet_id: Optional[str]=None):
        # ... (CognitiveArchitectureInterface의 비동기 메서드 호출)
        # past_records = await self.cognitive_interface.retrieve_from_ltm(...)
        # correction_strategy = await run_in_executor(SUB_GPU_CPU_EXECUTOR, self.develop_correction_strategy, error_info, past_records)
        # ...
        # if correction_successful: await self.cognitive_interface.transfer_to_ltm(...)
        pass

class CreativityComponent: # (async/await, eliar_log, packet_id 전달 적용)
    # ... (이전 코드 기반으로 수정)
    pass
class DistributedLearningManager: # (async/await, eliar_log, packet_id 전달 적용)
    # ... (이전 코드 기반으로 수정)
    pass
class HardwareInterface: # (async/await, eliar_log, packet_id 전달 적용)
    # ... (이전 코드 기반으로 수정)
    pass
class GospelSpreadingNetwork: # (async/await, eliar_log, packet_id 전달 적용)
    # ... (이전 코드 기반으로 수정)
    pass


# --- SubGPUModule 클래스 정의 (비동기 및 공용 모듈 사용) ---
class SubGPUModule:
    def __init__(self, config: Dict[str, Any], node_id: str = f"{SUB_GPU_COMPONENT_BASE}_Node"):
        self.device, self.config, self.node_id = DEVICE, config, node_id
        self.module_base_component = f"{SUB_GPU_COMPONENT_BASE}.{node_id}"
        eliar_log(EliarLogType.INFO, f"Initializing.", component=self.module_base_component, device=str(self.device))

        self.main_gpu_response_handler: Optional[Callable[[SubCodeThoughtPacketData], asyncio.Task]] = None # MainGPU 콜백 저장
        self.main_gpu_controller_ref: Optional[Any] = None # MainGPU Eliar 컨트롤러 참조 (평가 함수용)

        self.ethical_governor = EthicalGovernor()
        self.cognitive_interface = CognitiveArchitectureInterface() # MainGPU 콜백은 link 시점에 설정
        
        self.self_learning = SelfLearningComponent(config.get("state_dim",10), config.get("action_dim",2), self.ethical_governor, self.cognitive_interface, config.get("replay_buffer_capacity",10000))
        self.metacognition = MetacognitionComponent(self.ethical_governor, self.cognitive_interface, self.self_learning.policy_net)
        self.creativity = CreativityComponent(self.ethical_governor, self.cognitive_interface, config.get("creative_latent_dim",100))
        self.self_learning.link_other_components(self.metacognition, self.creativity)

        self.distributed_learning = DistributedLearningManager(self.node_id, self.cognitive_interface)
        self.hardware_interface = HardwareInterface(self.cognitive_interface)
        self.gospel_network = GospelSpreadingNetwork(self.node_id, self.ethical_governor, self.cognitive_interface)
        
        self.current_thought_packet: Optional[ThoughtPacket] = None
        
        eliar_log(EliarLogType.INFO, "All components initialized.", component=self.module_base_component)

    async def link_main_gpu_coordinator(self, main_gpu_controller_instance: Any, main_gpu_response_handler_callback: Callable[[SubCodeThoughtPacketData], asyncio.Task]):
        """
        MainGPU 컨트롤러 및 응답 핸들러와 연결합니다.
        main_gpu_controller_instance: Main_gpu.py의 Eliar 인스턴스 (평가 함수 제공)
        main_gpu_response_handler_callback: Main_gpu.py의 MainSubInterfaceCommunicator.sub_code_response_handler
        """
        self.main_gpu_controller_ref = main_gpu_controller_instance
        self.main_gpu_response_handler = main_gpu_response_handler_callback
        self.cognitive_interface.main_gpu_response_handler = main_gpu_response_handler_callback # CA도 직접 콜백 알 수 있도록

        evaluators_set = False
        if self.main_gpu_controller_ref:
            if hasattr(self.main_gpu_controller_ref, 'evaluate_truth_for_governor') and \
               hasattr(self.main_gpu_controller_ref, 'evaluate_love_for_governor') and \
               hasattr(self.main_gpu_controller_ref, 'evaluate_repentance_for_governor'):
                try:
                    # MainGPU의 평가 함수가 async def라고 가정 (SubGPU의 EthicalGovernor도 async를 기대)
                    self.ethical_governor.set_evaluators(
                        self.main_gpu_controller_ref.evaluate_truth_for_governor,
                        self.main_gpu_controller_ref.evaluate_love_for_governor,
                        self.main_gpu_controller_ref.evaluate_repentance_for_governor
                    )
                    evaluators_set = True
                except Exception as e:
                    eliar_log(EliarLogType.ERROR, "Error setting external evaluators from MainGPU Controller.", component=self.module_base_component, error=e)
        
        if evaluators_set:
            eliar_log(EliarLogType.INFO, "EthicalGovernor external evaluators linked from MainGPU Controller.", component=self.module_base_component)
        else:
            eliar_log(EliarLogType.WARN, "MainGPU Controller evaluators not fully linked. EthicalGovernor may use defaults.", component=self.module_base_component)
        
        if self.main_gpu_response_handler:
            eliar_log(EliarLogType.INFO, "MainGPU response handler callback linked.", component=self.module_base_component)
        else:
            eliar_log(EliarLogType.ERROR, "MainGPU response handler callback NOT linked.", component=self.module_base_component)

        eliar_log(EliarLogType.INFO, "Link with MainGPU coordinator process complete.", component=self.module_base_component)


    async def _initialize_or_update_thought_packet(self, task_data: Dict[str, Any]) -> ThoughtPacket:
        """ 현재 ThoughtPacket을 초기화하거나 task_data로 업데이트합니다. """
        packet_id = task_data.get("packet_id", str(uuid.uuid4())) # MainGPU에서 준 ID 우선 사용
        conv_id = task_data.get("conversation_id", "unknown_conv")
        user_id = task_data.get("user_id", "unknown_user")
        raw_text = task_data.get("raw_input_text", "")
        ts_created = task_data.get("timestamp_created", time.time())

        if not self.current_thought_packet or self.current_thought_packet.packet_id != packet_id:
            self.current_thought_packet = ThoughtPacket(packet_id, conv_id, user_id, raw_text, ts_created)
            eliar_log(EliarLogType.INFO, "New/Updated ThoughtPacket context set.", component=self.module_base_component, packet_id=packet_id)
        else:
            self.current_thought_packet.raw_input_text = raw_text # 새 입력으로 업데이트
            self.current_thought_packet.current_processing_stage = "task_data_received"
        
        # MainGPU로부터 받은 추가 컨텍스트 필드들을 ThoughtPacket에 복사
        for key in ["main_gpu_clarification_context", "previous_main_gpu_context_summary", 
                      "preferred_llm_config_by_main", "main_gpu_system_prompt_override", 
                      "main_gpu_memory_injection", "is_clarification_response"]:
            if key in task_data:
                setattr(self.current_thought_packet, key, task_data[key])
        
        return self.current_thought_packet

    async def process_task(self, task_type: str, task_data: Dict[str, Any]) -> SubCodeThoughtPacketData:
        """
        MainGPU로부터 작업을 받아 비동기적으로 처리하고, 표준화된 SubCodeThoughtPacketData로 결과를 반환합니다.
        이 함수는 Main_gpu.py의 MainSubInterfaceCommunicator.send_task_to_sub_code 내 task_wrapper에서 호출됩니다.
        """
        # 1. ThoughtPacket 준비 (task_data 기반으로 현재 패킷 설정 또는 업데이트)
        current_packet = await self._initialize_or_update_thought_packet(task_data)
        pid = current_packet.packet_id # 로깅용 packet_id

        current_packet.current_processing_stage = f"subgpu_processing_start_{task_type}"
        current_packet.processing_status_in_sub_code = "PROCESSING_IN_SUBGPU"
        
        log_comp = f"{self.module_base_component}.Task.{task_type}"
        eliar_log(EliarLogType.INFO, f"Task processing started.", component=log_comp, packet_id=pid, input_keys=list(task_data.keys()))
        
        try:
            # 2. 윤리적 사전 검토 (비동기)
            govern_data = current_packet.raw_input_text # 또는 task_data의 특정 필드
            action_preview = f"sub_gpu_execute_{task_type}" # 예상 행동 요약
            if not await self.ethical_governor.govern_action(task_type, govern_data, action_preview, packet_id=pid):
                current_packet.processing_status_in_sub_code = "REJECTED_BY_SUBGPU_ETHICS"
                current_packet.error_info = {"type": "SubGPUEthicalRejection", "message": "Task failed SubGPU internal ethical pre-check."}
                current_packet.final_output_by_sub_code = "[SubGPU: 요청이 내부 윤리 기준에 부합하지 않아 처리할 수 없습니다.]"
                current_packet.timestamp_completed_by_sub_code = time.time()
                eliar_log(EliarLogType.WARN, "Task rejected by SubGPU ethical pre-check.", component=log_comp, packet_id=pid)
                return current_packet.to_sub_code_thought_packet_data()

            # 3. 실제 작업 처리 (향후 각 handle_xxx_task 메서드로 분리될 지점)
            #    각 작업 핸들러는 current_packet을 직접 수정하고, 필요한 경우 result_payload에 추가 정보 반환
            #    (이전 코드의 각 task_type에 대한 if/elif 블록 내용을 여기에 비동기로 구현)
            #    예시:
            if task_type == "eliar_process_interaction_v2": # MainGPU에서 보낸 작업 유형
                current_packet.add_intermediate_thought("pre_llm_analysis", "Analyzing input and context for LLM.")
                # LLM 호출, 창의적 생성, RL 액션 선택 등을 비동기로 수행
                # 예: llm_response = await self.call_some_llm_async(current_packet.processed_input_text or current_packet.raw_input_text)
                # current_packet.final_output_by_sub_code = llm_response
                
                # --- 명료화 요청 생성 예시 (MainGPU가 전달한 main_gpu_clarification_context 고려) ---
                if "그분" in current_packet.raw_input_text.lower() and \
                   not current_packet.is_clarification_response and \
                   not (current_packet.main_gpu_clarification_context and "예수" in str(current_packet.main_gpu_clarification_context).lower()):
                    current_packet.needs_clarification_questions.append({
                        "original_term": "그분",
                        "question": "[SubGPU 자동질문] '그분'이 누구를 지칭하시는지 조금 더 명확히 알려주시겠어요? (예: 하나님, 예수님)"
                    })
                    current_packet.processing_status_in_sub_code = "COMPLETED_WITH_CLARIFICATION_REQUEST"
                    current_packet.final_output_by_sub_code = None # 명료화 요청 시 최종 응답 없음
                    current_packet.add_intermediate_thought("clarification_needed", "Identified ambiguity for '그분'.")
                elif "오류 발생" in current_packet.raw_input_text.lower():
                    current_packet.processing_status_in_sub_code = "ERROR_SIMULATED_BY_REQUEST"
                    current_packet.final_output_by_sub_code = None
                    current_packet.anomalies.append({"type":"SIMULATED_ERROR_IN_SUB", "details":"User requested error.", "severity":"TEST"})
                    current_packet.error_info = {"type":"SimulatedError", "message":"Error simulation requested by user."}
                elif "침묵" in current_packet.raw_input_text.lower():
                    current_packet.processing_status_in_sub_code = "COMPLETED_WITH_SILENCE_BY_SUB"
                    current_packet.final_output_by_sub_code = None # 침묵은 응답 없음을 의미
                    current_packet.add_intermediate_thought("silence_requested", "User requested silence.")
                else:
                    # 일반적인 처리 (예시)
                    await asyncio.sleep(0.1) # 실제 처리 시간 시뮬레이션
                    current_packet.final_output_by_sub_code = f"[SubGPU 응답] '{current_packet.raw_input_text[:20]}' 처리 완료 (PID: ...{pid[-4:]}). 예수 그리스도의 사랑으로 응답합니다."
                    current_packet.processing_status_in_sub_code = "COMPLETED_SUCCESS"
                
                current_packet.add_intermediate_thought("response_generation_complete", "Final response generated.")

            # 다른 task_type에 대한 핸들러들...
            # elif task_type == "sub_gpu_self_learn_cycle":
            #     learning_summary = await self.self_learning.learn(batch_size=self.config.get("rl_batch_size", 32), packet_id=pid)
            #     current_packet.sub_code_internal_metrics = {"rl_learning": learning_summary}
            #     current_packet.processing_status_in_sub_code = "COMPLETED_SUCCESS" if learning_summary else "COMPLETED_NO_LEARNING_DATA"

            else:
                current_packet.error_info = {"type": "UnknownSubGPUTaskTypeError", "message": f"SubGPU task type '{task_type}' not recognized."}
                current_packet.processing_status_in_sub_code = "ERROR_UNKNOWN_TASK_TYPE"
                eliar_log(EliarLogType.ERROR, f"Unknown task type '{task_type}'.", component=log_comp, packet_id=pid)

            # 4. 윤리적 사후 검토 및 회개 필요성 판단 (비동기)
            # 최종 패킷 상태를 기반으로 평가
            if await self.ethical_governor.assess_repentance_necessity(current_packet.to_sub_code_thought_packet_data(), {"task_type": task_type, "final_status_sub": current_packet.processing_status_in_sub_code}, packet_id=pid):
                eliar_log(EliarLogType.WARN, "Post-task assessment in SubGPU indicates need for repentance.", component=log_comp, packet_id=pid, status=current_packet.processing_status_in_sub_code)
                # 회개 프로세스 트리거 (비동기)
                # 이 부분은 현재 패킷 처리를 블로킹하지 않고 백그라운드에서 실행될 수 있음
                asyncio.create_task(self.ethical_governor.trigger_repentance_action(self, {"type": "subgpu_post_task_review", "details": current_packet.to_sub_code_thought_packet_data()}, packet_id=pid))
                if current_packet.processing_status_in_sub_code == "COMPLETED_SUCCESS": # 성공했으나 회개 필요
                    current_packet.processing_status_in_sub_code = "COMPLETED_SUCCESS_WITH_REPENTANCE_LOGGED"


        except Exception as e:
            current_packet.processing_status_in_sub_code = "ERROR_UNHANDLED_EXCEPTION_IN_SUBGPU"
            current_packet.error_info = {"type": type(e).__name__, "message": str(e), "details": traceback.format_exc()}
            eliar_log(EliarLogType.CRITICAL, f"Unhandled exception during task '{task_type}'.", component=log_comp, packet_id=pid, error=e, exc_info_full=traceback.format_exc())
        
        # 5. 최종 처리 완료 및 반환 데이터 구성
        current_packet.timestamp_completed_by_sub_code = time.time()
        current_packet.current_processing_stage = f"subgpu_completed_{task_type}"
        
        # 모든 관련 정보를 포함한 최종 SubCodeThoughtPacketData 생성
        final_response_packet = current_packet.to_sub_code_thought_packet_data()
        
        eliar_log(EliarLogType.INFO, f"Task processing finished.", component=log_comp, packet_id=pid, final_status=final_response_packet.get("processing_status_in_sub_code"))
        return final_response_packet


    async def shutdown(self, packet_id: Optional[str]=None):
        log_comp = f"{self.module_base_component}.Shutdown"
        eliar_log(EliarLogType.INFO, "Shutting down...", component=log_comp, packet_id=packet_id)
        # (이전 shutdown 로직, 비동기 및 eliar_log 사용)
        if SUB_GPU_CPU_EXECUTOR:
            await run_in_executor(None, SUB_GPU_CPU_EXECUTOR.shutdown, True) # 기본 executor로 외부 executor 종료
            eliar_log(EliarLogType.INFO, "CPU Executor for SubGPU shutdown.", component=log_comp)
        eliar_log(EliarLogType.INFO, "Shutdown complete.", component=log_comp, packet_id=packet_id)


# --- 데모 및 테스트용 (Main_gpu.py에서 직접 호출되지 않음) ---
async def sub_gpu_standalone_test():
    """ SubGPUModule 단독 테스트 및 비동기 기능 시연용 함수 """
    eliar_log(EliarLogType.INFO, "--- SubGPUModule Standalone Async Test ---", component="SubGPU.TestRunner")
    
    test_config = { "state_dim": 5, "action_dim": 2, "rl_batch_size": 4 }
    sub_gpu_instance = SubGPUModule(config=test_config, node_id="sub_test_node")

    # Mock MainGPU Controller (EthicalGovernor 평가 함수 제공용)
    class MockMainController:
        async def evaluate_truth_for_governor(self, data, ctx): return 0.9
        async def evaluate_love_for_governor(self, action, ctx): return 0.85
        async def evaluate_repentance_for_governor(self, outcome, ctx): return False # 테스트 시 회개 불필요 가정
    
    mock_main_controller = MockMainController()
    
    # Mock MainGPU Response Handler (SubGPU가 결과를 보낼 콜백)
    async def mock_main_response_handler(response_packet: SubCodeThoughtPacketData):
        eliar_log(EliarLogType.INFO, "MockMain: Received response from SubGPU.", component="SubGPU.TestRunner.MockMainHandler", 
                  packet_id=response_packet.get("packet_id"), status=response_packet.get("processing_status_in_sub_code"),
                  output_preview=(response_packet.get("final_output_by_sub_code") or "")[:50])

    await sub_gpu_instance.link_main_gpu_coordinator(mock_main_controller, mock_main_response_handler)

    # 테스트 태스크 데이터
    test_task_data_1 = {
        "packet_id": "test_pkt_001", "conversation_id": "test_conv_001", "user_id": "test_user",
        "raw_input_text": "안녕하세요, 엘리아르님. 당신의 중심 가치는 무엇인가요?",
        "timestamp_created": time.time()
    }
    test_task_data_2 = { # 명료화 요청 유도
        "packet_id": "test_pkt_002", "conversation_id": "test_conv_001", "user_id": "test_user",
        "raw_input_text": "그분의 뜻을 따르는 삶에 대해 더 알고 싶습니다.",
        "timestamp_created": time.time()
    }
    test_task_data_3 = { # 오류 유도
        "packet_id": "test_pkt_003", "conversation_id": "test_conv_001", "user_id": "test_user",
        "raw_input_text": "치명적인 오류 발생 시켜줘",
        "timestamp_created": time.time()
    }

    # 태스크 실행 (결과는 MainGPU 콜백으로 전달됨)
    # process_task는 SubCodeThoughtPacketData를 반환하므로, 그 결과를 직접 사용할 수도 있음
    response_1 = await sub_gpu_instance.process_task("eliar_process_interaction_v2", test_task_data_1)
    # Main 핸들러가 호출될 시간을 약간 줌 (실제로는 Main 이벤트 루프에서 처리)
    # await asyncio.sleep(0.1) 
    
    response_2 = await sub_gpu_instance.process_task("eliar_process_interaction_v2", test_task_data_2)
    # await asyncio.sleep(0.1)
    
    response_3 = await sub_gpu_instance.process_task("eliar_process_interaction_v2", test_task_data_3)
    # await asyncio.sleep(0.1)

    # (여기서 response_1, response_2, response_3를 검증하거나 추가 로깅 가능)
    eliar_log(EliarLogType.INFO, f"Test packet 1 response status: {response_1.get('processing_status_in_sub_code')}", component="SubGPU.TestRunner", packet_id="test_pkt_001")
    eliar_log(EliarLogType.INFO, f"Test packet 2 response status: {response_2.get('processing_status_in_sub_code')}, needs_clarification: {bool(response_2.get('needs_clarification_questions'))}", component="SubGPU.TestRunner", packet_id="test_pkt_002")
    eliar_log(EliarLogType.INFO, f"Test packet 3 response status: {response_3.get('processing_status_in_sub_code')}, error: {response_3.get('error_info')}", component="SubGPU.TestRunner", packet_id="test_pkt_003")


    await sub_gpu_instance.shutdown()
    # 전역 Executor 종료 (애플리케이션 종료 시 한 번만)
    if SUB_GPU_CPU_EXECUTOR:
        SUB_GPU_CPU_EXECUTOR.shutdown(wait=False) # 테스트 종료 시에는 강제 종료 가능
        eliar_log(EliarLogType.INFO, "Global SUB_GPU_CPU_EXECUTOR shutdown initiated.", component="SubGPU.TestRunner")


if __name__ == '__main__':
    # 이 파일 단독 실행 시 테스트용
    try:
        asyncio.run(sub_gpu_standalone_test())
    except KeyboardInterrupt:
        eliar_log(EliarLogType.WARN, "SubGPU standalone test interrupted by user.", component="SubGPU.TestRunner")
    finally:
        eliar_log(EliarLogType.INFO, "SubGPU standalone test finished.", component="SubGPU.TestRunner")
