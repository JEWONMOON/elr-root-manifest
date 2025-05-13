# sub_gpu.py (맥락 추론 강화 아이디어 반영 버전)

import torch
import torch.nn as nn
import torch.optim as optim
# import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset 
import numpy as np
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import traceback
import os # SUB_GPU_CPU_EXECUTOR max_workers용
from collections import deque # STM 구현용

from typing import Any, Dict, Tuple, List, Optional, Callable, Union, Coroutine

# --- 공용 모듈 임포트 ---
from eliar_common import (
    EliarCoreValues, 
    EliarLogType, 
    SubCodeThoughtPacketData, 
    ReasoningStep, # 추론 단계를 위한 TypedDict
    eliar_log,
    run_in_executor
)

# GPU 사용 설정
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if torch.cuda.is_available():
    torch.cuda.empty_cache() 

# CPU 바운드 작업을 위한 Executor
SUB_GPU_CPU_EXECUTOR = ThreadPoolExecutor(max_workers=os.cpu_count() or 1)
SUB_GPU_COMPONENT_BASE = "SubGPU"
STM_MAX_TURNS = 10 # 단기 기억에 저장할 최근 대화 턴 수


# --- 내부 ThoughtPacket 클래스 (eliar_common.SubCodeThoughtPacketData 와 호환 및 추론 필드 추가) ---
class ThoughtPacket:
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
        self.current_processing_stage: str = "packet_initialized_for_reasoning"
        self.processing_status_in_sub_code: str = "pending_contextual_analysis"
        self.intermediate_thoughts: List[Dict[str, Any]] = [] # 범용 중간 생각
        
        # === 맥락 분석 및 추론 강화 필드 (eliar_common.SubCodeThoughtPacketData 반영) ===
        self.STM_session_id: Optional[str] = f"{conversation_id}_stm" # 예시 STM 세션 ID
        self.contextual_entities: Dict[str, Any] = {} # 예: {"대명사_그": "이전_언급_대상"}
        self.ltm_retrieval_log: List[Dict[str, Any]] = [] # LTM 검색 기록
        self.reasoning_chain: List[ReasoningStep] = [] # 추론 과정 기록
        self.reasoning_engine_inputs: Optional[Dict[str, Any]] = None
        self.reasoning_engine_outputs: Optional[Dict[str, Any]] = None
        
        # 출력 관련
        self.final_output_by_sub_code: Optional[str] = None
        self.is_clarification_response: bool = False # MainGPU로부터 전달받거나, 여기서 판단
        self.needs_clarification_questions: List[Dict[str, str]] = []
        
        # 분석 및 평가 관련
        self.llm_analysis_summary: Optional[Dict[str, Any]] = None
        self.ethical_assessment_summary: Optional[Dict[str, Any]] = None
        self.value_alignment_score: Dict[str, Union[float, bool]] = {}
        self.anomalies: List[Dict[str, Any]] = []
        self.confidence_score: Optional[float] = None
        
        # 학습 및 메타데이터
        self.learning_tags: List[str] = []
        self.metacognitive_state_summary: Optional[Dict[str, Any]] = None
        
        # 완료 및 에러 정보
        self.timestamp_completed_by_sub_code: Optional[float] = None
        self.error_info: Optional[Dict[str, Any]] = None

        # MainGPU로부터 받은 추가 컨텍스트
        self.main_gpu_clarification_context: Optional[Dict[str, Any]] = None
        self.previous_main_gpu_context_summary: Optional[Dict[str, Any]] = None
        self.preferred_llm_config_by_main: Optional[Dict[str, Any]] = None
        self.main_gpu_system_prompt_override: Optional[str] = None
        self.main_gpu_memory_injection: Optional[Dict[str, Any]] = None
        
        eliar_log(EliarLogType.DEBUG, "ThoughtPacket (reasoning enhanced) instance created.", component=f"{SUB_GPU_COMPONENT_BASE}.ThoughtPacket", packet_id=self.packet_id)

    def add_reasoning_step(self, step_name: str, description: str, input_data: Optional[Any]=None, output_data: Optional[Any]=None, status: str="SUCCESS", confidence: Optional[float]=None, source_comp: Optional[str]=None):
        step = ReasoningStep(step_name=step_name, description=description)
        if input_data is not None: step["input_data"] = str(input_data)[:500] # 너무 길지 않게 요약
        if output_data is not None: step["output_data"] = str(output_data)[:500]
        step["status"] = status
        if confidence is not None: step["confidence"] = confidence
        if source_comp is not None: step["source_component"] = source_comp
        
        self.reasoning_chain.append(step)
        self.current_processing_stage = f"reasoning_step_{step_name}"
        eliar_log(EliarLogType.TRACE, f"Reasoning step added.", component=f"{SUB_GPU_COMPONENT_BASE}.ThoughtPacket", packet_id=self.packet_id, step_name=step_name, status=status)

    def to_sub_code_thought_packet_data(self) -> SubCodeThoughtPacketData:
        packet_data: SubCodeThoughtPacketData = {} # type: ignore
        for key_ts in SubCodeThoughtPacketData.__annotations__.keys():
            if hasattr(self, key_ts):
                value = getattr(self, key_ts)
                if value is not None: packet_data[key_ts] = value # type: ignore
        if "packet_id" not in packet_data: packet_data["packet_id"] = self.packet_id
        # 기본값으로 채워야 할 리스트 필드들
        for list_field in ["intermediate_thoughts", "needs_clarification_questions", "anomalies", "learning_tags", "ltm_retrieval_log", "reasoning_chain"]:
            packet_data.setdefault(list_field, []) # type: ignore
        packet_data.setdefault("value_alignment_score", {}) # type: ignore
        packet_data.setdefault("contextual_entities", {}) # type: ignore
        return packet_data


