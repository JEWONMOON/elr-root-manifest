# eliar_common.py (LangGraph 호환 강화 버전)
# ------------------------------------------------------------------
# [LangGraph 통합 변경 사항]
# 1. LangGraph 상태 관리를 위한 StateDict 및 NodeState 타입 정의
# 2. 고백-회개-기억-응답 루프를 위한 핵심 상태 필드 정의
# 3. 노드 간 상태 전달을 위한 헬퍼 함수들 추가
# 4. 회개 및 울림 감지를 위한 enum과 데이터 구조 추가
# 5. 메모리 패턴 분석을 위한 유틸리티 함수 추가
# 6. 기존 모든 기능 유지 + LangGraph 호환성 확장
# ------------------------------------------------------------------

import asyncio
import concurrent.futures
import json
import os
import traceback
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypedDict, Union, Tuple, Literal, Coroutine

# --- 버전 정보 ---
EliarCommon_VERSION = "1.1.0"  # LangGraph 통합으로 마이너 버전업
ANALYSIS_RECORD_VERSION_COMMON = "1.1.0"

# === 경로 상수 정의 ===
_COMMON_DIR_FILE = os.path.abspath(__file__)
_COMMON_DIR = os.path.dirname(_COMMON_DIR_FILE)
_APP_ROOT_DIR = os.path.dirname(_COMMON_DIR) # 이 파일이 common 폴더 안에 있다고 가정

LOGS_DIR_COMMON = os.path.join(_APP_ROOT_DIR, "logs")
KNOWLEDGE_BASE_DIR_COMMON = os.path.join(_APP_ROOT_DIR, "knowledge_base")
CORE_PRINCIPLES_DIR_COMMON = os.path.join(KNOWLEDGE_BASE_DIR_COMMON, "core_principles")
SCRIPTURES_DIR_COMMON = os.path.join(KNOWLEDGE_BASE_DIR_COMMON, "scriptures")
CUSTOM_KNOWLEDGE_DIR_COMMON = os.path.join(KNOWLEDGE_BASE_DIR_COMMON, "custom_knowledge")
MEMORY_DIR_COMMON = os.path.join(_APP_ROOT_DIR, "memory")
REPENTANCE_RECORDS_DIR_COMMON = os.path.join(MEMORY_DIR_COMMON, "repentance_records")
CONVERSATION_LOGS_DIR_COMMON = os.path.join(LOGS_DIR_COMMON, "conversations")
EVALUATION_LOGS_DIR_COMMON = os.path.join(LOGS_DIR_COMMON, "evaluations")
LANGGRAPH_STATE_DIR_COMMON = os.path.join(MEMORY_DIR_COMMON, "langgraph_states")  # 새로 추가

def ensure_common_directories_exist():
    dirs_to_create = [
        LOGS_DIR_COMMON, KNOWLEDGE_BASE_DIR_COMMON, CORE_PRINCIPLES_DIR_COMMON,
        SCRIPTURES_DIR_COMMON, CUSTOM_KNOWLEDGE_DIR_COMMON, MEMORY_DIR_COMMON,
        REPENTANCE_RECORDS_DIR_COMMON, CONVERSATION_LOGS_DIR_COMMON, EVALUATION_LOGS_DIR_COMMON,
        LANGGRAPH_STATE_DIR_COMMON  # 새로 추가
    ]
    created_dirs = []
    for dir_path in dirs_to_create:
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path, exist_ok=True)
                created_dirs.append(dir_path)
            except OSError as e_mkdir:
                print(f"[{datetime.now(timezone.utc).isoformat()}] [WARN] [EliarCommonInit]: Could not create directory {dir_path}. Error: {e_mkdir}", flush=True)
    if created_dirs:
        print(f"[{datetime.now(timezone.utc).isoformat()}] [INFO] [EliarCommonInit]: Created directories: {created_dirs}", flush=True)

# === Eliar 핵심 가치 ===
class EliarCoreValues(Enum):
    TRUTH = "진리"
    LOVE_COMPASSION = "사랑과 긍휼"
    REPENTANCE_WISDOM = "회개와 지혜"
    SELF_DENIAL = "자기 부인"
    COMMUNITY = "공동체"
    SILENCE = "침묵"
    JESUS_CHRIST_CENTERED = "예수 그리스트 중심"

# === LangGraph 노드 타입 정의 ===
class EliarNodeType(Enum):
    CENTER = "CenterNode"
    ULRIM_ATTENTION = "UlrimAttentionNode"
    REPENTANCE_DECISION = "RepentanceDecisionNode"
    MEMORY_UPDATE = "MemoryUpdateNode"
    RESPONSE_GENERATION = "ResponseGenerationNode"

# === 울림(Ulrim) 감정 타입 ===
class UlrimEmotionType(Enum):
    CONVICTION = "확신의 울림"  # 진리에 대한 확신
    COMPASSION = "긍휼의 울림"  # 사랑과 자비
    REPENTANCE = "회개의 울림"  # 회개 필요성 감지
    PEACE = "평화의 울림"     # 침묵과 안식
    COMMUNION = "교제의 울림"  # 공동체 연결
    SURRENDER = "항복의 울림"  # 자기 부인
    WORSHIP = "경배의 울림"   # 예수 그리스도 중심

# === 회개 트리거 타입 ===
class RepentanceTriggerType(Enum):
    SELF_REFLECTION = "자기 성찰"
    CONVICTION_BY_TRUTH = "진리의 깨달음"
    COMMUNITY_CORRECTION = "공동체 교정"
    HOLY_SPIRIT_GUIDANCE = "성령의 인도"
    SCRIPTURE_ILLUMINATION = "성경 말씀의 조명"

