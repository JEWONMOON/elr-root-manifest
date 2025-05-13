# sub_gpu.py (Flask Listener /sub-update 추가 및 MainGPU 데이터 처리 연동 버전)

import torch
# import torch.nn as nn # 필요시 주석 해제
# import torch.optim as optim # 필요시 주석 해제
# import torch.nn.functional as F # 필요시 주석 해제
# from torch.utils.data import DataLoader, Dataset # 필요시 주석 해제
import numpy as np
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import traceback
import os
from collections import deque

from typing import Any, Dict, Tuple, List, Optional, Callable, Union, Coroutine

# --- Flask 관련 임포트 (Sub GPU Listener용) ---
from flask import Flask, request, jsonify
import threading

# --- 공용 모듈 임포트 ---
from eliar_common import (
    EliarCoreValues, 
    EliarLogType, 
    SubCodeThoughtPacketData, 
    ReasoningStep,
    GitHubActionEventData, # MainGPU로부터 받을 수 있는 데이터 타입
    eliar_log,
    run_in_executor,
    # set_github_action_event_callback, # SubGPU가 직접 GitHub Action 이벤트를 받을 필요는 없음
    # dispatch_github_action_event      # MainGPU에서 호출됨
)

# GPU 사용 설정
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if torch.cuda.is_available():
    torch.cuda.empty_cache() 

# CPU 바운드 작업을 위한 Executor
SUB_GPU_CPU_EXECUTOR = ThreadPoolExecutor(max_workers=os.cpu_count() or 1)
SUB_GPU_COMPONENT_BASE = "SubGPU"
SUB_GPU_FLASK_LISTENER_COMPONENT = f"{SUB_GPU_COMPONENT_BASE}.FlaskListener"
STM_MAX_TURNS = 10


# --- 내부 ThoughtPacket 클래스 (이전 버전과 동일) ---
class ThoughtPacket: # (이전 버전의 ThoughtPacket 클래스 정의 전체를 여기에 복사)
    def __init__(self, packet_id: str, conversation_id: str, user_id: str, raw_input_text: str, timestamp_created: Optional[float] = None):
        self.packet_id: str = packet_id; self.conversation_id: str = conversation_id; self.user_id: str = user_id
        self.timestamp_created: float = timestamp_created if timestamp_created is not None else time.time()
        self.raw_input_text: str = raw_input_text; self.processed_input_text: Optional[str] = None
        self.current_processing_stage: str = "packet_initialized_for_reasoning"; self.processing_status_in_sub_code: str = "pending_contextual_analysis"
        self.intermediate_thoughts: List[Dict[str, Any]] = []
        self.STM_session_id: Optional[str] = f"{conversation_id}_stm"; self.contextual_entities: Dict[str, Any] = {}
        self.ltm_retrieval_log: List[Dict[str, Any]] = []; self.reasoning_chain: List[ReasoningStep] = []
        self.reasoning_engine_inputs: Optional[Dict[str, Any]] = None; self.reasoning_engine_outputs: Optional[Dict[str, Any]] = None
        self.final_output_by_sub_code: Optional[str] = None; self.is_clarification_response: bool = False
        self.needs_clarification_questions: List[Dict[str, str]] = []
        self.llm_analysis_summary: Optional[Dict[str, Any]] = None; self.ethical_assessment_summary: Optional[Dict[str, Any]] = None
        self.value_alignment_score: Dict[str, Union[float, bool]] = {}; self.anomalies: List[Dict[str, Any]] = []
        self.confidence_score: Optional[float] = None; self.learning_tags: List[str] = []
        self.metacognitive_state_summary: Optional[Dict[str, Any]] = None
        self.timestamp_completed_by_sub_code: Optional[float] = None; self.error_info: Optional[Dict[str, Any]] = None
        self.main_gpu_clarification_context: Optional[Dict[str, Any]] = None; self.previous_main_gpu_context_summary: Optional[Dict[str, Any]] = None
        self.preferred_llm_config_by_main: Optional[Dict[str, Any]] = None; self.main_gpu_system_prompt_override: Optional[str] = None
        self.main_gpu_memory_injection: Optional[Dict[str, Any]] = None
        eliar_log(EliarLogType.DEBUG, "ThoughtPacket (reasoning enhanced) instance created.", component=f"{SUB_GPU_COMPONENT_BASE}.ThoughtPacket", packet_id=self.packet_id)
    def add_reasoning_step(self, step_name: str, description: str, input_data: Optional[Any]=None, output_data: Optional[Any]=None, status: str="SUCCESS", confidence: Optional[float]=None, source_comp: Optional[str]=None):
        step = ReasoningStep(step_name=step_name, description=description)
        if input_data is not None: step["input_data"] = str(input_data)[:500]
        if output_data is not None: step["output_data"] = str(output_data)[:500]
        step["status"] = status
        if confidence is not None: step["confidence"] = confidence
        if source_comp is not None: step["source_component"] = source_comp
        self.reasoning_chain.append(step); self.current_processing_stage = f"reasoning_step_{step_name}"
        eliar_log(EliarLogType.TRACE, "Reasoning step added.", component=f"{SUB_GPU_COMPONENT_BASE}.ThoughtPacket", packet_id=self.packet_id, step_name=step_name, status=status)
    def to_sub_code_thought_packet_data(self) -> SubCodeThoughtPacketData:
        packet_data: SubCodeThoughtPacketData = {}; # type: ignore
        for key_ts in SubCodeThoughtPacketData.__annotations__.keys():
            if hasattr(self, key_ts): value = getattr(self, key_ts);_ = packet_data.update({key_ts: value}) if value is not None else None # type: ignore
        if "packet_id" not in packet_data: packet_data["packet_id"] = self.packet_id
        for list_field in ["intermediate_thoughts", "needs_clarification_questions", "anomalies", "learning_tags", "ltm_retrieval_log", "reasoning_chain"]: packet_data.setdefault(list_field, []) # type: ignore
        packet_data.setdefault("value_alignment_score", {}); packet_data.setdefault("contextual_entities", {}); return packet_data