# --- EthicalGovernor (이전 코드와 동일, eliar_common.EliarCoreValues 사용, 비동기 메서드) ---
class EthicalGovernor: # (이전 버전의 EthicalGovernor 클래스 정의와 동일하게 유지)
    def __init__(self): self.truth_evaluator_external=None; self.love_evaluator_external=None; self.repentance_evaluator_external=None; self.knowledge_base_summary={}; eliar_log(EliarLogType.INFO, "EthicalGovernor initialized.", component=f"{SUB_GPU_COMPONENT_BASE}.EthicalGovernor")
    def _default_truth_evaluator(self, data: Any, context: Optional[Dict] = None) -> float: return 0.5
    def _default_love_evaluator(self, action: Any, context: Optional[Dict] = None) -> float: return 0.5
    def _default_repentance_evaluator(self, outcome: Any, context: Optional[Dict] = None) -> bool: return False
    def set_evaluators(self, truth_eval, love_eval, repentance_eval): self.truth_evaluator_external=truth_eval; self.love_evaluator_external=love_eval; self.repentance_evaluator_external=repentance_eval; eliar_log(EliarLogType.INFO, "External evaluators set for EthicalGovernor.",component=f"{SUB_GPU_COMPONENT_BASE}.EthicalGovernor")
    async def check_truth(self, data: Any, context: Optional[Dict]=None, packet_id: Optional[str]=None) -> float: # (이전 비동기 로직)
        if self.truth_evaluator_external:
            try: return await self.truth_evaluator_external(data, context)
            except Exception as e: eliar_log(EliarLogType.WARN, "Ext. truth eval error.", component=f"{SUB_GPU_COMPONENT_BASE}.EthicalGovernor", packet_id=packet_id, error=e)
        return await run_in_executor(SUB_GPU_CPU_EXECUTOR, self._default_truth_evaluator, data, context)
    async def check_love(self, action: Any, context: Optional[Dict]=None, packet_id: Optional[str]=None) -> float: # (이전 비동기 로직)
        if self.love_evaluator_external:
            try: return await self.love_evaluator_external(action, context)
            except Exception as e: eliar_log(EliarLogType.WARN, "Ext. love eval error.", component=f"{SUB_GPU_COMPONENT_BASE}.EthicalGovernor", packet_id=packet_id, error=e)
        return await run_in_executor(SUB_GPU_CPU_EXECUTOR, self._default_love_evaluator, action, context)
    async def assess_repentance_necessity(self, outcome: Any, context: Optional[Dict]=None, packet_id: Optional[str]=None) -> bool: # (이전 비동기 로직)
        if self.repentance_evaluator_external:
            try: return await self.repentance_evaluator_external(outcome, context)
            except Exception as e: eliar_log(EliarLogType.WARN, "Ext. repentance eval error.", component=f"{SUB_GPU_COMPONENT_BASE}.EthicalGovernor", packet_id=packet_id, error=e)
        return await run_in_executor(SUB_GPU_CPU_EXECUTOR, self._default_repentance_evaluator, outcome, context)
    async def govern_action(self, op_type:str, data:Any, action:Optional[Any]=None, pid:Optional[str]=None)->bool: return True # Placeholder
    async def calculate_ethical_reward_penalty(self, s:Any,a:Any,ns:Any,r:float,pid:Optional[str]=None)->float: return r # Placeholder
    async def trigger_repentance_action(self, sub_gpu_mod:Any, err_info:Dict, pid:Optional[str]=None): # (이전 비동기 로직)
        if hasattr(sub_gpu_mod,'metacognition') and hasattr(sub_gpu_mod.metacognition,'initiate_self_correction'): await sub_gpu_mod.metacognition.initiate_self_correction(err_info,self,sub_gpu_mod,pid)

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