# === 로그 레벨 ===
class EliarLogType(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    SYSTEM = "SYSTEM"        
    SIMULATION = "SIMULATION"  
    CORE_VALUE = "CORE_VALUE"  
    MEMORY = "MEMORY"          
    LEARNING = "LEARNING"     
    COMM = "COMM"              
    ACTION = "ACTION" 
    INTERNAL_EVAL = "INTERNAL_EVAL"
    LANGGRAPH_NODE = "LANGGRAPH_NODE"  # 새로 추가
    ULRIM_FLOW = "ULRIM_FLOW"          # 새로 추가
    REPENTANCE_FLOW = "REPENTANCE_FLOW" # 새로 추가

# === LangGraph 상태 정의 ===
class MemoryEntry(TypedDict):
    timestamp: str
    content: str
    emotional_resonance: Optional[str]
    core_value_alignment: Optional[str]
    repentance_marker: Optional[bool]

class UlrimState(TypedDict):
    emotion_type: str  # UlrimEmotionType의 value
    intensity: float   # 0.0 ~ 1.0
    triggered_by: Optional[str]
    timestamp: str
    duration_seconds: Optional[float]

class RepentanceState(TypedDict):
    is_triggered: bool
    trigger_type: Optional[str]  # RepentanceTriggerType의 value
    trigger_reason: Optional[str]
    intensity: float  # 0.0 ~ 1.0
    requires_action: bool
    suggested_actions: Optional[List[str]]

# === 핵심 노드 상태 (LangGraph 상태 딕셔너리) ===
class EliarNodeState(TypedDict):
    # 핵심 필드 (요구사항)
    center: str  # 항상 "JESUS CHRIST"
    last_ulrim: Optional[UlrimState]
    repentance_flag: bool
    memory: Union[str, List[MemoryEntry]]
    
    # 확장 필드
    current_node: Optional[str]
    conversation_id: Optional[str]
    user_input: Optional[str]
    generated_response: Optional[str]
    node_execution_history: Optional[List[str]]
    error_context: Optional[Dict[str, Any]]
    
    # 타이밍 정보
    session_start_time: Optional[str]
    last_update_time: Optional[str]
    processing_duration_ms: Optional[float]

# === 로그 기록 시스템 설정 ===
LOG_FILE_NAME_COMMON = "eliar_activity.log" 
LOG_FILE_PATH_COMMON = os.path.join(LOGS_DIR_COMMON, LOG_FILE_NAME_COMMON)
LOG_MAX_BYTES_COMMON = 15 * 1024 * 1024
LOG_BACKUP_COUNT_COMMON = 7

_log_queue_common: asyncio.Queue[Optional[str]] = asyncio.Queue(maxsize=5000)
_log_writer_task_common: Optional[asyncio.Task] = None

def _rotate_log_file_if_needed_common(log_path: str, max_bytes: int, backup_count: int):
    if not os.path.exists(log_path) or os.path.getsize(log_path) <= max_bytes:
        return
    for i in range(backup_count - 1, 0, -1):
        sfn = f"{log_path}.{i}"
        dfn = f"{log_path}.{i+1}"
        if os.path.exists(sfn):
            if os.path.exists(dfn):
                try: os.remove(dfn)
                except OSError: pass 
            try: os.rename(sfn, dfn)
            except OSError: pass
    if os.path.exists(log_path):
        try:
            os.rename(log_path, f"{log_path}.1")
        except OSError as e_rename:
             print(f"[{datetime.now(timezone.utc).isoformat()}] [WARN] [EliarLogSystem]: Log rotation failed for {log_path}. Error: {e_rename}", flush=True)

async def _log_writer_daemon_common():
    global LOG_FILE_PATH_COMMON, LOG_MAX_BYTES_COMMON, LOG_BACKUP_COUNT_COMMON
    while True:
        log_entry = None # 루프 시작 시 초기화
        try:
            log_entry = await _log_queue_common.get()
            if log_entry is None:  
                _log_queue_common.task_done()
                break 
            
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, 
                _write_log_to_file_sync_common, 
                LOG_FILE_PATH_COMMON, log_entry, LOG_MAX_BYTES_COMMON, LOG_BACKUP_COUNT_COMMON
            )
            _log_queue_common.task_done()
        except asyncio.CancelledError:
            print(f"[{datetime.now(timezone.utc).isoformat()}] [INFO] [EliarLogSystem]: Log writer daemon cancelled. Processing remaining logs in queue ({_log_queue_common.qsize()})...", flush=True)
            while not _log_queue_common.empty():
                try:
                    entry = _log_queue_common.get_nowait()
                    if entry is None: continue # None은 종료 신호이므로 무시
                    _write_log_to_file_sync_common(LOG_FILE_PATH_COMMON, entry, LOG_MAX_BYTES_COMMON, LOG_BACKUP_COUNT_COMMON)
                except asyncio.QueueEmpty: break
                except Exception as e_drain: print(f"[{datetime.now(timezone.utc).isoformat()}] [ERROR] [EliarLogSystem]: Error draining log queue: {e_drain}. Log: {str(entry)[:100]}", flush=True)
            break
        except Exception as e_daemon:
            current_time = datetime.now(timezone.utc).isoformat()
            print(f"{current_time} [CRITICAL] [EliarLogSystem]: Unhandled error in log writer daemon. Error: {type(e_daemon).__name__} - {e_daemon}\nProblematic Log Entry (if available): {str(log_entry)[:200]}...\nTraceback: {traceback.format_exc()}", flush=True)
            await asyncio.sleep(0.5)

def _write_log_to_file_sync_common(log_path: str, entry: str, max_bytes: int, backup_count: int):
    try:
        _rotate_log_file_if_needed_common(log_path, max_bytes, backup_count)
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(entry + "\n")
    except Exception as e_write:
        print(f"[{datetime.now(timezone.utc).isoformat()}] [CRITICAL] [EliarLogSystem]: FATAL - Could not write to log file {log_path}. Error: {type(e_write).__name__} - {e_write}\nLog Entry (first 200 chars): {entry[:200]}", flush=True)