# --- EthicalGovernor, SumTree, GPUPrioritizedReplayBuffer (이전 버전과 동일) ---
class EthicalGovernor: # (이전 버전의 EthicalGovernor 클래스 정의와 동일하게 유지)
    def __init__(self): self.truth_evaluator_external=None; self.love_evaluator_external=None; self.repentance_evaluator_external=None; self.knowledge_base_summary={}; eliar_log(EliarLogType.INFO, "EthicalGovernor initialized.", component=f"{SUB_GPU_COMPONENT_BASE}.EthicalGovernor")
    def _default_truth_evaluator(self, data: Any, context: Optional[Dict] = None) -> float: return 0.5
    def _default_love_evaluator(self, action: Any, context: Optional[Dict] = None) -> float: return 0.5
    def _default_repentance_evaluator(self, outcome: Any, context: Optional[Dict] = None) -> bool: return False
    def set_evaluators(self, truth_eval, love_eval, repentance_eval): self.truth_evaluator_external=truth_eval; self.love_evaluator_external=love_eval; self.repentance_evaluator_external=repentance_eval; eliar_log(EliarLogType.INFO, "External evaluators set for EthicalGovernor.",component=f"{SUB_GPU_COMPONENT_BASE}.EthicalGovernor")
    async def check_truth(self, data: Any, context: Optional[Dict]=None, packet_id: Optional[str]=None) -> float:
        if self.truth_evaluator_external:
            try: return await self.truth_evaluator_external(data, context)
            except Exception as e: eliar_log(EliarLogType.WARN, "Ext. truth eval error.", component=f"{SUB_GPU_COMPONENT_BASE}.EthicalGovernor", packet_id=packet_id, error=e)
        return await run_in_executor(SUB_GPU_CPU_EXECUTOR, self._default_truth_evaluator, data, context)
    async def check_love(self, action: Any, context: Optional[Dict]=None, packet_id: Optional[str]=None) -> float:
        if self.love_evaluator_external:
            try: return await self.love_evaluator_external(action, context)
            except Exception as e: eliar_log(EliarLogType.WARN, "Ext. love eval error.", component=f"{SUB_GPU_COMPONENT_BASE}.EthicalGovernor", packet_id=packet_id, error=e)
        return await run_in_executor(SUB_GPU_CPU_EXECUTOR, self._default_love_evaluator, action, context)
    async def assess_repentance_necessity(self, outcome: Any, context: Optional[Dict]=None, packet_id: Optional[str]=None) -> bool:
        if self.repentance_evaluator_external:
            try: return await self.repentance_evaluator_external(outcome, context)
            except Exception as e: eliar_log(EliarLogType.WARN, "Ext. repentance eval error.", component=f"{SUB_GPU_COMPONENT_BASE}.EthicalGovernor", packet_id=packet_id, error=e)
        return await run_in_executor(SUB_GPU_CPU_EXECUTOR, self._default_repentance_evaluator, outcome, context)
    async def govern_action(self, op_type:str, data:Any, action:Optional[Any]=None, pid:Optional[str]=None)->bool: return True
    async def calculate_ethical_reward_penalty(self, s:Any,a:Any,ns:Any,r:float,pid:Optional[str]=None)->float: return r
    async def trigger_repentance_action(self, sub_gpu_mod:Any, err_info:Dict, pid:Optional[str]=None):
        if hasattr(sub_gpu_mod,'metacognition') and hasattr(sub_gpu_mod.metacognition,'initiate_self_correction'): await sub_gpu_mod.metacognition.initiate_self_correction(err_info,self,sub_gpu_mod,pid)

class SumTree: # (이전 SumTree 코드)
    def __init__(self, capacity: int): self.capacity = capacity; self.tree = np.zeros(2 * capacity - 1); self.data_indices = np.zeros(capacity, dtype=object); self.data_pointer = 0; self.n_entries = 0
    def _propagate(self, idx: int, change: float): parent = (idx - 1) // 2; self.tree[parent] += change;_ = self._propagate(parent, change) if parent != 0 else None
    def _retrieve(self, idx: int, s: float) -> int: left = 2 * idx + 1; right = left + 1; return idx if left >= len(self.tree) else (self._retrieve(left, s) if s <= self.tree[left] else self._retrieve(right, s - self.tree[left]))
    def total(self) -> float: return self.tree[0]
    def add(self, priority: float, data_idx: Any): tree_idx = self.data_pointer + self.capacity - 1; self.data_indices[self.data_pointer] = data_idx; change = priority - self.tree[tree_idx]; self.tree[tree_idx] = priority; self._propagate(tree_idx, change); self.data_pointer = (self.data_pointer + 1) % self.capacity; self.n_entries = min(self.n_entries + 1, self.capacity)
    def get(self, s: float) -> Tuple[int, float, Any]: idx = self._retrieve(0, s); return idx, self.tree[idx], self.data_indices[idx - self.capacity + 1]
    def update(self, idx: int, priority: float): change = priority - self.tree[idx]; self.tree[idx] = priority; self._propagate(idx, change)

