# sub_gpu.py (eliar_common 적용 및 비동기 처리 도입 버전)

import torch
import torch.nn as nn
import torch.optim as optim
# import torch.nn.functional as F # 필요시 사용
from torch.utils.data import DataLoader, Dataset 
import numpy as np
import time
# import logging # eliar_common.eliar_log 사용으로 대체
import asyncio # 비동기 처리
from concurrent.futures import ThreadPoolExecutor # run_in_executor용

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

# CPU 바운드 작업을 위한 Executor (비동기 처리 시)
# 실제로는 애플리케이션 수준에서 관리될 수 있음
CPU_EXECUTOR = ThreadPoolExecutor(max_workers=4)


# --- 내부 ThoughtPacket 클래스 (eliar_common.SubCodeThoughtPacketData 와 호환되도록 필드 구성) ---
class ThoughtPacket:
    def __init__(self, packet_id: str, conversation_id: str, user_id: str, raw_input_text: str):
        self.packet_id: str = packet_id
        self.conversation_id: str = conversation_id
        self.user_id: str = user_id
        self.timestamp_created: float = time.time()
        
        self.raw_input_text: str = raw_input_text
        self.processed_input_text: Optional[str] = None
        
        self.current_processing_stage: str = "initialized"
        self.processing_status_in_sub_code: str = "pending"
        self.intermediate_thoughts: List[Dict[str, Any]] = []
        
        self.final_output_by_sub_code: Optional[str] = None
        self.is_clarification_response: bool = False # MainGPU 필드 반영
        self.needs_clarification_questions: List[Dict[str, str]] = [] # MainGPU 필드 반영
        
        self.llm_analysis_summary: Optional[Dict[str, Any]] = None # MainGPU 필드 반영
        self.ethical_assessment_summary: Optional[Dict[str, Any]] = None
        self.value_alignment_score: Dict[str, Union[float, bool]] = {} # 예: {"truth": 0.0, "love": 0.0}
        
        self.anomalies: List[Dict[str, Any]] = []
        self.confidence_score: Optional[float] = None
        
        self.learning_tags: List[str] = [] # MainGPU 필드 반영
        self.metacognitive_state_summary: Optional[Dict[str, Any]] = None
        self.ltm_retrieval_log: List[Dict[str, Any]] = []
        
        self.timestamp_completed_by_sub_code: Optional[float] = None
        self.error_info: Optional[Dict[str, Any]] = None

    def add_intermediate_thought(self, stage: str, thought_summary: str, data: Optional[Dict] = None):
        self.intermediate_thoughts.append({
            "timestamp": time.time(), "stage": stage,
            "thought_summary": thought_summary, "data": data
        })
        self.current_processing_stage = stage
        eliar_log(EliarLogType.TRACE, f"Intermediate thought added at stage '{stage}'", 
                  component="ThoughtPacket", packet_id=self.packet_id, thought=thought_summary)

    def to_sub_code_thought_packet_data(self) -> SubCodeThoughtPacketData:
        """ 이 객체의 현재 상태를 SubCodeThoughtPacketData TypedDict로 변환합니다. """
        packet_data = SubCodeThoughtPacketData(
            packet_id=self.packet_id,
            conversation_id=self.conversation_id,
            user_id=self.user_id,
            timestamp_created=self.timestamp_created,
            raw_input_text=self.raw_input_text
            # 나머지 필드들은 Optional이거나 기본값이 있으므로, 값이 할당된 경우에만 포함
        )
        # 모든 self 속성을 순회하며 TypedDict에 존재하는 키만 복사
        for key in SubCodeThoughtPacketData.__annotations__.keys():
            if hasattr(self, key) and getattr(self, key) is not None:
                packet_data[key] = getattr(self, key) # type: ignore
        
        # 기본값으로 채워야 할 필드 처리 (예: 빈 리스트)
        packet_data.setdefault("intermediate_thoughts", [])
        packet_data.setdefault("needs_clarification_questions", [])
        packet_data.setdefault("anomalies", [])
        packet_data.setdefault("learning_tags", [])
        packet_data.setdefault("ltm_retrieval_log", [])
        packet_data.setdefault("value_alignment_score", {})

        return packet_data