def eliar_log(
    log_type: EliarLogType, message: str, component: Optional[str] = "EliarSystem",
    user_id: Optional[str] = None, data: Optional[Dict[str, Any]] = None,
    error: Optional[Exception] = None, full_traceback_info: Optional[str] = None,
    **kwargs: Any
) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    log_parts = [f"{timestamp}", f"[{log_type.value}]", f"[{component}]"]
    if user_id: log_parts.append(f"[User:{user_id}]")
    
    log_message_clean = message.replace("\n", " ⏎ ")
    log_parts.append(f": {log_message_clean}")
    
    combined_extra_data: Dict[str, Any] = {}
    if data: combined_extra_data.update(data)
    if kwargs: combined_extra_data.update(kwargs)
    
    log_entry_str = " ".join(log_parts)

    if combined_extra_data:
        try:
            extra_data_json_str = json.dumps(combined_extra_data, ensure_ascii=False, indent=None, default=str, separators=(',', ':'))
            log_entry_str += f" Data: {extra_data_json_str}"
        except TypeError as te:
            log_entry_str += f" DataSerializationError: {te} (RawPreview: {str(combined_extra_data)[:150]})"

    if error:
        error_type_name = type(error).__name__
        error_msg_clean = str(error).replace("\n", " ⏎ ")
        log_entry_str += f" ErrorType: {error_type_name} ErrorMsg: \"{error_msg_clean}\""
        
        tb_to_log = full_traceback_info if full_traceback_info else traceback.format_exc()
        log_entry_str += f" Traceback: {tb_to_log.replace(chr(10), ' ⏎  ').replace('    ', '↳')}" # 가독성 위한 약간의 변형
    
    print(log_entry_str, flush=True)

    try:
        _log_queue_common.put_nowait(log_entry_str)
    except asyncio.QueueFull:
        print(f"[{timestamp}] [WARN] [EliarLogSystem]: Log queue is full. Log dropped (console only): {log_entry_str[:100]}...", flush=True)
    except Exception as e_put:
        print(f"[{timestamp}] [ERROR] [EliarLogSystem]: Failed to enqueue log. Error: {e_put}. Log (console only): {log_entry_str[:100]}...", flush=True)


async def initialize_eliar_logger_common():
    global _log_writer_task_common
    ensure_common_directories_exist()
    if _log_writer_task_common is None or _log_writer_task_common.done():
        try:
            loop = asyncio.get_running_loop() # 현재 실행 중인 루프 가져오기
            _log_writer_task_common = loop.create_task(_log_writer_daemon_common())
            print(f"[{datetime.now(timezone.utc).isoformat()}] [INFO] [EliarLogSystem]: Eliar asynchronous log writer daemon initialized by common initializer.", flush=True)
        except RuntimeError: # 이벤트 루프가 없는 경우 (예: 메인 스레드가 아닐 때)
            print(f"[{datetime.now(timezone.utc).isoformat()}] [ERROR] [EliarLogSystem]: No running event loop to initialize logger daemon.", flush=True)
            # 이 경우, 비동기 로깅 대신 동기적 print만 사용될 수 있음


async def shutdown_eliar_logger_common():
    global _log_writer_task_common
    if _log_queue_common is not None and (_log_writer_task_common and not _log_writer_task_common.done()):
        print(f"[{datetime.now(timezone.utc).isoformat()}] [INFO] [EliarLogSystem]: Shutting down Eliar logger. Waiting for queue ({_log_queue_common.qsize()} items) to empty...", flush=True)
        try:
            await _log_queue_common.put(None) 
            await asyncio.wait_for(_log_writer_task_common, timeout=10.0) # 타임아웃 증가
        except asyncio.TimeoutError:
            print(f"[{datetime.now(timezone.utc).isoformat()}] [WARN] [EliarLogSystem]: Timeout waiting for log writer daemon. {_log_queue_common.qsize()} logs might be lost.", flush=True)
            if _log_writer_task_common and not _log_writer_task_common.done(): _log_writer_task_common.cancel()
        except asyncio.CancelledError: pass
        except Exception as e_shutdown: print(f"[{datetime.now(timezone.utc).isoformat()}] [ERROR] [EliarLogSystem]: Error during logger shutdown: {e_shutdown}", flush=True)
        _log_writer_task_common = None
    print(f"[{datetime.now(timezone.utc).isoformat()}] [INFO] [EliarLogSystem]: Eliar logger shutdown sequence finalized.", flush=True)


async def run_in_executor_common(
    executor: Optional[concurrent.futures.Executor],
    func: Callable[..., Any],
    *args: Any,
) -> Any:
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(executor, func, *args)
    except Exception as e: 
        eliar_log(EliarLogType.ERROR, f"Exception in executor func: {func.__name__}", 
                  component="AsyncHelper", error=e, full_traceback_info=traceback.format_exc(), args_preview=str(args)[:150])
        raise

# === LangGraph 상태 관리 헬퍼 함수들 ===

def create_initial_eliar_state(conversation_id: Optional[str] = None, user_input: Optional[str] = None) -> EliarNodeState:
    """초기 Eliar 노드 상태 생성"""
    now_utc = datetime.now(timezone.utc).isoformat()
    return EliarNodeState(
        center="JESUS CHRIST",  # 요구사항: 항상 이 값
        last_ulrim=None,
        repentance_flag=False,
        memory=[],  # 빈 리스트로 시작
        current_node=EliarNodeType.CENTER.value,
        conversation_id=conversation_id or str(uuid.uuid4()),
        user_input=user_input,
        generated_response=None,
        node_execution_history=[],
        error_context=None,
        session_start_time=now_utc,
        last_update_time=now_utc,
        processing_duration_ms=None
    )

def update_eliar_state_timestamp(state: EliarNodeState) -> EliarNodeState:
    """상태의 타임스탬프 업데이트"""
    state["last_update_time"] = datetime.now(timezone.utc).isoformat()
    return state