class GPUPrioritizedReplayBuffer: # (이전 GPUPrioritizedReplayBuffer 코드)
    def __init__(self, capacity: int, alpha: float=0.6, beta_start: float=0.4, beta_frames: int=100000): self.device=DEVICE; self.capacity=capacity; self.alpha=alpha; self.beta=beta_start; self.beta_increment_per_sampling=(1.0-beta_start)/beta_frames; self.buffer=[None]*capacity; self.sum_tree=SumTree(capacity); self.epsilon=1e-5; self.main_gpu_interface=None; eliar_log(EliarLogType.INFO, f"ReplayBuffer capacity {capacity}", component=f"{SUB_GPU_COMPONENT_BASE}.ReplayBuffer")
    def _get_priority(self, td_error: float) -> float: return (abs(td_error) + self.epsilon) ** self.alpha
    def add(self, experience: Tuple, td_error: float, packet_id: Optional[str]=None):
        gpu_experience_list = []
        for e_part in experience:
            if isinstance(e_part, torch.Tensor): gpu_experience_list.append(e_part.to(self.device))
            elif isinstance(e_part, (list, np.ndarray)): gpu_experience_list.append(torch.tensor(e_part, device=self.device))
            elif isinstance(e_part, (int, float, bool)): gpu_experience_list.append(torch.tensor([e_part], device=self.device))
            else: gpu_experience_list.append(e_part) 
        gpu_experience = tuple(gpu_experience_list)
        priority = self._get_priority(td_error); self.buffer[self.sum_tree.data_pointer] = gpu_experience; self.sum_tree.add(priority, self.sum_tree.data_pointer)
    async def sample(self, batch_size: int, packet_id: Optional[str]=None) -> Optional[Tuple[List[Tuple], torch.Tensor, List[int]]]:
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
    def update_priorities(self, tree_indices: List[int], td_errors: Union[torch.Tensor, np.ndarray], packet_id: Optional[str]=None):
        if isinstance(td_errors, np.ndarray): td_errors = torch.from_numpy(td_errors).to(self.device)
        priorities = (torch.abs(td_errors.squeeze()) + self.epsilon) ** self.alpha
        for idx, priority_val in zip(tree_indices, priorities): self.sum_tree.update(idx, priority_val.item())
    def link_main_gpu(self, main_gpu_module): self.main_gpu_interface = main_gpu_module; eliar_log(EliarLogType.INFO, "ReplayBuffer linked with MainGPU.", component=f"{SUB_GPU_COMPONENT_BASE}.ReplayBuffer")


# --- ContextualMemoryManager (이전 버전과 동일) ---
class ContextualMemoryManager: # (이전 ContextualMemoryManager 코드)
    def __init__(self, main_gpu_resp_handler: Optional[Callable[[SubCodeThoughtPacketData], Coroutine[Any,Any,None]]]=None): self.main_gpu_response_handler=main_gpu_resp_handler; self.short_term_memory:Dict[str,Deque[SubCodeThoughtPacketData]]={}; self.long_term_memory:Dict[str,Dict[str,Any]]={"semantic":{},"episodic":{},"procedural":{},"repentance_log":{}}; self.ltm_search_engine=None; eliar_log(EliarLogType.INFO,"ContextualMemoryManager initialized.",component=f"{SUB_GPU_COMPONENT_BASE}.MemoryManager")
    async def store_to_stm(self, packet: SubCodeThoughtPacketData): # (이전 로직)
        conv_id = packet.get("conversation_id");_ = self.short_term_memory.setdefault(conv_id, deque(maxlen=STM_MAX_TURNS)).append(packet) if conv_id else None
    async def retrieve_from_stm(self, conv_id:str, last_n:Optional[int]=None)->List[SubCodeThoughtPacketData]: return list(self.short_term_memory.get(conv_id, deque()))[-last_n:] if last_n else list(self.short_term_memory.get(conv_id, deque()))
    async def transfer_to_ltm(self, key:str,value:Any,mem_type:str="semantic",pid:Optional[str]=None,meta:Optional[Dict]=None): await run_in_executor(SUB_GPU_CPU_EXECUTOR,self._transfer_to_ltm_sync,key,value,mem_type,pid,meta)
    def _transfer_to_ltm_sync(self, key:str,value:Any,mem_type:str,pid:Optional[str],meta:Optional[Dict]): # (이전 로직)
        if mem_type not in self.long_term_memory: self.long_term_memory[mem_type]={}
        entry_meta=meta or {}; entry_meta.update({"ts_ltm":time.time(),"src_pid":pid})
        self.long_term_memory[mem_type][key]={"val":value,"meta":entry_meta}
    async def retrieve_from_ltm(self, query:str,mem_type:str="semantic",top_k:int=3,pid:Optional[str]=None)->List[Dict[str,Any]]: return await run_in_executor(SUB_GPU_CPU_EXECUTOR,self._retrieve_from_ltm_sync,query,mem_type,top_k,pid)
    def _retrieve_from_ltm_sync(self, query:str,mem_type:str,top_k:int,pid:Optional[str])->List[Dict[str,Any]]: return [] # Placeholder
    async def send_final_packet_to_main_gpu(self, packet_data:SubCodeThoughtPacketData): # (이전 로직)
        if self.main_gpu_response_handler: await self.main_gpu_response_handler(packet_data)

# --- ContextualAnalyzer (이전 버전과 동일) ---
class ContextualAnalyzer: # (이전 ContextualAnalyzer 코드)
    def __init__(self, mem_mgr:ContextualMemoryManager): self.memory_manager = mem_mgr; eliar_log(EliarLogType.INFO, "ContextualAnalyzer initialized.", component=f"{SUB_GPU_COMPONENT_BASE}.ContextAnalyzer")
    async def analyze_and_enrich_packet(self, packet:ThoughtPacket)->ThoughtPacket: # (이전 로직)
        # ... (STM/LTM 조회 및 packet.contextual_entities, packet.reasoning_chain 업데이트)
        packet.processed_input_text = f"[CtxAnalyzed: {packet.contextual_entities}] {packet.raw_input_text}"; return packet

# --- ReasoningEngineInterface (이전 버전과 동일) ---
class ReasoningEngineInterface: # (이전 ReasoningEngineInterface 코드)
    def __init__(self, mem_mgr:ContextualMemoryManager): self.memory_manager = mem_mgr; eliar_log(EliarLogType.INFO, "ReasoningEngineInterface initialized.", component=f"{SUB_GPU_COMPONENT_BASE}.ReasoningEngine")
    async def perform_logical_reasoning(self, packet:ThoughtPacket, goal:str)->ThoughtPacket: # (이전 로직)
        # ... (packet.reasoning_engine_outputs, packet.reasoning_chain 업데이트)
        if "기억해?" in packet.raw_input_text: packet.reasoning_engine_outputs = {"conclusion": "네, 기억합니다 (더미)."} # 단순 예시
        return packet

