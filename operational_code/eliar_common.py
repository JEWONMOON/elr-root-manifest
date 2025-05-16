# eliar_common.py (내부 개선 평가 지원 강화 및 로직 복원, 추가 오류 수정 버전)
# ------------------------------------------------------------------
# [최종본 변경 사항]
# 1. 이전 답변의 모든 개선 사항 통합 (버전, 경로, Enum, 로깅, Executor, TypedDict 등)
# 2. validate_analysis_record_common: 중첩 TypedDict에 대한 유효성 검사 로직 추가 및 상세화.
# 3. load/save_analysis_records_from_file_common: 실제 파일 처리 로직 복원 및 에러 로깅 강화.
# 4. _append_record_sync_common: 파일 쓰기 로직 및 예외 처리 복원.
# 5. eliar_log 함수 개선: kwargs 처리, 트레이스백 핸들링, 직렬화 오류 처리.
# 6. _log_writer_daemon_common, _rotate_log_file_if_needed_common 오류 처리 강화.
# 7. 경로 상수 정의 방식 개선 및 디렉토리 생성 로직 강화.
# 8. 로거 초기화 및 종료 로직 개선.
# 9. TypedDict 정의 명확화 (StressTestData).
# 10. 기타 주석 추가 및 코드 명료화.
# ------------------------------------------------------------------

import asyncio
import concurrent.futures
import json
import os
import traceback
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypedDict, Union, Tuple, Literal, Coroutine, cast

# --- 버전 정보 ---
EliarCommon_VERSION = "1.0.4" # 버전 업데이트
ANALYSIS_RECORD_VERSION_COMMON = "1.0.4" # 버전 업데이트

# === 경로 상수 정의 ===
_COMMON_DIR_FILE = os.path.abspath(__file__)
_COMMON_DIR = os.path.dirname(_COMMON_DIR_FILE)
# 가정: eliar_common.py는 프로젝트 루트의 'common' 또는 'utils' 같은 하위 폴더에 위치.
# 만약 eliar_common.py가 프로젝트 루트에 있다면 _APP_ROOT_DIR = _COMMON_DIR
_APP_ROOT_DIR = os.path.dirname(_COMMON_DIR) if os.path.basename(_COMMON_DIR) != "" else _COMMON_DIR


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
    """필요한 공용 디렉토리들이 존재하는지 확인하고 없으면 생성합니다."""
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
                # 로거가 아직 초기화되지 않았을 수 있으므로 print 사용
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
    TEST_RESULT = "TEST_RESULT" # 테스트 결과용 추가

# === 로그 기록 시스템 설정 ===
LOG_FILE_NAME_COMMON = "eliar_activity.log"
LOG_FILE_PATH_COMMON = os.path.join(LOGS_DIR_COMMON, LOG_FILE_NAME_COMMON)
LOG_MAX_BYTES_COMMON = 15 * 1024 * 1024  # 15MB
LOG_BACKUP_COUNT_COMMON = 7

_log_queue_common: asyncio.Queue[Optional[str]] = asyncio.Queue(maxsize=5000)
_log_writer_task_common: Optional[asyncio.Task] = None

def _rotate_log_file_if_needed_common(log_path: str, max_bytes: int, backup_count: int):
    """로그 파일 크기가 임계값을 넘으면 로테이션을 수행합니다."""
    if not os.path.exists(log_path) or os.path.getsize(log_path) <= max_bytes:
        return
    try:
        for i in range(backup_count - 1, 0, -1):
            sfn = f"{log_path}.{i}"
            dfn = f"{log_path}.{i+1}"
            if os.path.exists(sfn):
                if os.path.exists(dfn):
                    try: os.remove(dfn)
                    except OSError: pass # 실패해도 계속 진행
                try: os.rename(sfn, dfn)
                except OSError: pass # 실패해도 계속 진행
        if os.path.exists(log_path):
            try:
                os.rename(log_path, f"{log_path}.1")
            except OSError as e_rename:
                 print(f"[{datetime.now(timezone.utc).isoformat()}] [WARN] [EliarLogSystem]: Log rotation failed for {log_path}. Error: {e_rename}", flush=True)
    except Exception as e_rotate_generic:
        print(f"[{datetime.now(timezone.utc).isoformat()}] [ERROR] [EliarLogSystem]: Unexpected error during log rotation for {log_path}. Error: {e_rotate_generic}", flush=True)