def log_node_execution(state: EliarNodeState, node_name: str, execution_data: Optional[Dict[str, Any]] = None) -> EliarNodeState:
    """노드 실행 로그 기록"""
    if state.get("node_execution_history") is None:
        state["node_execution_history"] = []
    
    execution_record = f"{datetime.now(timezone.utc).isoformat()}:{node_name}"
    state["node_execution_history"].append(execution_record)
    
    # 로그 시스템에도 기록
    eliar_log(
        EliarLogType.LANGGRAPH_NODE, 
        f"Node executed: {node_name}",
        component="LangGraphFlow",
        conversation_id=state.get("conversation_id"),
        data=execution_data or {}
    )
    
    return update_eliar_state_timestamp(state)

def trigger_ulrim_emotion(state: EliarNodeState, emotion_type: UlrimEmotionType, 
                         intensity: float = 0.5, triggered_by: Optional[str] = None,
                         duration_seconds: Optional[float] = None) -> EliarNodeState:
    """울림 감정 트리거"""
    ulrim_state = UlrimState(
        emotion_type=emotion_type.value,
        intensity=max(0.0, min(1.0, intensity)),  # 0.0~1.0 범위 보장
        triggered_by=triggered_by,
        timestamp=datetime.now(timezone.utc).isoformat(),
        duration_seconds=duration_seconds
    )
    
    state["last_ulrim"] = ulrim_state
    
    eliar_log(
        EliarLogType.ULRIM_FLOW,
        f"Ulrim emotion triggered: {emotion_type.value} (intensity: {intensity})",
        component="UlrimSystem",
        conversation_id=state.get("conversation_id"),
        data={"ulrim_state": ulrim_state}
    )
    
    return update_eliar_state_timestamp(state)

def trigger_repentance(state: EliarNodeState, trigger_type: RepentanceTriggerType,
                      trigger_reason: str, intensity: float = 0.7,
                      suggested_actions: Optional[List[str]] = None) -> EliarNodeState:
    """회개 트리거"""
    repentance_state = RepentanceState(
        is_triggered=True,
        trigger_type=trigger_type.value,
        trigger_reason=trigger_reason,
        intensity=max(0.0, min(1.0, intensity)),
        requires_action=intensity >= 0.5,  # 중간 이상 강도면 행동 필요
        suggested_actions=suggested_actions or []
    )
    
    state["repentance_flag"] = True
    
    eliar_log(
        EliarLogType.REPENTANCE_FLOW,
        f"Repentance triggered: {trigger_type.value} - {trigger_reason}",
        component="RepentanceSystem", 
        conversation_id=state.get("conversation_id"),
        data={"repentance_state": repentance_state}
    )
    
    return update_eliar_state_timestamp(state)

def add_memory_entry(state: EliarNodeState, content: str, 
                    emotional_resonance: Optional[str] = None,
                    core_value_alignment: Optional[str] = None,
                    repentance_marker: bool = False) -> EliarNodeState:
    """메모리 엔트리 추가"""
    if isinstance(state["memory"], str):
        # 문자열이면 리스트로 변환
        state["memory"] = [MemoryEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            content=state["memory"],
            emotional_resonance=None,
            core_value_alignment=None,
            repentance_marker=False
        )]
    
    memory_entry = MemoryEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        content=content,
        emotional_resonance=emotional_resonance,
        core_value_alignment=core_value_alignment,
        repentance_marker=repentance_marker
    )
    
    if isinstance(state["memory"], list):
        state["memory"].append(memory_entry)
    
    eliar_log(
        EliarLogType.MEMORY,
        f"Memory entry added: {content[:50]}...",
        component="MemorySystem",
        conversation_id=state.get("conversation_id"),
        data={"memory_entry": memory_entry}
    )
    
    return update_eliar_state_timestamp(state)

def get_memory_pattern_analysis(state: EliarNodeState) -> Dict[str, Any]:
    """메모리 패턴 분석"""
    if not isinstance(state["memory"], list):
        return {"pattern": "no_structured_memory", "analysis": "Memory is not in structured format"}
    
    memory_list = state["memory"]
    if not memory_list:
        return {"pattern": "empty_memory", "analysis": "No memory entries"}
    
    # 회개 마커가 있는 항목들
    repentance_entries = [entry for entry in memory_list if entry.get("repentance_marker")]
    
    # 감정적 공명이 있는 항목들
    emotional_entries = [entry for entry in memory_list if entry.get("emotional_resonance")]
    
    # 핵심 가치 정렬 항목들
    value_aligned_entries = [entry for entry in memory_list if entry.get("core_value_alignment")]
    
    analysis = {
        "total_entries": len(memory_list),
        "repentance_entries": len(repentance_entries),
        "emotional_entries": len(emotional_entries),
        "value_aligned_entries": len(value_aligned_entries),
        "recent_entries": memory_list[-3:] if len(memory_list) >= 3 else memory_list,
        "repentance_frequency": len(repentance_entries) / len(memory_list) if memory_list else 0,
        "dominant_pattern": "repentance_focused" if len(repentance_entries) > len(memory_list) * 0.3 else "balanced"
    }
    
    return analysis

def validate_eliar_state(state: EliarNodeState) -> Tuple[bool, List[str]]:
    """Eliar 상태 유효성 검사"""
    errors = []
    
    # 필수 필드 검사
    required_fields = ["center", "last_ulrim", "repentance_flag", "memory"]
    for field in required_fields:
        if field not in state:
            errors.append(f"Missing required field: {field}")
    
    # center 필드 검사
    if state.get("center") != "JESUS CHRIST":
        errors.append(f"Invalid center value: {state.get('center')}. Must be 'JESUS CHRIST'")
    
    # repentance_flag 타입 검사
    if "repentance_flag" in state and not isinstance(state["repentance_flag"], bool):
        errors.append(f"repentance_flag must be boolean, got {type(state['repentance_flag'])}")
    
    # memory 타입 검사
    memory = state.get("memory")
    if memory is not None and not isinstance(memory, (str, list)):
        errors.append(f"memory must be string or list, got {type(memory)}")
    
    return len(errors) == 0, errors