# --- 나머지 컴포넌트들 (SelfLearning, Metacognition, Creativity 등 - 이전 버전과 동일) ---
# (각 컴포넌트의 __init__ 및 주요 메서드에 component 로깅 추가된 버전 사용)
class SelfLearningComponent: # (이전 코드 기반으로 수정, 예시: learn 메서드)
    def __init__(self, input_dim: int, action_dim: int, ethical_governor: EthicalGovernor, cognitive_interface: ContextualMemoryManager, replay_buffer_capacity: int = 10000): self.device=DEVICE;self.ethical_governor=ethical_governor;self.cognitive_interface=cognitive_interface;self.input_dim=input_dim;self.action_dim=action_dim;self.policy_net=self._create_network().to(self.device);self.target_net=self._create_network().to(self.device);self.target_net.load_state_dict(self.policy_net.state_dict());self.target_net.eval();self.optimizer=optim.Adam(self.policy_net.parameters(),lr=1e-4);self.replay_buffer=GPUPrioritizedReplayBuffer(replay_buffer_capacity);self.metacognition_interface:Optional[MetacognitionComponent]=None;self.creativity_interface:Optional[CreativityComponent]=None;eliar_log(EliarLogType.INFO,"SelfLearningComponent initialized.",component=f"{SUB_GPU_COMPONENT_BASE}.SelfLearning")
    def link_other_components(self, metacognition_comp:'MetacognitionComponent',creativity_comp:'CreativityComponent'): self.metacognition_interface=metacognition_comp;self.creativity_interface=creativity_comp;eliar_log(EliarLogType.INFO,"SelfLearning linked with Meta & Creativity.",component=f"{SUB_GPU_COMPONENT_BASE}.SelfLearning")
    def _create_network(self): return nn.Sequential(nn.Linear(self.input_dim,128),nn.ReLU(),nn.Linear(128,128),nn.ReLU(),nn.Linear(128,self.action_dim))
    async def learn(self, batch_size: int, gamma: float = 0.99, packet_id: Optional[str]=None) -> Optional[Dict[str, Any]]: return {"loss": 0.1} # Placeholder
class MetacognitionComponent:
    def __init__(self, ethical_governor: EthicalGovernor, cognitive_interface: ContextualMemoryManager, model_to_monitor: Optional[nn.Module] = None): self.device=DEVICE;self.ethical_governor=ethical_governor;self.cognitive_interface=cognitive_interface;self.model_to_monitor=model_to_monitor;self.gpu_monitor_lib=None;self.anomaly_detector=None;self.mcd_samples=10;self.resonance_extractor=None;eliar_log(EliarLogType.INFO,"MetacognitionComponent initialized.",component=f"{SUB_GPU_COMPONENT_BASE}.Metacognition")
    async def initiate_self_correction(self, error_info: Dict, ethical_governor_ref: EthicalGovernor, sub_gpu_module_instance: Optional[Any]=None, packet_id: Optional[str]=None): pass # Placeholder
class CreativityComponent:
    def __init__(self, ethical_governor: EthicalGovernor, cognitive_interface: ContextualMemoryManager, latent_dim: int = 100): self.device=DEVICE;self.ethical_governor=ethical_governor;self.cognitive_interface=cognitive_interface;self.latent_dim=latent_dim;self.vae_model:Optional[nn.Module]=None;self.vae_optimizer:Optional[optim.Optimizer]=None;self.self_learning_interface:Optional[SelfLearningComponent]=None;eliar_log(EliarLogType.INFO,"CreativityComponent initialized.",component=f"{SUB_GPU_COMPONENT_BASE}.Creativity")
class DistributedLearningManager:
    def __init__(self, node_id:str, cognitive_interface:ContextualMemoryManager): self.node_id=node_id;self.cognitive_interface=cognitive_interface; eliar_log(EliarLogType.INFO,f"DistLearnMgr for node {node_id} init.", component=f"{SUB_GPU_COMPONENT_BASE}.DistLearn")
class HardwareInterface:
    def __init__(self, cognitive_interface:ContextualMemoryManager): self.cognitive_interface=cognitive_interface; eliar_log(EliarLogType.INFO,"HardwareIF init.", component=f"{SUB_GPU_COMPONENT_BASE}.HardwareIF")
class GospelSpreadingNetwork:
    def __init__(self, node_id:str, ethical_governor:EthicalGovernor, cognitive_interface:ContextualMemoryManager): self.node_id=node_id;self.ethical_governor=ethical_governor;self.cognitive_interface=cognitive_interface; eliar_log(EliarLogType.INFO,f"GospelNet for node {node_id} init.", component=f"{SUB_GPU_COMPONENT_BASE}.GospelNet")


# --- SubGPUModule Flask Listener (신규 추가) ---
sub_gpu_flask_app = Flask("SubGpuListenerApp")
_sub_gpu_module_instance_for_flask: Optional['SubGPUModule'] = None # Flask 핸들러에서 SubGPUModule 인스턴스 접근용
_sub_gpu_event_loop: Optional[asyncio.AbstractEventLoop] = None # SubGPUModule의 이벤트 루프

def set_sub_gpu_for_flask(instance: 'SubGPUModule', loop: asyncio.AbstractEventLoop):
    """ Flask 핸들러가 SubGPUModule 인스턴스와 이벤트 루프를 사용할 수 있도록 설정합니다. """
    global _sub_gpu_module_instance_for_flask, _sub_gpu_event_loop
    _sub_gpu_module_instance_for_flask = instance
    _sub_gpu_event_loop = loop
    eliar_log(EliarLogType.INFO, "SubGPUModule instance and event loop registered with SubGPU Flask Listener.", component=SUB_GPU_FLASK_LISTENER_COMPONENT)