async def _log_writer_daemon_common():
    """백그라운드에서 로그 큐의 항목을 파일에 비동기적으로 기록하는 데몬입니다."""
    global LOG_FILE_PATH_COMMON, LOG_MAX_BYTES_COMMON, LOG_BACKUP_COUNT_COMMON
    while True:
        log_entry: Optional[str] = None # 루프 시작 시 초기화
        try:
            log_entry = await _log_queue_common.get()
            if log_entry is None: # 종료 신호
                _log_queue_common.task_done()
                break

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, # 기본 ThreadPoolExecutor 사용
                _write_log_to_file_sync_common,
                LOG_FILE_PATH_COMMON, log_entry, LOG_MAX_BYTES_COMMON, LOG_BACKUP_COUNT_COMMON
            )
            _log_queue_common.task_done()
        except asyncio.CancelledError:
            print(f"[{datetime.now(timezone.utc).isoformat()}] [INFO] [EliarLogSystem]: Log writer daemon cancelled. Processing remaining logs in queue ({_log_queue_common.qsize()})...", flush=True)
            # 취소 시 남은 로그 처리
            while not _log_queue_common.empty():
                try:
                    entry = _log_queue_common.get_nowait()
                    if entry is None: continue
                    _write_log_to_file_sync_common(LOG_FILE_PATH_COMMON, entry, LOG_MAX_BYTES_COMMON, LOG_BACKUP_COUNT_COMMON)
                except asyncio.QueueEmpty:
                    break
                except Exception as e_drain:
                    print(f"[{datetime.now(timezone.utc).isoformat()}] [ERROR] [EliarLogSystem]: Error draining log queue: {e_drain}. Log: {str(entry)[:100]}", flush=True)
            break # 데몬 종료
        except Exception as e_daemon:
            current_time = datetime.now(timezone.utc).isoformat()
            # 데몬 자체의 심각한 오류는 print로 직접 출력
            print(f"{current_time} [CRITICAL] [EliarLogSystem]: Unhandled error in log writer daemon. Error: {type(e_daemon).__name__} - {e_daemon}\nProblematic Log Entry (if available): {str(log_entry)[:200]}...\nTraceback: {traceback.format_exc()}", flush=True)
            await asyncio.sleep(0.5) # 빠른 재시도 방지

def _write_log_to_file_sync_common(log_path: str, entry: str, max_bytes: int, backup_count: int):
    """동기적으로 로그 항목을 파일에 기록하고 필요시 로테이션합니다."""
    try:
        _rotate_log_file_if_needed_common(log_path, max_bytes, backup_count)
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(entry + "\n")
    except Exception as e_write:
        # 파일 쓰기 실패는 매우 심각한 상황이므로 print로 강력하게 알림
        print(f"[{datetime.now(timezone.utc).isoformat()}] [CRITICAL] [EliarLogSystem]: FATAL - Could not write to log file {log_path}. Error: {type(e_write).__name__} - {e_write}\nLog Entry (first 200 chars): {entry[:200]}", flush=True)

