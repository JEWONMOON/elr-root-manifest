import torch
import torch.nn as nn
import torch.nn.functional as F
import random
import numpy as np
from typing import Dict, List, Set, Tuple, Optional, Union

class AttentionModule(nn.Module):
    """
    고급 주의 집중 메커니즘 모듈
    -   입력 시퀀스 내의 다양한 위치에 가중치를 할당하여 관련성이 높은 정보에 집중.
    -   멀티 헤드 어텐션과 스케일링된 닷 프로덕트 어텐션을 사용하여 다양한 표현 캡처.
    """
    def __init__(self, feature_size: int, attention_heads: int = 8, dropout_prob: float = 0.1): # attention_heads를 8로 늘림
        super().__init__()
        self.feature_size = feature_size
        self.attention_heads = attention_heads
        self.head_dim = feature_size // attention_heads
        
        # 멀티헤드 어텐션을 위한 가중치 행렬
        self.query = nn.Linear(feature_size, feature_size)
        self.key = nn.Linear(feature_size, feature_size)
        self.value = nn.Linear(feature_size, feature_size)
        self.out_proj = nn.Linear(feature_size, feature_size)
        
        self.dropout = nn.Dropout(dropout_prob) # Dropout 추가
        
        assert feature_size % attention_heads == 0, "feature_size must be divisible by attention_heads"
        
    def forward(self, node_features: torch.Tensor, edge_index: torch.Tensor, attention_mask: Optional[torch.Tensor] = None) -> torch.Tensor: # attention_mask 추가
        """
        확장된 주의 집중 메커니즘을 사용하여 노드 특성을 업데이트합니다.
        
        Args:
            node_features: 모든 노드의 특성 (N, feature_size)
            edge_index: 엣지 인덱스 텐서 (2, E)
            attention_mask: (Optional) 어텐션 스코어에 적용할 마스크 (E, attention_heads)
            
        Returns:
            torch.Tensor: 업데이트된 노드 특성
        """
        if edge_index.size(1) == 0:  # 엣지가 없는 경우
            return node_features
            
        # 소스 노드와 타겟 노드
        src_nodes, dest_nodes = edge_index
        
        # 쿼리, 키, 밸류 계산
        q = self.query(node_features).view(-1, self.attention_heads, self.head_dim)
        k = self.key(node_features).view(-1, self.attention_heads, self.head_dim)
        v = self.value(node_features).view(-1, self.attention_heads, self.head_dim)
        
        # 소스 노드의 쿼리와 목적지 노드의 키 사이의 어텐션 점수 계산
        src_q = q[src_nodes]  # (E, heads, head_dim)
        dest_k = k[dest_nodes]  # (E, heads, head_dim)
        
        # 어텐션 점수 계산 (스케일링 포함)
        attention_scores = torch.sum(src_q * dest_k, dim=-1) / np.sqrt(self.head_dim)  # (E, heads)
        
        if attention_mask is not None:
            attention_scores = attention_scores + attention_mask # 마스크 적용
        
        # 소스 노드별로 어텐션 가중치 정규화
        unique_src, counts = torch.unique(src_nodes, return_counts=True)
        attention_weights = torch.zeros_like(attention_scores)
        
        for i, node in enumerate(unique_src):
            mask = (src_nodes == node)
            node_scores = attention_scores[mask]
            attention_weights[mask] = F.softmax(node_scores, dim=0)
            
        attention_weights = self.dropout(attention_weights) # Dropout 적용
        
        # 가중치를 적용하여 메시지 집계
        src_v = v[src_nodes]  # (E, heads, head_dim)
        weighted_values = src_v * attention_weights.unsqueeze(-1)  # (E, heads, head_dim)
        
        # 노드별 집계
        output = torch.zeros_like(node_features).view(-1, self.attention_heads, self.head_dim)
        for i in range(edge_index.size(1)):
            output[dest_nodes[i]] += weighted_values[i]
        
        # 차원 재구성 및 선형 투영
        output = output.reshape(-1, self.feature_size)
        return self.out_proj(output)