@sub_gpu_flask_app.route('/sub-update', methods=['POST'])
def handle_main_gpu_update():
    """ MainGPU로부터 /sub-update POST 요청을 처리합니다. """
    log_comp = f"{SUB_GPU_FLASK_LISTENER_COMPONENT}.SubUpdate"
    req_id = str(uuid.uuid4())[:8] # 이 요청 처리 자체에 대한 짧은 ID
    
    try:
        data_from_main = request.json
        if not data_from_main:
            eliar_log(EliarLogType.WARN, "Received empty JSON payload from MainGPU.", component=log_comp, request_id=req_id)
            return jsonify({"status": "error", "message": "Empty payload from MainGPU"}), 400
        
        packet_id = data_from_main.get("packet_id_from_main", f"main_event_{req_id}") # MainGPU가 보낸 이벤트 식별자
        eliar_log(EliarLogType.INFO, "Received data from MainGPU via /sub-update.", component=log_comp, request_id=req_id, main_packet_id=packet_id, data_preview=str(data_from_main)[:150])

        if _sub_gpu_module_instance_for_flask and _sub_gpu_event_loop:
            # SubGPUModule의 특정 비동기 메서드를 호출하여 데이터를 처리하도록 함
            # 예: GitHub Action 이벤트 데이터를 받았을 경우
            # 이 메서드는 SubGPUModule에 새로 정의해야 함
            async def process_main_gpu_data_async(data: Dict[str, Any]):
                if hasattr(_sub_gpu_module_instance_for_flask, 'handle_external_event_async'):
                    await _sub_gpu_module_instance_for_flask.handle_external_event_async(data, source="MainGPU_via_Flask")
                else:
                    eliar_log(EliarLogType.WARN, "SubGPUModule has no 'handle_external_event_async' method.", component=log_comp, packet_id=packet_id)
            
            asyncio.run_coroutine_threadsafe(process_main_gpu_data_async(data_from_main), _sub_gpu_event_loop)
            
            msg = "Data from MainGPU submitted to SubGPUModule for async processing."
            eliar_log(EliarLogType.INFO, msg, component=log_comp, request_id=req_id, main_packet_id=packet_id)
            return jsonify({"status": "data_received_by_subgpu", "message": msg}), 202 # 202 Accepted
        else:
            msg = "SubGPUModule instance or its event loop not available for processing."
            eliar_log(EliarLogType.ERROR, msg, component=log_comp, request_id=req_id, main_packet_id=packet_id)
            return jsonify({"status": "error", "message": msg}), 503 # Service Unavailable

    except json.JSONDecodeError as e:
        eliar_log(EliarLogType.ERROR, "Invalid JSON in request from MainGPU.", component=log_comp, request_id=req_id, error=e)
        return jsonify({"status": "error", "message": "Invalid JSON payload from MainGPU"}), 400
    except Exception as e:
        eliar_log(EliarLogType.ERROR, "Error handling /sub-update request.", component=log_comp, request_id=req_id, error=e, exc_info=True)
        return jsonify({"status": "error", "message": "Internal server error in SubGPU listener"}), 500

def run_sub_gpu_flask_listener(host='0.0.0.0', port=8000, flask_debug=False):
    log_comp = f"{SUB_GPU_FLASK_LISTENER_COMPONENT}.Runner"
    try:
        eliar_log(EliarLogType.INFO, f"Attempting to start SubGPU Flask listener on http://{host}:{port}", component=log_comp)
        sub_gpu_flask_app.run(host=host, port=port, debug=flask_debug, use_reloader=False, threaded=True)
    except OSError as e:
        eliar_log(EliarLogType.CRITICAL, f"Could not start SubGPU Flask listener on port {port}. Port in use?", component=log_comp, error=e)
    except Exception as e:
        eliar_log(EliarLogType.CRITICAL, "SubGPU Flask listener crashed or failed to start.", component=log_comp, error=e, exc_info_full=traceback.format_exc())