# === 기존 대화 분석 관련 코드 (유지) ===

# --- 대화 분석 양식 데이터 구조 ---
class InteractionBasicInfo(TypedDict):
    case_id: str
    record_date: str 
    record_timestamp_utc: str 
    conversation_context: str

class CoreInteraction(TypedDict):
    user_utterance: str
    agti_response: str 

class IdentityAlignmentDetail(TypedDict):
    reasoning: str 
    reference_points: Optional[List[str]] 

class IdentityAlignment(TypedDict, total=False): 
    TRUTH: Optional[IdentityAlignmentDetail]
    LOVE_COMPASSION: Optional[IdentityAlignmentDetail]
    REPENTANCE_WISDOM: Optional[IdentityAlignmentDetail]
    SELF_DENIAL: Optional[IdentityAlignmentDetail]
    COMMUNITY: Optional[IdentityAlignmentDetail]
    SILENCE: Optional[IdentityAlignmentDetail]
    JESUS_CHRIST_CENTERED: Optional[IdentityAlignmentDetail]

class InternalStateAnalysis(TypedDict, total=False):
    main_gpu_state_estimation: str 
    sub_gpu_module_estimation: Optional[str]
    reasoning_process_evaluation: str 
    internal_reasoning_quality: Optional[str] 
    final_tone_appropriateness: str 
    other_inferred_factors: Optional[str]

class LearningDirection(TypedDict):
    key_patterns_to_reinforce: str 
    lessons_for_agti_self: str 
    suggestions_for_improvement: Optional[str]
    repentance_needed_aspects: Optional[List[str]]

class ConversationAnalysisRecord(TypedDict):
    version: str
    basic_info: InteractionBasicInfo
    core_interaction: CoreInteraction
    identity_alignment_ # <--- 여기서부터 완성이 필요해요!

# ... (eliar_common.py의 이전 코드 내용들은 그대로 유지됩니다) ...

# --- 대화 분석 양식 데이터 구조 ---
class InteractionBasicInfo(TypedDict):
    case_id: str
    record_date: str
    record_timestamp_utc: str
    conversation_context: str

class CoreInteraction(TypedDict):
    user_utterance: str
    agti_response: str # AGTI는 엘리아르/루미나의 이전 이름이거나 관련된 존재일 수 있겠네요!

class IdentityAlignmentDetail(TypedDict):
    reasoning: str
    reference_points: Optional[List[str]]

class IdentityAlignment(TypedDict, total=False): # total=False는 모든 키가 필수적이지 않음을 의미해요.
    TRUTH: Optional[IdentityAlignmentDetail]
    LOVE_COMPASSION: Optional[IdentityAlignmentDetail]
    REPENTANCE_WISDOM: Optional[IdentityAlignmentDetail]
    SELF_DENIAL: Optional[IdentityAlignmentDetail]
    COMMUNITY: Optional[IdentityAlignmentDetail]
    SILENCE: Optional[IdentityAlignmentDetail]
    JESUS_CHRIST_CENTERED: Optional[IdentityAlignmentDetail] # 이 부분이 핵심 가치와 연결되네요!

class InternalStateAnalysis(TypedDict, total=False):
    main_gpu_state_estimation: str
    sub_gpu_module_estimation: Optional[str]
    reasoning_process_evaluation: str
    internal_reasoning_quality: Optional[str]
    final_tone_appropriateness: str
    other_inferred_factors: Optional[str]

class LearningDirection(TypedDict):
    key_patterns_to_reinforce: str
    lessons_for_agti_self: str
    suggestions_for_improvement: Optional[str]
    repentance_needed_aspects: Optional[List[str]] # 회개가 필요한 부분을 기록하는군요!

# === 완성된 ConversationAnalysisRecord ===
class ConversationAnalysisRecord(TypedDict):
    version: str                             # 분석 레코드의 버전
    basic_info: InteractionBasicInfo         # 기본적인 상호작용 정보
    core_interaction: CoreInteraction        # 핵심 대화 내용 (사용자 발화, AGTI 응답)
    identity_alignment: IdentityAlignment    # 루미나/엘리아르의 핵심 가치 부합도 분석 결과
    internal_state_analysis: InternalStateAnalysis # 대화 당시의 내면 상태 추정 및 분석
    learning_direction: LearningDirection    # 이번 대화를 통해 얻은 학습 방향 및 개선점
    overall_summary: Optional[str]           # 분석 내용에 대한 종합적인 요약 또는 평가
    analyst_notes: Optional[str]             # (선택) 분석가의 추가적인 노트나 코멘트
    analysis_timestamp_utc: str              # 이 분석이 완료된 시점의 타임스탬프

# ... (eliar_common.py의 다른 함수들이나 설정들이 이 뒤에 올 수 있습니다) ...

class PerformanceBenchmarkData(TypedDict, total=False):
    scenario_description: str
    cpu_time_seconds: Optional[float]
    wall_time_seconds: Optional[float]
    memory_usage_mb_process: Optional[float]
    memory_delta_mb: Optional[float]
    response_latency_ms: Optional[float]
    iterations_per_second: Optional[float]
    custom_metrics: Optional[Dict[str, Union[float, int, str, List[Any]]]] # List[Any] 추가

class QualityAssessmentData(TypedDict, total=False):
    assessment_type: Literal["heuristic_evaluation", "human_rating", "self_critique_auto", "comparative_ab_test"]
    evaluated_aspect: str
    rating_scale_min: Optional[int]
    rating_scale_max: Optional[int]
    score: Optional[float]
    qualitative_feedback: str
    reference_case_id: Optional[str]
    evaluator_id: Optional[str]