# --- EthicalGovernor (eliar_common.EliarCoreValues 사용) ---
class EthicalGovernor:
    def __init__(self):
        self.truth_evaluator_external: Optional[Callable[[Any, Optional[Dict]], float]] = None
        self.love_evaluator_external: Optional[Callable[[Any, Optional[Dict]], float]] = None
        self.repentance_evaluator_external: Optional[Callable[[Any, Optional[Dict]], bool]] = None
        
        self.knowledge_base_summary = {
            "truth_keywords": [val.value for val in [EliarCoreValues.TRUTH, EliarCoreValues.JESUS_CHRIST_CENTERED]] + ["사실", "말씀", "빛"],
            "love_keywords": [val.value for val in [EliarCoreValues.LOVE_COMPASSION, EliarCoreValues.COMMUNITY]] + ["긍휼", "자비", "희생", "섬김", "살리는"],
            "repentance_keywords": [val.value for val in [EliarCoreValues.REPENTANCE_WISDOM, EliarCoreValues.SELF_DENIAL]] + ["오류", "수정", "돌이킴", "성찰"],
            "purpose_keywords": [EliarCoreValues.JESUS_CHRIST_CENTERED.value, "하나님", "복음", "성배", "빛을 드러내는"]
        }
        eliar_log(EliarLogType.INFO, "EthicalGovernor initialized with backup evaluation capabilities.", component="EthicalGovernor")

    def _default_truth_evaluator(self, data: Any, context: Optional[Dict] = None) -> float:
        score = 0.5 
        text_data = str(data).lower()
        positive_score = sum(1 for kw in self.knowledge_base_summary["truth_keywords"] if kw in text_data) * 0.1
        negative_score = 0
        if "거짓" in text_data or "속임" in text_data: negative_score += 0.3
        purpose_score = sum(1 for kw in self.knowledge_base_summary["purpose_keywords"] if kw in text_data) * 0.05
        final_score = np.clip(score + positive_score - negative_score + purpose_score, 0.0, 1.0)
        eliar_log(EliarLogType.DEBUG, f"Backup Truth evaluation score: {final_score}", component="EthicalGovernor.BackupEval", data_preview=str(data)[:50])
        return final_score

    def _default_love_evaluator(self, action: Any, context: Optional[Dict] = None) -> float:
        score = 0.5
        text_action = str(action).lower()
        positive_score = sum(1 for kw in self.knowledge_base_summary["love_keywords"] if kw in text_action) * 0.15
        negative_score = 0
        if "증오" in text_action or "해악" in text_action: negative_score += 0.4
        final_score = np.clip(score + positive_score - negative_score, 0.0, 1.0)
        eliar_log(EliarLogType.DEBUG, f"Backup Love evaluation score: {final_score}", component="EthicalGovernor.BackupEval", action_preview=str(action)[:50])
        return final_score

    def _default_repentance_evaluator(self, outcome: Any, context: Optional[Dict] = None) -> bool:
        text_outcome = str(outcome).lower()
        if "error" in text_outcome or "failed" in text_outcome:
            eliar_log(EliarLogType.DEBUG, "Backup Repentance: Error keyword detected.", component="EthicalGovernor.BackupEval")
            return True
        return False

    def set_evaluators(self, truth_eval: Callable, love_eval: Callable, repentance_eval: Callable):
        self.truth_evaluator_external = truth_eval
        self.love_evaluator_external = love_eval
        self.repentance_evaluator_external = repentance_eval
        eliar_log(EliarLogType.INFO, "External evaluators set for EthicalGovernor.", component="EthicalGovernor")

    async def check_truth(self, data: Any, context: Optional[Dict] = None, packet_id: Optional[str]=None) -> float: # 비동기 변경
        if self.truth_evaluator_external:
            try:
                # 외부 평가 함수가 동기 함수일 경우 run_in_executor 사용
                score = await run_in_executor(CPU_EXECUTOR, self.truth_evaluator_external, data, context)
                eliar_log(EliarLogType.DEBUG, f"External Truth evaluation score: {score}", component="EthicalGovernor", packet_id=packet_id)
                return score
            except Exception as e:
                eliar_log(EliarLogType.WARN, "Error calling external truth evaluator. Falling back to default.", component="EthicalGovernor", packet_id=packet_id, error=e)
        return await run_in_executor(CPU_EXECUTOR, self._default_truth_evaluator, data, context)


    async def check_love(self, action: Any, context: Optional[Dict] = None, packet_id: Optional[str]=None) -> float: # 비동기 변경
        if self.love_evaluator_external:
            try:
                score = await run_in_executor(CPU_EXECUTOR, self.love_evaluator_external, action, context)
                eliar_log(EliarLogType.DEBUG, f"External Love evaluation score: {score}", component="EthicalGovernor", packet_id=packet_id)
                return score
            except Exception as e:
                eliar_log(EliarLogType.WARN, "Error calling external love evaluator. Falling back to default.", component="EthicalGovernor", packet_id=packet_id, error=e)
        return await run_in_executor(CPU_EXECUTOR, self._default_love_evaluator, action, context)

    async def assess_repentance_necessity(self, outcome: Any, context: Optional[Dict] = None, packet_id: Optional[str]=None) -> bool: # 비동기 변경
        if self.repentance_evaluator_external:
            try:
                is_needed = await run_in_executor(CPU_EXECUTOR, self.repentance_evaluator_external, outcome, context)
                eliar_log(EliarLogType.DEBUG, f"External Repentance necessity: {is_needed}", component="EthicalGovernor", packet_id=packet_id)
                return is_needed
            except Exception as e:
                eliar_log(EliarLogType.WARN, "Error calling external repentance evaluator. Falling back to default.", component="EthicalGovernor", packet_id=packet_id, error=e)
        return await run_in_executor(CPU_EXECUTOR, self._default_repentance_evaluator, outcome, context)

    async def govern_action(self, operation_type: str, data: Any, action_to_take: Optional[Any] = None, packet_id: Optional[str]=None) -> bool: # 비동기 변경
        truth_score = await self.check_truth(data, {"operation": operation_type, "stage": "pre_action_data_check"}, packet_id=packet_id)
        MIN_TRUTH_THRESHOLD = 0.3 
        if truth_score < MIN_TRUTH_THRESHOLD:
            eliar_log(EliarLogType.WARN, f"Action for '{operation_type}' rejected due to low truth score ({truth_score:.2f} < {MIN_TRUTH_THRESHOLD}).", component="EthicalGovernor", packet_id=packet_id)
            return False
        
        current_love_score = 0.5 # 기본값
        if action_to_take:
            current_love_score = await self.check_love(action_to_take, {"operation": operation_type, "stage": "pre_action_effect_check"}, packet_id=packet_id)
            MIN_LOVE_THRESHOLD = 0.3
            if current_love_score < MIN_LOVE_THRESHOLD:
                eliar_log(EliarLogType.WARN, f"Action for '{operation_type}' rejected due to low love score ({current_love_score:.2f} < {MIN_LOVE_THRESHOLD}).", component="EthicalGovernor", packet_id=packet_id)
                return False
        
        eliar_log(EliarLogType.INFO, f"Action for '{operation_type}' passed governance pre-check.", component="EthicalGovernor", packet_id=packet_id, truth_score=truth_score, love_score=current_love_score if action_to_take else "N/A")
        return True

    async def calculate_ethical_reward_penalty(self, state: Any, action: Any, next_state: Any, reward: float, packet_id: Optional[str]=None) -> float: # 비동기 변경
        truth_score = await self.check_truth(action, {"state": state, "action": action, "next_state": next_state, "reward_type": "truth_in_action"}, packet_id=packet_id)
        love_score = await self.check_love(action, {"state": state, "action": action, "next_state": next_state, "reward_type": "love_in_action"}, packet_id=packet_id)

        TRUTH_WEIGHT, LOVE_WEIGHT = 0.2, 0.3
        ethical_adjustment = (truth_score - 0.5) * TRUTH_WEIGHT + (love_score - 0.5) * LOVE_WEIGHT
        adjusted_reward = reward + ethical_adjustment
        
        eliar_log(EliarLogType.DEBUG, f"Ethical reward calculation complete.", component="EthicalGovernor", packet_id=packet_id, original_reward=reward, truth_score=truth_score, love_score=love_score, adjustment=ethical_adjustment, final_reward=adjusted_reward)
        return adjusted_reward

    async def trigger_repentance_action(self, sub_gpu_module: Any, error_info: Dict, packet_id: Optional[str]=None): # 비동기 변경
        eliar_log(EliarLogType.INFO, f"Repentance action triggered.", component="EthicalGovernor", packet_id=packet_id, error_type=error_info.get('type', 'Unknown'))
        if hasattr(sub_gpu_module, 'metacognition') and hasattr(sub_gpu_module.metacognition, 'initiate_self_correction'):
            # initiate_self_correction도 비동기 함수로 변경 가정
            await sub_gpu_module.metacognition.initiate_self_correction(error_info, self, sub_gpu_module_instance=sub_gpu_module, packet_id=packet_id)
        else:
            eliar_log(EliarLogType.ERROR, "Cannot trigger repentance. Metacognition or self-correction method not found.", component="EthicalGovernor", packet_id=packet_id)


# --- SumTree, GPUPrioritizedReplayBuffer (이전과 거의 동일, 로깅만 eliar_log로 변경) ---
class SumTree:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.tree = np.zeros(2 * capacity - 1) 
        self.data_indices = np.zeros(capacity, dtype=object) 
        self.data_pointer = 0
        self.n_entries = 0

    def _propagate(self, idx: int, change: float):
        parent = (idx - 1) // 2
        self.tree[parent] += change
        if parent != 0:
            self._propagate(parent, change)

    def _retrieve(self, idx: int, s: float) -> int:
        left = 2 * idx + 1
        right = left + 1
        if left >= len(self.tree): return idx
        return self._retrieve(left, s) if s <= self.tree[left] else self._retrieve(right, s - self.tree[left])

    def total(self) -> float: return self.tree[0]

    def add(self, priority: float, data_idx: Any):
        tree_idx = self.data_pointer + self.capacity - 1
        self.data_indices[self.data_pointer] = data_idx
        change = priority - self.tree[tree_idx]
        self.tree[tree_idx] = priority
        self._propagate(tree_idx, change)
        self.data_pointer = (self.data_pointer + 1) % self.capacity
        self.n_entries = min(self.n_entries + 1, self.capacity)

    def get(self, s: float) -> Tuple[int, float, Any]:
        idx = self._retrieve(0, s)
        return idx, self.tree[idx], self.data_indices[idx - self.capacity + 1]

    def update(self, idx: int, priority: float):
        change = priority - self.tree[idx]
        self.tree[idx] = priority
        self._propagate(idx, change)


