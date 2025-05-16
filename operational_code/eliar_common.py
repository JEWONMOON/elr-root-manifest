# eliar_common.py (내부 개선 평가 지원 강화 및 로직 복원 버전)
# ------------------------------------------------------------------
# [최종본 변경 사항]
# 1. 이전 답변의 모든 개선 사항 통합 (버전, 경로, Enum, 로깅, Executor, TypedDict 등)
# 2. validate_analysis_record_common: 중첩 TypedDict에 대한 유효성 검사 로직 추가 및 상세화.
# 3. load/save_analysis_records_from_file_common: 실제 파일 처리 로직 복원 및 에러 로깅 강화.
# 4. _append_record_sync_common: 파일 쓰기 로직 및 예외 처리 복원.
# 5. 주석 추가 및 코드 명료화.
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
EliarCommon_VERSION = "1.0.3"
ANALYSIS_RECORD_VERSION_COMMON = "1.0.3"

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

def ensure_common_directories_exist():
    dirs_to_create = [
        LOGS_DIR_COMMON, KNOWLEDGE_BASE_DIR_COMMON, CORE_PRINCIPLES_DIR_COMMON,
        SCRIPTURES_DIR_COMMON, CUSTOM_KNOWLEDGE_DIR_COMMON, MEMORY_DIR_COMMON,
        REPENTANCE_RECORDS_DIR_COMMON, CONVERSATION_LOGS_DIR_COMMON, EVALUATION_LOGS_DIR_COMMON
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
    JESUS_CHRIST_CENTERED = "예수 그리스도 중심"

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
    identity_alignment_assessment: Optional[IdentityAlignment]
    internal_state_and_process_analysis: InternalStateAnalysis
    learning_and_growth_direction: LearningDirection

# --- 내부 개선 평가 기록용 TypedDict ---
class PerformanceBenchmarkData(TypedDict, total=False):
    scenario_description: str 
    cpu_time_seconds: Optional[float]
    wall_time_seconds: Optional[float] 
    memory_usage_mb_process: Optional[float]
    memory_delta_mb: Optional[float]
    response_latency_ms: Optional[float]
    iterations_per_second: Optional[float]
    custom_metrics: Optional[Dict[str, Union[float, int, str]]]

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
    test_parameters: Dict[str, Any]
    duration_seconds: Optional[float]
    passed: bool 
    failure_reason: Optional[str]
    observed_metrics: Optional[Dict[str, Any]]

class InternalImprovementEvaluationRecord(TypedDict):
    evaluation_id: str 
    timestamp_utc: str 
    lumina_version_evaluated: str 
    evaluation_type: Literal["benchmark", "quality_assessment", "stress_test", "regression_test_suite_result", "periodic_self_check"] 
    component_evaluated: Optional[str]
    evaluation_trigger_reason: Optional[str]
    evaluation_data: Union[PerformanceBenchmarkData, QualityAssessmentData, StressTestData, Dict[str, Any]] 
    summary_of_findings: str 
    is_improvement_validated: Optional[bool]
    actionable_insights_or_next_steps: Optional[List[str]]
    evaluator_notes: Optional[str]


# --- 유틸리티 함수 ---
def generate_case_id_common(conversation_topic_keyword: str, sequence_num: int) -> str:
    now_kst = datetime.now(timezone(timedelta(hours=9))) 
    topic_abbr = "".join([word[0] for word in conversation_topic_keyword.replace(" ","_").split("_") if word and word[0].isalnum()]).upper()[:5]
    return f"{now_kst.strftime('%Y%m%d%H%M%S')}-{topic_abbr if topic_abbr else 'GEN'}-{sequence_num:04d}"

def _is_valid_iso_timestamp(timestamp_str: Optional[str]) -> bool:
    if not isinstance(timestamp_str, str): return False
    try:
        datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return True
    except ValueError:
        return False

def _validate_str_field(data: Dict, key: str, section: str, errors: List[str], min_len: int = 1, is_optional: bool = False):
    """ 문자열 필드 유효성 검사 (공통 헬퍼) """
    field_value = data.get(key)
    if field_value is None:
        if not is_optional:
            errors.append(f"Missing required key '{key}' in section '{section}'.")
        return # Optional이고 없으면 통과
    if not isinstance(field_value, str):
        errors.append(f"Key '{key}' in section '{section}' must be a string, got {type(field_value).__name__}.")
        return
    if min_len > 0 and not field_value.strip():
        errors.append(f"Key '{key}' in section '{section}' must not be empty or just whitespace.")
    elif len(field_value.strip()) < min_len :
         errors.append(f"Key '{key}' in section '{section}' must be at least {min_len} characters long (excluding whitespace).")


def validate_analysis_record_common(record_data: Dict[str, Any], record_path_for_log: Optional[str]=None) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    log_ctx = {"record_path": record_path_for_log} if record_path_for_log else {}

    if not isinstance(record_data, dict): return False, ["Record data is not a dictionary."]

    _validate_str_field(record_data, "version", "top-level", errors)
    if record_data.get("version") != ANALYSIS_RECORD_VERSION_COMMON:
        errors.append(f"Invalid 'version'. Expected {ANALYSIS_RECORD_VERSION_COMMON}, got {record_data.get('version')}.")

    # basic_info
    basic_info = record_data.get("basic_info")
    if not isinstance(basic_info, dict): errors.append("'basic_info' section is required and must be a dictionary.")
    else:
        _validate_str_field(basic_info, "case_id", "basic_info", errors)
        _validate_str_field(basic_info, "record_date", "basic_info", errors) # TODO: Add date format validation
        ts_utc = basic_info.get("record_timestamp_utc")
        if not _is_valid_iso_timestamp(ts_utc): errors.append(f"Invalid 'record_timestamp_utc': '{ts_utc}'. Expected ISO 8601 UTC.")
        _validate_str_field(basic_info, "conversation_context", "basic_info", errors, min_len=5)

    # core_interaction
    core_interaction = record_data.get("core_interaction")
    if not isinstance(core_interaction, dict): errors.append("'core_interaction' section is required and must be a dictionary.")
    else:
        _validate_str_field(core_interaction, "user_utterance", "core_interaction", errors)
        _validate_str_field(core_interaction, "agti_response", "core_interaction", errors)

    # identity_alignment_assessment (Optional section, but if present, validate its structure)
    identity_assessment = record_data.get("identity_alignment_assessment")
    if identity_assessment is not None:
        if not isinstance(identity_assessment, dict): errors.append("'identity_alignment_assessment' must be a dictionary if present.")
        else:
            valid_alignment_keys = {cv.name for cv in EliarCoreValues}
            for key, detail in identity_assessment.items():
                if key not in valid_alignment_keys: errors.append(f"Unknown key '{key}' in 'identity_alignment_assessment'. Valid keys are: {valid_alignment_keys}")
                elif not isinstance(detail, dict): errors.append(f"Detail for '{key}' in 'identity_alignment_assessment' must be a dictionary.")
                else:
                    _validate_str_field(detail, "reasoning", f"identity_alignment_assessment.{key}", errors)
                    ref_points = detail.get("reference_points")
                    if ref_points is not None and not (isinstance(ref_points, list) and all(isinstance(ref, str) for ref in ref_points)):
                        errors.append(f"'reference_points' for '{key}' must be a list of strings if present.")
    
    # internal_state_and_process_analysis
    internal_analysis = record_data.get("internal_state_and_process_analysis")
    if not isinstance(internal_analysis, dict): errors.append("'internal_state_and_process_analysis' section is required and must be a dictionary.")
    else:
        _validate_str_field(internal_analysis, "main_gpu_state_estimation", "internal_state_and_process_analysis", errors)
        _validate_str_field(internal_analysis, "reasoning_process_evaluation", "internal_state_and_process_analysis", errors)
        _validate_str_field(internal_analysis, "final_tone_appropriateness", "internal_state_and_process_analysis", errors)
        _validate_str_field(internal_analysis, "sub_gpu_module_estimation", "internal_state_and_process_analysis", errors, is_optional=True)
        _validate_str_field(internal_analysis, "internal_reasoning_quality", "internal_state_and_process_analysis", errors, is_optional=True)
        _validate_str_field(internal_analysis, "other_inferred_factors", "internal_state_and_process_analysis", errors, is_optional=True)

    # learning_and_growth_direction
    learning_direction = record_data.get("learning_and_growth_direction")
    if not isinstance(learning_direction, dict): errors.append("'learning_and_growth_direction' section is required and must be a dictionary.")
    else:
        _validate_str_field(learning_direction, "key_patterns_to_reinforce", "learning_and_growth_direction", errors)
        _validate_str_field(learning_direction, "lessons_for_agti_self", "learning_and_growth_direction", errors)
        _validate_str_field(learning_direction, "suggestions_for_improvement", "learning_and_growth_direction", errors, is_optional=True)
        rep_aspects = learning_direction.get("repentance_needed_aspects")
        if rep_aspects is not None and not (isinstance(rep_aspects, list) and all(isinstance(aspect, str) for aspect in rep_aspects)):
            errors.append("'repentance_needed_aspects' must be a list of strings if present.")

    if errors:
        log_message = f"Validation failed for record"
        if record_path_for_log: log_message += f" from '{record_path_for_log}'"
        eliar_log(EliarLogType.WARN, log_message, component="AnalysisValidator", errors=errors, record_preview=str(record_data)[:300], **log_ctx) # type: ignore
    
    return not errors, errors

def load_analysis_records_from_file_common(file_path: str) -> List[ConversationAnalysisRecord]:
    records: List[ConversationAnalysisRecord] = []
    if not os.path.exists(file_path):
        eliar_log(EliarLogType.INFO, f"Analysis record file not found: {file_path}. Will proceed with empty list.", component="AnalysisLoader")
        return records
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                line_num = i + 1
                stripped_line = line.strip()
                if not stripped_line: continue

                try:
                    record_data_raw = json.loads(stripped_line)
                    # 타입 캐스팅 시도는 하지 않고, 구조만 검증 후 사용
                    is_valid, _ = validate_analysis_record_common(record_data_raw, file_path) # 오류는 validate 내부에서 로그
                    if is_valid:
                        records.append(cast(ConversationAnalysisRecord, record_data_raw)) # 검증 통과시 캐스팅 (mypy용)
                except json.JSONDecodeError as e_json:
                    eliar_log(EliarLogType.ERROR, f"JSON decode error in {file_path} at line {line_num}", component="AnalysisLoader", error=e_json, line_content=stripped_line[:200])
                except Exception as e_parse: 
                    eliar_log(EliarLogType.ERROR, f"Error parsing record in {file_path} at line {line_num}", component="AnalysisLoader", error=e_parse, data_preview=stripped_line[:200], full_traceback_info=traceback.format_exc())
        eliar_log(EliarLogType.INFO, f"Loaded {len(records)} records from {file_path}. Validation status logged for each.", component="AnalysisLoader")
    except Exception as e_load:
        eliar_log(EliarLogType.ERROR, f"Error loading analysis records from file: {file_path}", component="AnalysisLoader", error=e_load, full_traceback_info=traceback.format_exc())
    return records

def save_analysis_record_to_file_common(file_path: str, record: ConversationAnalysisRecord) -> bool:
    is_valid, validation_errors = validate_analysis_record_common(record, file_path)
    if not is_valid:
        eliar_log(EliarLogType.ERROR, "Attempted to save an invalid ConversationAnalysisRecord.",
                  case_id=record.get("basic_info", {}).get("case_id", "UNKNOWN_CASE"),
                  errors=validation_errors, component="AnalysisSaver", record_preview=str(record)[:200])
        return False
    try:
        record_dir = os.path.dirname(file_path)
        if not os.path.exists(record_dir):
            os.makedirs(record_dir, exist_ok=True)
            eliar_log(EliarLogType.INFO, f"Created directory for analysis records: {record_dir}", component="AnalysisSaver")

        _append_record_sync_common(file_path, record)
        eliar_log(EliarLogType.INFO, f"Successfully saved ConversationAnalysisRecord to {file_path}",
                  case_id=record.get("basic_info", {}).get("case_id"), component="AnalysisSaver")
        return True
    except Exception as e_save:
        eliar_log(EliarLogType.ERROR, f"Error saving ConversationAnalysisRecord to {file_path}", error=e_save,
                  case_id=record.get("basic_info", {}).get("case_id", "UNKNOWN_CASE"), component="AnalysisSaver",
                  full_traceback_info=traceback.format_exc())
        return False

def _append_record_sync_common(file_path: str, record: ConversationAnalysisRecord):
    """ 동기적으로 파일에 JSONL 형태로 기록. 성공/실패는 호출부에서 판단/로깅. """
    # 이 함수는 run_in_executor 내부에서 실행되므로, 예외 발생 시 run_in_executor가 처리함.
    # 따라서 여기서는 예외를 그대로 전파.
    with open(file_path, 'a', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, separators=(',', ':')) # 더 간결한 JSON
        f.write('\n')

# --- 추가: 내부 개선 평가 기록 저장 함수 (예시) ---
def save_improvement_evaluation_record_common(record: InternalImprovementEvaluationRecord, 
                                           filename_prefix: str = "eval_record") -> bool:
    """ 내부 개선 평가 기록을 EVALUATION_LOGS_DIR_COMMON에 저장합니다. """
    ensure_common_directories_exist() # 디렉토리 존재 확인
    timestamp_file_part = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    file_path = os.path.join(EVALUATION_LOGS_DIR_COMMON, f"{filename_prefix}_{timestamp_file_part}_{record['evaluation_id']}.jsonl")
    
    # TODO: InternalImprovementEvaluationRecord에 대한 유효성 검사 함수 추가 및 호출
    # is_valid, errors = validate_internal_improvement_record(record)
    # if not is_valid:
    #     eliar_log(EliarLogType.ERROR, "Invalid InternalImprovementEvaluationRecord", errors=errors, component="EvalSaver")
    #     return False
        
    try:
        with open(file_path, 'a', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2) # 가독성을 위해 indent 사용
            f.write('\n') # JSONL이 아니어도 되지만, 일관성을 위해
        eliar_log(EliarLogType.INTERNAL_EVAL, f"Saved InternalImprovementEvaluationRecord to {file_path}", 
                  component="EvalSaver", evaluation_id=record["evaluation_id"], type=record["evaluation_type"])
        return True
    except Exception as e:
        eliar_log(EliarLogType.ERROR, f"Error saving InternalImprovementEvaluationRecord to {file_path}", 
                  component="EvalSaver", error=e, evaluation_id=record["evaluation_id"], full_traceback_info=traceback.format_exc())
        return False

# Python 3.9+에서 TypedDict의 __optional_keys__를 사용하기 위한 임시 조치
# (실제 환경에서는 Python 버전에 맞춰 처리)
if not hasattr(TypedDict, '__optional_keys__'):
    setattr(TypedDict, '__optional_keys__', set())

# cast import (validate_analysis_record_common 에서 사용)
from typing import cast