class TemporalMemoryModule(nn.Module):
    """
    향상된 시간적 메모리 모듈
    -   LSTM 셀 외에 GRU 셀도 지원.
    -   어텐션을 사용하여 메모리 읽기 작업을 개선.
    -   메모리 업데이트 시 decay 메커니즘 추가.
    """
    def __init__(self, node_count: int, feature_size: int, memory_size: int = 10, use_gru: bool = False, memory_decay: float = 0.9): # memory_size 늘림, GRU 지원, memory_decay 추가
        super().__init__()
        self.node_count = node_count
        self.feature_size = feature_size
        self.memory_size = memory_size
        self.use_gru = use_gru
        self.memory_decay = memory_decay
        
        # LSTM 또는 GRU 셀을 사용한 시간적 메모리
        self.rnn_cell = nn.LSTMCell(feature_size, feature_size) if not use_gru else nn.GRUCell(feature_size, feature_size)
        
        # 각 노드의 히든 상태와 셀 상태 초기화
        self.hidden_states = nn.Parameter(torch.zeros(node_count, feature_size))
        self.cell_states = nn.Parameter(torch.zeros(node_count, feature_size)) if not use_gru else None
        
        # 각 노드별 이전 상태를 저장하는 메모리 버퍼
        self.register_buffer('temporal_memory', torch.zeros(node_count, memory_size, feature_size))
        self.register_buffer('memory_ptr', torch.zeros(node_count, dtype=torch.long))
        
        # 메모리 어텐션을 위한 추가 레이어
        self.memory_query = nn.Linear(feature_size, feature_size)
        self.memory_key = nn.Linear(feature_size, feature_size)
        self.memory_value = nn.Linear(feature_size, feature_size)
        
    def update_memory(self, node_indices: torch.Tensor, node_features: torch.Tensor):
        """
        특정 노드들의 메모리를 업데이트합니다.
        
        Args:
            node_indices: 업데이트할 노드 인덱스 (B,)
            node_features: 해당 노드의 새 특성 (B, feature_size)
        """
        # RNN 셀을 통해 상태 업데이트
        if not self.use_gru:
            h_new, c_new = self.rnn_cell(
                node_features, 
                (self.hidden_states[node_indices], self.cell_states[node_indices])
            )
        else:
            h_new = self.rnn_cell(
                node_features,
                self.hidden_states[node_indices]
            )
            c_new = None
        
        with torch.no_grad():
            # 히든 상태와 셀 상태 업데이트
            self.hidden_states[node_indices] = h_new
            if not self.use_gru:
                self.cell_states[node_indices] = c_new
            
            # 시간적 메모리 버퍼에 현재 상태 저장 (decay 적용)
            for i, idx in enumerate(node_indices):
                ptr = self.memory_ptr[idx].item()
                self.temporal_memory[idx, ptr] = node_features[i]
                if ptr > 0:
                    self.temporal_memory[idx, ptr-1] = self.temporal_memory[idx, ptr-1] * self.memory_decay # 이전 메모리 상태 decay
                self.memory_ptr[idx] = (ptr + 1) % self.memory_size
        
    def get_temporal_context(self, node_indices: torch.Tensor) -> torch.Tensor:
        """
        어텐션을 사용하여 특정 노드들의 시간적 컨텍스트를 가져옵니다.
        
        Args:
            node_indices: 컨텍스트를 가져올 노드 인덱스 (B,)
            
        Returns:
            torch.Tensor: 시간적 컨텍스트 벡터 (B, feature_size)
        """
        # 각 노드의 시간적 메모리
        memory = self.temporal_memory[node_indices] # (B, memory_size, feature_size)
        
        # 쿼리, 키, 밸류 계산
        q = self.memory_query(self.hidden_states[node_indices]).unsqueeze(1) # (B, 1, feature_size)
        k = self.memory_key(memory) # (B, memory_size, feature_size)
        v = self.memory_value(memory) # (B, memory_size, feature_size)
        
        # 어텐션 스코어 계산
        attention_scores = torch.sum(q * k, dim=-1) / np.sqrt(self.feature_size) # (B, memory_size)
        attention_weights = F.softmax(attention_scores, dim=-1) # (B, memory_size)
        
        # 가중합을 통해 컨텍스트 벡터 계산
        context = torch.sum(v * attention_weights.unsqueeze(-1), dim=1) # (B, feature_size)
        return context