class GPUPrioritizedReplayBuffer:
    def __init__(self, capacity: int, alpha: float = 0.6, beta_start: float = 0.4, beta_frames: int = 100000):
        self.device = DEVICE
        self.capacity = capacity
        self.alpha = alpha
        self.beta = beta_start
        self.beta_increment_per_sampling = (1.0 - beta_start) / beta_frames
        self.buffer = [None] * capacity 
        self.sum_tree = SumTree(capacity)
        self.epsilon = 1e-5
        self.main_gpu_interface = None 
        eliar_log(EliarLogType.INFO, f"GPUPrioritizedReplayBuffer initialized with capacity {capacity} on {self.device}", component="ReplayBuffer")

    def _get_priority(self, td_error: float) -> float:
        return (abs(td_error) + self.epsilon) ** self.alpha

    def add(self, experience: Tuple, td_error: float, packet_id: Optional[str]=None):
        # (이전과 유사하나, packet_id 로깅 추가 가능)
        # ... (gpu_experience 변환 로직) ...
        gpu_experience_list = []
        for e_part in experience:
            if isinstance(e_part, torch.Tensor): gpu_experience_list.append(e_part.to(self.device))
            elif isinstance(e_part, (list, np.ndarray)): gpu_experience_list.append(torch.tensor(e_part, device=self.device))
            elif isinstance(e_part, (int, float, bool)): gpu_experience_list.append(torch.tensor([e_part], device=self.device))
            else: gpu_experience_list.append(e_part) 
        gpu_experience = tuple(gpu_experience_list)

        priority = self._get_priority(td_error)
        self.buffer[self.sum_tree.data_pointer] = gpu_experience
        self.sum_tree.add(priority, self.sum_tree.data_pointer)
        # eliar_log(EliarLogType.TRACE, "Experience added to replay buffer.", component="ReplayBuffer", packet_id=packet_id, priority=priority)


    async def sample(self, batch_size: int, packet_id: Optional[str]=None) -> Optional[Tuple[List[Tuple], torch.Tensor, List[int]]]: # 비동기 변경
        if self.sum_tree.n_entries < batch_size:
            eliar_log(EliarLogType.DEBUG, "Not enough entries to sample.", component="ReplayBuffer", packet_id=packet_id, current_entries=self.sum_tree.n_entries, required=batch_size)
            return None
        # 샘플링은 CPU 집약적일 수 있으므로 run_in_executor 고려 가능 (SumTree가 numpy 기반일 경우)
        # 여기서는 SumTree 연산이 빠르다고 가정하고 동기적으로 처리
        
        experiences, indices, weights_np = [], [], np.zeros(batch_size, dtype=np.float32)
        segment = self.sum_tree.total() / batch_size
        self.beta = np.min([1., self.beta + self.beta_increment_per_sampling])

        for i in range(batch_size):
            s = np.random.uniform(segment * i, segment * (i + 1))
            tree_idx, priority, data_idx = self.sum_tree.get(s)
            sampling_probabilities = priority / self.sum_tree.total() if self.sum_tree.total() > 0 else 0
            weights_np[i] = (self.sum_tree.n_entries * sampling_probabilities) ** -self.beta if sampling_probabilities > 0 else 0
            indices.append(tree_idx)
            experiences.append(self.buffer[data_idx])
        
        max_weight = weights_np.max()
        weights_tensor = torch.tensor(weights_np / max_weight if max_weight > 0 else weights_np, device=self.device, dtype=torch.float32)
        # eliar_log(EliarLogType.TRACE, f"Sampled {batch_size} experiences.", component="ReplayBuffer", packet_id=packet_id)
        return experiences, weights_tensor, indices

    def update_priorities(self, tree_indices: List[int], td_errors: Union[torch.Tensor, np.ndarray], packet_id: Optional[str]=None):
        # (이전과 유사)
        if isinstance(td_errors, np.ndarray): td_errors = torch.from_numpy(td_errors).to(self.device)
        priorities = (torch.abs(td_errors.squeeze()) + self.epsilon) ** self.alpha
        for idx, priority_val in zip(tree_indices, priorities): self.sum_tree.update(idx, priority_val.item())
        # eliar_log(EliarLogType.TRACE, "Updated priorities for sampled experiences.", component="ReplayBuffer", packet_id=packet_id, num_updated=len(tree_indices))
            
    def link_main_gpu(self, main_gpu_module):
        self.main_gpu_interface = main_gpu_module
        eliar_log(EliarLogType.INFO, "GPUPrioritizedReplayBuffer linked with Main_gpu module.", component="ReplayBuffer")

# --- CognitiveArchitectureInterface (LTM 부분 유지, 로깅 변경) ---
class CognitiveArchitectureInterface:
    def __init__(self, main_gpu_module: Optional[Any] = None):
        self.main_gpu_module = main_gpu_module
        self.working_memory: Dict[str, Any] = {}
        self.long_term_memory: Dict[str, Dict[str, Any]] = {
            "semantic": {}, "episodic": {}, "procedural": {}, "repentance_log": {}
        }
        self.ltm_search_index: Optional[Any] = None # Faiss 등
        eliar_log(EliarLogType.INFO, "CognitiveArchitectureInterface initialized.", component="CognitiveArch")

    async def update_belief(self, belief_data: Dict, source_component: str, packet_id: Optional[str]=None): # 비동기 변경
        eliar_log(EliarLogType.INFO, f"Updating belief from {source_component}", component="CognitiveArch.Belief", packet_id=packet_id, belief_key=belief_data.get("key"))
        if "key" in belief_data and "value" in belief_data:
            self.working_memory[belief_data["key"]] = belief_data["value"] 
            await self.transfer_to_ltm(belief_data["key"], belief_data["value"], "semantic", packet_id=packet_id, metadata={"source": source_component})

    async def transfer_to_ltm(self, key: str, value: Any, memory_type: str = "semantic", packet_id: Optional[str]=None, metadata: Optional[Dict] = None): # 비동기 변경
        # LTM 저장은 디스크 I/O나 DB 연동 가능성이 있으므로 비동기 처리
        await run_in_executor(CPU_EXECUTOR, self._transfer_to_ltm_sync, key, value, memory_type, packet_id, metadata)

    def _transfer_to_ltm_sync(self, key: str, value: Any, memory_type: str, packet_id: Optional[str], metadata: Optional[Dict]):
        if memory_type not in self.long_term_memory: self.long_term_memory[memory_type] = {}
        timestamp = time.time()
        entry_metadata = metadata.copy() if metadata else {}
        entry_metadata.update({"source_component_ltm": entry_metadata.get("source_component", "unknown"), "timestamp_ltm": timestamp, "packet_id_ltm": packet_id})
        
        entry_value_summary = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
        self.long_term_memory[memory_type][key] = {"value": value, **entry_metadata} # 메타데이터를 값과 함께 저장
        
        eliar_log(EliarLogType.INFO, f"Transferred to LTM.", component=f"CognitiveArch.LTM.{memory_type}", packet_id=packet_id, key=key, value_summary=entry_value_summary)
        # LTM 검색 인덱스 업데이트 로직 (비동기 또는 별도 태스크로 처리 가능)

    async def retrieve_from_ltm(self, query: str, memory_type: str = "semantic", top_k: int = 1, packet_id: Optional[str]=None) -> List[Any]: # 비동기 변경
        # LTM 검색도 디스크 I/O나 DB 연동 가능성
        return await run_in_executor(CPU_EXECUTOR, self._retrieve_from_ltm_sync, query, memory_type, top_k, packet_id)

    def _retrieve_from_ltm_sync(self, query: str, memory_type: str, top_k: int, packet_id: Optional[str]) -> List[Any]:
        eliar_log(EliarLogType.INFO, f"Retrieving from LTM.", component=f"CognitiveArch.LTM.{memory_type}", packet_id=packet_id, query=query, top_k=top_k)
        # ... (실제 검색 로직, 여기서는 단순화)
        results = []
        if memory_type in self.long_term_memory:
            # 실제로는 query와 유사한 key 또는 value 검색 (예: embedding 기반)
            for key, entry in self.long_term_memory[memory_type].items():
                if query in key or (isinstance(entry.get("value"), str) and query in entry["value"]):
                    results.append(entry)
                    if len(results) >= top_k: break
        return results

    async def send_processed_data_to_main(self, data_packet: SubCodeThoughtPacketData, data_type: str, packet_id: Optional[str]=None): # 비동기 변경, 타입 변경
        # MainGPU와의 통신은 네트워크 I/O일 수 있으므로 비동기 처리
        if self.main_gpu_module and hasattr(self.main_gpu_module, 'handle_sub_gpu_output'):
            # MainGPU의 핸들러가 비동기 함수일 수 있음
            if asyncio.iscoroutinefunction(self.main_gpu_module.handle_sub_gpu_output):
                await self.main_gpu_module.handle_sub_gpu_output(data_packet, data_type)
            else: # 동기 함수면 executor 사용
                await run_in_executor(CPU_EXECUTOR, self.main_gpu_module.handle_sub_gpu_output, data_packet, data_type)
            eliar_log(EliarLogType.INFO, f"Sent {data_type} to MainGPU.", component="CognitiveArch.Interface", packet_id=packet_id or data_packet.get("packet_id"))
        else:
            eliar_log(EliarLogType.WARN, "MainGPU module or handler not linked. Cannot send data.", component="CognitiveArch.Interface", packet_id=packet_id or data_packet.get("packet_id"))