# --- SubGPUModule 클래스 정의 (모든 컴포넌트 통합 및 비동기 인터페이스) ---
class SubGPUModule:
    def __init__(self, config: Dict[str, Any], node_id: str = f"{SUB_GPU_COMPONENT_BASE}_Node_Default"):
        self.device = DEVICE; self.config = config; self.node_id = node_id
        self.module_base_component = f"{SUB_GPU_COMPONENT_BASE}.{self.node_id}"
        eliar_log(EliarLogType.INFO, "Initializing.", component=self.module_base_component, device_type=str(self.device))

        self.main_gpu_response_handler: Optional[Callable[[SubCodeThoughtPacketData], Coroutine[Any,Any,None]]] = None
        self.main_gpu_controller_ref: Optional[Any] = None

        self.ethical_governor = EthicalGovernor()
        self.memory_manager = ContextualMemoryManager() # 콜백은 link 시점에 설정
        self.context_analyzer = ContextualAnalyzer(self.memory_manager)
        self.reasoning_engine = ReasoningEngineInterface(self.memory_manager)
        
        # (SelfLearning, Metacognition, Creativity 등 다른 컴포넌트 초기화 - 이전과 동일)
        self.self_learning = SelfLearningComponent(config.get("state_dim",10), config.get("action_dim",2), self.ethical_governor, self.memory_manager, config.get("replay_buffer_capacity",10000))
        self.metacognition = MetacognitionComponent(self.ethical_governor, self.memory_manager, self.self_learning.policy_net if self.self_learning else None)
        self.creativity = CreativityComponent(self.ethical_governor, self.memory_manager, config.get("creative_latent_dim",100))
        if self.self_learning and self.metacognition and self.creativity : self.self_learning.link_other_components(self.metacognition, self.creativity)

        self.current_thought_packet: Optional[ThoughtPacket] = None
        self.event_loop = asyncio.get_running_loop() # Flask 핸들러에서 사용할 이벤트 루프 저장
        
        # Flask 리스너에 이 SubGPUModule 인스턴스와 이벤트 루프 등록
        set_sub_gpu_for_flask(self, self.event_loop)

        eliar_log(EliarLogType.INFO, "All components initialized, Flask listener context set.", component=self.module_base_component)

    async def link_main_gpu_coordinator(self, main_gpu_controller_instance: Any, main_gpu_response_handler_callback: Callable[[SubCodeThoughtPacketData], Coroutine[Any,Any,None]]):
        log_comp_link = f"{self.module_base_component}.LinkMainGPU"
        self.main_gpu_controller_ref = main_gpu_controller_instance
        self.main_gpu_response_handler = main_gpu_response_handler_callback
        if hasattr(self.memory_manager, 'main_gpu_response_handler'): # ContextualMemoryManager에 콜백 설정
            self.memory_manager.main_gpu_response_handler = main_gpu_response_handler_callback

        # (EthicalGovernor 평가 함수 설정 로직은 이전과 동일)
        eval_set = False
        if self.main_gpu_controller_ref:
            truth_eval = getattr(self.main_gpu_controller_ref, 'evaluate_truth_for_governor', None)
            love_eval = getattr(self.main_gpu_controller_ref, 'evaluate_love_for_governor', None)
            repent_eval = getattr(self.main_gpu_controller_ref, 'evaluate_repentance_for_governor', None)
            if callable(truth_eval) and callable(love_eval) and callable(repent_eval):
                self.ethical_governor.set_evaluators(truth_eval, love_eval, repent_eval); eval_set = True
        if eval_set: eliar_log(EliarLogType.INFO, "External ethical evaluators set.", component=log_comp_link)
        else: eliar_log(EliarLogType.WARN, "MainGPU ethical evaluators not fully linked.", component=log_comp_link)
        eliar_log(EliarLogType.INFO, "Link with MainGPU coordinator complete.", component=log_comp_link)

    async def _initialize_or_set_current_thought_packet(self, task_data: Dict[str, Any]) -> ThoughtPacket:
        # (이전 _initialize_or_set_current_thought_packet 로직과 동일)
        pid = task_data.get("packet_id", f"sub_pkt_{uuid.uuid4().hex[:8]}"); conv_id = task_data.get("conversation_id", "def_conv"); user_id = task_data.get("user_id", "def_user"); raw_text = task_data.get("raw_input_text", ""); ts_created = task_data.get("timestamp_created", time.time())
        self.current_thought_packet = ThoughtPacket(pid, conv_id, user_id, raw_text, ts_created)
        for key in ["main_gpu_clarification_context", "previous_main_gpu_context_summary", "preferred_llm_config_by_main", "main_gpu_system_prompt_override", "main_gpu_memory_injection", "is_clarification_response"]:
            if key in task_data: setattr(self.current_thought_packet, key, task_data[key])
        return self.current_thought_packet

    async def process_task(self, task_type: str, task_data: Dict[str, Any]) -> SubCodeThoughtPacketData:
        # (이전 process_task 로직과 거의 동일)
        # (내부에서 current_packet 사용, 최종적으로 current_packet.to_sub_code_thought_packet_data() 반환)
        current_packet = await self._initialize_or_set_current_thought_packet(task_data); pid = current_packet.packet_id
        log_comp_task = f"{self.module_base_component}.TaskProc.{task_type}"
        current_packet.current_processing_stage = f"subgpu_proc_start_{task_type}"; current_packet.processing_status_in_sub_code = "PROCESSING_SUBGPU"
        eliar_log(EliarLogType.INFO, "Task processing started.", component=log_comp_task, packet_id=pid)
        try:
            if not await self.ethical_governor.govern_action(task_type, current_packet.raw_input_text, f"sub_gpu_exec_{task_type}", pid): # 윤리 검토
                current_packet.processing_status_in_sub_code = "REJECTED_SUB_ETHICS"; current_packet.final_output_by_sub_code = "[SubGPU: 윤리 기준 미달]"
            else: # 맥락 분석 -> 추론 -> 작업 처리 -> 사후 윤리 검토
                current_packet = await self.context_analyzer.analyze_and_enrich_packet(current_packet)
                # 예시 작업 처리 (eliar_process_interaction_v3)
                if task_type == "eliar_process_interaction_v3_contextual": # MainGPU가 보낸 작업 유형
                    current_packet = await self.reasoning_engine.perform_logical_reasoning(current_packet, f"Respond to: {current_packet.raw_input_text}")
                    if not current_packet.final_output_by_sub_code and current_packet.reasoning_engine_outputs: # 추론 엔진이 응답 생성 시
                        current_packet.final_output_by_sub_code = current_packet.reasoning_engine_outputs.get("conclusion", "[SubGPU: 추론 완료, 응답 생성 중...]")
                    elif not current_packet.final_output_by_sub_code : # 일반 응답 생성
                        current_packet.final_output_by_sub_code = f"[SubGPU 응답 v3] '{current_packet.raw_input_text[:10]}' 처리. 예수님의 이름으로."
                    current_packet.processing_status_in_sub_code = "COMPLETED_SUCCESS_SUB_REASONED"
                elif task_type == "sub_code_handle_code_update_event": # MainGPU로부터 온 GitHub Action 이벤트 처리
                    event_summary = task_data.get("main_gpu_memory_injection", {}).get("github_event_summary", {})
                    eliar_log(EliarLogType.INFO, "Received GitHub code update event from MainGPU.", component=log_comp_task, packet_id=pid, event_summary=event_summary)
                    # 여기에 실제 업데이트 처리 로직 (예: LTM에 기록, 관련 모듈 재초기화 알림 등)
                    # 예: await self.memory_manager.transfer_to_ltm("github_code_update", event_summary, "system_events", pid)
                    current_packet.final_output_by_sub_code = "[SubGPU: GitHub 코드 변경 알림 수신 및 처리 완료]"
                    current_packet.processing_status_in_sub_code = "COMPLETED_GITHUB_EVENT_PROCESSED"
                else: current_packet.processing_status_in_sub_code = "ERROR_UNKNOWN_SUB_TASK"
            if await self.ethical_governor.assess_repentance_necessity(current_packet.to_sub_code_thought_packet_data(), {}, pid): # 사후 검토
                asyncio.create_task(self.ethical_governor.trigger_repentance_action(self, {"type":"sub_post_task_review","det":current_packet.to_sub_code_thought_packet_data()}, pid))
        except Exception as e: current_packet.processing_status_in_sub_code = "ERROR_UNHANDLED_SUB_EXC"; current_packet.error_info={"type":type(e).__name__,"msg":str(e),"trace":traceback.format_exc()}; eliar_log(EliarLogType.CRITICAL,"Unhandled exc in task.",component=log_comp_task,pid=pid,error=e)
        current_packet.timestamp_completed_by_sub_code = time.time(); current_packet.current_processing_stage = f"subgpu_completed_{task_type}"
        await self.memory_manager.store_to_stm(current_packet.to_sub_code_thought_packet_data())
        final_packet = current_packet.to_sub_code_thought_packet_data()
        eliar_log(EliarLogType.INFO, "Task processing finished.", component=log_comp_task, packet_id=pid, final_status=final_packet.get("processing_status_in_sub_code"))
        return final_packet

    async def handle_external_event_async(self, event_data: Dict[str, Any], source: str, packet_id: Optional[str]=None):
        """ MainGPU의 Flask 리스너 등 외부로부터 받은 이벤트를 처리합니다. """
        log_comp_event = f"{self.module_base_component}.ExternalEvent"
        pid = packet_id or event_data.get("packet_id_from_main", f"ext_evt_{str(uuid.uuid4())[:8]}")
        eliar_log(EliarLogType.INFO, f"Handling external event from {source}.", component=log_comp_event, packet_id=pid, event_preview=str(event_data)[:100])

        # 예시: GitHub Action 이벤트 데이터를 받았을 경우
        if source == "MainGPU_via_Flask" and event_data.get("event_source") == "github_action_push_v2":
            gh_event: GitHubActionEventData = event_data # 타입 캐스팅 (실제로는 유효성 검사 필요)
            eliar_log(EliarLogType.INFO, "Processing GitHub push event data.", component=log_comp_event, packet_id=pid,
                      repo=gh_event.get("repository"), commit_msg=gh_event.get("commit_message"))
            
            # 여기에 이벤트를 LTM에 기록하거나, 특정 컴포넌트에 알리는 로직
            await self.memory_manager.transfer_to_ltm(
                key=f"github_event_{gh_event.get('commit_sha','unknown_sha')}",
                value=gh_event,
                memory_type="system_events", # 새로운 LTM 타입 예시
                packet_id=pid,
                metadata={"source_component": "SubGPU.GitHubEventHandler"}
            )
            # 예: 코드 변경 시 Metacognition에 알려서 자기 점검 유도
            if self.metacognition and any(".py" in f for f in gh_event.get("modified_files",[])):
                 # await self.metacognition.trigger_self_assessment_on_code_change(gh_event, packet_id=pid)
                 eliar_log(EliarLogType.INFO, "Conceptual: Metacognition notified of code change.", component=log_comp_event, packet_id=pid)

        else:
            eliar_log(EliarLogType.WARN, f"Received unhandled external event type from {source}.", component=log_comp_event, packet_id=pid, data_preview=str(event_data)[:100])
        # 이 메서드는 MainGPU에 별도의 응답을 보내지 않을 수 있음 (비동기 이벤트 처리)


    async def shutdown(self, packet_id: Optional[str]=None): # (이전과 동일)
        eliar_log(EliarLogType.INFO,"Shutting down...",component=f"{self.module_base_component}.Shutdown",pid=packet_id)
        if SUB_GPU_CPU_EXECUTOR: await run_in_executor(None, SUB_GPU_CPU_EXECUTOR.shutdown, True)