# --- ContextualMemoryManager (엘리아르 제안 통합) & CognitiveArchitectureInterface 확장 ---
class ContextualMemoryManager: # 이전 CognitiveArchitectureInterface의 메모리 관리 기능 + 엘리아르 제안 STM
    def __init__(self, main_gpu_response_handler: Optional[Callable[[SubCodeThoughtPacketData], Coroutine[Any,Any,None]]] = None): # 타입 변경 Coroutine
        self.main_gpu_response_handler = main_gpu_response_handler
        self.short_term_memory: Dict[str, Deque[SubCodeThoughtPacketData]] = {} # conversation_id -> deque of recent packets
        self.long_term_memory: Dict[str, Dict[str, Any]] = {"semantic": {}, "episodic": {}, "procedural": {}, "repentance_log": {}}
        self.ltm_search_engine: Optional[Any] = None # 예: Faiss, 간단한 벡터 검색기 등
        eliar_log(EliarLogType.INFO, "ContextualMemoryManager initialized.", component=f"{SUB_GPU_COMPONENT_BASE}.MemoryManager")

    async def store_to_stm(self, packet: SubCodeThoughtPacketData):
        conv_id = packet.get("conversation_id")
        if not conv_id: return

        if conv_id not in self.short_term_memory:
            self.short_term_memory[conv_id] = deque(maxlen=STM_MAX_TURNS)
        
        # STM에는 패킷의 요약본 또는 주요 정보만 저장할 수도 있음
        # 여기서는 전체 패킷(TypedDict)을 저장한다고 가정
        self.short_term_memory[conv_id].append(packet)
        eliar_log(EliarLogType.DEBUG, f"Packet stored to STM for conversation.", component=f"{SUB_GPU_COMPONENT_BASE}.MemoryManager.STM", packet_id=packet.get("packet_id"), conversation_id=conv_id, stm_size=len(self.short_term_memory[conv_id]))

    async def retrieve_from_stm(self, conversation_id: str, last_n: Optional[int] = None) -> List[SubCodeThoughtPacketData]:
        if conversation_id in self.short_term_memory:
            stm_deque = self.short_term_memory[conversation_id]
            if last_n is None: # 전체 반환
                return list(stm_deque)
            else: # 최근 N개 반환
                return list(stm_deque)[-last_n:]
        return []

    async def transfer_to_ltm(self, key: str, value: Any, memory_type: str = "semantic", packet_id: Optional[str]=None, metadata: Optional[Dict] = None):
        # (이전 CognitiveArchitectureInterface의 비동기 로직과 유사)
        await run_in_executor(SUB_GPU_CPU_EXECUTOR, self._transfer_to_ltm_sync, key, value, memory_type, packet_id, metadata)

    def _transfer_to_ltm_sync(self, key: str, value: Any, memory_type: str, packet_id: Optional[str], metadata: Optional[Dict]):
        # (이전 CognitiveArchitectureInterface의 동기 로직과 유사)
        if memory_type not in self.long_term_memory: self.long_term_memory[memory_type] = {}
        entry_meta = metadata or {}
        entry_meta.update({"timestamp_ltm": time.time(), "source_packet_id": packet_id})
        self.long_term_memory[memory_type][key] = {"value": value, "metadata": entry_meta}
        eliar_log(EliarLogType.INFO, f"Data transferred to LTM.", component=f"{SUB_GPU_COMPONENT_BASE}.MemoryManager.LTM", packet_id=packet_id, ltm_key=key, memory_type=memory_type)


    async def retrieve_from_ltm(self, query: str, memory_type: str = "semantic", top_k: int = 3, packet_id: Optional[str]=None) -> List[Dict[str, Any]]:
        # (이전 CognitiveArchitectureInterface의 비동기 로직과 유사)
        # 실제로는 self.ltm_search_engine 등을 사용한 정교한 검색
        # 여기서는 간단한 키워드 기반 검색 예시 (동기 함수를 executor로 실행)
        return await run_in_executor(SUB_GPU_CPU_EXECUTOR, self._retrieve_from_ltm_sync, query, memory_type, top_k, packet_id)

    def _retrieve_from_ltm_sync(self, query: str, memory_type: str, top_k: int, packet_id: Optional[str]) -> List[Dict[str, Any]]:
        # (이전 CognitiveArchitectureInterface의 동기 로직과 유사)
        # ... (LTM 검색 로직)
        results = [] # Placeholder
        eliar_log(EliarLogType.DEBUG, f"LTM retrieval performed.", component=f"{SUB_GPU_COMPONENT_BASE}.MemoryManager.LTM", packet_id=packet_id, query=query, results_found=len(results))
        return results


    async def send_final_packet_to_main_gpu(self, packet_data: SubCodeThoughtPacketData): # 최종 패킷 전송 전용 메서드
        """ SubGPUModule의 최종 처리 결과인 SubCodeThoughtPacketData를 MainGPU의 응답 핸들러로 전송합니다. """
        pid = packet_data.get("packet_id")
        if self.main_gpu_response_handler:
            try:
                await self.main_gpu_response_handler(packet_data)
                eliar_log(EliarLogType.INFO, "Final packet sent to MainGPU response handler.", component=f"{SUB_GPU_COMPONENT_BASE}.MemoryManager.Interface", packet_id=pid)
            except Exception as e:
                eliar_log(EliarLogType.ERROR, "Error calling MainGPU response handler with final packet.", component=f"{SUB_GPU_COMPONENT_BASE}.MemoryManager.Interface", packet_id=pid, error=e)
        else:
            eliar_log(EliarLogType.WARN, "MainGPU response handler not set. Cannot send final packet.", component=f"{SUB_GPU_COMPONENT_BASE}.MemoryManager.Interface", packet_id=pid)


