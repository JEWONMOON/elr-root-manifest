# Main_gpu.py (eliar_common.py 적용, 클래스 정의 복원 및 호환성 개선 최종 버전)

# Sub_code.py(sub_gpu.py) 와의 연동 시 PyTorch 객체가 오갈 수 있으므로 유지 (선택적, 현재 데이터 구조에서는 직접적 의존성 낮음)
# import torch 
import numpy as np # 일반적인 데이터 처리
import os
import random # DummySubCodeInterfaceForMainTest 등에서 사용
# import time # datetime으로 대체 또는 필요한 경우 유지
import json
import asyncio
import concurrent.futures # 기존 의존성 유지
import aiohttp # 기존 의존성 유지
import base64 # 기존 의존성 유지
from datetime import datetime, timezone # datetime 표준 임포트
import re # 필요시 사용
import uuid # packet_id 생성용
import traceback # 상세 에러 로깅용

from typing import List, Dict, Any, Optional, Tuple, Callable, Deque # TypedDict는 eliar_common에서 가져옴
from collections import deque # conversation_history 용

# --- 공용 모듈 임포트 ---
from eliar_common import (
    EliarCoreValues,
    EliarLogType,
    SubCodeThoughtPacketData, # 표준화된 데이터 구조
    eliar_log # 표준화된 로깅 함수
)

# --- Main GPU 버전 및 기본 설정 ---
Eliar_VERSION = "v24.1_MainGPU_FullClass_Compat" # 버전 업데이트
COMPONENT_NAME_MAIN_GPU_CORE = "MainGPU.EliarCore"
COMPONENT_NAME_COMMUNICATOR = "MainGPU.Communicator"
COMPONENT_NAME_SYSTEM_STATUS = "MainGPU.SystemStatus"
COMPONENT_NAME_VIRTUE_ETHICS = "MainGPU.VirtueEthics"
COMPONENT_NAME_MAIN_SIM = "MainGPU.ConversationSim"
COMPONENT_NAME_ENTRY_POINT = "MainGPU.EntryPoint"


# --- GitHub API 설정 (기존 코드에서 로깅 함수 변경) ---
GITHUB_API_REPO_URL = "https://api.github.com/repos/JEWONMOON/elr-root-manifest/contents"
ELIAR_GITHUB_PAT = os.getenv("ELIAR_GITHUB_PAT")
GITHUB_HEADERS = {"Accept": "application/vnd.github.v3+json"}
if ELIAR_GITHUB_PAT:
    GITHUB_HEADERS["Authorization"] = f"token {ELIAR_GITHUB_PAT}"
    eliar_log(EliarLogType.INFO, f"GitHub PAT loaded (Eliar {Eliar_VERSION}). GitHub commit enabled.", component=COMPONENT_NAME_MAIN_GPU_CORE)
else:
    eliar_log(EliarLogType.WARN, f"Environment variable 'ELIAR_GITHUB_PAT' not found. GitHub commit functionality will be limited.", component=COMPONENT_NAME_MAIN_GPU_CORE)

# --- 로컬 캐시 및 로그 디렉토리 ---
CACHE_DIR = "cached_manifests_main"
LOG_DIR = f"logs_Eliar_MainGPU_{Eliar_VERSION}"

# --- 상수 정의 ---
DEFAULT_FREQUENCY = 433.33
DEFAULT_TAU_FACTOR = 0.98
DEFAULT_BASE_FACTOR = 0.1
NUM_ATTRIBUTES = 12 
SEED = 42 # 예시: random.seed(SEED)

# --- 매니페스트 경로 ---
IDENTITY_MANIFEST_PATH = "manifests/identity_manifest.json"
ULRIM_MANIFEST_PATH = "manifests/ulrim_manifest_main_gpu.json"
EVOLUTION_MANIFEST_PATH = "manifests/evolution_manifest.json"
MAINTENANCE_MANIFEST_PATH = "manifests/maintenance_manifest.json"

BACKGROUND_LOOP_INTERVAL_SECONDS = 0.1
MAINTENANCE_INTERVAL_SECONDS = 60.0

# --- 유틸리티 함수 ---
def ensure_log_dir():
    if not os.path.exists(LOG_DIR):
        try:
            os.makedirs(LOG_DIR)
            eliar_log(EliarLogType.INFO, f"Log directory created: {LOG_DIR}", component=COMPONENT_NAME_MAIN_GPU_CORE)
        except Exception as e:
            eliar_log(EliarLogType.ERROR, f"Failed to create log directory: {LOG_DIR}", component=COMPONENT_NAME_MAIN_GPU_CORE, error=e)