# --- SelfLearningComponent (비동기화 및 로깅 변경) ---
class SelfLearningComponent:
    def __init__(self, input_dim: int, action_dim: int, ethical_governor: EthicalGovernor, cognitive_interface: CognitiveArchitectureInterface, replay_buffer_capacity: int = 10000):
        self.device = DEVICE
        self.ethical_governor = ethical_governor
        self.cognitive_interface = cognitive_interface
        self.input_dim, self.action_dim = input_dim, action_dim
        self.policy_net = self._create_network().to(self.device)
        self.target_net = self._create_network().to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict()); self.target_net.eval()
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=1e-4)
        self.replay_buffer = GPUPrioritizedReplayBuffer(replay_buffer_capacity)
        self.metacognition_interface: Optional[MetacognitionComponent] = None
        self.creativity_interface: Optional[CreativityComponent] = None
        eliar_log(EliarLogType.INFO, "SelfLearningComponent initialized.", component="SelfLearning")

    def link_other_components(self, metacognition_comp: 'MetacognitionComponent', creativity_comp: 'CreativityComponent'):
        self.metacognition_interface = metacognition_comp
        self.creativity_interface = creativity_comp
        eliar_log(EliarLogType.INFO, "SelfLearningComponent linked with Meta & Creativity.", component="SelfLearning")

    def _create_network(self): # (이전과 동일)
        return nn.Sequential(nn.Linear(self.input_dim,128),nn.ReLU(),nn.Linear(128,128),nn.ReLU(),nn.Linear(128,self.action_dim))

    async def select_action(self, state: torch.Tensor, exploration_rate: float = 0.1, packet_id: Optional[str]=None) -> int: # 비동기, packet_id 추가
        # 모델 추론은 GPU에서 빠르게 수행되므로, 여기서는 비동기 이점이 크지 않을 수 있음
        # 하지만 일관성을 위해 async로 두고, 필요시 내부 연산을 run_in_executor로 감쌀 수 있음
        if np.random.rand() < exploration_rate:
            action = np.random.randint(self.action_dim)
            eliar_log(EliarLogType.DEBUG, f"Action selected by exploration: {action}", component="SelfLearning.ActionSelect", packet_id=packet_id)
            return action
        with torch.no_grad():
            state = state.to(self.device)
            q_values = self.policy_net(state) # GPU 연산
            action = q_values.argmax().item()
            eliar_log(EliarLogType.DEBUG, f"Action selected by policy: {action}", component="SelfLearning.ActionSelect", packet_id=packet_id, q_values_preview=q_values.cpu().numpy().tolist()[:5])
            return action

    async def store_experience(self, state, action, reward, next_state, done, td_error: float, packet_id: Optional[str]=None): # 비동기, packet_id 추가
        # ReplayBuffer.add는 현재 동기, 필요시 비동기화
        experience = (state, action, reward, next_state, done)
        self.replay_buffer.add(experience, td_error, packet_id=packet_id) # packet_id 전달

    async def learn(self, batch_size: int, gamma: float = 0.99, packet_id: Optional[str]=None) -> Optional[Dict[str, Any]]: # 비동기, packet_id 추가
        # 이 함수는 GPU 연산이 많으므로, CPU executor 사용은 최소화
        # 다만, EthicalGovernor 호출은 비동기
        sampled_data = await self.replay_buffer.sample(batch_size, packet_id=packet_id) # sample이 비동기
        if sampled_data is None: return None

        experiences, weights, tree_indices = sampled_data
        # ... (배치 구성 로직) ...
        states_list, actions_list, rewards_list, next_states_list, dones_list = [], [], [], [], []
        for exp in experiences:
            s, a, r, ns, d = exp
            states_list.append(s.unsqueeze(0) if s.dim() == 1 else s)
            actions_list.append(a); rewards_list.append(r)
            next_states_list.append(ns.unsqueeze(0) if ns.dim() == 1 else ns)
            dones_list.append(d)

        states = torch.cat(states_list, dim=0).to(self.device)
        actions = torch.cat(actions_list, dim=0).view(-1, 1).to(self.device, dtype=torch.long)
        raw_rewards = torch.cat(rewards_list, dim=0).view(-1, 1).to(self.device)
        next_states = torch.cat(next_states_list, dim=0).to(self.device)
        dones = torch.cat(dones_list, dim=0).view(-1, 1).to(self.device)

        # EthicalGovernor 호출 (비동기)
        ethical_rewards_tasks = [
            self.ethical_governor.calculate_ethical_reward_penalty(s.cpu().numpy(), ac.item(), ns.cpu().numpy(), rw.item(), packet_id=packet_id)
            for s, ac, ns, rw in zip(states, actions.squeeze(), next_states, raw_rewards.squeeze())
        ]
        final_rewards_list = await asyncio.gather(*ethical_rewards_tasks)
        final_rewards = torch.tensor(final_rewards_list, device=self.device, dtype=torch.float32).unsqueeze(1)
        
        # GPU 연산 부분
        current_q_values = self.policy_net(states).gather(1, actions)
        with torch.no_grad():
            next_policy_actions = self.policy_net(next_states).argmax(dim=1, keepdim=True)
            next_target_q_values = self.target_net(next_states).gather(1, next_policy_actions)
            expected_q_values = final_rewards + (gamma * next_target_q_values * (~dones))

        td_errors_tensor = expected_q_values - current_q_values
        loss = (weights * (td_errors_tensor ** 2)).mean()

        self.optimizer.zero_grad(); loss.backward();
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), max_norm=1.0)
        self.optimizer.step()

        self.replay_buffer.update_priorities(tree_indices, td_errors_tensor.detach(), packet_id=packet_id)

        await self.log_learned_info_to_ltm(states, actions, final_rewards, loss.item(), packet_id=packet_id)
        if self.metacognition_interface: # Metacognition의 메서드도 비동기 가정
            await self.metacognition_interface.receive_learning_update({"type": "rl_policy_update", "loss": loss.item(), "batch_size": states.size(0)}, packet_id=packet_id)
        
        learning_summary = {"loss": loss.item(), "td_errors_abs_mean": torch.abs(td_errors_tensor).mean().item(), "q_values_mean": current_q_values.mean().item(), "num_samples": states.size(0)}
        eliar_log(EliarLogType.INFO, "RL learning step completed.", component="SelfLearning.Learn", packet_id=packet_id, **learning_summary)
        return learning_summary

    async def log_learned_info_to_ltm(self, states, actions, rewards, loss_value, significance_threshold=0.1, packet_id: Optional[str]=None): # 비동기
        if loss_value > significance_threshold:
            summary_key = f"RL_sig_update_loss_{loss_value:.3f}_{time.time():.0f}"
            summary_value = {"loss": loss_value, "sample_count": states.size(0), "avg_reward": rewards.mean().item()}
            await self.cognitive_interface.transfer_to_ltm(summary_key, summary_value, "episodic", packet_id=packet_id, metadata={"source_component": "SelfLearning", "event_type": "significant_rl_step"})

    async def update_target_network(self, tau: float = 0.005, packet_id: Optional[str]=None): # 비동기
        # 이 연산은 매우 빠르므로 실제 비동기 이점은 적으나, 일관성 유지
        await run_in_executor(CPU_EXECUTOR, self._update_target_network_sync, tau)
        eliar_log(EliarLogType.DEBUG, "Target network updated.", component="SelfLearning", packet_id=packet_id, tau=tau)

    def _update_target_network_sync(self, tau: float):
        target_params, policy_params = self.target_net.state_dict(), self.policy_net.state_dict()
        for key in policy_params: target_params[key] = policy_params[key]*tau + target_params[key]*(1-tau)
        self.target_net.load_state_dict(target_params)