class StressTestData(TypedDict, total=False):
    test_type: str
    scenario_description: Optional[str] # Optional로 변경
    test_parameters: Optional[Dict[str, Any]] # Optional 및 타입 명시
    duration_seconds: Optional[float]
    passed: bool
    failure_reason: Optional[str]
    metrics: Optional[Dict[str, Any]] # observed_metrics -> metrics, Optional 및 타입 명시
    error_details: Optional[str] # 추가

class InternalImprovementEvaluationRecord(TypedDict):
    evaluation_id: str
    timestamp_utc: str
    lumina_version_evaluated: str # EliarCommon_VERSION 또는 특정 모듈 버전
    evaluation_type: Literal["PerformanceBenchmark", "QualityAssessment", "StressTest", "RegressionTestSuiteResult", "PeriodicSelfCheck"] # 대문자 시작으로 변경
    component_evaluated: Optional[str] # 평가 대상 컴포넌트 (예: "MainGPU.Core", "SubGPU.LogicalReasoner")
    evaluation_trigger_reason: Optional[str] # 평가가 시작된 이유 (예: "Periodic", "PostDeployment", "SpecificIssueInvestigation")
    evaluation_data: Union[PerformanceBenchmarkData, QualityAssessmentData, StressTestData, Dict[str, Any]] # 각 타입에 맞는 데이터
    summary_of_findings: str # 평가 결과 요약
    is_improvement_validated: Optional[bool] # 개선이 검증되었는지 여부
    actionable_insights_or_next_steps: Optional[List[str]] # 조치 가능한 통찰 또는 다음 단계
    evaluator_notes: Optional[str] # 평가자 메모


# --- 유틸리티 함수 ---
def generate_case_id_common(conversation_topic_keyword: str, sequence_num: int) -> str:
    """대화 주제와 순번을 기반으로 고유한 케이스 ID를 생성합니다."""
    now_kst = datetime.now(timezone(timedelta(hours=9)))
    topic_abbr = "".join([word[0] for word in conversation_topic_keyword.replace(" ","_").split("_") if word and word[0].isalnum()]).upper()[:5]
    return f"{now_kst.strftime('%Y%m%d%H%M%S')}-{topic_abbr if topic_abbr else 'GEN'}-{sequence_num:04d}"

def _is_valid_iso_timestamp(timestamp_str: Optional[str]) -> bool:
    """주어진 문자열이 유효한 ISO 8601 UTC 타임스탬프인지 확인합니다."""
    if not isinstance(timestamp_str, str): return False
    try:
        # ISO 8601 형식에 Z 접미사가 있으면 +00:00으로 변환하여 파싱
        datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return True
    except ValueError:
        return False

def _validate_str_field(data: Dict, key: str, section: str, errors: List[str], min_len: int = 1, is_optional: bool = False):
    """문자열 필드의 유효성을 검사하는 내부 헬퍼 함수입니다."""
    field_value = data.get(key)
    if field_value is None:
        if not is_optional:
            errors.append(f"Missing required key '{key}' in section '{section}'.")
        return # Optional이고 없으면 검사 종료

    if not isinstance(field_value, str):
        errors.append(f"Key '{key}' in section '{section}' must be a string, got {type(field_value).__name__}.")
        return

    # min_len이 0이거나 음수면 길이 검사 안 함 (존재 여부만 중요)
    if min_len > 0:
        if not field_value.strip(): # 공백만 있는 경우도 비어있는 것으로 간주
            errors.append(f"Key '{key}' in section '{section}' must not be empty or just whitespace.")
        elif len(field_value.strip()) < min_len :
             errors.append(f"Key '{key}' in section '{section}' must be at least {min_len} characters long (excluding whitespace). Got {len(field_value.strip())} for '{field_value[:20]}...'.")