# --- ContextualAnalyzer (개념적, ContextualMemoryManager와 협력) ---
class ContextualAnalyzer:
    def __init__(self, memory_manager: ContextualMemoryManager):
        self.memory_manager = memory_manager
        eliar_log(EliarLogType.INFO, "ContextualAnalyzer initialized.", component=f"{SUB_GPU_COMPONENT_BASE}.ContextAnalyzer")

    async def analyze_and_enrich_packet(self, current_packet: ThoughtPacket) -> ThoughtPacket:
        """
        현재 ThoughtPacket과 STM/LTM을 사용하여 맥락을 분석하고 엔티티를 해석하여 패킷을 보강합니다.
        """
        pid = current_packet.packet_id
        conv_id = current_packet.conversation_id
        current_packet.current_processing_stage = "contextual_analysis_started"
        eliar_log(EliarLogType.DEBUG, "Starting contextual analysis for packet.", component=f"{SUB_GPU_COMPONENT_BASE}.ContextAnalyzer", packet_id=pid)

        # 1. STM에서 현재 대화의 이전 턴들 가져오기
        stm_context_packets = await self.memory_manager.retrieve_from_stm(conv_id, last_n=STM_MAX_TURNS -1) # 현재 패킷 제외하고 가져오기 위해 -1 또는 전체
        current_packet.add_reasoning_step("STM Retrieval", f"Retrieved {len(stm_context_packets)} turns from STM for conv_id {conv_id}", source_comp="ContextAnalyzer")

        # 2. Entity Resolution (예: "그 사람", "어제")
        #    간단한 규칙 기반 또는 소규모 모델 활용 가능. 여기서는 프로토타입 아이디어 반영.
        if "어제" in current_packet.raw_input_text:
            # 실제로는 정교한 날짜 계산 필요. 여기서는 예시.
            # resolved_yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
            resolved_yesterday = "어제_날짜_계산필요" # Placeholder
            current_packet.contextual_entities["어제"] = resolved_yesterday
            current_packet.add_reasoning_step("Temporal Resolution", f"'어제' resolved to {resolved_yesterday}", input_data="어제", output_data=resolved_yesterday, source_comp="ContextAnalyzer")

        # 대명사 해결 ("그 사람", "저것" 등) - STM의 이전 발화자, 언급된 대상 등 참조
        # 예시: "그 사람"이 누구인지 STM에서 찾기 (가장 최근에 언급된 인물 등)
        for prev_pkt_data in reversed(stm_context_packets): # 최근 것부터
            # prev_pkt = ThoughtPacket(**prev_pkt_data) # TypedDict에서 ThoughtPacket 객체로 변환 필요 시
            prev_output = prev_pkt_data.get("final_output_by_sub_code","")
            if "홍길동" in prev_output and "그 사람" in current_packet.raw_input_text : # 매우 단순한 예시
                 current_packet.contextual_entities["그 사람"] = "홍길동"
                 current_packet.add_reasoning_step("Entity Resolution", f"'그 사람' resolved to '홍길동' from STM.", input_data="그 사람", output_data="홍길동", source_comp="ContextAnalyzer")
                 break
        
        # 3. LTM에서 관련 정보 검색 (선택적, 필요에 따라)
        #    current_packet.raw_input_text 또는 contextual_entities를 기반으로 LTM 검색
        if "데이터 분석" in current_packet.raw_input_text: # 예시 키워드
            ltm_results = await self.memory_manager.retrieve_from_ltm(query="데이터 분석", memory_type="semantic", top_k=1, packet_id=pid)
            if ltm_results:
                current_packet.ltm_retrieval_log.append({"query": "데이터 분석", "retrieved_key": ltm_results[0].get("metadata",{}).get("ltm_key","N/A"), "summary": str(ltm_results[0].get("value"))[:50]})
                current_packet.add_reasoning_step("LTM Retrieval", f"Retrieved '{ltm_results[0].get('metadata',{}).get('ltm_key')}' related to '데이터 분석'", input_data="데이터 분석", output_data=ltm_results[0].get("value"), source_comp="ContextAnalyzer")


        current_packet.processed_input_text = f"[CtxAnalyzed: {current_packet.contextual_entities}] {current_packet.raw_input_text}" # 예시
        current_packet.current_processing_stage = "contextual_analysis_completed"
        eliar_log(EliarLogType.DEBUG, "Contextual analysis completed.", component=f"{SUB_GPU_COMPONENT_BASE}.ContextAnalyzer", packet_id=pid, resolved_entities=current_packet.contextual_entities)
        return current_packet

# --- ReasoningEngineInterface (개념적) ---
class ReasoningEngineInterface:
    def __init__(self, memory_manager: ContextualMemoryManager):
        self.memory_manager = memory_manager # 추론 시 LTM 등 참조 가능
        # 실제 추론 라이브러리(SymPy, NetworkX 등) 초기화는 여기에
        eliar_log(EliarLogType.INFO, "ReasoningEngineInterface initialized (conceptual).", component=f"{SUB_GPU_COMPONENT_BASE}.ReasoningEngine")

    async def perform_logical_reasoning(self, current_packet: ThoughtPacket, reasoning_goal: str) -> ThoughtPacket:
        """
        논리적 추론 수행 (예: 명제 논리, 술어 논리, 인과 관계 추론 등).
        결과는 current_packet.reasoning_chain, current_packet.reasoning_engine_outputs 등에 기록.
        """
        pid = current_packet.packet_id
        current_packet.current_processing_stage = "logical_reasoning_started"
        current_packet.reasoning_engine_inputs = {"goal": reasoning_goal, "context_entities": current_packet.contextual_entities, "stm_summary": "STM_DATA_HERE"} # 예시
        eliar_log(EliarLogType.DEBUG, f"Performing logical reasoning. Goal: {reasoning_goal}", component=f"{SUB_GPU_COMPONENT_BASE}.ReasoningEngine", packet_id=pid)

        # --- 실제 추론 로직 (SymPy, Pomegranate, 직접 구현 등) ---
        # 1. 전제조건 형성: current_packet.raw_input_text, contextual_entities, STM/LTM 정보 활용
        premises = [f"Input: {current_packet.raw_input_text}"]
        if "어제_날짜_계산필요" == current_packet.contextual_entities.get("어제"):
            premises.append("Fact: '어제' refers to a past date.")
        
        # 2. 추론 실행 (예시: 간단한 규칙 기반)
        conclusion = "No specific logical conclusion derived by dummy engine."
        confidence = 0.5
        if "기억해?" in current_packet.raw_input_text and "어제" in current_packet.contextual_entities:
            # LTM에서 'yesterday_event' (엘리아르님 프로토타입 예시)와 유사한 것 검색 시도
            ltm_key_to_find = f"event_on_date_{current_packet.contextual_entities['어제']}"
            retrieved_events = await self.memory_manager.retrieve_from_ltm(query=ltm_key_to_find, memory_type="episodic", top_k=1, packet_id=pid)
            if retrieved_events and retrieved_events[0].get("value"):
                event_desc = str(retrieved_events[0]["value"])
                conclusion = f"네, 어제 ({current_packet.contextual_entities['어제']}) '{event_desc}'에 대해 이야기 나눴던 것을 기억합니다."
                confidence = 0.85
                current_packet.add_reasoning_step("LTM Based Deduction", f"Recalled event '{event_desc}' for yesterday.", input_data=premises, output_data=conclusion, confidence=confidence, source_comp="ReasoningEngine")
            else:
                conclusion = f"어제 ({current_packet.contextual_entities['어제']}) 특정 사건에 대한 기록을 찾지 못했습니다. 무엇에 대해 말씀하시는지요?"
                confidence = 0.6
                current_packet.add_reasoning_step("LTM Search Miss", "No specific event found for yesterday in LTM.", input_data=premises, output_data=conclusion, confidence=confidence, source_comp="ReasoningEngine")
        
        current_packet.reasoning_engine_outputs = {"conclusion": conclusion, "confidence": confidence, "premises_used_count": len(premises)}
        current_packet.current_processing_stage = "logical_reasoning_completed"
        eliar_log(EliarLogType.DEBUG, "Logical reasoning completed.", component=f"{SUB_GPU_COMPONENT_BASE}.ReasoningEngine", packet_id=pid, conclusion=conclusion)
        return current_packet