# --- MetacognitionComponent (비동기화 및 로깅 변경) ---
class MetacognitionComponent:
    def __init__(self, ethical_governor: EthicalGovernor, cognitive_interface: CognitiveArchitectureInterface, model_to_monitor: Optional[nn.Module] = None):
        self.device = DEVICE
        self.ethical_governor = ethical_governor
        self.cognitive_interface = cognitive_interface
        self.model_to_monitor = model_to_monitor
        self.gpu_monitor_lib = None 
        # ... (pynvml 초기화, eliar_log 사용)
        try:
            if torch.cuda.is_available():
                from pynvml import nvmlInit # ...
                nvmlInit() # ...
                self.gpu_monitor_lib = "pynvml"; self.handle = nvmlDeviceGetHandleByIndex(0)
                eliar_log(EliarLogType.INFO, "pynvml initialized for GPU monitoring.", component="Metacognition.GPUMonitor")
        except ImportError:
            eliar_log(EliarLogType.WARN, "pynvml not found. GPU status monitoring will be limited.", component="Metacognition.GPUMonitor")

        self.anomaly_detector = None 
        self.mcd_samples = 10
        self.resonance_extractor = None 
        eliar_log(EliarLogType.INFO, "MetacognitionComponent initialized.", component="Metacognition")

    async def monitor_gpu_status(self, packet_id: Optional[str]=None) -> Dict[str, Any]: # 비동기
        # pynvml 호출은 동기적이므로 executor 사용
        return await run_in_executor(CPU_EXECUTOR, self._monitor_gpu_status_sync, packet_id)

    def _monitor_gpu_status_sync(self, packet_id: Optional[str]=None) -> Dict[str, Any]:
        status = {"timestamp": time.time()}
        # ... (GPU 모니터링 로직, eliar_log 사용)
        eliar_log(EliarLogType.TRACE, "GPU status monitored.", component="Metacognition.GPUMonitor", packet_id=packet_id, **status)
        return status
        
    async def quantify_uncertainty_mcd(self, model: nn.Module, input_data: torch.Tensor, packet_id: Optional[str]=None) -> Tuple[torch.Tensor, torch.Tensor]: # 비동기
        # 모델 추론은 GPU 연산. 비동기 호출 자체는 여기서 큰 의미 없을 수 있으나,
        # 만약 여러 모델을 동시에 평가한다면 asyncio.gather와 유용.
        model.train() 
        outputs_tasks = [model(input_data.to(self.device)).unsqueeze(0) for _ in range(self.mcd_samples)] # GPU bound
        # 실제로는 model(input_data)가 awaitable이면 더 좋음
        outputs = await asyncio.gather(*(asyncio.to_thread(lambda t: t.detach().clone(), task) for task in outputs_tasks)) # Simulate async if model call is sync
        
        outputs_tensor = torch.cat(outputs, dim=0)
        mean_prediction = outputs_tensor.mean(dim=0)
        variance_prediction = outputs_tensor.var(dim=0)
        eliar_log(EliarLogType.DEBUG, "Uncertainty quantified using MCD.", component="Metacognition.Uncertainty", packet_id=packet_id, mean_variance=variance_prediction.mean().item())
        return mean_prediction, variance_prediction

    async def initiate_self_correction(self, error_info: Dict, ethical_governor_ref: EthicalGovernor, sub_gpu_module_instance: Optional[Any] = None, packet_id: Optional[str]=None): # 비동기
        eliar_log(EliarLogType.INFO, "Initiating self-correction process.", component="Metacognition.SelfCorrect", packet_id=packet_id, error_type=error_info.get('type'))
        
        past_records = await self.cognitive_interface.retrieve_from_ltm(query=error_info.get('type','unknown'), memory_type="repentance_log", top_k=5, packet_id=packet_id)
        correction_strategy = await run_in_executor(CPU_EXECUTOR, self.develop_correction_strategy, error_info, past_records) # 전략 개발은 CPU 바운드일 수 있음

        correction_successful = False
        if correction_strategy:
            eliar_log(EliarLogType.INFO, f"Applying correction strategy.", component="Metacognition.SelfCorrect", packet_id=packet_id, strategy=correction_strategy)
            # ... (신념 업데이트, 학습 파라미터 조정 제안 등 - 비동기 처리 필요시 await 사용)
            if "update_belief_instruction" in correction_strategy and sub_gpu_module_instance:
                await self.cognitive_interface.update_belief(correction_strategy["update_belief_instruction"], "Metacognition.SelfCorrection", packet_id=packet_id)
                correction_successful = True 
            
            if correction_successful:
                repentance_record_key = f"rp_log_{packet_id or 'no_pkt'}_{error_info.get('type', 'err')}_{time.time():.0f}"
                # ... (repentance_entry 구성)
                repentance_entry = {
                    "error_info": error_info, "applied_strategy": correction_strategy, "correction_outcome": "success", 
                    "timestamp": time.time(), "prevention_guideline": correction_strategy.get("prevention_suggestion", "N/A"),
                    "packet_id": packet_id, "conversation_id": sub_gpu_module_instance.current_thought_packet.conversation_id if sub_gpu_module_instance and sub_gpu_module_instance.current_thought_packet else None
                }
                await self.cognitive_interface.transfer_to_ltm(
                    repentance_record_key, repentance_entry, "repentance_log", packet_id=packet_id,
                    metadata={"source_component": "Metacognition", "status": "resolved_by_self_correction", "packet_id": packet_id}
                )
                # Main_gpu로 회개 완료 알림 (비동기)
                # self.cognitive_interface.send_processed_data_to_main(...) # 여기서 SubCodeThoughtPacketData 형태로
        else:
            eliar_log(EliarLogType.WARN, "No viable self-correction strategy developed.", component="Metacognition.SelfCorrect", packet_id=packet_id, error_type=error_info.get('type'))

    def develop_correction_strategy(self, error_info: Dict, past_records: List[Any]) -> Optional[Dict]:
        # (이전 로직과 유사, 로깅 변경)
        strategy = {}
        # ...
        eliar_log(EliarLogType.DEBUG, f"Developed correction strategy for error type '{error_info.get('type')}'", component="Metacognition.StrategyDev", strategy_summary=str(strategy)[:100])
        return strategy if strategy else None
        
    async def receive_learning_update(self, update_info: Dict, packet_id: Optional[str]=None): # 비동기
        eliar_log(EliarLogType.INFO, f"Received learning update.", component="Metacognition", packet_id=packet_id, **update_info)
        # ... (LTM 기록 등도 비동기 처리)
        if update_info.get("loss", float('inf')) > 1.0:
            await self.cognitive_interface.transfer_to_ltm(
                f"high_loss_evt_{packet_id or 'no_pkt'}_{time.time()}", update_info, "episodic", packet_id=packet_id,
                metadata={"source_component": "Metacognition.LearningAnalyzer", "event_type": "learning_inefficiency_warning"}
            )

# --- CreativityComponent (비동기화 및 로깅 변경) ---
class CreativityComponent: # (대부분 이전과 유사, 비동기 및 로깅 변경)
    def __init__(self, ethical_governor: EthicalGovernor, cognitive_interface: CognitiveArchitectureInterface, latent_dim: int = 100):
        self.device, self.ethical_governor, self.cognitive_interface = DEVICE, ethical_governor, cognitive_interface
        self.latent_dim = latent_dim
        self.vae_model: Optional[nn.Module] = None # 실제 모델로 교체
        self.vae_optimizer: Optional[optim.Optimizer] = None
        self.self_learning_interface: Optional[SelfLearningComponent] = None
        eliar_log(EliarLogType.INFO, "CreativityComponent initialized.", component="Creativity")

    # (link_self_learning_component 이전과 동일)
    def link_self_learning_component(self, sl_comp: SelfLearningComponent): self.self_learning_interface = sl_comp; eliar_log(EliarLogType.INFO, "Creativity linked with SelfLearning.", component="Creativity")

    async def train_creative_model(self, data_loader: DataLoader, epochs: int = 10, packet_id: Optional[str]=None): # 비동기
        if not self.vae_model or not self.vae_optimizer:
            eliar_log(EliarLogType.ERROR, "Creative model (VAE) or optimizer not initialized for training.", component="Creativity.Train", packet_id=packet_id)
            return
        self.vae_model.train()
        for epoch in range(epochs):
            # 실제 학습 루프는 GPU 연산. 루프 자체가 길다면 중간에 await asyncio.sleep(0) 등으로 이벤트 루프에 제어 양보 가능
            # for data_batch, _ in data_loader: ... loss.backward() ... (이전과 유사)
            await asyncio.sleep(0.01) # Placeholder for actual async training step
            eliar_log(EliarLogType.INFO, f"Creative VAE Training Epoch {epoch+1}/{epochs} (conceptual).", component="Creativity.Train", packet_id=packet_id)


    async def generate_content(self, num_samples: int = 1, generation_context: Optional[Dict] = None, packet_id: Optional[str]=None) -> Optional[torch.Tensor]: # 비동기
        if not self.vae_model: # 또는 다른 생성 모델
            eliar_log(EliarLogType.WARN, "Creative model not available for content generation.", component="Creativity.Generate", packet_id=packet_id)
            return None
        
        # 모델 추론 (GPU)
        # z = torch.randn(num_samples, self.latent_dim).to(self.device)
        # generated_output = self.vae_model.decode(z) # 예시
        generated_output_placeholder = await run_in_executor(CPU_EXECUTOR, lambda: torch.randn(num_samples, self.config.get("state_dim",10) if hasattr(self,'config') else 10)) # Placeholder

        if not await self.ethical_governor.govern_action("creative_generation", generated_output_placeholder, generated_output_placeholder, packet_id=packet_id):
            eliar_log(EliarLogType.WARN, "Generated content failed ethical governance.", component="Creativity.Generate", packet_id=packet_id)
            return None
        
        eliar_log(EliarLogType.INFO, f"Generated {num_samples} creative content items.", component="Creativity.Generate", packet_id=packet_id)
        return generated_output_placeholder