def eliar_log(
    log_type: EliarLogType, message: str, component: Optional[str] = "EliarSystem",
    user_id: Optional[str] = None, data: Optional[Dict[str, Any]] = None,
    error: Optional[Exception] = None, full_traceback_info: Optional[str] = None,
    final_log: bool = False, # 로거 종료 직전 강제 flush 위한 플래그
    **kwargs: Any
) -> None:
    """Eliar 시스템 전역에서 사용되는 표준 로깅 함수입니다."""
    timestamp = datetime.now(timezone.utc).isoformat()
    log_parts = [f"{timestamp}", f"[{log_type.value}]", f"[{component}]"]
    if user_id: log_parts.append(f"[User:{user_id}]")

    log_message_clean = message.replace("\n", " ⏎ ") # 개행문자 변경
    log_parts.append(f": {log_message_clean}")

    combined_extra_data: Dict[str, Any] = {}
    if data: combined_extra_data.update(data)
    if kwargs: combined_extra_data.update(kwargs) # kwargs를 data에 병합

    log_entry_str = " ".join(log_parts)

    if combined_extra_data:
        try:
            # default=str 추가하여 datetime 등 직렬화 불가능 객체 처리
            extra_data_json_str = json.dumps(combined_extra_data, ensure_ascii=False, indent=None, default=str, separators=(',', ':'))
            log_entry_str += f" Data: {extra_data_json_str}"
        except TypeError as te:
            log_entry_str += f" DataSerializationError: {te} (RawPreview: {str(combined_extra_data)[:150]})"
        except Exception as e_json_dump: # 기타 JSON 직렬화 오류
            log_entry_str += f" DataUnexpectedSerializationError: {e_json_dump} (RawPreview: {str(combined_extra_data)[:150]})"


    if error:
        error_type_name = type(error).__name__
        error_msg_clean = str(error).replace("\n", " ⏎ ")
        log_entry_str += f" ErrorType: {error_type_name} ErrorMsg: \"{error_msg_clean}\""

        # full_traceback_info가 제공되면 그것을 사용, 아니면 현재 예외의 트레이스백 생성
        tb_to_log = full_traceback_info if full_traceback_info else traceback.format_exc()
        # 트레이스백 문자열에서 개행과 공백을 정리하여 한 줄로 표시되도록 시도
        tb_to_log_clean = tb_to_log.replace(chr(10), ' ⏎  ').replace('    ', '↳')
        log_entry_str += f" Traceback: {tb_to_log_clean}"

    # 최종 로그는 즉시 print (큐에 넣지 않음 - 로거 종료 시 사용)
    if final_log:
        print(log_entry_str, flush=True)
        # 필요시 파일에도 직접 기록 (동기적으로)
        if _log_writer_task_common: # 데몬이 실행 중이었다면 파일에도 기록 시도
             _write_log_to_file_sync_common(LOG_FILE_PATH_COMMON, log_entry_str, LOG_MAX_BYTES_COMMON, LOG_BACKUP_COUNT_COMMON)
        return

    # 일반 로그는 콘솔에 먼저 출력 후 큐에 추가
    print(log_entry_str, flush=True)

    if _log_queue_common is not None: # 큐가 초기화되었는지 확인
        try:
            _log_queue_common.put_nowait(log_entry_str)
        except asyncio.QueueFull:
            # 큐가 가득 찼을 경우의 처리 (콘솔에는 이미 출력됨)
            print(f"[{timestamp}] [WARN] [EliarLogSystem]: Log queue is full. Log dropped from file log (console only): {log_entry_str[:100]}...", flush=True)
        except Exception as e_put: # 큐에 넣는 중 다른 예외 발생
            print(f"[{timestamp}] [ERROR] [EliarLogSystem]: Failed to enqueue log. Error: {e_put}. Log (console only): {log_entry_str[:100]}...", flush=True)
    else: # 로거가 아직 완전히 초기화되지 않은 경우
        print(f"[{timestamp}] [WARN] [EliarLogSystem]: Log queue not available. Log (console only): {log_entry_str[:100]}...", flush=True)


async def initialize_eliar_logger_common():
    """Eliar 비동기 로거 시스템을 초기화합니다."""
    global _log_writer_task_common
    ensure_common_directories_exist() # 디렉토리 먼저 생성

    if _log_writer_task_common is None or _log_writer_task_common.done():
        try:
            loop = asyncio.get_running_loop()
            _log_writer_task_common = loop.create_task(_log_writer_daemon_common())
            print(f"[{datetime.now(timezone.utc).isoformat()}] [INFO] [EliarLogSystem]: Eliar asynchronous log writer daemon initialized by common initializer.", flush=True)
        except RuntimeError: # 이벤트 루프가 없는 경우
            print(f"[{datetime.now(timezone.utc).isoformat()}] [ERROR] [EliarLogSystem]: No running event loop to initialize logger daemon. Logging will be console-only until an event loop is available.", flush=True)
            _log_writer_task_common = None # 명시적으로 None 설정