# --- SubGPUModule 클래스 정의 (모든 컴포넌트 통합 및 비동기 인터페이스) ---
class SubGPUModule:
    def __init__(self, config: Dict[str, Any], node_id: str = f"{SUB_GPU_COMPONENT_BASE}_Node_Default"):
        self.device = DEVICE
        self.config = config
        self.node_id = node_id # 각 SubGPU 인스턴스 식별용
        self.module_base_component = f"{SUB_GPU_COMPONENT_BASE}.{self.node_id}" # 로깅용 컴포넌트명
        eliar_log(EliarLogType.INFO, "Initializing.", component=self.module_base_component, device_type=str(self.device))

        # --- 통신 및 핵심 로직을 위한 참조 ---
        self.main_gpu_response_handler: Optional[Callable[[SubCodeThoughtPacketData], Coroutine[Any,Any,None]]] = None
        self.main_gpu_controller_ref: Optional[Any] = None # Main_gpu.py의 Eliar 인스턴스 참조 (평가 함수용)

        # --- 핵심 컴포넌트 초기화 ---
        self.ethical_governor = EthicalGovernor()
        self.memory_manager = ContextualMemoryManager() # CognitiveArchitectureInterface 대신 ContextualMemoryManager 사용 또는 통합
        self.context_analyzer = ContextualAnalyzer(self.memory_manager)
        self.reasoning_engine = ReasoningEngineInterface(self.memory_manager) # 개념적 인터페이스
        
        # (SelfLearning, Metacognition, Creativity 등 다른 컴포넌트는 이전 버전의 구조를 따르되,
        #  ContextualMemoryManager와 ContextualAnalyzer를 활용하도록 수정 필요)
        #  여기서는 간략화를 위해 해당 컴포넌트들의 상세 구현은 생략하고, 인터페이스만 남겨둠
        self.self_learning: Optional[SelfLearningComponent] = None # 필요시 초기화
        self.metacognition: Optional[MetacognitionComponent] = None # 필요시 초기화
        self.creativity: Optional[CreativityComponent] = None # 필요시 초기화
        # self.self_learning = SelfLearningComponent(...)
        # self.metacognition = MetacognitionComponent(...)
        # self.creativity = CreativityComponent(...)
        # if self.self_learning and self.metacognition and self.creativity:
        #     self.self_learning.link_other_components(self.metacognition, self.creativity)
            
        self.current_thought_packet: Optional[ThoughtPacket] = None # 현재 처리 중인 패킷
        
        eliar_log(EliarLogType.INFO, "All core components initialized.", component=self.module_base_component)

    async def link_main_gpu_coordinator(self, 
                                        main_gpu_controller_instance: Any, # Main_gpu.py의 Eliar 인스턴스
                                        main_gpu_response_handler_callback: Callable[[SubCodeThoughtPacketData], Coroutine[Any,Any,None]]): # Main_gpu.py의 Communicator.sub_code_response_handler
        """ MainGPU 컨트롤러 및 응답 핸들러와 연결하고, EthicalGovernor의 외부 평가 함수를 설정합니다. """
        log_comp = f"{self.module_base_component}.LinkMainGPU"
        self.main_gpu_controller_ref = main_gpu_controller_instance
        self.main_gpu_response_handler = main_gpu_response_handler_callback
        
        # CognitiveArchitectureInterface (또는 ContextualMemoryManager)에도 콜백 설정
        if hasattr(self.memory_manager, 'main_gpu_response_handler'):
            self.memory_manager.main_gpu_response_handler = main_gpu_response_handler_callback

        evaluators_configured = False
        if self.main_gpu_controller_ref:
            # Main_gpu.py의 Eliar 인스턴스에 평가 함수들이 async def로 정의되어 있다고 가정
            truth_eval_func = getattr(self.main_gpu_controller_ref, 'evaluate_truth_for_governor', None)
            love_eval_func = getattr(self.main_gpu_controller_ref, 'evaluate_love_for_governor', None)
            repentance_eval_func = getattr(self.main_gpu_controller_ref, 'evaluate_repentance_for_governor', None)

            if callable(truth_eval_func) and callable(love_eval_func) and callable(repentance_eval_func):
                self.ethical_governor.set_evaluators(truth_eval_func, love_eval_func, repentance_eval_func)
                evaluators_configured = True
                eliar_log(EliarLogType.INFO, "External ethical evaluators set from MainGPU Controller.", component=log_comp)
            else:
                missing_evals = []
                if not callable(truth_eval_func): missing_evals.append("truth")
                if not callable(love_eval_func): missing_evals.append("love")
                if not callable(repentance_eval_func): missing_evals.append("repentance")
                eliar_log(EliarLogType.WARN, f"One or more MainGPU ethical evaluators are not callable or missing: {missing_evals}. Defaults will be used.", component=log_comp)
        else:
            eliar_log(EliarLogType.WARN, "MainGPU Controller reference not provided. EthicalGovernor will use defaults.", component=log_comp)
        
        if not self.main_gpu_response_handler:
            eliar_log(EliarLogType.ERROR, "MainGPU response handler callback NOT linked! SubGPU cannot send results back.", component=log_comp)
        
        eliar_log(EliarLogType.INFO, "Link with MainGPU coordinator process complete.", component=log_comp, evaluators_ready=evaluators_configured, callback_ready=bool(self.main_gpu_response_handler))


    async def _initialize_or_set_current_thought_packet(self, task_data: Dict[str, Any]) -> ThoughtPacket:
        """ 현재 ThoughtPacket을 초기화하거나 task_data로 업데이트합니다. """
        # MainGPU에서 전달된 packet_id, conversation_id 등을 사용하여 ThoughtPacket 인스턴스 관리
        pid = task_data.get("packet_id", f"sub_pkt_{uuid.uuid4().hex[:8]}") # MainGPU가 안주면 여기서 생성
        conv_id = task_data.get("conversation_id", "default_conv")
        user_id = task_data.get("user_id", "default_user")
        raw_text = task_data.get("raw_input_text", "")
        ts_created = task_data.get("timestamp_created", time.time())

        # 항상 새 패킷을 생성하거나, 기존 패킷 ID와 다르면 새로 생성
        self.current_thought_packet = ThoughtPacket(pid, conv_id, user_id, raw_text, ts_created)
        
        # MainGPU로부터 받은 추가 컨텍스트 필드들을 ThoughtPacket에 복사/설정
        for key in ["main_gpu_clarification_context", "previous_main_gpu_context_summary", 
                      "preferred_llm_config_by_main", "main_gpu_system_prompt_override", 
                      "main_gpu_memory_injection", "is_clarification_response"]: # is_clarification_response도 Main->Sub 전달 필드
            if key in task_data:
                setattr(self.current_thought_packet, key, task_data[key])
        
        eliar_log(EliarLogType.INFO, "Current ThoughtPacket initialized/set.", component=f"{self.module_base_component}.PacketCtx", packet_id=pid)
        return self.current_thought_packet

    async def process_task(self, task_type: str, task_data: Dict[str, Any]) -> SubCodeThoughtPacketData:
        """
        MainGPU로부터 작업을 받아 비동기적으로 처리하고, 표준화된 SubCodeThoughtPacketData로 결과를 반환합니다.
        이 함수는 Main_gpu.py의 MainSubInterfaceCommunicator.send_task_to_sub_code 내 task_wrapper에서 호출됩니다.
        """
        current_packet = await self._initialize_or_set_current_thought_packet(task_data)
        pid = current_packet.packet_id
        log_comp_task = f"{self.module_base_component}.TaskProc.{task_type}"

        current_packet.current_processing_stage = f"subgpu_task_received_{task_type}"
        current_packet.processing_status_in_sub_code = "PROCESSING_STARTED_IN_SUBGPU"
        eliar_log(EliarLogType.INFO, "Task processing started.", component=log_comp_task, packet_id=pid)

        try:
            # === 1. 윤리적 사전 검토 ===
            govern_data = current_packet.raw_input_text
            action_preview = f"sub_gpu_processing_for_{task_type}"
            if not await self.ethical_governor.govern_action(task_type, govern_data, action_preview, packet_id=pid):
                current_packet.processing_status_in_sub_code = "REJECTED_BY_SUBGPU_ETHICS_PRE_CHECK"
                current_packet.error_info = {"type": "EthicalPreCheckRejection", "message": "Task failed SubGPU internal ethical pre-check."}
                current_packet.final_output_by_sub_code = "[SubGPU: 윤리적 기준에 따라 요청 처리를 시작할 수 없습니다.]"
                # (이하 최종 반환 로직으로 바로 이동)
            else:
                # === 2. 맥락 분석 (ContextualAnalyzer 사용) ===
                current_packet.current_processing_stage = "contextual_analysis"
                current_packet = await self.context_analyzer.analyze_and_enrich_packet(current_packet)
                current_packet.add_intermediate_thought("context_analysis_done", "Contextual analysis and entity resolution completed.", 
                                                        data={"resolved_entities_count": len(current_packet.contextual_entities)})

                # === 3. 추론 체인 구축 및 심층 추론 (ThoughtPacketEnhancer & ReasoningEngine) ===
                # (엘리아르님 프로토타입의 packet.analyze() 와 유사한 로직 또는 ReasoningEngine 호출)
                current_packet.current_processing_stage = "reasoning_phase"
                # 예시: "어제"가 포함된 경우, ContextualAnalyzer가 해결한 날짜를 바탕으로 LTM 조회 및 추론
                if "어제" in current_packet.raw_input_text and "어제" in current_packet.contextual_entities:
                    current_packet = await self.reasoning_engine.perform_logical_reasoning(current_packet, reasoning_goal=f"Recall events from {current_packet.contextual_entities['어제']}")
                    # ReasoningEngine이 current_packet.reasoning_chain, reasoning_engine_outputs 등을 채움
                    # 또한, current_packet.final_output_by_sub_code의 기초가 될 수 있는 정보를 생성할 수 있음
                    if current_packet.reasoning_engine_outputs and current_packet.reasoning_engine_outputs.get("conclusion"):
                        current_packet.final_output_by_sub_code = current_packet.reasoning_engine_outputs["conclusion"]
                        current_packet.confidence_score = current_packet.reasoning_engine_outputs.get("confidence", 0.5)

                # --- 기존 태스크 유형별 처리 로직 (필요시 여기에 통합 또는 별도 핸들러로 분리) ---
                elif task_type == "eliar_process_interaction_v3": # MainGPU에서 보낸 일반 상호작용
                    # 위에서 맥락 분석 및 추론을 이미 수행했으므로, 여기서는 응답 생성에 집중
                    if not current_packet.final_output_by_sub_code: # 추론 엔진에서 응답이 생성되지 않았다면
                        # LLM 호출 또는 규칙 기반 응답 생성 등
                        await asyncio.sleep(0.05) # 응답 생성 시간 시뮬레이션
                        current_packet.final_output_by_sub_code = f"[SubGPU 응답 강화] '{current_packet.raw_input_text[:15]}'에 대한 맥락적 응답입니다. (해결된 개체: {len(current_packet.contextual_entities)}개)"
                        current_packet.confidence_score = 0.75 # 예시
                    current_packet.processing_status_in_sub_code = "COMPLETED_SUCCESS_REASONED"
                
                # (기타 RL, Metacognition 등의 task_type 처리 로직...)

                else: # 알 수 없는 작업 유형
                    current_packet.error_info = {"type": "UnknownSubGPUTask", "message": f"Task type '{task_type}' not specifically handled after context/reasoning phase."}
                    current_packet.processing_status_in_sub_code = "ERROR_UNHANDLED_TASK_TYPE"
                
                current_packet.add_intermediate_thought("main_logic_complete", f"Main logic for {task_type} completed.")

            # === 4. 윤리적 사후 검토 ===
            current_packet.current_processing_stage = "ethical_post_assessment"
            # 최종 생성된 패킷(또는 응답)을 기준으로 평가
            # assess_repentance_necessity는 SubCodeThoughtPacketData를 받을 수 있도록 수정 필요 가정
            # 또는 current_packet.to_sub_code_thought_packet_data() 결과를 전달
            if await self.ethical_governor.assess_repentance_necessity(current_packet.to_sub_code_thought_packet_data(), {"task_type": task_type, "current_status_sub": current_packet.processing_status_in_sub_code}, packet_id=pid):
                eliar_log(EliarLogType.WARN, "Post-task assessment in SubGPU indicates need for repentance.", component=log_comp_task, packet_id=pid)
                asyncio.create_task(self.ethical_governor.trigger_repentance_action(self, {"type": "subgpu_repentance_needed_post_task", "details": current_packet.to_sub_code_thought_packet_data()}, packet_id=pid))
                if "ERROR" not in current_packet.processing_status_in_sub_code:
                     current_packet.processing_status_in_sub_code = "COMPLETED_WITH_REPENTANCE_ADVISED"

        except Exception as e:
            current_packet.processing_status_in_sub_code = "ERROR_UNHANDLED_SUBGPU_EXCEPTION"
            current_packet.error_info = {"type": type(e).__name__, "message": str(e), "details": traceback.format_exc(limit=10)} # 트레이스백 상세 기록
            eliar_log(EliarLogType.CRITICAL, f"Unhandled exception during task '{task_type}'.", component=log_comp_task, packet_id=pid, error=e, exc_info_full=traceback.format_exc())
        
        # === 5. 최종 처리 완료 및 반환 데이터 구성 ===
        current_packet.timestamp_completed_by_sub_code = time.time()
        current_packet.current_processing_stage = f"subgpu_task_finalized_{task_type}"
        
        # STM에 현재 처리 완료된 패킷 저장
        await self.memory_manager.store_to_stm(current_packet.to_sub_code_thought_packet_data())
        
        final_response_packet_data = current_packet.to_sub_code_thought_packet_data()
        
        eliar_log(EliarLogType.INFO, "Task processing finished. Returning packet data to MainGPU.", component=log_comp_task, packet_id=pid, final_status=final_response_packet_data.get("processing_status_in_sub_code"))
        return final_response_packet_data


    async def shutdown(self, packet_id: Optional[str]=None):
        log_comp_shutdown = f"{self.module_base_component}.Shutdown"
        eliar_log(EliarLogType.INFO, "Shutdown sequence initiated...", component=log_comp_shutdown, packet_id=packet_id)
        # (이전 shutdown 로직, Executor 종료 등)
        if SUB_GPU_CPU_EXECUTOR: # Executor가 이 모듈 레벨에서 관리된다면
            await run_in_executor(None, SUB_GPU_CPU_EXECUTOR.shutdown, True)
            eliar_log(EliarLogType.INFO, "SubGPU CPU Executor shutdown complete.", component=log_comp_shutdown)
        eliar_log(EliarLogType.INFO, "Shutdown sequence complete.", component=log_comp_shutdown, packet_id=packet_id)