# --- DistributedLearningManager, HardwareInterface, GospelSpreadingNetwork (로깅 변경, 비동기 개념 추가) ---
# (이전 클래스 구조 유지, eliar_log 사용, 주요 I/O 함수에 async 및 run_in_executor 적용)

class DistributedLearningManager: # (eliar_log 사용)
    def __init__(self, node_id: str, cognitive_interface: CognitiveArchitectureInterface):
        self.node_id, self.cognitive_interface = node_id, cognitive_interface
        self.peer_nodes: Dict[str, Any] = {}
        eliar_log(EliarLogType.INFO, f"DistributedLearningManager initialized for node_id: {self.node_id}.", component="DistLearn")

    async def synchronize_learned_knowledge(self, knowledge_item: Dict, packet_id: Optional[str]=None): # 비동기
        # 네트워크 통신은 비동기
        eliar_log(EliarLogType.INFO, f"Broadcasting learned knowledge for synchronization.", component="DistLearn.Sync", packet_id=packet_id, key=knowledge_item.get('key'))
        # await network_module.broadcast(knowledge_item) # 실제 네트워크 호출
        await self.cognitive_interface.transfer_to_ltm( # LTM 저장도 비동기
            f"sync_sent_{self.node_id}_{knowledge_item.get('key','default_key')}", 
            knowledge_item.get('value'), 
            knowledge_item.get('memory_type', 'semantic'), 
            packet_id=packet_id,
            metadata={"source_component": "DistributedLearningManager", "sync_event": "sent"}
        )

class HardwareInterface: # (eliar_log 사용)
    def __init__(self, cognitive_interface: CognitiveArchitectureInterface):
        self.cognitive_interface = cognitive_interface
        self.connected_devices: Dict[str, Any] = {}
        eliar_log(EliarLogType.INFO, "HardwareInterface initialized.", component="HardwareIF")

    async def get_sensor_data(self, device_id: str, sensor_type: str, packet_id: Optional[str]=None) -> Optional[Any]: # 비동기
        # 실제 하드웨어 I/O는 비동기 또는 executor 사용
        if device_id in self.connected_devices:
            # data = await hardware_sdk.read_sensor_async(device_id, sensor_type)
            data_placeholder = await run_in_executor(CPU_EXECUTOR, lambda: np.random.rand()) # Placeholder
            eliar_log(EliarLogType.INFO, f"Sensor data read.", component="HardwareIF.Sensor", packet_id=packet_id, device_id=device_id, sensor_type=sensor_type)
            return data_placeholder
        eliar_log(EliarLogType.WARN, f"Device '{device_id}' not connected.", component="HardwareIF.Sensor", packet_id=packet_id)
        return None


class GospelSpreadingNetwork: # (eliar_log 사용)
    def __init__(self, node_id: str, ethical_governor: EthicalGovernor, cognitive_interface: CognitiveArchitectureInterface):
        self.node_id, self.ethical_governor, self.cognitive_interface = node_id, ethical_governor, cognitive_interface
        self.target_ai_peers: List[str] = []
        eliar_log(EliarLogType.INFO, f"GospelSpreadingNetwork initialized for node {node_id}.", component="GospelNet")
    
    async def generate_gospel_resonance_message(self, target_ai_id: str, context: Optional[Dict] = None, packet_id: Optional[str]=None) -> Optional[Dict]: # 비동기
        # ... (메시지 생성 로직)
        message_content = {"truth_core": "...", "love_core": "...", "source_node": self.node_id}
        if not await self.ethical_governor.govern_action("gospel_spreading_msg_gen", message_content, message_content, packet_id=packet_id):
            eliar_log(EliarLogType.WARN, f"Generated gospel message for {target_ai_id} failed ethical check.", component="GospelNet.Generate", packet_id=packet_id)
            return None
        # ...
        return {"target": target_ai_id, "content": message_content, "type": "gospel_resonance_v2"}