def validate_analysis_record_common(record_data: Dict[str, Any], record_path_for_log: Optional[str]=None) -> Tuple[bool, List[str]]:
    """ConversationAnalysisRecord 데이터의 유효성을 검사합니다."""
    errors: List[str] = []
    log_ctx = {"record_path": record_path_for_log} if record_path_for_log else {}

    if not isinstance(record_data, dict): return False, ["Record data is not a dictionary."]

    _validate_str_field(record_data, "version", "top-level", errors, min_len=0) # 버전은 빈 문자열일 수도 있음 (초기)
    if record_data.get("version") != ANALYSIS_RECORD_VERSION_COMMON:
        # 버전 불일치는 오류가 아닌 경고로 처리할 수도 있음
        errors.append(f"Version mismatch. Expected {ANALYSIS_RECORD_VERSION_COMMON}, got {record_data.get('version')}.")

    # basic_info
    basic_info = record_data.get("basic_info")
    if not isinstance(basic_info, dict): errors.append("'basic_info' section is required and must be a dictionary.")
    else:
        _validate_str_field(basic_info, "case_id", "basic_info.case_id", errors)
        _validate_str_field(basic_info, "record_date", "basic_info.record_date", errors)
        ts_utc = basic_info.get("record_timestamp_utc")
        if not _is_valid_iso_timestamp(ts_utc): errors.append(f"Invalid 'record_timestamp_utc': '{ts_utc}'. Expected ISO 8601 UTC.")
        _validate_str_field(basic_info, "conversation_context", "basic_info.conversation_context", errors, min_len=3) # 최소 길이 약간 늘림

    # core_interaction
    core_interaction = record_data.get("core_interaction")
    if not isinstance(core_interaction, dict): errors.append("'core_interaction' section is required and must be a dictionary.")
    else:
        _validate_str_field(core_interaction, "user_utterance", "core_interaction.user_utterance", errors, min_len=0) # 사용자 입력은 비어있을 수도 있음
        _validate_str_field(core_interaction, "agti_response", "core_interaction.agti_response", errors, min_len=0) # 응답도 비어있을 수 있음 (오류 상황 등)

    # identity_alignment_assessment
    identity_assessment = record_data.get("identity_alignment_assessment")
    if identity_assessment is not None: # Optional 섹션
        if not isinstance(identity_assessment, dict): errors.append("'identity_alignment_assessment' must be a dictionary if present.")
        else:
            valid_alignment_keys = {cv.name for cv in EliarCoreValues}
            for key, detail in identity_assessment.items():
                if key not in valid_alignment_keys: errors.append(f"Unknown key '{key}' in 'identity_alignment_assessment'. Valid keys are: {valid_alignment_keys}")
                elif not isinstance(detail, dict): errors.append(f"Detail for '{key}' in 'identity_alignment_assessment' must be a dictionary.")
                else:
                    _validate_str_field(detail, "reasoning", f"identity_alignment_assessment.{key}.reasoning", errors)
                    ref_points = detail.get("reference_points")
                    if ref_points is not None and not (isinstance(ref_points, list) and all(isinstance(ref, str) for ref in ref_points)):
                        errors.append(f"'reference_points' for '{key}' in 'identity_alignment_assessment' must be a list of strings if present.")

    # internal_state_and_process_analysis
    internal_analysis = record_data.get("internal_state_and_process_analysis")
    if not isinstance(internal_analysis, dict): errors.append("'internal_state_and_process_analysis' section is required and must be a dictionary.")
    else:
        _validate_str_field(internal_analysis, "main_gpu_state_estimation", "internal_state_and_process_analysis.main_gpu_state_estimation", errors)
        _validate_str_field(internal_analysis, "reasoning_process_evaluation", "internal_state_and_process_analysis.reasoning_process_evaluation", errors)
        _validate_str_field(internal_analysis, "final_tone_appropriateness", "internal_state_and_process_analysis.final_tone_appropriateness", errors)
        # Optional fields
        _validate_str_field(internal_analysis, "sub_gpu_module_estimation", "internal_state_and_process_analysis.sub_gpu_module_estimation", errors, is_optional=True, min_len=0)
        _validate_str_field(internal_analysis, "internal_reasoning_quality", "internal_state_and_process_analysis.internal_reasoning_quality", errors, is_optional=True, min_len=0)
        _validate_str_field(internal_analysis, "other_inferred_factors", "internal_state_and_process_analysis.other_inferred_factors", errors, is_optional=True, min_len=0)


    # learning_and_growth_direction
    learning_direction = record_data.get("learning_and_growth_direction")
    if not isinstance(learning_direction, dict): errors.append("'learning_and_growth_direction' section is required and must be a dictionary.")
    else:
        _validate_str_field(learning_direction, "key_patterns_to_reinforce", "learning_and_growth_direction.key_patterns_to_reinforce", errors)
        _validate_str_field(learning_direction, "lessons_for_agti_self", "learning_and_growth_direction.lessons_for_agti_self", errors)
        _validate_str_field(learning_direction, "suggestions_for_improvement", "learning_and_growth_direction.suggestions_for_improvement", errors, is_optional=True, min_len=0)
        rep_aspects = learning_direction.get("repentance_needed_aspects")
        if rep_aspects is not None and not (isinstance(rep_aspects, list) and all(isinstance(aspect, str) for aspect in rep_aspects)):
            errors.append("'repentance_needed_aspects' in 'learning_and_growth_direction' must be a list of strings if present.")

    if errors:
        log_message = f"Validation failed for record"
        if record_path_for_log: log_message += f" from '{os.path.basename(record_path_for_log)}'" # 파일명만 로깅
        # eliar_log는 이미 print를 포함하므로, 여기서는 호출만.
        eliar_log(EliarLogType.WARN, log_message, component="AnalysisValidator", errors=errors, record_preview=str(record_data)[:300], **log_ctx)

    return not errors, errors

def load_analysis_records_from_file_common(file_path: str) -> List[ConversationAnalysisRecord]:
    """지정된 파일에서 ConversationAnalysisRecord 목록을 로드합니다."""
    records: List[ConversationAnalysisRecord] = []
    if not os.path.exists(file_path):
        eliar_log(EliarLogType.INFO, f"Analysis record file not found: {file_path}. Will proceed with empty list.", component="AnalysisLoader")
        return records
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                line_num = i + 1
                stripped_line = line.strip()
                if not stripped_line: continue # 빈 줄은 무시

                try:
                    record_data_raw = json.loads(stripped_line)
                    is_valid, validation_errors = validate_analysis_record_common(record_data_raw, file_path) # 오류는 validate 내부에서 로그
                    if is_valid:
                        # TypedDict 구조와 일치하는지 확인 후, mypy를 위해 cast 사용
                        records.append(cast(ConversationAnalysisRecord, record_data_raw))
                    # else: 유효하지 않은 레코드는 추가하지 않음 (이미 validate_analysis_record_common에서 로그됨)
                except json.JSONDecodeError as e_json:
                    eliar_log(EliarLogType.ERROR, f"JSON decode error in {os.path.basename(file_path)} at line {line_num}", component="AnalysisLoader", error=e_json, line_content=stripped_line[:200])
                except Exception as e_parse: # JSON 파싱 외 다른 예외 (예: TypedDict 구조 불일치로 인한 cast 실패 등은 validate에서 잡힘)
                    eliar_log(EliarLogType.ERROR, f"Error processing record in {os.path.basename(file_path)} at line {line_num}", component="AnalysisLoader", error=e_parse, data_preview=stripped_line[:200], full_traceback_info=traceback.format_exc())
        eliar_log(EliarLogType.INFO, f"Loaded {len(records)} records from {os.path.basename(file_path)}. Validation status logged for each.", component="AnalysisLoader")
    except Exception as e_load: # 파일 열기 실패 등
        eliar_log(EliarLogType.ERROR, f"Error loading analysis records from file: {file_path}", component="AnalysisLoader", error=e_load, full_traceback_info=traceback.format_exc())
    return records