async def shutdown_eliar_logger_common():
    """Eliar 로거 시스템을 정상적으로 종료합니다. 큐에 남은 로그를 처리합니다."""
    global _log_writer_task_common
    shutdown_timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{shutdown_timestamp}] [INFO] [EliarLogSystem]: Initiating Eliar logger shutdown...", flush=True)

    if _log_queue_common is not None and _log_writer_task_common is not None and not _log_writer_task_common.done():
        q_size_before_signal = _log_queue_common.qsize()
        print(f"[{shutdown_timestamp}] [INFO] [EliarLogSystem]: Sending shutdown signal to log writer. Queue size: {q_size_before_signal}", flush=True)
        try:
            await _log_queue_common.put(None) # 종료 신호 전송
            # 데몬이 종료될 때까지 대기 (타임아웃 설정)
            await asyncio.wait_for(_log_writer_task_common, timeout=10.0)
            print(f"[{datetime.now(timezone.utc).isoformat()}] [INFO] [EliarLogSystem]: Log writer daemon confirmed shutdown. Remaining queue size: {_log_queue_common.qsize()}", flush=True)
        except asyncio.TimeoutError:
            print(f"[{datetime.now(timezone.utc).isoformat()}] [WARN] [EliarLogSystem]: Timeout waiting for log writer daemon to complete. {_log_queue_common.qsize()} logs might be lost.", flush=True)
            if _log_writer_task_common and not _log_writer_task_common.done():
                _log_writer_task_common.cancel() # 강제 취소
                try:
                    await _log_writer_task_common # 취소 완료 대기
                except asyncio.CancelledError:
                    print(f"[{datetime.now(timezone.utc).isoformat()}] [INFO] [EliarLogSystem]: Log writer task successfully cancelled after timeout.", flush=True)
                except Exception as e_cancel_wait: # 취소 대기 중 다른 예외
                    print(f"[{datetime.now(timezone.utc).isoformat()}] [ERROR] [EliarLogSystem]: Error waiting for cancelled log writer: {e_cancel_wait}", flush=True)
        except asyncio.CancelledError: # shutdown_eliar_logger 자체가 취소된 경우
            print(f"[{datetime.now(timezone.utc).isoformat()}] [WARN] [EliarLogSystem]: Logger shutdown process was cancelled.", flush=True)
        except Exception as e_shutdown:
            print(f"[{datetime.now(timezone.utc).isoformat()}] [ERROR] [EliarLogSystem]: Error during logger shutdown: {e_shutdown}", flush=True)
    elif _log_writer_task_common and _log_writer_task_common.done():
        print(f"[{shutdown_timestamp}] [INFO] [EliarLogSystem]: Log writer daemon was already done.", flush=True)
    else:
        print(f"[{shutdown_timestamp}] [INFO] [EliarLogSystem]: Log writer daemon was not active or queue not initialized.", flush=True)
    
    _log_writer_task_common = None # 태스크 참조 제거
    # 최종 종료 로그는 eliar_log의 final_log=True를 통해 직접 파일에 기록될 수 있음 (필요시 호출부에서)
    print(f"[{datetime.now(timezone.utc).isoformat()}] [INFO] [EliarLogSystem]: Eliar logger shutdown sequence finalized.", flush=True)


async def run_in_executor_common(
    executor: Optional[concurrent.futures.Executor], # None이면 기본 ThreadPoolExecutor 사용
    func: Callable[..., Any],
    *args: Any,
) -> Any:
    """주어진 함수를 지정된 Executor 또는 기본 Executor에서 비동기적으로 실행합니다."""
    loop = asyncio.get_running_loop()
    try:
        # executor가 None이면 asyncio의 기본 ThreadPoolExecutor를 사용합니다.
        return await loop.run_in_executor(executor, func, *args)
    except Exception as e:
        # 여기서 eliar_log를 호출하면 순환 의존 또는 로거 미초기화 문제가 발생할 수 있으므로 주의.
        # 대신 print로 직접 에러를 출력하거나, 에러를 그대로 raise하여 호출부에서 처리하도록 함.
        print(f"[{datetime.now(timezone.utc).isoformat()}] [ERROR] [AsyncHelper]: Exception in executor func: {func.__name__}. Error: {e}. Args: {str(args)[:150]}\nTraceback: {traceback.format_exc()}", flush=True)
        raise # 오류를 다시 발생시켜 호출부에서 인지하도록 함


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