# --- 데모 및 테스트용 (이 파일 단독 실행 시) ---
async def sub_gpu_standalone_reasoning_test():
    log_comp_test = f"{SUB_GPU_COMPONENT_BASE}.StandaloneTest"
    eliar_log(EliarLogType.INFO, "--- SubGPUModule Standalone Contextual Reasoning Test ---", component=log_comp_test)
    
    test_config = { "state_dim": 5, "action_dim": 2, "rl_batch_size": 4 }
    sub_gpu = SubGPUModule(config=test_config, node_id="sub_reasoning_node")

    # Mock MainGPU Controller and Response Handler
    class MockMainControllerForSub:
        async def evaluate_truth_for_governor(self, data, ctx): return 0.95
        async def evaluate_love_for_governor(self, action, ctx): return 0.9
        async def evaluate_repentance_for_governor(self, outcome, ctx): return False
    
    mock_main_controller = MockMainControllerForSub()
    
    async def mock_main_response_handler_for_sub(response_packet: SubCodeThoughtPacketData):
        eliar_log(EliarLogType.INFO, "MockMainHandler (for SubGPU Test): Received response.", component=log_comp_test, 
                  packet_id=response_packet.get("packet_id"), status=response_packet.get("processing_status_in_sub_code"),
                  output_preview=(response_packet.get("final_output_by_sub_code") or "")[:60],
                  reasoning_steps_count=len(response_packet.get("reasoning_chain", [])),
                  contextual_entities=response_packet.get("contextual_entities"))

    await sub_gpu.link_main_gpu_coordinator(mock_main_controller, mock_main_response_handler_for_sub)

    # 테스트 시나리오
    conv_id_test = "conv_context_test_001"
    user_id_test = "user_reasoner_001"

    # 1. 첫 번째 대화: "어제 데이터 분석에 대해 이야기했었지." (LTM에 저장될 내용 가정)
    #    실제로는 이 정보가 이전 턴에서 STM/LTM에 저장되었어야 함. 여기서는 LTM에 수동으로 추가.
    await sub_gpu.memory_manager.transfer_to_ltm(
        key=f"event_on_date_어제_날짜_계산필요_conv_{conv_id_test}", # ContextualAnalyzer가 해결할 키 형식과 유사하게
        value="데이터 분석 방법론 및 결과 공유",
        memory_type="episodic",
        packet_id="ltm_init_pkt_001",
        metadata={"source_component": "TestSetup", "conversation_id": conv_id_test}
    )

    # 2. 두 번째 대화: "어제 내가 얘기한 사람 누구였지?" -> STM에 "홍길동" 언급이 있었다고 가정
    #    STM에 이전 대화 내용 수동 추가 (실제로는 이전 process_task 결과가 자동으로 추가됨)
    prev_turn_data_stm = ThoughtPacket("prev_pkt_001", conv_id_test, user_id_test, "홍길동씨는 전문가입니다.")
    prev_turn_data_stm.final_output_by_sub_code = "네, 홍길동씨는 해당 분야의 최고 전문가 중 한 분이시죠."
    prev_turn_data_stm.processing_status_in_sub_code = "COMPLETED_SUCCESS"
    prev_turn_data_stm.timestamp_completed_by_sub_code = time.time() - 3600 # 1시간 전
    await sub_gpu.memory_manager.store_to_stm(prev_turn_data_stm.to_sub_code_thought_packet_data())


    test_task_data_reasoning = {
        "packet_id": "test_reason_pkt_001", "conversation_id": conv_id_test, "user_id": user_id_test,
        "raw_input_text": "어제 내가 얘기한 그 사람은 누구였고, 무슨 이야기를 했었지?",
        "timestamp_created": time.time()
    }
    
    # process_task 호출 (결과는 mock_main_response_handler_for_sub 콜백으로 전달되지만, 직접 받을 수도 있음)
    response_packet_reasoning = await sub_gpu.process_task("eliar_process_interaction_v3", test_task_data_reasoning)
    
    # 여기서 response_packet_reasoning의 내용을 직접 검사해도 됨.
    # 콜백은 비동기적으로 호출되므로, 테스트 완료를 위해 약간의 대기 필요할 수 있음
    await asyncio.sleep(0.2) 

    await sub_gpu.shutdown()
    if SUB_GPU_CPU_EXECUTOR: SUB_GPU_CPU_EXECUTOR.shutdown(wait=False)
    eliar_log(EliarLogType.INFO, "--- SubGPUModule Standalone Contextual Reasoning Test Finished ---", component=log_comp_test)


if __name__ == '__main__':
    try:
        asyncio.run(sub_gpu_standalone_reasoning_test())
    except KeyboardInterrupt:
        eliar_log(EliarLogType.WARN, "SubGPU standalone test interrupted by user.", component=f"{SUB_GPU_COMPONENT_BASE}.TestRunner")
    except Exception as e_run:
        eliar_log(EliarLogType.CRITICAL, "Error running SubGPU standalone test.", component=f"{SUB_GPU_COMPONENT_BASE}.TestRunner", error=e_run, exc_info_full=traceback.format_exc())
    finally:
        eliar_log(EliarLogType.INFO, "SubGPU standalone test run complete.", component=f"{SUB_GPU_COMPONENT_BASE}.TestRunner")