class AbstractionLayer(nn.Module):
    """
    확장된 추상화 계층
    -   다양한 비선형 활성화 함수 지원 (ReLU, LeakyReLU, Tanh).
    -   Skip connection을 추가하여 정보 손실 방지.
    -   Batch Normalization 추가.
    """
    def __init__(self, feature_size: int, abstraction_size: int, activation: str = 'relu', use_skip_connection: bool = True, use_batch_norm: bool = True): # activation, use_skip_connection, use_batch_norm 추가
        super().__init__()
        self.feature_size = feature_size
        self.abstraction_size = abstraction_size
        self.use_skip_connection = use_skip_connection
        self.use_batch_norm = use_batch_norm
        
        # 활성화 함수 선택
        if activation.lower() == 'relu':
            self.activation = nn.ReLU()
        elif activation.lower() == 'leakyrelu':
            self.activation = nn.LeakyReLU()
        elif activation.lower() == 'tanh':
            self.activation = nn.Tanh()
        else:
            self.activation = nn.ReLU() # 기본값으로 ReLU 사용
            
        # Projection 레이어
        self.projection = nn.Sequential(
            nn.Linear(feature_size, feature_size * 2),
            nn.BatchNorm1d(feature_size * 2) if use_batch_norm else nn.Identity(), # Batch Normalization
            self.activation,
            nn.Linear(feature_size * 2, abstraction_size),
            nn.BatchNorm1d(abstraction_size) if use_batch_norm else nn.Identity(), # Batch Normalization
        )
        
        # Reconstruction 레이어
        self.reconstruction = nn.Sequential(
            nn.Linear(abstraction_size, feature_size * 2),
            nn.BatchNorm1d(feature_size * 2) if use_batch_norm else nn.Identity(), # Batch Normalization
            self.activation,
            nn.Linear(feature_size * 2, feature_size),
            nn.BatchNorm1d(feature_size) if use_batch_norm else nn.Identity(), # Batch Normalization
        )
        
    def forward(self, features: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        특성에서 추상적 표현을 추출하고 재구성합니다.
        
        Args:
            features: 입력 특성 (B, feature_size)
            
        Returns:
            Tuple[torch.Tensor, torch.Tensor]: (추상적 표현, 재구성된 특성)
        """
        # 추상적 표현 추출
        abstractions = self.projection(features)
        
        # 원래 특성 재구성
        reconstructed = self.reconstruction(abstractions)
        
        if self.use_skip_connection:
            reconstructed = reconstructed + features # Skip connection
            
        return abstractions, reconstructed

class MetaCognitiveModule(nn.Module):
    """
    고급 메타인지 모듈
    -   시스템 상태 평가에 추가 메트릭 (일관성, 복잡성)을 도입.
    -   평가 메트릭에 따라 적응적으로 학습률 조정.
    -   외부 지식 통합 메커니즘 추가.
    """
    def __init__(self, feature_size: int, node_count: int, use_adaptive_lr: bool = True, use_external_knowledge: bool = True): # use_adaptive_lr, use_external_knowledge 추가
        super().__init__()
        self.feature_size = feature_size
        self.node_count = node_count
        self.use_adaptive_lr = use_adaptive_lr
        self.use_external_knowledge = use_external_knowledge
        
        # 글로벌 상태 임베딩
        self.global_state = nn.Parameter(torch.zeros(1, feature_size))
        
        # 시스템 상태 평가 레이어
        self.evaluation = nn.Sequential(
            nn.Linear(feature_size * 2, feature_size),
            nn.ReLU(),
            nn.Linear(feature_size, 5)  # 신뢰도, 불확실성, 주의 필요성, 일관성, 복잡성
        )
        
        # 자기 조정 레이어
        self.adjustment = nn.Sequential(
            nn.Linear(feature_size * 2 + 5, feature_size),
            nn.ReLU(),
            nn.Linear(feature_size, feature_size)
        )
        
        # 외부 지식 통합 레이어 (예시)
        if use_external_knowledge:
            self.knowledge_embedding = nn.Embedding(100, feature_size) # 100개 외부 지식 임베딩
            self.knowledge_attention = nn.Linear(feature_size * 2, 1)
        
        self.lr = 0.001 # 기본 학습률
        
    def assess_and_adjust(self, memory_graph: torch.Tensor, active_nodes: List[int]) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        현재 시스템 상태를 평가하고 필요한 조정을 수행합니다.
        
        Args:
            memory_graph: 현재 메모리 그래프 (node_count, feature_size)
            active_nodes: 현재 활성화된 노드 인덱스 목록
            
        Returns:
            Tuple[torch.Tensor, Dict[str, float]]: (조정된 글로벌 상태, 평가 메트릭)
        """
        if not active_nodes:
            # 활성화된 노드가 없는 경우 기본 상태 반환
            return self.global_state, {"confidence": 0.0, "uncertainty": 1.0, "attention_need": 0.5, "consistency": 0.5, "complexity": 0.5}
            
        # 활성화된 노드의 특성 평균 계산
        active_features = memory_graph[active_nodes].mean(dim=0, keepdim=True)
        
        # 글로벌 상태와 활성 특성 결합
        combined = torch.cat([self.global_state, active_features], dim=1)
        
        # 상태 평가
        eval_scores = self.evaluation(combined)
        confidence, uncertainty, attention_need, consistency, complexity = torch.sigmoid(eval_scores).squeeze().tolist()
        
        # 외부 지식 통합 (예시)
        if self.use_external_knowledge:
            knowledge_index = torch.randint(0, 100, (1,)) # 무작위 외부 지식 선택
            knowledge_embedding = self.knowledge_embedding(knowledge_index)
            knowledge_attention_weight = torch.sigmoid(self.knowledge_attention(torch.cat([combined, knowledge_embedding], dim=1)))
            combined = combined + knowledge_embedding * knowledge_attention_weight
        
        # 글로벌 상태 조정
        adjustment_input = torch.cat([combined, eval_scores], dim=1)
        adjustment = self.adjustment(adjustment_input)
        
        with torch.no_grad():
            self.global_state.add_(adjustment * 0.1)  # 점진적 조정
            
        # 적응적 학습률 조정
        if self.use_adaptive_lr:
            if uncertainty > 0.7:
                self.lr = 0.0005 # 높은 불확실성
            elif confidence > 0.8:
                self.lr = 0.002 # 높은 신뢰도
            else:
                self.lr = 0.001 # 기본값
                
        return self.global_state, {
            "confidence": confidence,
            "uncertainty": uncertainty,
            "attention_need": attention_need,
            "consistency": consistency,
            "complexity": complexity
        }

class ConceptHierarchyModule(nn.Module):
    """
    동적 개념 계층 모듈
    -   노드 간의 계층적 관계를 동적으로 조정.
    -   계층 수준에 따라 다른 변환 적용.
    -   순환 관계 감지 및 해소.
    """
    def __init__(self, node_count: int, feature_size: int, levels: int = 4): # levels를 4로 늘림
        super().__init__()
        self.node_count = node_count
        self.feature_size = feature_size
        self.levels = levels
        
        # 각 노드의 계층 수준 (높을수록 더 추상적)
        self.hierarchy_levels = nn.Parameter(torch.zeros(node_count))
        
        # 계층 간 변환 레이어
        self.level_transforms = nn.ModuleList([
            nn.Linear(feature_size, feature_size) for _ in range(levels) # levels에 맞게 조정
        ])
        
        # 계층적 관계를 저장하는 인접 행렬 (희소 표현)
        self.register_buffer('hierarchy_edges', torch.zeros(0, 2, dtype=torch.long))
        
        # 순환 관계 감지를 위한 변수
        self.register_buffer('visited', torch.zeros(node_count, dtype=torch.bool))
        self.register_buffer('stack', torch.zeros(node_count, dtype=torch.bool))
        
    def add_hierarchy_edge(self, lower_node: int, higher_node: int):
        """
        계층적 관계 엣지를 추가합니다. 순환 관계를 감지하고 해소합니다.
        
        Args:
            lower_node: 하위 개념 노드 인덱스
            higher_node: 상위 개념 노드 인덱스
        """
        if lower_node == higher_node:
            return  # 자기 참조 방지
        
        # 순환 관계 감지
        is_cyclic = self.detect_cycle(lower_node, higher_node)
        if is_cyclic:
            print(f"Warning: Cycle detected when adding edge ({lower_node}, {higher_node}). Edge not added.")
            return
        
        new_edge = torch.tensor([[lower_node, higher_node]], dtype=torch.long)
        self.hierarchy_edges = torch.cat([self.hierarchy_edges, new_edge], dim=0)
        
        # 계층 수준 업데이트
        with torch.no_grad():
            if self.hierarchy_levels[higher_node] <= self.hierarchy_levels[lower_node]:
                self.hierarchy_levels[higher_node] = self.hierarchy_levels[lower_node] + 1
                
    def detect_cycle(self, start_node: int, end_node: int) -> bool:
        """
        DFS를 사용하여 순환 관계를 감지합니다.
        """
        self.visited.fill_(False)
        self.stack.fill_(False)
        
        def dfs(node: int) -> bool:
            self.visited[node] = True
            self.stack[node] = True
            
            for edge in self.hierarchy_edges:
                if edge[0] == node:
                    neighbor = edge[1].item()
                    if neighbor == end_node:
                        return True # Cycle Found
                    if not self.visited[neighbor]:
                        if dfs(neighbor):
                            return True
                    elif self.stack[neighbor]:
                        return True
            
            self.stack[node] = False
            return False
        
        return dfs(start_node)
                
    def propagate_hierarchically(self, node_features: torch.Tensor) -> torch.Tensor:
        """
        계층 구조를 따라 정보를 전파합니다. 각 계층 수준에 맞는 변환을 적용합니다.
        
        Args:
            node_features: 모든 노드의 특성 (node_count, feature_size)
            
        Returns:
            torch.Tensor: 계층적 전파 후 업데이트된 노드 특성
        """
        if self.hierarchy_edges.size(0) == 0:
            return node_features
            
        updated_features = node_features.clone()
        
        # 각 계층 엣지를 따라 정보 전파
        for edge in self.hierarchy_edges:
            lower_node, higher_node = edge.tolist()
            lower_level = int(self.hierarchy_levels[lower_node].item())
            higher_level = int(self.hierarchy_levels[higher_node].item())
            
            # 적절한 계층 변환 적용
            if 0 <= lower_level < self.levels and higher_level > lower_level: # out of bound 수정
                transform = self.level_transforms[lower_level]
                propagated = transform(node_features[lower_node].unsqueeze(0)).squeeze(0)
                updated_features[higher_node] = updated_features[higher_node] + 0.2 * propagated
        
        return updated_features

class ReasoningModule(nn.Module):
    """
    향상된 추론 모듈
    -   관계 분석에 추가적인 관계 유형 (예: temporal, spatial)을 고려.
    -   추론 생성 시 일관성 검증 및 자기 강화 메커니즘 추가.
    """
    def __init__(self, feature_size: int):
        super().__init__()
        self.feature_size = feature_size
        
        # 두 노드 간의 관계를 분석하는 레이어
        self.relation_analyzer = nn.Sequential(
            nn.Linear(feature_size * 2, feature_size),
            nn.ReLU(),
            nn.Linear(feature_size, feature_size // 2),
            nn.ReLU(),
            nn.Linear(feature_size // 2, 5)  # 유사성, 인과성, 대립성, 시간적 관계, 공간적 관계
        )
        
        # 새로운 추론 생성 레이어
        self.inference_generator = nn.Sequential(
            nn.Linear(feature_size * 2 + 5, feature_size * 2),
            nn.ReLU(),
            nn.Linear(feature_size * 2, feature_size)
        )
        
    def analyze_relation(self, feature_a: torch.Tensor, feature_b: torch.Tensor) -> Dict[str, float]:
        """
        두 특성 벡터 간의 관계를 분석합니다.
        
        Args:
            feature_a: 첫 번째 특성 벡터 (feature_size,)
            feature_b: 두 번째 특성 벡터 (feature_size,)
            
        Returns:
            Dict[str, float]: 관계 분석 결과
        """
        combined = torch.cat([feature_a, feature_b]).unsqueeze(0)
        relation_scores = self.relation_analyzer(combined)
        similarity, causality, opposition, temporal, spatial = torch.sigmoid(relation_scores).squeeze().tolist()
        
        return {
            "similarity": similarity,
            "causality": causality,
            "opposition": opposition,
            "temporal": temporal,
            "spatial": spatial
        }
        
    def generate_inference(self, feature_a: torch.Tensor, feature_b: torch.Tensor, memory_graph: torch.Tensor) -> torch.Tensor: # memory_graph 추가
        """
        두 특성 벡터로부터 새로운 추론을 생성합니다. 생성된 추론이 기존 지식과 일관성이 있는지 검증하고, 일관성이 높으면 추론을 강화합니다.
        
        Args:
            feature_a: 첫 번째 특성 벡터 (feature_size,)
            feature_b: 두 번째 특성 벡터 (feature_size,)
            memory_graph: 현재 메모리 그래프 (node_count, feature_size)
            
        Returns:
            torch.Tensor: 추론 결과 특성 벡터 (feature_size,)
        """
        # 관계 분석
        combined = torch.cat([feature_a, feature_b]).unsqueeze(0)
        relation_scores = self.relation_analyzer(combined)
        
        # 관계 정보를 포함하여 추론 생성
        inference_input = torch.cat([combined, relation_scores], dim=1)
        inference = self.inference_generator(inference_input).squeeze(0)
        
        # 일관성 검증 (예시: 코사인 유사도)
        consistency = F.cosine_similarity(inference.unsqueeze(0), memory_graph, dim=1).max()
        
        if consistency > 0.8: # 일관성이 높으면 추론 강화
            inference = inference * 1.2
        
        return inference

class EnhancedReflectiveCognitiveGraph(nn.Module):
    """
    향상된 Reflective Cognitive Graph 모델.
    
    기존의 메모리 그래프와 사고망을 확장하여 주의 집중, 시간적 메모리, 
    추상화, 메타인지, 개념 계층 및 추론 기능을 추가하였습니다.
    """
    def __init__(self, 
                 node_count: int, 
                 feature_size: int, 
                 connection_prob: float = 0.1, # 연결 확률 증가
                 depth: int = 4, # 탐색 깊이 증가
                 abstraction_size: int = 128, # 추상화 크기 증가
                 attention_heads: int = 8, # 어텐션 헤드 수 증가
                 memory_size: int = 10, # 메모리 크기 증가
                 hierarchy_levels: int = 4, # 계층 수준 증가
                 use_gru: bool = True, # GRU 사용
                 memory_decay: float = 0.8, # 메모리 decay 추가
                 activation: str = 'leakyrelu', # 활성화 함수 변경
                 use_skip_connection: bool = True, # Skip connection 사용
                 use_batch_norm: bool = True, # Batch Normalization 사용
                 use_adaptive_lr: bool = True, # 적응적 학습률 사용
                 use_external_knowledge: bool = True, # 외부 지식 사용
                 dropout_prob: float = 0.2 # Dropout 확률
                 ):
        super().__init__()
        
        self.node_count = node_count
        self.feature_size = feature_size
        self.connection_prob = connection_prob
        self.depth = depth
        
        # 기본 메모리 그래프
        self.memory_graph = nn.Parameter(torch.randn(node_count, feature_size))
        
        # 사고 네트워크
        self.thought_network = {}
        
        # 전파 추적 변수
        self._visited_during_propagate = set()
        self._current_edges_list = []
        self.edge_index = None
        
        # 향상된 모듈들
        self.attention = AttentionModule(feature_size, attention_heads, dropout_prob)
        self.temporal_memory = TemporalMemoryModule(node_count, feature_size, memory_size, use_gru, memory_decay)
        self.abstraction = AbstractionLayer(feature_size, abstraction_size, activation, use_skip_connection, use_batch_norm)
        self.metacognition = MetaCognitiveModule(feature_size, node_count, use_adaptive_lr, use_external_knowledge)
        self.concept_hierarchy = ConceptHierarchyModule(node_count, feature_size, hierarchy_levels)
        self.reasoning = ReasoningModule(feature_size)
        
        # 활성화된 노드 추적
        self.active_nodes = []
        
        # 개념 카테고리 매핑 (예: {'자연어': [0, 1, 2], '수학': [3, 4, 5], ...})
        self.concept_categories = {}
        
        # AGI 관련 파라미터 (예시)
        self.novelty_threshold = 0.8
        self.exploration_prob = 0.2
        self.long_term_memory = nn.Parameter(torch.randn(node_count, feature_size))
        self.memory_update_decay = 0.95
        
    def activate_node(self, node_index: int):
        """
        노드를 활성화하고 사고망 전파를 준비합니다.
        """
        if not (0 <= node_index < self.node_count):
            print(f"Warning: Node index {node_index} is out of bounds.")
            return

        # 추적 변수 초기화
        self._visited_during_propagate = set()
        self._current_edges_list = []

        # 시작 노드의 자기 루프 추가
        self._current_edges_list.append((node_index, node_index))
        self._visited_during_propagate.add(node_index)

        # 사고망에 노드 초기화
        if node_index not in self.thought_network:
            self.thought_network[node_index] = set()
            
        # 활성 노드 목록에 추가
        if node_index not in self.active_nodes:
            self.active_nodes.append(node_index)
            
        # 시간적 메모리 업데이트
        self.temporal_memory.update_memory(
            torch.tensor([node_index]), 
            self.memory_graph[node_index].unsqueeze(0)
        )

    def recursive_propagate(self, start_node: int):
        """
        시작 노드에서 재귀적으로 사고망을 전파합니다.
        """
        # activate_node가 먼저 호출되지 않았을 경우 방어 코드
        if not self._visited_during_propagate or not self._current_edges_list:
            print("Warning: recursive_propagate called without activating a node first. Activating node.")
            self.activate_node(start_node)

        # 재귀적 전파 내부 함수
        def _propagate(node: int, current_depth: int):
            if current_depth > self.depth:
                return

            potential_neighbors = range(self.node_count)

            for neighbor in potential_neighbors:
                # 깊이에 따라 연결 확률 조정
                connection_probability = self.connection_prob + 0.01 * current_depth
                
                # 개념 카테고리가 같은 경우 연결 확률 증가
                for category, nodes in self.concept_categories.items():
                    if node in nodes and neighbor in nodes:
                        connection_probability += 0.1
                        break
                
                # AGI: Novelty 기반 탐색
                if random.random() < self.exploration_prob:
                    connection_probability = 1.0 # 높은 exploration_prob
                
                if random.random() < connection_probability:
                    # 엣지 추가 (neighbor <- node)
                    self._current_edges_list.append((neighbor, node))
                    self.thought_network[node].add(neighbor)

                    # 방문하지 않은 노드인 경우에만 재귀 호출
                    if neighbor not in self._visited_during_propagate:
                        self._visited_during_propagate.add(neighbor)
                        
                        # 메타인지 모듈을 통한 전파 중요도 평가
                        _, metrics = self.metacognition.assess_and_adjust(
                            self.memory_graph, 
                            [node, neighbor]
                        )
                        
                        # 중요도가 높은 경우에만 계속 전파
                        if metrics["attention_need"] > 0.3:
                            _propagate(neighbor, current_depth + 1)
                        
                        # 활성 노드에 추가
                        if neighbor not in self.active_nodes:
                            self.active_nodes.append(neighbor)

        # 전파 시작
        _propagate(start_node, 0)

        # 수집된 엣지 리스트를 텐서로 변환
        if self._current_edges_list:
            unique_edges = list(set(self._current_edges_list))
            self.edge_index = torch.tensor(unique_edges, dtype=torch.long).t().contiguous()
        else:
            self.edge_index = torch.empty((2, 0), dtype=torch.long)

        # 추적 변수 초기화
        self._visited_during_propagate = set()
        self._current_edges_list = []
        
        # 활성 노드 목록 정리 (최대 10개 유지)
        if len(self.active_nodes) > 10:
            self.active_nodes = self.active_nodes[-10:]

    def register_concept_category(self, category_name: str, node_indices: List[int]):
        """
        노드들의 개념 카테고리를 등록합니다.
        
        Args:
            category_name: 카테고리 이름
            node_indices: 해당 카테고리에 속하는 노드 인덱스 목록
        """
        self.concept_categories[category_name] = node_indices
        
        # 같은 카테고리 내 노드 간 계층 관계 자동 설정
        if len(node_indices) > 1:
            for i in range(len(node_indices) - 1):
                for j in range(i + 1, len(node_indices)):
                    # 무작위로 계층 관계 설정 (50% 확률)
                    if random.random() < 0.5:
                        self.concept_hierarchy.add_hierarchy_edge(node_indices[i], node_indices[j])
                    else:
                        self.concept_hierarchy.add_hierarchy_edge(node_indices[j], node_indices[i])
                        
    def update_long_term_memory(self):
        """
        장기 기억을 활성화된 노드의 현재 상태로 업데이트합니다.
        """
        if self.active_nodes:
            active_indices = torch.tensor(self.active_nodes)
            self.long_term_memory[active_indices] = (
                self.long_term_memory[active_indices] * self.memory_update_decay +
                self.memory_graph[active_indices] * (1 - self.memory_update_decay)
            )

    def forward(self):
        """
        인지 그래프 포워드 패스를 수행하여 메모리 그래프를 업데이트합니다.
        """
        # edge_index가 없는 경우 원래 메모리 그래프 반환
        if self.edge_index is None or self.edge_index.size(1) == 0:
            print("Warning: forward called before recursive_propagate or with no edges. Returning original features.")
            return self.memory_graph

        updated_features = self.memory_graph.clone()
        
        # 1. 주의 집중 메커니즘 적용
        attention_features = self.attention(self.memory_graph, self.edge_index)
        updated_features = updated_features + 0.2 * attention_features
        
        # 2. 활성 노드에 대한 시간적 컨텍스트 적용
        if self.active_nodes:
            active_indices = torch.tensor(self.active_nodes)
            temporal_context = self.temporal_memory.get_temporal_context(active_indices)
            updated_features[self.active_nodes] = updated_features[self.active_nodes] + 0.1 * temporal_context
        
        # 3. 추상화 계층 적용 (활성 노드만)
        if self.active_nodes:
            active_features = updated_features[self.active_nodes]
            abstractions, reconstructed = self.abstraction(active_features)
            updated_features[self.active_nodes] = updated_features[self.active_nodes] + 0.15 * reconstructed
        
        # 4. 계층적 개념 전파
        hierarchical_features = self.concept_hierarchy.propagate_hierarchically(updated_features)
        updated_features = updated_features + 0.1 * hierarchical_features
        
        # 5. 메타인지 평가 및 조정
        global_state, metrics = self.metacognition.assess_and_adjust(updated_features, self.active_nodes)
        
        # 메타인지 정보를 기반으로 불확실한 영역에 초점 맞추기
        if metrics["uncertainty"] > 0.6 and self.active_nodes:
            # 높은 불확실성이 있는 경우, 활성 노드 간 추론 수행
            for i in range(len(self.active_nodes) - 1):
                for j in range(i + 1, len(self.active_nodes)):
                    node_a = self.active_nodes[i]
                    node_b = self.active_nodes[j]
                    
                    # 노드 간 관계 분석
                    relation = self.reasoning.analyze_relation(
                        updated_features[node_a], 
                        updated_features[node_b]
                    )
                    
                    # 유사성이 높으면 서로의 특성 혼합
                    if relation["similarity"] > 0.7:
                        mixed = 0.3 * updated_features[node_a] + 0.3 * updated_features[node_b]
                        updated_features[node_a] = updated_features[node_a] + 0.1 * mixed
                        updated_features[node_b] = updated_features[node_b] + 0.1 * mixed
                    
                    # 인과성이 높으면 추론 생성
                    if relation["causality"] > 0.7:
                        inference = self.reasoning.generate_inference(updated_features[node_a], updated_features[node_b], self.memory_graph)
                        updated_features[node_a] = updated_features[node_a] + 0.05 * inference
                        
        # 장기 기억 업데이트
        self.update_long_term_memory()
        
        self.memory_graph = updated_features.clone() # Update memory graph
        
        return updated_features

