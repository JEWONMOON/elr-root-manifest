# eliar_common.py
import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict, Union # Union 추가

# --- 핵심 가치 ---
class EliarCoreValues(Enum):
    TRUTH = "진리"
    LOVE_COMPASSION = "사랑과 긍휼" # "사랑"으로 명시되었으나, "사랑과 긍휼"이 더 정확한 의미 전달 가능성
    REPENTANCE_WISDOM = "회개와 지혜" # "회개"로 명시되었으나, 지혜를 통한 성장을 포함
    SELF_DENIAL = "자기부인"
    COMMUNITY = "공동체"
    SILENCE = "침묵"
    JESUS_CHRIST_CENTERED = "예수 그리스도 중심"

# --- 로그 레벨 ---
class EliarLogType(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    TRACE = "TRACE" # 상세 디버깅용

# --- 표준화된 로깅 함수 ---
def eliar_log(level: EliarLogType, 
              message: str, 
              component: str = "EliarSystem", 
              packet_id: Optional[str] = None,
              error: Optional[Exception] = None,
              **kwargs: Any):
    """
    엘리아르 시스템 전체에서 사용될 표준화된 로깅 함수입니다.
    kwargs를 통해 추가적인 구조화된 로그 정보를 전달할 수 있습니다.
    """
    timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
    log_entry = {
        "timestamp": timestamp,
        "level": level.name,
        "component": component,
        "message": message,
    }
    if packet_id:
        log_entry["packet_id"] = packet_id
    if error:
        log_entry["error_type"] = type(error).__name__
        log_entry["error_message"] = str(error)
        # traceback은 필요시 로깅 레벨에 따라 선택적으로 포함 가능 (매우 길어질 수 있음)
        # import traceback
        # log_entry["traceback"] = traceback.format_exc() if level in [EliarLogType.ERROR, EliarLogType.CRITICAL] else None
    if kwargs:
        log_entry.update(kwargs)

    # 실제 로깅 출력 (여기서는 print 사용, 실제 환경에서는 logging 라이브러리 핸들러 등으로 대체)
    # 예: logging.getLogger(component).log(getattr(logging, level.name), log_entry)
    print(f"✝️ {log_entry}")


# --- SubCode와 MainGPU 간 공유 데이터 구조 (ThoughtPacket) ---
# total=False를 사용하여 모든 키가 항상 존재하지 않을 수 있음을 명시 (선택적 필드)
class SubCodeThoughtPacketData(TypedDict, total=False):
    # 필수 기본 정보 (항상 존재해야 함)
    packet_id: str                      # 고유 패킷 ID
    conversation_id: str              # 대화 ID
    user_id: str                        # 사용자 ID
    timestamp_created: float            # 생성 타임스탬프 (time.time())

    # 입력 관련
    raw_input_text: str                 # 사용자 원본 입력
    processed_input_text: Optional[str] # SubCode 내부 처리/정제된 입력

    # 처리 과정 및 상태
    current_processing_stage: Optional[str] # 현재 처리 단계 (예: "ethical_check", "response_generation")
    processing_status_in_sub_code: Optional[str] # SubCode 처리 상태 (예: "processing", "completed", "error")
    intermediate_thoughts: List[Dict[str, Any]] # 처리 중 중간 생각/결과 (구조는 자유롭게)

    # 출력 관련
    final_output_by_sub_code: Optional[str] # SubCode가 생성한 최종 응답
    is_clarification_response: Optional[bool]   # MainGPU 필드: 이것이 명료화 요청에 대한 응답인지
    needs_clarification_questions: List[Dict[str, str]] # MainGPU 필드: 추가 질문 목록

    # 분석 및 평가 관련
    llm_analysis_summary: Optional[Dict[str, Any]]      # MainGPU 필드: LLM 분석 요약
    ethical_assessment_summary: Optional[Dict[str, Any]]# EthicalGovernor의 평가 요약
    value_alignment_score: Dict[str, Union[float, bool]]# 각 핵심 가치와의 정렬 점수 또는 상태
                                                        # 예: {"truth": 0.8, "love": 0.9, "repentance_needed": False}
    anomalies: List[Dict[str, Any]]                     # Metacognition에 의해 감지된 이상 징후
    confidence_score: Optional[float]                   # 응답/판단에 대한 신뢰도 점수

    # 학습 및 메타데이터
    learning_tags: List[str]                            # MainGPU 필드: 학습 관련 태그
    metacognitive_state_summary: Optional[Dict[str, Any]] # Metacognition 상태 요약
    ltm_retrieval_log: List[Dict[str, Any]]             # LTM 검색 결과 요약

    # 완료 시점
    timestamp_completed_by_sub_code: Optional[float]    # SubCode 처리 완료 타임스탬프 (time.time())

    # 에러 정보
    error_info: Optional[Dict[str, Any]] # 에러 발생 시 관련 정보


# --- 비동기 작업을 위한 헬퍼 (필요시 추가) ---
async def run_in_executor(executor, func, *args):
    """
    동기 함수를 비동기적으로 실행하기 위한 래퍼.
    CPU 바운드 작업을 별도의 스레드/프로세스 풀에서 실행하여 이벤트 루프 블로킹 방지.
    """
    if executor is None: # Default executor (ThreadPoolExecutor)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func, *args)
    return await asyncio.get_running_loop().run_in_executor(executor, func, *args)