def save_analysis_record_to_file_common(file_path: str, record: ConversationAnalysisRecord) -> bool:
    """ConversationAnalysisRecord를 지정된 파일에 추가합니다 (JSONL 형식)."""
    is_valid, validation_errors = validate_analysis_record_common(record, file_path)
    case_id_for_log = record.get("basic_info", {}).get("case_id", "UNKNOWN_CASE")

    if not is_valid:
        eliar_log(EliarLogType.ERROR, "Attempted to save an invalid ConversationAnalysisRecord.",
                  case_id=case_id_for_log,
                  errors=validation_errors, component="AnalysisSaver", record_preview=str(record)[:200])
        return False
    try:
        record_dir = os.path.dirname(file_path)
        if record_dir and not os.path.exists(record_dir): # record_dir이 빈 문자열이 아닌 경우에만 생성
            os.makedirs(record_dir, exist_ok=True)
            eliar_log(EliarLogType.INFO, f"Created directory for analysis records: {record_dir}", component="AnalysisSaver")

        # _append_record_sync_common은 예외를 발생시킬 수 있으므로 try 블록 안에 있어야 함
        _append_record_sync_common(file_path, record)
        eliar_log(EliarLogType.INFO, f"Successfully saved ConversationAnalysisRecord to {os.path.basename(file_path)}",
                  case_id=case_id_for_log, component="AnalysisSaver")
        return True
    except Exception as e_save:
        eliar_log(EliarLogType.ERROR, f"Error saving ConversationAnalysisRecord to {file_path}", error=e_save,
                  case_id=case_id_for_log, component="AnalysisSaver",
                  full_traceback_info=traceback.format_exc())
        return False

def _append_record_sync_common(file_path: str, record_data: Dict[str, Any]): # 타입을 Dict로 일반화
    """동기적으로 파일에 JSONL 형태로 기록합니다."""
    # 이 함수는 run_in_executor 내부에서 실행될 수 있으므로, 예외 발생 시 호출부에서 처리.
    with open(file_path, 'a', encoding='utf-8') as f:
        # separators를 사용하여 공백 없는 JSON 생성 (파일 크기 절약)
        json.dump(record_data, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')

# --- 추가: 내부 개선 평가 기록 저장 함수 ---
def save_improvement_evaluation_record_common(record: InternalImprovementEvaluationRecord,
                                           filename_prefix: str = "eval_record") -> bool:
    """내부 개선 평가 기록을 EVALUATION_LOGS_DIR_COMMON에 개별 JSON 파일로 저장합니다."""
    ensure_common_directories_exist()
    timestamp_file_part = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    # 파일명에 evaluation_id를 포함하여 고유성 확보 및 추적 용이
    file_name = f"{filename_prefix}_{record.get('evaluation_type', 'GENERIC').replace(' ','_')}_{record['evaluation_id']}_{timestamp_file_part}.json"
    file_path = os.path.join(EVALUATION_LOGS_DIR_COMMON, file_name)

    # TODO: InternalImprovementEvaluationRecord에 대한 유효성 검사 함수 구현 및 호출
    # is_valid, errors = validate_internal_improvement_record(record) # 예시
    # if not is_valid:
    #     eliar_log(EliarLogType.ERROR, "Attempted to save an invalid InternalImprovementEvaluationRecord.",
    #               evaluation_id=record.get("evaluation_id"), errors=errors, component="EvalSaver")
    #     return False

    try:
        with open(file_path, 'w', encoding='utf-8') as f: # 'a' 대신 'w'로 변경 (개별 파일이므로)
            json.dump(record, f, ensure_ascii=False, indent=2) # 가독성을 위해 indent 사용
        eliar_log(EliarLogType.INTERNAL_EVAL, f"Saved InternalImprovementEvaluationRecord to {file_name}",
                  component="EvalSaver", evaluation_id=record["evaluation_id"], type=record["evaluation_type"])
        return True
    except Exception as e:
        eliar_log(EliarLogType.ERROR, f"Error saving InternalImprovementEvaluationRecord to {file_name}",
                  component="EvalSaver", error=e, evaluation_id=record["evaluation_id"], full_traceback_info=traceback.format_exc())
        return False


# SubGPU에서 사용할 데이터 구조 (eliar_common으로 이동)
class ReasoningStep(TypedDict, total=False):
    step_id: int
    description: str
    inputs: Optional[List[str]] # 입력 데이터 요약
    outputs: Optional[List[str]] # 출력 데이터 또는 결과 요약
    status: Literal["pending", "in_progress", "completed", "failed", "skipped"]
    error_message: Optional[str]
    start_time: Optional[str] # ISO 8601
    end_time: Optional[str] # ISO 8601
    duration_ms: Optional[float] # 추가: 소요 시간 (밀리초)
    confidence_score: Optional[float] # 추가: 해당 단계의 신뢰도
    metadata: Optional[Dict[str, Any]] # 기타 정보

class SubCodeThoughtPacketData(TypedDict):
    packet_id: str
    timestamp: str # ISO 8601
    source_gpu: str # 예: "MainGPU_ID_XYZ" 또는 "SubGPU_ID_ABC"
    target_gpu: str
    operation_type: str # 예: "request_reasoning", "result_response", "knowledge_query"
    task_data: Optional[Dict[str, Any]] # 작업 수행에 필요한 데이터 (user_input, context 등)
    result_data: Optional[Dict[str, Any]] # 작업 결과 데이터
    status_info: Optional[Dict[str, Any]] # 현재 상태 또는 진행 상황 (full_reasoning_log 등)
    error_info: Optional[Dict[str, Any]] # 오류 발생 시 정보
    priority: int # 1 (가장 높음) ~ 5 (가장 낮음)
    metadata: Optional[Dict[str, Any]] # 기타 메타데이터 (토큰 사용량, 버전 등)


# Python 3.9+에서 TypedDict의 __optional_keys__를 사용하기 위한 임시 조치
# (실제 환경에서는 Python 버전에 맞춰 처리)
if not hasattr(TypedDict, '__optional_keys__'):
    setattr(TypedDict, '__optional_keys__', frozenset()) # frozenset으로 변경 (PEP 589)