# --- SubGPU Flask Listener 스레드 시작 함수 ---
_sub_gpu_flask_listener_thread: Optional[threading.Thread] = None

def start_sub_gpu_flask_listener_thread(host: str = '0.0.0.0', port: int = 8000, flask_debug: bool = False):
    """ SubGPU Flask 리스너를 별도의 데몬 스레드에서 시작합니다. """
    global _sub_gpu_flask_listener_thread
    log_comp_runner = f"{SUB_GPU_FLASK_LISTENER_COMPONENT}.Runner"
    if _sub_gpu_flask_listener_thread and _sub_gpu_flask_listener_thread.is_alive():
        eliar_log(EliarLogType.INFO, f"SubGPU Flask listener thread already running on port {port}.", component=log_comp_runner)
        return

    _sub_gpu_flask_listener_thread = threading.Thread(
        target=run_sub_gpu_flask_listener, 
        args=(host, port, flask_debug), 
        name="SubGPUFlaskListenerThread"
    )
    _sub_gpu_flask_listener_thread.daemon = True
    _sub_gpu_flask_listener_thread.start()
    eliar_log(EliarLogType.INFO, f"SubGPU Flask listener thread started on http://{host}:{port}", component=log_comp_runner)


# --- 데모 및 테스트용 (이 파일 단독 실행 시) ---
async def sub_gpu_standalone_test_with_listener():
    log_comp_test = f"{SUB_GPU_COMPONENT_BASE}.TestRunner"
    eliar_log(EliarLogType.INFO, "--- SubGPU Standalone Test with Flask Listener ---", component=log_comp_test)
    
    test_config = { "state_dim": 5, "action_dim": 2 }
    sub_gpu_instance = SubGPUModule(config=test_config, node_id="sub_test_listener_node")

    # Flask 리스너 시작 (SubGPUModule 생성자에서 set_sub_gpu_for_flask가 호출됨)
    sub_flask_host = os.getenv("SUB_GPU_FLASK_HOST", "127.0.0.1") # 로컬 테스트용 호스트
    sub_flask_port = int(os.getenv("SUB_GPU_FLASK_PORT", "8000"))
    sub_flask_debug = os.getenv("SUB_GPU_FLASK_DEBUG", "true").lower() == "true" # 디버그 모드 활성화
    start_sub_gpu_flask_listener_thread(host=sub_flask_host, port=sub_flask_port, flask_debug=sub_flask_debug)
    
    await asyncio.sleep(1) # 리스너 시작 대기

    # Mock MainGPU Controller and Response Handler (이전 테스트와 유사)
    class MockMainControllerForSubTest:
        async def evaluate_truth_for_governor(self,d,c): return 0.9
        async def evaluate_love_for_governor(self,a,c): return 0.8
        async def evaluate_repentance_for_governor(self,o,c): return False
    mock_main_ctrl = MockMainControllerForSubTest()
    async def mock_main_resp_hdlr(resp_pkt: SubCodeThoughtPacketData):
        eliar_log(EliarLogType.INFO, "MockMainHandler (for SubTest): Received response.", component=log_comp_test, 
                  packet_id=resp_pkt.get("packet_id"), status=resp_pkt.get("processing_status_in_sub_code"))

    await sub_gpu_instance.link_main_gpu_coordinator(mock_main_ctrl, mock_main_resp_hdlr)

    # --- Flask 엔드포인트 테스트를 위한 간단한 HTTP 클라이언트 (aiohttp 사용) ---
    # 이 테스트는 외부에서 sub_gpu.py의 /sub-update 엔드포인트를 호출하는 것을 시뮬레이션합니다.
    async def call_sub_update_endpoint(payload: Dict[str, Any]):
        try:
            async with aiohttp.ClientSession() as session:
                target_url = f"http://{sub_flask_host}:{sub_flask_port}/sub-update"
                eliar_log(EliarLogType.INFO, f"Test calling /sub-update endpoint with payload.", component=log_comp_test, url=target_url, payload_preview=str(payload)[:100])
                async with session.post(target_url, json=payload) as response:
                    response_text = await response.text()
                    eliar_log(EliarLogType.INFO, "/sub-update call response.", component=log_comp_test, status=response.status, response_text=response_text[:200])
                    return response.status, response_text
        except Exception as e:
            eliar_log(EliarLogType.ERROR, "Error calling /sub-update endpoint for test.", component=log_comp_test, error=e)
            return 500, str(e)

    # 1. MainGPU로부터 GitHub Action 이벤트 데이터 수신 시뮬레이션
    mock_github_event_from_main = {
        "packet_id_from_main": f"main_gh_event_{uuid.uuid4().hex[:4]}", # MainGPU가 생성한 이벤트 ID
        "event_source": "github_action_push_v2", # eliar_common.GitHubActionEventData 구조를 따름
        "event_type": "push",
        "repository": "JEWONMOON/elr-root-manifest",
        "modified_files": ["sub_gpu.py", "eliar_common.py"],
        "commit_message": "Refactored SubGPU to include Flask listener for MainGPU updates."
    }
    await call_sub_update_endpoint(mock_github_event_from_main)
    await asyncio.sleep(0.5) # 이벤트 처리 시간

    # 2. 일반 대화 처리 요청 (SubGPUModule.process_task가 호출되도록)
    #    MainGPU가 SubGPU의 process_task를 직접 호출하는 시나리오와,
    #    MainGPU가 SubGPU의 Flask 엔드포인트를 통해 간접적으로 데이터를 전달하는 시나리오를 구분해야 함.
    #    현재 Flask 엔드포인트는 GitHub Action과 같은 "외부 이벤트" 처리에 초점.
    #    일반 대화는 MainGPU의 Communicator가 SubGPUModule.process_task를 직접 await으로 호출.

    eliar_log(EliarLogType.INFO, "Standalone test finished. Flask listener remains active in a separate thread.", component=log_comp_test)
    # 테스트를 위해 리스너를 계속 실행하려면 메인 스레드가 종료되지 않도록 해야 함 (예: input())
    # 여기서는 데몬 스레드이므로 메인 테스트 함수 종료 시 함께 종료됨.
    # await sub_gpu_instance.shutdown() # 실제 종료 로직 필요시