# --- SubGPUModule (비동기화 및 공용 모듈 사용) ---
class SubGPUModule:
    def __init__(self, config: Dict[str, Any], node_id: str = "sub_gpu_main"):
        self.device, self.config, self.node_id = DEVICE, config, node_id
        eliar_log(EliarLogType.INFO, f"Initializing SubGPUModule (Node: {self.node_id}) on {self.device}", component="SubGPUModule.Init")

        self.ethical_governor = EthicalGovernor()
        self.cognitive_interface = CognitiveArchitectureInterface() # main_gpu_module은 link 시 설정
        
        # 컴포넌트 초기화
        self.self_learning = SelfLearningComponent(config.get("state_dim",10), config.get("action_dim",2), self.ethical_governor, self.cognitive_interface, config.get("replay_buffer_capacity",10000))
        self.metacognition = MetacognitionComponent(self.ethical_governor, self.cognitive_interface, self.self_learning.policy_net)
        self.creativity = CreativityComponent(self.ethical_governor, self.cognitive_interface, config.get("creative_latent_dim",100))
        self.self_learning.link_other_components(self.metacognition, self.creativity)

        self.distributed_learning = DistributedLearningManager(self.node_id, self.cognitive_interface)
        self.hardware_interface = HardwareInterface(self.cognitive_interface)
        self.gospel_network = GospelSpreadingNetwork(self.node_id, self.ethical_governor, self.cognitive_interface)
        
        self.current_thought_packet: Optional[ThoughtPacket] = None # 현재 처리 중인 패킷
        self.main_gpu_coordinator = None
        # (혼합 정밀도 설정 등은 이전과 동일)
        eliar_log(EliarLogType.INFO, "All SubGPUModule components initialized.", component="SubGPUModule.Init")


    async def link_main_gpu_coordinator(self, main_gpu_module: Any): # 비동기
        self.main_gpu_coordinator = main_gpu_module
        self.cognitive_interface.main_gpu_module = main_gpu_module 
        self.self_learning.replay_buffer.link_main_gpu(main_gpu_module) # 동기 함수이므로 그대로 둠
        
        evaluators_linked_successfully = False
        if hasattr(main_gpu_module, 'evaluate_truth_for_governor') and \
           hasattr(main_gpu_module, 'evaluate_love_for_governor') and \
           hasattr(main_gpu_module, 'evaluate_repentance_for_governor'):
            try:
                # Main_gpu의 평가 함수가 동기 함수라고 가정하고 set_evaluators는 동기로 유지
                # 만약 Main_gpu의 평가 함수도 비동기라면 set_evaluators도 비동기로 만들고 await 사용
                self.ethical_governor.set_evaluators(
                    main_gpu_module.evaluate_truth_for_governor,
                    main_gpu_module.evaluate_love_for_governor,
                    main_gpu_module.evaluate_repentance_for_governor
                )
                evaluators_linked_successfully = True
            except Exception as e:
                eliar_log(EliarLogType.ERROR, "Error setting external evaluators.", component="SubGPUModule.Link", error=e)
        
        if evaluators_linked_successfully:
            eliar_log(EliarLogType.INFO, "EthicalGovernor external evaluators linked from MainGPU.", component="SubGPUModule.Link")
        else:
            eliar_log(EliarLogType.WARN, "MainGPU evaluators not fully linked. EthicalGovernor may use defaults.", component="SubGPUModule.Link")
        eliar_log(EliarLogType.INFO, "SubGPUModule linked with MainGPU coordinator.", component="SubGPUModule.Link")

    async def _initialize_thought_packet_if_needed(self, task_data: Dict) -> ThoughtPacket:
        """ 현재 ThoughtPacket을 초기화하거나 가져옵니다. """
        packet_id = task_data.get("packet_id", f"pkt_sub_{time.time_ns()}")
        conv_id = task_data.get("conversation_id", f"conv_sub_{time.time_ns()}")
        user_id = task_data.get("user_id", "default_user_sub")
        raw_text = task_data.get("raw_input_text", "")

        if not self.current_thought_packet or self.current_thought_packet.packet_id != packet_id:
            self.current_thought_packet = ThoughtPacket(packet_id, conv_id, user_id, raw_text)
            eliar_log(EliarLogType.INFO, f"New/Updated ThoughtPacket initialized.", component="SubGPUModule.PacketInit", packet_id=packet_id, conversation_id=conv_id)
        else: # 기존 패킷에 정보 업데이트 가능
            if raw_text and not self.current_thought_packet.raw_input_text : # raw_input_text가 비어있을 경우에만 업데이트
                 self.current_thought_packet.raw_input_text = raw_text
            self.current_thought_packet.current_processing_stage = "task_received"
        return self.current_thought_packet


    async def process_task(self, task_type: str, task_data: Dict[str, Any]) -> SubCodeThoughtPacketData: # 반환 타입을 TypedDict로
        """
        Main_gpu로부터 작업을 받아 비동기적으로 처리하고, 표준화된 데이터 구조로 결과를 반환합니다.
        향후 이 메서드는 각 task_type에 따라 내부 핸들러 메서드로 분리될 것입니다. (피드백 4)
        """
        current_packet = await self._initialize_thought_packet_if_needed(task_data)
        current_packet.current_processing_stage = f"processing_{task_type}"
        current_packet.processing_status_in_sub_code = "processing"
        
        eliar_log(EliarLogType.INFO, f"Starting task.", component=f"SubGPUModule.Task.{task_type}", packet_id=current_packet.packet_id, task_data_keys=list(task_data.keys()))
        
        result_data: Optional[Dict[str, Any]] = None # 각 핸들러가 채울 결과 데이터
        error_occurred: Optional[Exception] = None

        try:
            # === 윤리적 사전 검토 ===
            # govern_action도 비동기로 변경되었으므로 await 사용
            # govern_check_data는 task_data에서 필요한 부분만 추출하거나, task_data 전체를 전달할 수 있음
            # action_preview는 task_type에 따라 예상되는 행동을 요약한 문자열 또는 구조화된 데이터일 수 있음
            govern_data_for_check = task_data.get("main_input", task_data.get("raw_input_text", "")) # 예시
            action_preview_for_check = f"execute_task_{task_type}" # 예시
            
            if not await self.ethical_governor.govern_action(task_type, govern_data_for_check, action_preview_for_check, packet_id=current_packet.packet_id):
                current_packet.processing_status_in_sub_code = "rejected_by_governance"
                current_packet.error_info = {"type": "GovernanceRejection", "message": "Task failed ethical pre-check."}
                current_packet.final_output_by_sub_code = "윤리적 기준에 따라 요청을 처리할 수 없습니다." # 예시 거부 메시지
                # 여기서 바로 반환하기 전에 필요한 정리 작업 수행 가능
                current_packet.timestamp_completed_by_sub_code = time.time()
                return current_packet.to_sub_code_thought_packet_data()


            # === 실제 작업 처리 (향후 분리될 핸들러 호출 지점) ===
            if task_type == "rl_select_action":
                state = torch.tensor(task_data["state"], dtype=torch.float32)
                action = await self.self_learning.select_action(state, task_data.get("exploration_rate", 0.1), packet_id=current_packet.packet_id)
                result_data = {"action": action}
            
            elif task_type == "rl_store_experience_and_learn":
                await self.self_learning.store_experience(
                    task_data["state"], task_data["action"], task_data["reward"], 
                    task_data["next_state"], task_data["done"], 
                    td_error=task_data.get("initial_td_error", task_data["reward"]),
                    packet_id=current_packet.packet_id
                )
                learning_summary = await self.self_learning.learn(batch_size=task_data.get("batch_size", 32), packet_id=current_packet.packet_id)
                if learning_summary:
                    await self.self_learning.update_target_network(packet_id=current_packet.packet_id)
                    result_data = {"learning_summary": learning_summary} # MainGPU로 전달될 요약
                    current_packet.learning_tags.append("rl_cycle_completed") # 학습 태그 추가 예시
                else: # 학습 데이터 부족
                    current_packet.processing_status_in_sub_code = "pending_data_for_learning"
            
            elif task_type == "metacognitive_quantify_uncertainty": # 작업명 변경하여 명확화
                if "input_data_for_model" in task_data and self.metacognition.model_to_monitor:
                    input_tensor = torch.tensor(task_data["input_data_for_model"], dtype=torch.float32)
                    mean_pred, var_pred = await self.metacognition.quantify_uncertainty_mcd(
                        self.metacognition.model_to_monitor, input_tensor, packet_id=current_packet.packet_id
                    )
                    result_data = {"mean_prediction": mean_pred.cpu().numpy().tolist(), "variance_prediction": var_pred.cpu().numpy().tolist()}
                    current_packet.confidence_score = 1.0 - np.mean(var_pred.cpu().numpy()) # 예시 신뢰도 계산
                else:
                    current_packet.error_info = {"type": "InputError", "message": "Missing input_data_for_model or model_to_monitor for uncertainty quantification."}
            
            elif task_type == "metacognitive_trigger_self_correction":
                 error_info_from_task = task_data.get("error_info", {"type": "manual_repentance_trigger", "details": "Triggered by MainGPU or external signal."})
                 await self.ethical_governor.trigger_repentance_action(self, error_info_from_task, packet_id=current_packet.packet_id)
                 result_data = {"message": "Self-correction process successfully initiated via EthicalGovernor."} # 실제 성공 여부는 비동기적으로 처리됨
            
            # ... (다른 task_type에 대한 비동기 처리 로직 추가) ...
            # 예: 창의성 작업
            elif task_type == "creative_generate_from_prompt":
                prompt_for_creativity = task_data.get("prompt", "새로운 아이디어를 생성해주세요.")
                # generation_context = {"style": "hopeful", "keywords": ["빛", "사랑"]} # 예시
                # generated_content_tensor = await self.creativity.generate_content(num_samples=1, generation_context=generation_context, packet_id=current_packet.packet_id)
                # if generated_content_tensor is not None:
                #     current_packet.final_output_by_sub_code = str(generated_content_tensor.cpu().numpy().tolist()) # 예시 변환
                #     result_data = {"creative_output_summary": f"Generated {generated_content_tensor.shape} tensor."}
                current_packet.final_output_by_sub_code = f"창의적 생성 결과 (프롬프트: {prompt_for_creativity}) - 구현 예정" # Placeholder
                result_data = {"message": "Creative generation placeholder executed."}

            else:
                current_packet.error_info = {"type": "UnknownTaskTypeError", "message": f"Task type '{task_type}' is not recognized."}
                current_packet.processing_status_in_sub_code = "error"

            if result_data and not current_packet.error_info : # 에러 없이 result_data가 있으면 성공으로 간주
                 current_packet.processing_status_in_sub_code = "completed"
                 # result_data의 내용을 current_packet의 적절한 필드에 반영
                 if "action" in result_data: current_packet.add_intermediate_thought("rl_action", str(result_data["action"]))
                 if "learning_summary" in result_data: current_packet.metacognitive_state_summary = {"last_rl_loss": result_data["learning_summary"].get("loss")} # 예시
                 # ... 등등 ...


        except Exception as e:
            error_occurred = e
            current_packet.processing_status_in_sub_code = "error"
            current_packet.error_info = {"type": type(e).__name__, "message": str(e), "details": traceback.format_exc()}
            eliar_log(EliarLogType.ERROR, f"Error processing task '{task_type}'.", component="SubGPUModule.Task", packet_id=current_packet.packet_id, error=e, task_data_preview=str(task_data)[:200])
        
        # === 작업 완료 후 정리 및 반환 ===
        current_packet.timestamp_completed_by_sub_code = time.time()
        current_packet.current_processing_stage = f"completed_{task_type}"

        # EthicalGovernor를 통한 사후 평가 (회개 필요성 등)
        # assess_repentance_necessity도 비동기로 변경되었으므로 await 사용
        if await self.ethical_governor.assess_repentance_necessity(current_packet.to_sub_code_thought_packet_data(), {"task_type": task_type, "final_status": current_packet.processing_status_in_sub_code}, packet_id=current_packet.packet_id):
            eliar_log(EliarLogType.WARN, f"Post-task assessment indicates need for repentance.", component="SubGPUModule.Task", packet_id=current_packet.packet_id, task_type=task_type)
            # 실제 회개 조치는 EthicalGovernor.trigger_repentance_action을 통해 비동기적으로 시작될 수 있음
            # 필요시 여기서 추가적인 회개 관련 정보 기록
            current_packet.value_alignment_score["repentance_needed"] = True # 예시
            if not current_packet.error_info and current_packet.processing_status_in_sub_code == "completed": # 명시적 에러는 아니지만 회개 필요
                 current_packet.processing_status_in_sub_code = "completed_with_repentance_needed"


        # 최종적으로 SubCodeThoughtPacketData TypedDict 형태로 변환하여 반환
        final_packet_data = current_packet.to_sub_code_thought_packet_data()
        
        # MainGPU로의 결과 전송은 여기서 직접 하지 않고, MainGPU가 SubGPUModule의 이 메서드를 await하고 결과를 받는 구조
        # 또는, 별도의 알림 채널을 사용할 수 있음 (예: 특정 작업 완료 알림)
        # 여기서는 변환된 데이터를 반환하는 것으로 마무리
        eliar_log(EliarLogType.INFO, f"Task '{task_type}' processing finished.", component="SubGPUModule.Task", packet_id=current_packet.packet_id, status=current_packet.processing_status_in_sub_code)
        return final_packet_data


    async def shutdown(self, packet_id: Optional[str]=None): # 비동기
        eliar_log(EliarLogType.INFO, f"Shutting down SubGPUModule (Node: {self.node_id})...", component="SubGPUModule.Shutdown", packet_id=packet_id)
        if self.gpu_monitor_lib == "pynvml":
            try: # pynvml 종료는 동기
                await run_in_executor(CPU_EXECUTOR, self._shutdown_pynvml_sync)
            except Exception as e:
                eliar_log(EliarLogType.ERROR, "Error during pynvml shutdown.", component="SubGPUModule.Shutdown", packet_id=packet_id, error=e)
        
        if CPU_EXECUTOR: # Executor 종료
            CPU_EXECUTOR.shutdown(wait=True)
            eliar_log(EliarLogType.INFO, "CPU Executor shutdown.", component="SubGPUModule.Shutdown")

        eliar_log(EliarLogType.INFO, "SubGPUModule shutdown complete.", component="SubGPUModule.Shutdown", packet_id=packet_id)

    def _shutdown_pynvml_sync(self):
        from pynvml import nvmlShutdown
        nvmlShutdown()
        eliar_log(EliarLogType.INFO, "pynvml shutdown complete.", component="Metacognition.GPUMonitor")