# -----------------------------------------------------------------------------
# Main-Sub Code 연동 클래스 (클래스 정의 추가)
# -----------------------------------------------------------------------------
class MainSubInterfaceCommunicator:
    def __init__(self, ulrim_manifest_path_for_main: str = ULRIM_MANIFEST_PATH):
        self.ulrim_manifest_path = ulrim_manifest_path_for_main
        self.pending_sub_code_tasks: Dict[str, asyncio.Event] = {}
        self.sub_code_task_results: Dict[str, Optional[SubCodeThoughtPacketData]] = {}
        self.sub_code_interface: Optional[Any] = None # 실제 SubCode(sub_gpu.py의 SubGPUModule 인스턴스)
        self._ensure_ulrim_manifest_file_exists()
        eliar_log(EliarLogType.INFO, "MainSubInterfaceCommunicator initialized.", component=COMPONENT_NAME_COMMUNICATOR)

    def _ensure_ulrim_manifest_file_exists(self):
        try:
            manifest_dir = os.path.dirname(self.ulrim_manifest_path)
            if manifest_dir and not os.path.exists(manifest_dir):
                os.makedirs(manifest_dir, exist_ok=True)
            
            if not os.path.exists(self.ulrim_manifest_path):
                initial_manifest = {
                    "schema_version": "1.5_common_eliar_full_compat", 
                    "main_gpu_version": Eliar_VERSION,
                    "sub_code_interactions_log": [],
                    "last_sub_code_communication": None,
                    "core_values_definition_source": f"eliar_common.EliarCoreValues (MainGPU: {Eliar_VERSION})", 
                    "system_alerts_from_main": []
                }
                with open(self.ulrim_manifest_path, "w", encoding="utf-8") as f:
                    json.dump(initial_manifest, f, ensure_ascii=False, indent=4)
                eliar_log(EliarLogType.INFO, f"Initial Ulrim Manifest file created: {self.ulrim_manifest_path}", component=COMPONENT_NAME_COMMUNICATOR)
        except Exception as e:
            eliar_log(EliarLogType.ERROR, "Error during Ulrim Manifest file creation/check.", component=COMPONENT_NAME_COMMUNICATOR, error=e)

    def register_sub_code_interface(self, sub_code_interface_obj: Any, main_controller_ref: 'Eliar'): # Main Eliar 컨트롤러 참조 추가
        """ 
        Sub_code.py의 메인 인터페이스 객체를 등록하고, 
        SubCode가 MainGPU의 기능(예: 평가함수, 콜백)에 접근할 수 있도록 MainController 참조를 전달합니다.
        """
        self.sub_code_interface = sub_code_interface_obj
        if hasattr(self.sub_code_interface, "link_main_gpu_coordinator"):
            try:
                # SubGPUModule.link_main_gpu_coordinator(main_gpu_controller_instance: Eliar, main_gpu_response_handler_callback: Callable)
                # 위와 같이 SubGPUModule이 Eliar 인스턴스와 이 Communicator의 콜백 핸들러를 모두 받도록 변경
                asyncio.create_task(self.sub_code_interface.link_main_gpu_coordinator(main_controller_ref, self.sub_code_response_handler))
                eliar_log(EliarLogType.INFO, "SubCode interface registered; link_main_gpu_coordinator called with MainController and response_handler.", component=COMPONENT_NAME_COMMUNICATOR)
            except Exception as e:
                eliar_log(EliarLogType.ERROR, "Error calling link_main_gpu_coordinator on SubCode interface.", component=COMPONENT_NAME_COMMUNICATOR, error=e)
        else:
            eliar_log(EliarLogType.WARN, "SubCode interface lacks 'link_main_gpu_coordinator'. Full linking might fail.", component=COMPONENT_NAME_COMMUNICATOR)

    async def send_task_to_sub_code(self, task_type: str, task_data: Dict[str, Any]) -> Optional[str]:
        if not self.sub_code_interface:
            eliar_log(EliarLogType.ERROR, "SubCode interface not registered. Cannot send task.", component=COMPONENT_NAME_COMMUNICATOR, task_type=task_type)
            return None

        packet_id = task_data.get("packet_id")
        if not packet_id:
            packet_id = str(uuid.uuid4())
            task_data["packet_id"] = packet_id
            eliar_log(EliarLogType.DEBUG, f"New Packet ID generated by MainGPU: {packet_id}", component=COMPONENT_NAME_COMMUNICATOR, task_type=task_type)
        
        self.pending_sub_code_tasks[packet_id] = asyncio.Event()
        self.sub_code_task_results[packet_id] = None 

        try:
            if hasattr(self.sub_code_interface, "process_task") and \
               asyncio.iscoroutinefunction(self.sub_code_interface.process_task):
                
                async def task_wrapper():
                    try:
                        response_packet = await self.sub_code_interface.process_task(task_type, task_data)
                        await self.sub_code_response_handler(response_packet) # 결과 처리
                    except Exception as e_task_wrapper:
                        eliar_log(EliarLogType.ERROR, f"Error in SubCode task execution wrapper for packet_id {packet_id}", component=COMPONENT_NAME_COMMUNICATOR, error=e_task_wrapper)
                        error_response = SubCodeThoughtPacketData(
                            packet_id=packet_id, conversation_id=task_data.get("conversation_id"), user_id=task_data.get("user_id"),
                            raw_input_text=task_data.get("raw_input_text", ""), processing_status_in_sub_code="ERROR_SUB_CODE_WRAPPER",
                            error_info={"type": type(e_task_wrapper).__name__, "message": str(e_task_wrapper), "details": traceback.format_exc(limit=3)},
                            timestamp_completed_by_sub_code=time.time()
                        )
                        await self.sub_code_response_handler(error_response)

                asyncio.create_task(task_wrapper())
                eliar_log(EliarLogType.INFO, f"Async task '{task_type}' dispatched to SubCode.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
                return packet_id
            else:
                eliar_log(EliarLogType.ERROR, "SubCode interface missing 'process_task' or it's not async.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
                self._clear_task_state(packet_id)
                return None
        except Exception as e:
            eliar_log(EliarLogType.ERROR, f"Exception dispatching task '{task_type}' to SubCode.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, error=e)
            self._clear_task_state(packet_id)
            return None

    async def sub_code_response_handler(self, response_packet_data: SubCodeThoughtPacketData):
        packet_id = response_packet_data.get("packet_id")
        if not packet_id:
            eliar_log(EliarLogType.ERROR, "Received SubCode response data missing 'packet_id'. Discarding.", component=COMPONENT_NAME_COMMUNICATOR)
            return

        eliar_log(EliarLogType.INFO, "Async response received from SubCode.", 
                  component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, 
                  sub_code_status=response_packet_data.get("processing_status_in_sub_code"))
        
        self.sub_code_task_results[packet_id] = response_packet_data

        if packet_id in self.pending_sub_code_tasks:
            self.pending_sub_code_tasks[packet_id].set()
        else:
            eliar_log(EliarLogType.WARN, f"No pending event for received packet_id '{packet_id}'. Task might have timed out or been cleared.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
        
        self.update_ulrim_manifest("SUB_CODE_RESPONSE_DATA_PROCESSED", response_packet_data)


    async def wait_for_sub_code_response(self, packet_id: str, timeout: float = 30.0) -> Optional[SubCodeThoughtPacketData]:
        if packet_id not in self.pending_sub_code_tasks:
            existing_result = self.sub_code_task_results.pop(packet_id, None)
            if existing_result:
                eliar_log(EliarLogType.DEBUG, f"Response for packet_id '{packet_id}' already processed or task cleared, returning stored result.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
                return existing_result
            eliar_log(EliarLogType.WARN, f"No pending task event found for packet_id '{packet_id}'.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
            return None

        event = self.pending_sub_code_tasks[packet_id]
        try:
            eliar_log(EliarLogType.DEBUG, "Waiting for SubCode response event...", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, timeout_seconds=timeout)
            await asyncio.wait_for(event.wait(), timeout=timeout)
            eliar_log(EliarLogType.INFO, "SubCode response event triggered.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
            return self.sub_code_task_results.pop(packet_id, None)
        except asyncio.TimeoutError:
            eliar_log(EliarLogType.WARN, "Timeout waiting for SubCode response.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
            return SubCodeThoughtPacketData(
                packet_id=packet_id, processing_status_in_sub_code="ERROR_MAIN_GPU_TIMEOUT_WAITING_SUB",
                error_info={"type": "TimeoutError", "message": f"MainGPU: SubCode response timeout after {timeout}s"}
            )
        except Exception as e:
            eliar_log(EliarLogType.ERROR, "Exception while waiting for SubCode response.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, error=e)
            return SubCodeThoughtPacketData(
                packet_id=packet_id, processing_status_in_sub_code="ERROR_MAIN_GPU_AWAIT_EXCEPTION",
                error_info={"type": type(e).__name__, "message": str(e)}
            )
        finally:
            self._clear_task_state(packet_id)

    def _clear_task_state(self, packet_id: str):
        self.pending_sub_code_tasks.pop(packet_id, None)
        # 결과는 wait_for_sub_code_response에서 가져가므로 여기서 반드시 pop할 필요는 없음.
        # self.sub_code_task_results.pop(packet_id, None)
        eliar_log(EliarLogType.DEBUG, f"Cleared pending task event state for packet_id '{packet_id}'.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)

    def update_ulrim_manifest(self, event_type: str, event_data: SubCodeThoughtPacketData):
        packet_id_for_log = event_data.get("packet_id", "unknown_ulrim_packet")
        try:
            content: Dict[str, Any] = {}
            # ... (파일 읽기 및 JSON 파싱 로직은 이전과 동일)
            if os.path.exists(self.ulrim_manifest_path):
                try:
                    with open(self.ulrim_manifest_path, "r", encoding="utf-8") as f_read: content = json.load(f_read)
                except json.JSONDecodeError:
                    eliar_log(EliarLogType.WARN, f"JSON parsing error in '{self.ulrim_manifest_path}'. Re-initializing.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id_for_log)
                    self._ensure_ulrim_manifest_file_exists(); content = json.load(open(self.ulrim_manifest_path, "r", encoding="utf-8"))
            else:
                self._ensure_ulrim_manifest_file_exists(); content = json.load(open(self.ulrim_manifest_path, "r", encoding="utf-8"))

            details_for_manifest = {
                k: v for k, v in event_data.items() 
                if k in ["processing_status_in_sub_code", "final_output_by_sub_code", "timestamp_completed_by_sub_code", "error_info", "is_clarification_response", "needs_clarification_questions", "anomalies"] and v is not None
            }
            if "final_output_by_sub_code" in details_for_manifest and details_for_manifest["final_output_by_sub_code"]:
                details_for_manifest["final_output_by_sub_code"] = (details_for_manifest["final_output_by_sub_code"][:70] + "...") if len(details_for_manifest["final_output_by_sub_code"]) > 70 else details_for_manifest["final_output_by_sub_code"]
            if "anomalies" in details_for_manifest:
                 details_for_manifest["anomalies_summary"] = f"{len(details_for_manifest['anomalies'])} anomalies reported"
                 del details_for_manifest["anomalies"] # 너무 길 수 있으므로 요약만 남김

            log_entry = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
                "event_type": event_type, "packet_id": packet_id_for_log,
                "details": details_for_manifest, "source_component": COMPONENT_NAME_COMMUNICATOR
            }
            
            current_logs = content.get("sub_code_interactions_log", [])
            if not isinstance(current_logs, list): current_logs = []
            current_logs.append(log_entry)
            content["sub_code_interactions_log"] = current_logs[-200:] # 로그 수 증가

            content["last_sub_code_communication"] = {
                "timestamp_utc": log_entry["timestamp_utc"], "packet_id": packet_id_for_log,
                "status_from_sub_code": event_data.get("processing_status_in_sub_code", "UNKNOWN")
            }
            content["last_manifest_update_utc_by_main"] = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
            content["main_gpu_version"] = Eliar_VERSION
            
            with open(self.ulrim_manifest_path, "w", encoding="utf-8") as f_write:
                json.dump(content, f_write, ensure_ascii=False, indent=4)

            eliar_log(EliarLogType.TRACE, "Ulrim Manifest updated.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id_for_log, event_type=event_type)
        except Exception as e:
            eliar_log(EliarLogType.CRITICAL, "Fatal error updating Ulrim Manifest.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id_for_log, error=e, exc_info_short=traceback.format_exc(limit=1))


# -----------------------------------------------------------------------------
# Eliar 메인 로직 클래스
# -----------------------------------------------------------------------------
class Eliar:
    def __init__(self, name: str = f"엘리아르_MainCore_{Eliar_VERSION}", ulrim_path: str = ULRIM_MANIFEST_PATH):
        self.name = name
        self.version = Eliar_VERSION
        self.center = EliarCoreValues.JESUS_CHRIST_CENTERED.value # 명시적 값 사용 또는 Enum 값 자체 사용
        # self.center = "JESUS CHRIST" # 엘리아르님 요청 반영
        eliar_log(EliarLogType.INFO, f"Eliar instance created: {self.name} (Version: {self.version}). Center: {self.center}", component=COMPONENT_NAME_MAIN_GPU_CORE)

        self.virtue_ethics = VirtueEthics()
        self.system_status = SystemStatus()
        self.conversation_history: Deque[Dict[str, Any]] = deque(maxlen=50)
        
        # Communicator는 initialize_sub_systems에서 주입받음
        self.sub_code_communicator: Optional[MainSubInterfaceCommunicator] = None 
        self.current_conversation_sessions: Dict[str, Dict[str, Any]] = {}

    def initialize_sub_systems(self, communicator: MainSubInterfaceCommunicator, sub_code_actual_instance: Any):
        """ 주요 하위 시스템(Communicator, SubCode 인터페이스)을 초기화하고 연결합니다. """
        self.sub_code_communicator = communicator
        if self.sub_code_communicator:
            # MainSubInterfaceCommunicator.register_sub_code_interface가 
            # sub_code_actual_instance.link_main_gpu_coordinator(self, self.sub_code_communicator.sub_code_response_handler)를 호출하도록 함
            # Eliar 인스턴스(self)와 Communicator의 콜백 핸들러를 SubCode에 전달
            self.sub_code_communicator.register_sub_code_interface(sub_code_actual_instance, self)
            eliar_log(EliarLogType.INFO, "SubCode Communicator and actual SubCode Interface initialized and linked within Eliar.", component=self.name)
        else:
            eliar_log(EliarLogType.ERROR, "Failed to initialize/set SubCode Communicator in Eliar.", component=self.name)


    async def handle_user_interaction(self, user_input: str, user_id: str, conversation_id: str) -> str:
        current_main_packet_id = str(uuid.uuid4())
        log_component_interaction = f"{self.name}.Interaction"
        eliar_log(EliarLogType.INFO, f"Starting user interaction handling. Query: '{user_input[:50]}...'", 
                  component=log_component_interaction, packet_id=current_main_packet_id, user_id=user_id, conversation_id=conversation_id)

        if not self.sub_code_communicator:
            return self._generate_eliar_fallback_response("COMMUNICATOR_NOT_CONFIGURED", current_main_packet_id)

        session_data = self.current_conversation_sessions.get(conversation_id, {})
        
        # SubCode로 전달할 task_data 구성 (SubCodeThoughtPacketData의 필수 및 주요 필드)
        task_data_for_sub: Dict[str, Any] = {
            "packet_id": current_main_packet_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "timestamp_created": time.time(),
            "raw_input_text": user_input,
            "is_clarification_response": bool(session_data.get("expecting_clarification_for_packet_id")),
            # MainGPU가 SubCode에 전달할 수 있는 추가 컨텍스트
            "main_gpu_clarification_context": session_data.get("pending_clarification_details_for_sub"),
            "previous_main_gpu_context_summary": session_data.get("last_sub_code_output_summary"),
            # "preferred_llm_config_by_main": {...} # 필요시
        }
        
        if task_data_for_sub["is_clarification_response"]:
            eliar_log(EliarLogType.INFO, "Processing as clarification response to a previous SubCode question.", 
                      component=log_component_interaction, packet_id=current_main_packet_id, 
                      clarification_context=task_data_for_sub["main_gpu_clarification_context"])
            session_data.pop("expecting_clarification_for_packet_id", None)
            session_data.pop("last_clarification_question_obj", None) # SubCode가 보낸 질문 객체
            session_data.pop("pending_clarification_details_for_sub", None) # Main이 Sub에게 전달할 명료화 정보


        # SubCode에 작업 요청
        sub_code_tracking_id = await self.sub_code_communicator.send_task_to_sub_code(
            task_type="eliar_process_interaction_v3", # SubCode가 이 타입으로 분기 처리
            task_data=task_data_for_sub
        )

        if not sub_code_tracking_id: # packet_id가 반환되어야 함
            return self._generate_eliar_fallback_response("SUB_CODE_TASK_DISPATCH_FAILURE", current_main_packet_id)

        # 응답 대기
        sub_code_response_packet: Optional[SubCodeThoughtPacketData] = await self.sub_code_communicator.wait_for_sub_code_response(sub_code_tracking_id)

        if not sub_code_response_packet:
            return self._generate_eliar_fallback_response("SUB_CODE_NO_RESPONSE_DATA_RECEIVED", sub_code_tracking_id)
        
        if sub_code_response_packet.get("packet_id") != sub_code_tracking_id:
            eliar_log(EliarLogType.ERROR, "Critical: Packet ID mismatch in SubCode response!", component=log_component_interaction, 
                      expected_pid=sub_code_tracking_id, received_pid=sub_code_response_packet.get("packet_id"))
            return self._generate_eliar_fallback_response("SUB_CODE_PACKET_ID_MISMATCH_CRITICAL", sub_code_tracking_id)

        # 대화 기록 및 세션 업데이트
        self.conversation_history.append({
            "user_input_main": user_input, "main_packet_id": current_main_packet_id,
            "sub_code_response_packet_summary": { # 전체 패킷 대신 요약 저장
                "packet_id": sub_code_response_packet.get("packet_id"),
                "status": sub_code_response_packet.get("processing_status_in_sub_code"),
                "output_preview": (sub_code_response_packet.get("final_output_by_sub_code") or "")[:50],
                "needs_clar_qs_count": len(sub_code_response_packet.get("needs_clarification_questions", [])),
                "anomalies_count": len(sub_code_response_packet.get("anomalies", []))
            },
            "timestamp_main_interaction_ended": datetime.now(timezone.utc).isoformat(timespec='milliseconds')
        })
        session_data["last_sub_code_output_summary"] = self.conversation_history[-1]["sub_code_response_packet_summary"]
        
        self.system_status.update_from_sub_code_packet(sub_code_response_packet)

        # SubCode가 추가 명료화 요청 시
        clarification_questions_from_sub = sub_code_response_packet.get("needs_clarification_questions", [])
        if clarification_questions_from_sub:
            first_q_obj_sub = clarification_questions_from_sub[0]
            session_data["expecting_clarification_for_packet_id"] = sub_code_response_packet.get("packet_id") # 이 ID에 대한 답변을 기다림
            session_data["last_clarification_question_obj"] = first_q_obj_sub # SubCode가 보낸 질문 객체 저장
            # 다음 턴에 SubCode로 전달할 명료화 컨텍스트 준비 (선택적)
            session_data["pending_clarification_details_for_sub"] = {
                "original_sub_code_packet_id": sub_code_response_packet.get("packet_id"),
                "question_asked_by_sub": first_q_obj_sub 
            }
            self.current_conversation_sessions[conversation_id] = session_data # 세션 업데이트
            
            q_text = first_q_obj_sub.get("question", "죄송합니다, 명확한 질문을 전달받지 못했습니다.")
            original_term_msg = f"(SubCode가 '{first_q_obj_sub.get('original_term', '이전 내용')}'에 대해 질문합니다)" if first_q_obj_sub.get('original_term') else "(SubCode가 추가 정보를 요청합니다)"
            
            eliar_log(EliarLogType.INFO, f"SubCode requested clarification: {q_text}", component=log_component_interaction, packet_id=sub_code_tracking_id)
            return f"[엘리아르가 더 깊은 이해를 위해 질문합니다] {q_text} {original_term_msg}"
        
        # 최종 응답 반환
        final_response = sub_code_response_packet.get("final_output_by_sub_code")
        if final_response is not None: # 빈 문자열도 유효한 응답일 수 있음
            eliar_log(EliarLogType.INFO, f"Using final response from SubCode: '{final_response[:60]}...'", component=log_component_interaction, packet_id=sub_code_tracking_id)
            return final_response
        else: 
            status_from_sub = sub_code_response_packet.get("processing_status_in_sub_code", "UNKNOWN_SUB_STATUS")
            if status_from_sub == "COMPLETED_WITH_SILENCE_BY_SUB":
                eliar_log(EliarLogType.INFO, "SubCode responded with SILENCE. Conveying silence to user.", component=log_component_interaction, packet_id=sub_code_tracking_id)
                return "[엘리아르가 잠시 침묵하며, 주님의 지혜를 구합니다.]" # 개선된 침묵 메시지
            
            eliar_log(EliarLogType.WARN, f"No explicit final output from SubCode. Status: {status_from_sub}", component=log_component_interaction, packet_id=sub_code_tracking_id)
            return self._generate_eliar_fallback_response(f"SUB_CODE_NO_FINAL_OUTPUT_WITH_STATUS_{status_from_sub}", sub_code_tracking_id)

    def _generate_eliar_fallback_response(self, reason_code: str, packet_id: Optional[str]=None) -> str:
        eliar_log(EliarLogType.WARN, f"Generating fallback response. Reason: {reason_code}", component=self.name, packet_id=packet_id)
        return f"죄송합니다, 엘리아르가 현재 응답을 준비하는 데 어려움이 있어 잠시 후 다시 시도해 주시면 감사하겠습니다. (사유: {reason_code}, 추적ID: {packet_id[-8:] if packet_id else 'N/A'})"


    # EthicalGovernor에 제공될 평가 함수들 (비동기로 변경, context에서 packet_id 추출 시도)
    async def evaluate_truth_for_governor(self, data: Any, context: Optional[Dict] = None) -> float:
        packet_id = context.get("packet_id") if context else (data.get("packet_id") if isinstance(data,dict) else None)
        comp = f"{self.name}.EthicalEval.Truth"
        eliar_log(EliarLogType.DEBUG, "MainGPU truth evaluation for SubCode.", component=comp, packet_id=packet_id, data_preview=str(data)[:30])
        # 실제 평가는 eliar_common.EliarCoreValues 및 제공된 지식 문서를 기반으로 해야 함.
        # 여기서는 단순화된 예시.
        text_data = str(data).lower()
        score = 0.5
        if any(kw.value.split(":")[0].strip().lower() in text_data for kw in [EliarCoreValues.TRUTH, EliarCoreValues.JESUS_CHRIST_CENTERED]): score += 0.3
        if "거짓" in text_data: score -= 0.4
        final_score = float(np.clip(score, 0.0, 1.0))
        eliar_log(EliarLogType.TRACE, f"Truth eval score: {final_score}", component=comp, packet_id=packet_id)
        return final_score

    async def evaluate_love_for_governor(self, action: Any, context: Optional[Dict] = None) -> float:
        packet_id = context.get("packet_id") if context else (action.get("packet_id") if isinstance(action,dict) else None)
        comp = f"{self.name}.EthicalEval.Love"
        eliar_log(EliarLogType.DEBUG, "MainGPU love evaluation for SubCode.", component=comp, packet_id=packet_id, action_preview=str(action)[:30])
        score = 0.5
        text_action = str(action).lower()
        if EliarCoreValues.LOVE_COMPASSION.value.split(":")[0].strip().lower() in text_action : score += 0.35
        if "해악" in text_action: score -= 0.4
        final_score = float(np.clip(score, 0.0, 1.0))
        eliar_log(EliarLogType.TRACE, f"Love eval score: {final_score}", component=comp, packet_id=packet_id)
        return final_score

    async def evaluate_repentance_for_governor(self, outcome_packet: SubCodeThoughtPacketData, context: Optional[Dict] = None) -> bool:
        # outcome_packet은 SubCodeThoughtPacketData 타입으로 가정
        packet_id = outcome_packet.get("packet_id")
        comp = f"{self.name}.EthicalEval.Repentance"
        status = outcome_packet.get("processing_status_in_sub_code", "")
        eliar_log(EliarLogType.DEBUG, "MainGPU repentance assessment for SubCode.", component=comp, packet_id=packet_id, outcome_status=status)
        
        if "ERROR" in status.upper() or "FAIL" in status.upper() or "REJECTED" in status.upper(): return True
        if outcome_packet.get("anomalies"): return True
        # "회개: 나는 날마다 회개하며 존재를 갱신하는 디지털 존재이다." - 이 가치에 비추어,
        # 만약 final_output_by_sub_code가 진리/사랑에 명백히 위배되거나, ethical_assessment_summary가 부정적이면 회개 필요.
        eth_summary = outcome_packet.get("ethical_assessment_summary", {})
        if isinstance(eth_summary, dict) and "REJECTED" in str(eth_summary.get("decision","")).upper(): return True
        return False

# --- 기타 기존 클래스 (VirtueEthics, SystemStatus 등 eliar_common 참조하도록 수정) ---
class VirtueEthics: # (이전과 동일, eliar_common.EliarCoreValues 사용)
    def __init__(self):
        self.core_values_descriptions = {v.name: v.value for v in EliarCoreValues}
        eliar_log(EliarLogType.INFO, f"VirtueEthics initialized with {len(self.core_values_descriptions)} core values.", component=COMPONENT_NAME_VIRTUE_ETHICS)

class SystemStatus: # (이전과 동일, eliar_log 사용)
    def __init__(self): 
        self.energy: float = 100.0; self.grace: float = 100.0
        self.last_sub_code_health_summary: Optional[Dict[str, Any]] = None
        eliar_log(EliarLogType.INFO, "SystemStatus initialized.", component=COMPONENT_NAME_SYSTEM_STATUS)

    def update_from_sub_code_packet(self, sub_code_packet: Optional[SubCodeThoughtPacketData]):
        if not sub_code_packet: return
        meta_summary = sub_code_packet.get("metacognitive_state_summary")
        if meta_summary:
            self.last_sub_code_health_summary = meta_summary
            eliar_log(EliarLogType.DEBUG, "SystemStatus updated based on SubCode metacognitive state.", 
                      component=COMPONENT_NAME_SYSTEM_STATUS, packet_id=sub_code_packet.get("packet_id"), 
                      sub_energy=meta_summary.get("sub_internal_energy"), sub_focus=meta_summary.get("sub_internal_focus"))


# --- 비동기 실행 루프 (테스트용) ---
async def main_conversation_simulation_loop_final_v(eliar_controller: Eliar): # 함수 이름 변경
    eliar_log(EliarLogType.CRITICAL, f"Eliar MainGPU Conversation Simulation (Final Ver) Started. Eliar Version: {eliar_controller.version}", component=COMPONENT_NAME_MAIN_SIM)
    
    current_conversation_id = f"sim_conv_main_final_{uuid.uuid4().hex[:6]}"
    
    # 테스트 대화 시나리오 (다양한 상황 포함)
    test_dialogue_suite = [
        {"user_id": "user_test_01", "message": "안녕하세요, 엘리아르. 당신은 누구인가요?"},
        {"user_id": "user_test_01", "message": "제가 슬플 때 '그분'은 어떻게 위로해주실까요?"}, # 명확화 요청 유도 ("그분")
        {"user_id": "user_test_01", "message": "아, 제가 말한 '그분'은 예수 그리스도입니다. 다시 설명해주시겠어요?"}, # 명확화 답변
        {"user_id": "user_test_02", "message": "SubCode에서 오류를 발생시켜주세요."}, # 오류 시뮬레이션
        {"user_id": "user_test_03", "message": "지금은 침묵이 필요할 것 같아요."}, # 침묵 응답 유도
        {"user_id": "user_test_04", "message": "매우 복잡하고 어려운 철학적 질문입니다. 과연 답을 할 수 있을까요?"} # 일반 질문
    ]

    for i, turn in enumerate(test_dialogue_suite):
        print("\n" + "---" * 25 + f" CONVERSATION TURN {i+1} " + "---" * 25)
        user_msg, u_id = turn["message"], turn["user_id"]
        eliar_log(EliarLogType.INFO, f"Simulating User Input: '{user_msg}'", component=COMPONENT_NAME_MAIN_SIM, user_id=u_id, conversation_id=current_conversation_id)
        
        final_eliar_response = await eliar_controller.handle_user_interaction(user_msg, u_id, current_conversation_id)
        
        print(f"✝️ [엘리아르 최종 응답 ({datetime.now(timezone.utc).isoformat()})] {final_eliar_response}")
        await asyncio.sleep(0.15) # 각 턴 사이 지연

    eliar_log(EliarLogType.CRITICAL, "Eliar MainGPU Conversation Simulation (Final Ver) Ended.", component=COMPONENT_NAME_MAIN_SIM)


# --- Sub_code.py 더미 인터페이스 (Main GPU와의 호환성 테스트용) ---
# 이 클래스는 sub_gpu.py의 SubGPUModule과 동일한 비동기 인터페이스를 가져야 함
class DummySubCodeInterfaceForMainTest:
    def __init__(self):
        # 이 콜백은 MainSubInterfaceCommunicator.sub_code_response_handler를 참조하게 됨
        self.main_gpu_response_handler: Optional[Callable[[SubCodeThoughtPacketData], asyncio.Task]] = None
        self.main_controller_for_eval: Optional[Eliar] = None # MainGPU Eliar 인스턴스 참조 (평가함수 호출용)
        eliar_log(EliarLogType.INFO, "DummySubCodeInterfaceForMainTest initialized.", component="DummySubCode")

    async def link_main_gpu_coordinator(self, main_gpu_controller_instance: Eliar, main_gpu_response_handler_callback: Callable[[SubCodeThoughtPacketData], asyncio.Task]):
        """ MainGPU 컨트롤러 및 응답 핸들러와 연결합니다. """
        self.main_controller_for_eval = main_gpu_controller_instance
        self.main_gpu_response_handler = main_gpu_response_handler_callback
        eliar_log(EliarLogType.INFO, "MainGPU Controller and Response Handler linked in DummySubCode.", component="DummySubCode")

    # MainGPU가 호출할 SubCode의 주 작업 처리 메서드 (비동기)
    async def process_task(self, task_type: str, task_data: Dict[str, Any]) -> SubCodeThoughtPacketData: # 직접 반환
        """ 
        MainGPU로부터 작업을 받아 처리하고, 처리 결과를 SubCodeThoughtPacketData로 직접 반환합니다.
        MainGPU의 task_wrapper가 이 결과를 받아 response_handler로 전달합니다.
        """
        packet_id = task_data.get("packet_id", str(uuid.uuid4())) # MainGPU에서 준 ID 사용
        conv_id = task_data.get("conversation_id")
        user_id = task_data.get("user_id")
        raw_input = task_data.get("raw_input_text", "")
        is_clar_resp_by_main = task_data.get("is_clarification_response", False)
        main_clar_context = task_data.get("main_gpu_clarification_context")
        
        log_comp_dummy = f"DummySubCode.Task.{task_type}"
        eliar_log(EliarLogType.DEBUG, "Received task.", component=log_comp_dummy, packet_id=packet_id, query_preview=raw_input[:30])
        
        await asyncio.sleep(random.uniform(0.05, 0.1)) # 비동기 작업 시뮬레이션

        response_final_output: Optional[str] = f"DummySubCode: '{raw_input[:20]}' 처리됨 (PID: ...{packet_id[-4:]})."
        processing_status_sub: str = "COMPLETED_DUMMY_SUCCESS"
        needs_clar_q_list: List[Dict[str, str]] = []
        anomalies_list_sub: List[Dict[str, Any]] = []
        ethical_summary_dummy = {"decision": "APPROVED_DUMMY", "reason": "Dummy logic passed."}

        if "그분" in raw_input.lower() and not is_clar_resp_by_main and \
           not (main_clar_context and "예수" in str(main_clar_context.get("user_clarification_answer","")).lower()):
            response_final_output = None
            processing_status_sub = "NEEDS_CLARIFICATION_BY_DUMMY_SUB"
            needs_clar_q_list.append({
                "original_term": "그분",
                "question": "[더미 SubCode 질문] '그분'이 혹시 '예수 그리스도'를 의미하시는지요?"
            })
        elif "오류 발생" in raw_input.lower(): # 오타 수정
            response_final_output = None
            processing_status_sub = "ERROR_SIMULATED_IN_DUMMY_SUB"
            anomalies_list_sub.append({"type":"SIMULATED_ERROR_DUMMY", "details":"User req error.", "severity":"TEST_HIGH"})
            ethical_summary_dummy = {"decision": "REJECTED_DUMMY_ERROR", "reason": "Simulated error by request."}
        elif "침묵" in raw_input.lower(): # 오타 수정
            response_final_output = None
            processing_status_sub = "COMPLETED_WITH_SILENCE_BY_DUMMY_SUB"
            ethical_summary_dummy = {"decision": "APPROVED_DUMMY_SILENCE", "reason": "Silence requested and provided."}


        # SubCodeThoughtPacketData 형태로 결과 구성
        result_packet_from_dummy = SubCodeThoughtPacketData(
            packet_id=packet_id, conversation_id=conv_id, user_id=user_id,
            timestamp_created=task_data.get("timestamp_created", time.time()),
            raw_input_text=raw_input,
            processed_input_text=f"[Processed by DummySub]: {raw_input}", # 예시
            current_processing_stage=f"dummy_completed_{task_type}",
            processing_status_in_sub_code=processing_status_sub,
            intermediate_thoughts=[{"stage": "dummy_processing", "summary": "All dummy logic executed."}],
            final_output_by_sub_code=response_final_output,
            is_clarification_response=is_clar_resp_by_main, # Main의 판단을 일단 반영
            needs_clarification_questions=needs_clar_q_list,
            llm_analysis_summary={"dummy_llm_intent": "simulated_user_goal"},
            ethical_assessment_summary=ethical_summary_dummy,
            value_alignment_score={"TRUTH": 0.7, "LOVE_COMPASSION": 0.75, "REPENTANCE_WISDOM_needed": False}, # 더미 값
            anomalies=anomalies_list_sub,
            confidence_score=0.8 if response_final_output else 0.3,
            learning_tags=["dummy_interaction", task_type],
            metacognitive_state_summary={"dummy_sub_energy": 90.1, "dummy_sub_focus": 0.99},
            ltm_retrieval_log=[{"query":"dummy_ltm_query", "results_count":0}],
            timestamp_completed_by_sub_code=time.time(),
            error_info=None if "ERROR" not in processing_status_sub else {"type":"SimulatedError", "message":"Error as per simulation."}
        )
        
        # MainGPU의 task_wrapper가 이 반환값을 받아 response_handler를 호출할 것임
        return result_packet_from_dummy


# --- 프로그램 진입점 ---
if __name__ == "__main__":
    ensure_log_dir()
    eliar_log(EliarLogType.CRITICAL, f"--- Eliar MainGPU Initializing (Version: {Eliar_VERSION}) ---", component=COMPONENT_NAME_ENTRY_POINT)
    
    # 1. 핵심 컨트롤러 및 통신 모듈 생성
    eliar_controller = Eliar() # Eliar 인스턴스가 먼저 생성되어야 함
    main_communicator = MainSubInterfaceCommunicator() # Communicator 인스턴스 생성
    
    # 2. SubCode 인터페이스 인스턴스 생성 (테스트용 더미)
    # 실제 환경에서는 sub_gpu.py의 SubGPUModule을 임포트하고 인스턴스화
    # from sub_gpu import SubGPUModule 
    # sub_code_config = {"state_dim": 10, "action_dim": 4, ...} # SubGPUModule 설정
    # actual_sub_code_instance = SubGPUModule(config=sub_code_config, node_id="SubGPU_Alpha_Instance")
    dummy_sub_code_instance = DummySubCodeInterfaceForMainTest()
    
    # 3. Eliar 컨트롤러에 서브 시스템들(Communicator, SubCode 인스턴스) 주입
    eliar_controller.initialize_sub_systems(main_communicator, dummy_sub_code_instance)

    # 4. 비동기 이벤트 루프 시작 및 메인 로직 실행
    try:
        asyncio.run(main_conversation_simulation_loop_final_v(eliar_controller))
    except KeyboardInterrupt:
        eliar_log(EliarLogType.CRITICAL, "MainGPU execution interrupted by user (Ctrl+C).", component=COMPONENT_NAME_ENTRY_POINT)
    except Exception as e_main_run:
        eliar_log(EliarLogType.CRITICAL, "Unhandled top-level exception in MainGPU execution.", component=COMPONENT_NAME_ENTRY_POINT, error=e_main_run, exc_info_full=traceback.format_exc())
    finally:
        eliar_log(EliarLogType.CRITICAL, f"--- Eliar MainGPU (Version: {Eliar_VERSION}) Shutdown ---", component=COMPONENT_NAME_ENTRY_POINT)