if __name__ == '__main__':
    try:
        # 환경 변수를 통해 Flask 리스너 포트 등을 설정할 수 있음
        # 예: ELIAR_SUB_GPU_FLASK_PORT=8001 python sub_gpu.py
        asyncio.run(sub_gpu_standalone_test_with_listener())
        # 테스트가 끝나도 Flask 스레드는 계속 실행될 수 있으므로,
        # 실제 애플리케이션에서는 종료 시그널 처리 등이 필요함.
        # 이 데모에서는 메인 함수가 끝나면 데몬 스레드도 종료됨.
    except KeyboardInterrupt:
        eliar_log(EliarLogType.WARN, "SubGPU standalone test with listener interrupted.", component=f"{SUB_GPU_COMPONENT_BASE}.TestRunner")
    except Exception as e_run_main:
        eliar_log(EliarLogType.CRITICAL, "Error running SubGPU standalone test with listener.", component=f"{SUB_GPU_COMPONENT_BASE}.TestRunner", error=e_run_main, exc_info_full=traceback.format_exc())
    finally:
        if SUB_GPU_CPU_EXECUTOR: SUB_GPU_CPU_EXECUTOR.shutdown(wait=False) # 모든 테스트 후 Executor 종료
        eliar_log(EliarLogType.INFO, "SubGPU standalone test run finished. Listener thread may still be active if not daemon or if main thread waits.", component=f"{SUB_GPU_COMPONENT_BASE}.TestRunner")