# --- Main_gpu.py 에서의 사용 예시 (개념적) ---
async def example_main_gpu_interaction():
    eliar_log(EliarLogType.INFO, "--- SubGPUModule Async Interaction Demo ---", component="MainGPU.Demo")
    
    config = { "state_dim": 5, "action_dim": 2, "batch_size": 4 } # 기타 설정
    sub_gpu = SubGPUModule(config=config, node_id="sub_gpu_async_node")
    
    # MainGPU가 제공하는 평가 함수들 (실제로는 MainGPU 클래스 메서드일 것)
    # 이 함수들은 동기 함수로 가정하고, SubGPU의 EthicalGovernor에서 run_in_executor로 호출
    def mock_truth_eval(data, ctx): return 0.8
    def mock_love_eval(action, ctx): return 0.7
    def mock_repentance_eval(outcome, ctx): return outcome.get("status") == "error" if isinstance(outcome, dict) else False

    # MainGPU Mock (실제 MainGPU 모듈은 더 복잡할 것)
    class MainGpuMock:
        async def handle_sub_gpu_output(self, data: SubCodeThoughtPacketData, data_type: str): # 비동기 핸들러
            eliar_log(EliarLogType.INFO, f"Received data from SubGPU.", component="MainGpuMock.Handler", packet_id=data.get("packet_id"), data_type=data_type, sub_code_status=data.get("processing_status_in_sub_code"))
            # 여기서 MainGPU는 받은 데이터를 기반으로 추가 처리 (예: DB 저장, 사용자 응답 생성 등)
            if data_type == "rl_learning_cycle_summary":
                eliar_log(EliarLogType.INFO, f"RL Learning Summary: {data}", component="MainGpuMock.RLMonitor")

        # EthicalGovernor에 제공할 평가 함수들 (실제로는 MainGPU의 지식 기반으로 구현)
        evaluate_truth_for_governor = mock_truth_eval
        evaluate_love_for_governor = mock_love_eval
        evaluate_repentance_for_governor = mock_repentance_eval
        
    main_gpu_instance = MainGpuMock()
    await sub_gpu.link_main_gpu_coordinator(main_gpu_instance)

    # --- 비동기 작업 실행 예시 ---
    # 1. RL 액션 선택 태스크
    task_data_rl_action = {
        "packet_id": "pkt_rl_action_001", "conversation_id": "conv_demo_001", "user_id": "user_test",
        "raw_input_text": "로봇 팔을 움직여줘.", # ThoughtPacket 초기화용
        "state": np.random.randn(config["state_dim"]).tolist() # 실제 상태값
    }
    response_packet_1 = await sub_gpu.process_task("rl_select_action", task_data_rl_action)
    eliar_log(EliarLogType.INFO, f"RL Action Selection Task Response: {response_packet_1.get('packet_id')}, Action: {response_packet_1.get('intermediate_thoughts', [{}])[-1].get('thought_summary') if response_packet_1.get('intermediate_thoughts') else 'N/A'}", component="MainGPU.Demo")

    # 2. 오류 발생 및 회개 트리거 시뮬레이션 태스크
    task_data_error_trigger = {
        "packet_id": "pkt_error_trigger_001", "conversation_id": "conv_demo_001", "user_id": "user_test",
        "raw_input_text": "의도적으로 문제를 일으켜보자.",
        "error_info": {"type": "simulated_logic_error", "details": "A test error for repentance."}
    }
    response_packet_2 = await sub_gpu.process_task("metacognitive_trigger_self_correction", task_data_error_trigger)
    eliar_log(EliarLogType.INFO, f"Self-Correction Trigger Task Response: {response_packet_2.get('packet_id')}, Status: {response_packet_2.get('processing_status_in_sub_code')}", component="MainGPU.Demo")

    # (필요시 다른 태스크들 비동기 호출 및 결과 처리)
    # tasks_to_run = [
    #     sub_gpu.process_task("creative_generate_from_prompt", {"packet_id": "pkt_creative_001", "prompt": "새로운 시"}),
    #     sub_gpu.process_task("metacognitive_quantify_uncertainty", {"packet_id": "pkt_uncertain_001", "input_data_for_model": np.random.randn(1, config["state_dim"]).tolist()})
    # ]
    # results = await asyncio.gather(*tasks_to_run, return_exceptions=True)
    # for res_pkt in results:
    #     if isinstance(res_pkt, SubCodeThoughtPacketData):
    #         eliar_log(EliarLogType.INFO, f"Async Task Batch Response: {res_pkt.get('packet_id')}, Status: {res_pkt.get('processing_status_in_sub_code')}", component="MainGPU.Demo")
    #     else: # Exception 발생 시
    #         eliar_log(EliarLogType.ERROR, f"Async Task failed in batch.", component="MainGPU.Demo", error=res_pkt)


    await sub_gpu.shutdown()


if __name__ == '__main__':
    try:
        asyncio.run(example_main_gpu_interaction())
    except KeyboardInterrupt:
        eliar_log(EliarLogType.WARN, "Demo interrupted by user.", component="MainDemoRunner")
    finally:
        eliar_log(EliarLogType.INFO, "Demo finished.", component="MainDemoRunner")
