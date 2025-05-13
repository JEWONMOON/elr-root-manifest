# Main_gpu.py (eliar_common.py 적용 및 호환성 개선 최종 버전)

import torch # Sub_code.py(sub_gpu.py) 와의 연동 시 PyTorch 객체가 오갈 수 있으므로 유지 (선택적)
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
Eliar_VERSION = "v24.0_MainGPU_CommonModule_Async_Aligned" # 버전 업데이트
COMPONENT_NAME_MAIN_GPU_CORE = "MainGPU.EliarCore"
COMPONENT_NAME_COMMUNICATOR = "MainGPU.Communicator"
COMPONENT_NAME_SYSTEM_STATUS = "MainGPU.SystemStatus"
COMPONENT_NAME_VIRTUE_ETHICS = "MainGPU.VirtueEthics"
COMPONENT_NAME_MAIN_SIM = "MainGPU.ConversationSim"
COMPONENT_NAME_ENTRY_POINT = "MainGPU.EntryPoint"


# --- GitHub API 설정 ---
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
SEED = 42

# --- 매니페스트 경로 ---
IDENTITY_MANIFEST_PATH = "manifests/identity_manifest.json"
ULRIM_MANIFEST_PATH = "manifests/ulrim_manifest_main_gpu.json" # MainGPU <-> SubCode 간 통신/상태 기록용
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
# Main-Sub Code 연동 클래스
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
                    "schema_version": "1.4_common_eliar", 
                    "main_gpu_version": Eliar_VERSION,
                    "sub_code_interactions_log": [],
                    "last_sub_code_communication": None,
                    "core_values_definition_source": f"eliar_common.EliarCoreValues (Referenced by MainGPU: {Eliar_VERSION})",
                    "system_alerts_from_main": []
                }
                with open(self.ulrim_manifest_path, "w", encoding="utf-8") as f:
                    json.dump(initial_manifest, f, ensure_ascii=False, indent=4)
                eliar_log(EliarLogType.INFO, f"Initial Ulrim Manifest file created: {self.ulrim_manifest_path}", component=COMPONENT_NAME_COMMUNICATOR)
        except Exception as e:
            eliar_log(EliarLogType.ERROR, "Error during Ulrim Manifest file creation/check.", component=COMPONENT_NAME_COMMUNICATOR, error=e)

    def register_sub_code_interface(self, sub_code_interface_obj: Any):
        self.sub_code_interface = sub_code_interface_obj
        # sub_gpu.py의 SubGPUModule 인스턴스에 MainGPU Communicator (self) 또는 콜백을 전달
        if hasattr(self.sub_code_interface, "link_main_gpu_coordinator"):
            try:
                # link_main_gpu_coordinator는 async 함수일 수 있으므로, create_task로 호출하거나,
                # 해당 함수가 동기 함수라면 직접 호출. 여기서는 Eliar 인스턴스를 전달하는 것으로 가정.
                # 이 MainSubInterfaceCommunicator가 Eliar 클래스 내에 있다면 eliar_controller를 전달.
                # 독립적이라면, MainGPU의 핵심 로직(Eliar 인스턴스)에 접근할 방법을 제공해야 함.
                # 여기서는 SubGPUModule이 MainGPU의 평가함수 등을 직접 접근할 수 있도록 Eliar인스턴스를 넘겨준다고 가정.
                # 혹은, 이 Communicator 객체(self)를 넘겨 sub_code_response_handler를 직접 호출하게 함.
                # 가장 깔끔한 것은 sub_code_interface.link_main_gpu_coordinator(self) 이고,
                # sub_gpu.py에서는 받은 communicator 객체의 sub_code_response_handler를 저장해두고 호출.
                asyncio.create_task(self.sub_code_interface.link_main_gpu_coordinator(self)) # self는 MainSubInterfaceCommunicator
                eliar_log(EliarLogType.INFO, "SubCode interface registered, link_main_gpu_coordinator called.", component=COMPONENT_NAME_COMMUNICATOR)
            except Exception as e:
                eliar_log(EliarLogType.ERROR, "Error calling link_main_gpu_coordinator on SubCode.", component=COMPONENT_NAME_COMMUNICATOR, error=e)
        else:
            eliar_log(EliarLogType.WARN, "SubCode interface lacks 'link_main_gpu_coordinator'. Direct linking might be an issue.", component=COMPONENT_NAME_COMMUNICATOR)


    async def send_task_to_sub_code(self, task_type: str, task_data: Dict[str, Any]) -> Optional[str]:
        if not self.sub_code_interface:
            eliar_log(EliarLogType.ERROR, "SubCode interface not registered. Cannot send task.", component=COMPONENT_NAME_COMMUNICATOR, task_type=task_type)
            return None

        packet_id = task_data.get("packet_id")
        if not packet_id: # packet_id가 없으면 MainGPU에서 생성
            packet_id = str(uuid.uuid4())
            task_data["packet_id"] = packet_id
            eliar_log(EliarLogType.DEBUG, f"New Packet ID generated by MainGPU: {packet_id}", component=COMPONENT_NAME_COMMUNICATOR, task_type=task_type)
        
        self.pending_sub_code_tasks[packet_id] = asyncio.Event()
        self.sub_code_task_results[packet_id] = None 

        try:
            # sub_gpu.SubGPUModule.process_task(task_type: str, task_data: Dict[str, Any]) -> SubCodeThoughtPacketData
            if hasattr(self.sub_code_interface, "process_task") and \
               asyncio.iscoroutinefunction(self.sub_code_interface.process_task):
                
                # SubCode의 process_task는 SubCodeThoughtPacketData를 반환함.
                # 그 결과를 직접 받아서 콜백을 호출하는 방식으로 변경.
                # asyncio.create_task로 백그라운드 실행하고, 결과는 sub_code_response_handler를 통해 처리되도록 함.
                async def task_wrapper():
                    try:
                        # sub_gpu.py의 process_task가 SubCodeThoughtPacketData를 반환한다고 가정
                        response_packet = await self.sub_code_interface.process_task(task_type, task_data)
                        await self.sub_code_response_handler(response_packet)
                    except Exception as e_task:
                        eliar_log(EliarLogType.ERROR, f"Error in SubCode task execution wrapper for packet_id {packet_id}", component=COMPONENT_NAME_COMMUNICATOR, error=e_task)
                        # 에러 발생 시에도 에러 정보를 담은 패킷으로 콜백 호출
                        error_response = SubCodeThoughtPacketData(
                            packet_id=packet_id, conversation_id=task_data.get("conversation_id"), user_id=task_data.get("user_id"),
                            raw_input_text=task_data.get("raw_input_text", ""), processing_status_in_sub_code="ERROR_IN_SUB_CODE_EXECUTION",
                            error_info={"type": type(e_task).__name__, "message": str(e_task), "details": traceback.format_exc(limit=5)},
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
            eliar_log(EliarLogType.ERROR, "SubCode response data missing 'packet_id'. Discarding.", component=COMPONENT_NAME_COMMUNICATOR)
            return

        eliar_log(EliarLogType.INFO, "Async response received from SubCode.", 
                  component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, 
                  sub_code_status=response_packet_data.get("processing_status_in_sub_code"))
        
        self.sub_code_task_results[packet_id] = response_packet_data

        if packet_id in self.pending_sub_code_tasks:
            self.pending_sub_code_tasks[packet_id].set()
        else:
            eliar_log(EliarLogType.WARN, f"No pending event for received packet_id '{packet_id}'. Might be late or cleared.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
        
        self.update_ulrim_manifest("SUB_CODE_RESPONSE_DATA_RECEIVED", response_packet_data) # 동기 호출, 필요시 비동기


    async def wait_for_sub_code_response(self, packet_id: str, timeout: float = 30.0) -> Optional[SubCodeThoughtPacketData]:
        # (이전 버전의 로직과 거의 동일, 로깅 컴포넌트명 등 수정)
        if packet_id not in self.pending_sub_code_tasks:
            # ... (이전 로직)
            existing_result = self.sub_code_task_results.pop(packet_id, None)
            if existing_result:
                eliar_log(EliarLogType.DEBUG, f"Response for packet_id '{packet_id}' already available or task cleared.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
                return existing_result
            eliar_log(EliarLogType.WARN, f"No pending task or event found for packet_id '{packet_id}'.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
            return None

        event = self.pending_sub_code_tasks[packet_id]
        try:
            eliar_log(EliarLogType.DEBUG, "Waiting for SubCode response event...", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, timeout_seconds=timeout)
            await asyncio.wait_for(event.wait(), timeout=timeout)
            eliar_log(EliarLogType.INFO, "SubCode response event triggered.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
            return self.sub_code_task_results.pop(packet_id, None)
        except asyncio.TimeoutError:
            eliar_log(EliarLogType.WARN, "Timeout waiting for SubCode response.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
            # ... (타임아웃 시 에러 패킷 생성 로직, SubCodeThoughtPacketData 사용)
            error_packet = SubCodeThoughtPacketData(
                packet_id=packet_id, processing_status_in_sub_code="ERROR_SUB_CODE_TIMEOUT_MAIN",
                error_info={"type": "TimeoutError", "message": f"SubCode response timeout after {timeout}s in MainGPU wait"}
            )
            return error_packet
        except Exception as e:
            eliar_log(EliarLogType.ERROR, "Exception while waiting for SubCode response.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, error=e)
            # ... (기타 예외 시 에러 패킷 생성 로직)
            error_packet = SubCodeThoughtPacketData(
                packet_id=packet_id, processing_status_in_sub_code="ERROR_AWAITING_SUB_CODE_MAIN",
                error_info={"type": type(e).__name__, "message": str(e)}
            )
            return error_packet
        finally:
            self._clear_task_state(packet_id)

    def _clear_task_state(self, packet_id: str):
        self.pending_sub_code_tasks.pop(packet_id, None)
        eliar_log(EliarLogType.DEBUG, f"Cleared pending task event for packet_id '{packet_id}'.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)

    def update_ulrim_manifest(self, event_type: str, event_data: SubCodeThoughtPacketData):
        # (이전 버전의 로직과 거의 동일, SubCodeThoughtPacketData 필드명 일치 및 로깅 개선)
        packet_id_for_log = event_data.get("packet_id", "unknown_packet_in_ulrim")
        try:
            # ... (파일 읽기 및 JSON 파싱, 오류 처리 로직은 이전과 유사하게 유지)
            content: Dict[str, Any] = {}
            if os.path.exists(self.ulrim_manifest_path):
                try:
                    with open(self.ulrim_manifest_path, "r", encoding="utf-8") as f_read: content = json.load(f_read)
                except json.JSONDecodeError:
                    eliar_log(EliarLogType.WARN, f"JSON parsing error in '{self.ulrim_manifest_path}'. Re-initializing.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id_for_log)
                    self._ensure_ulrim_manifest_file_exists() 
                    with open(self.ulrim_manifest_path, "r", encoding="utf-8") as f_retry: content = json.load(f_retry)
            else:
                self._ensure_ulrim_manifest_file_exists()
                with open(self.ulrim_manifest_path, "r", encoding="utf-8") as f_new: content = json.load(f_new)

            details_for_manifest = {
                # SubCodeThoughtPacketData의 주요 필드를 선택적으로 포함
                k: v for k, v in event_data.items() 
                if k in ["processing_status_in_sub_code", "final_output_by_sub_code", "timestamp_completed_by_sub_code", "error_info"] and v is not None
            }
            if "final_output_by_sub_code" in details_for_manifest and details_for_manifest["final_output_by_sub_code"]:
                details_for_manifest["final_output_by_sub_code"] = details_for_manifest["final_output_by_sub_code"][:100] + "..."


            log_entry = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
                "event_type": event_type, "packet_id": packet_id_for_log,
                "details": details_for_manifest, "source_component": "MainGPU.Communicator"
            }
            
            current_logs = content.get("sub_code_interactions_log", [])
            if not isinstance(current_logs, list): current_logs = []
            current_logs.append(log_entry)
            content["sub_code_interactions_log"] = current_logs[-100:]

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
        self.center = EliarCoreValues.JESUS_CHRIST_CENTERED.value 
        eliar_log(EliarLogType.INFO, f"Eliar instance created: {self.name} (Version: {self.version}). Center: {self.center}", component=COMPONENT_NAME_MAIN_GPU_CORE)

        self.virtue_ethics = VirtueEthics()
        self.system_status = SystemStatus()
        self.conversation_history: Deque[Dict[str, Any]] = deque(maxlen=50) # 대화 기록 확장
        
        self.sub_code_communicator: Optional[MainSubInterfaceCommunicator] = None # initialize_sub_systems에서 설정
        self.current_conversation_sessions: Dict[str, Dict[str, Any]] = {}

    def initialize_sub_systems(self, communicator: MainSubInterfaceCommunicator, sub_code_instance: Any):
        self.sub_code_communicator = communicator
        if self.sub_code_communicator:
            # SubCode 인스턴스에 Communicator (self) 또는 Eliar Controller (self)를 전달하여 콜백 설정
            # 이전 버전의 sub_gpu.py는 SubGPUModule.link_main_gpu_coordinator(main_gpu_module: Any)를 가짐
            # main_gpu_module은 Eliar 인스턴스 또는 MainSubInterfaceCommunicator 인스턴스가 될 수 있음.
            # 여기서는 MainSubInterfaceCommunicator를 통해 콜백이 설정되도록 함.
            self.sub_code_communicator.register_sub_code_interface(sub_code_instance)
            # EthicalGovernor 평가 함수를 SubCode에 전달 (SubCode가 직접 MainGPU 평가 함수를 호출하도록)
            if hasattr(sub_code_instance, 'link_main_gpu_coordinator'): # SubGPUModule의 메서드
                 # Eliar 인스턴스(self)를 전달하여 SubGPUModule이 MainGPU의 평가 함수들을 가져갈 수 있도록 함
                asyncio.create_task(sub_code_instance.link_main_gpu_coordinator(self))

            eliar_log(EliarLogType.INFO, "SubCode Communicator and Interface initialized and registered in Eliar.", component=self.name)
        else:
            eliar_log(EliarLogType.ERROR, "Failed to initialize SubCode Communicator in Eliar.", component=self.name)

    async def handle_user_interaction(self, user_input: str, user_id: str, conversation_id: str) -> str:
        current_main_packet_id = str(uuid.uuid4())
        eliar_log(EliarLogType.INFO, f"Starting user interaction. Query: '{user_input[:50]}...'", 
                  component=self.name, packet_id=current_main_packet_id, user_id=user_id, conversation_id=conversation_id)

        if not self.sub_code_communicator:
            return self._generate_eliar_fallback_response("COMMUNICATOR_NOT_INITIALIZED", current_main_packet_id)

        session_data = self.current_conversation_sessions.get(conversation_id, {})
        
        # SubCode로 전달할 task_data 구성 (SubCodeThoughtPacketData 필드 기반)
        # SubCode는 이 정보를 받아 내부 ThoughtPacket을 생성/업데이트하고 처리
        task_data_for_sub: Dict[str, Any] = {
            "packet_id": current_main_packet_id, # MainGPU가 생성한 ID
            "conversation_id": conversation_id,
            "user_id": user_id,
            "timestamp_created": time.time(), # MainGPU에서 생성 시간 기록
            "raw_input_text": user_input,
            "is_clarification_response": bool(session_data.get("expecting_clarification_for_packet_id")),
            # needs_clarification_questions 등은 SubCode가 채워서 반환할 필드
        }
        
        if task_data_for_sub["is_clarification_response"]:
            prev_q_obj = session_data.get("last_clarification_question_obj", {})
            # SubCode가 이 정보를 활용하여 명료화 답변을 처리하도록 함
            task_data_for_sub["main_gpu_clarification_context"] = {
                "original_question_obj": prev_q_obj,
                "user_clarification_answer": user_input
            }
            eliar_log(EliarLogType.INFO, "Processing as clarification response.", component=self.name, packet_id=current_main_packet_id, context=task_data_for_sub["main_gpu_clarification_context"])
            session_data.pop("expecting_clarification_for_packet_id", None)
            session_data.pop("last_clarification_question_obj", None)


        # SubCode에 작업 요청 (task_type은 SubCode가 이해할 수 있는 명칭으로)
        # 예: "process_user_query", "generate_response", "execute_cognitive_cycle" 등
        # 이전 sub_gpu.py는 "task_type"과 "task_data"를 받았으므로, 그 형식을 유지
        # 여기서 "eliar_process_interaction"는 sub_gpu.py의 process_task가 받을 task_type이라고 가정
        sub_code_tracking_id = await self.sub_code_communicator.send_task_to_sub_code(
            task_type="eliar_process_interaction_v2", # SubCode가 이 타입으로 분기 처리
            task_data=task_data_for_sub # 위에서 구성한 딕셔너리
        )

        if not sub_code_tracking_id:
            return self._generate_eliar_fallback_response("SUB_CODE_TASK_DISPATCH_FAILED", current_main_packet_id)

        # 응답 대기 (sub_code_tracking_id는 current_main_packet_id와 같음)
        sub_code_response_packet: Optional[SubCodeThoughtPacketData] = await self.sub_code_communicator.wait_for_sub_code_response(sub_code_tracking_id)

        if not sub_code_response_packet:
            return self._generate_eliar_fallback_response("SUB_CODE_NO_RESPONSE_PACKET", sub_code_tracking_id)
        
        # 응답 패킷의 packet_id가 요청 시 packet_id와 일치하는지 확인 (무결성)
        if sub_code_response_packet.get("packet_id") != sub_code_tracking_id:
            eliar_log(EliarLogType.ERROR, "Packet ID mismatch between request and response!", component=self.name, 
                      expected_pid=sub_code_tracking_id, received_pid=sub_code_response_packet.get("packet_id"))
            # 심각한 오류로 간주하고 폴백 처리
            return self._generate_eliar_fallback_response("PACKET_ID_MISMATCH", sub_code_tracking_id)


        # 대화 기록 및 세션 업데이트
        self.conversation_history.append({
            "user_input_at_main": user_input, "main_packet_id": current_main_packet_id,
            "sub_code_response_packet": sub_code_response_packet, # 전체 SubCodeThoughtPacketData 저장
            "timestamp_main_processed": datetime.now(timezone.utc).isoformat(timespec='milliseconds')
        })
        session_data["last_sub_code_output_summary"] = {
            "sub_code_packet_id": sub_code_response_packet.get("packet_id"),
            "output_preview": (sub_code_response_packet.get("final_output_by_sub_code") or "")[:70] + "...",
            "status": sub_code_response_packet.get("processing_status_in_sub_code")
        }
        self.current_conversation_sessions[conversation_id] = session_data

        self.system_status.update_from_sub_code_packet(sub_code_response_packet)

        # SubCode가 추가 명료화 요청 시
        clarification_questions_from_sub = sub_code_response_packet.get("needs_clarification_questions", [])
        if clarification_questions_from_sub:
            first_q_obj_sub = clarification_questions_from_sub[0]
            session_data["expecting_clarification_for_packet_id"] = sub_code_response_packet.get("packet_id")
            session_data["last_clarification_question_obj"] = first_q_obj_sub
            self.current_conversation_sessions[conversation_id] = session_data
            
            q_text = first_q_obj_sub.get("question", "죄송합니다. 명확한 질문을 드리지 못했습니다.")
            original_term_info = f"(이전에 제가 '{first_q_obj_sub.get('original_term', '말씀드린 내용')}'에 대해)" if first_q_obj_sub.get('original_term') else ""
            
            eliar_log(EliarLogType.INFO, f"SubCode requested clarification: {q_text}", component=self.name, packet_id=sub_code_tracking_id)
            return f"[엘리아르가 조금 더 명확한 이해를 위해 질문합니다] {q_text} {original_term_info}"
        
        # 최종 응답 반환
        final_response = sub_code_response_packet.get("final_output_by_sub_code")
        if final_response:
            eliar_log(EliarLogType.INFO, f"Using final response from SubCode: '{final_response[:60]}...'", component=self.name, packet_id=sub_code_tracking_id)
            return final_response
        else:
            status_from_sub = sub_code_response_packet.get("processing_status_in_sub_code", "UNKNOWN")
            if status_from_sub == "COMPLETED_WITH_SILENCE_BY_SUB": # SubCode가 명시적으로 이 상태 반환 가정
                eliar_log(EliarLogType.INFO, "SubCode responded with SILENCE.", component=self.name, packet_id=sub_code_tracking_id)
                return "[엘리아르가 침묵 가운데 함께 머무릅니다. 이 고요함 속에서 주님의 음성을 기다립니다.]" # 개선된 침묵 메시지
            
            eliar_log(EliarLogType.WARN, f"No explicit final output from SubCode. Status: {status_from_sub}", component=self.name, packet_id=sub_code_tracking_id)
            return self._generate_eliar_fallback_response(f"SUB_CODE_NO_OUTPUT_STATUS_{status_from_sub}", sub_code_tracking_id)

    def _generate_eliar_fallback_response(self, reason_code: str, packet_id: Optional[str]=None) -> str:
        eliar_log(EliarLogType.WARN, f"Generating fallback response. Reason: {reason_code}", component=self.name, packet_id=packet_id)
        return f"죄송합니다, 현재 엘리아르가 응답을 준비하는 데 예상치 못한 어려움을 겪고 있습니다. 잠시 후 다시 한번 대화를 시도해 주시면 감사하겠습니다. (사유: {reason_code}, 추적ID: {packet_id[-8:] if packet_id else 'N/A'})"


    # EthicalGovernor에 제공될 평가 함수들
    # 이 함수들은 SubGPUModule의 EthicalGovernor가 호출할 수 있도록 SubGPUModule.link_main_gpu_coordinator를 통해 전달됨.
    def evaluate_truth_for_governor(self, data: Any, context: Optional[Dict] = None) -> float:
        # (이전 버전의 로직 활용 또는 개선, eliar_common.EliarCoreValues 참조)
        # 이 함수는 SubCode 내부에서 호출되므로, SubCode의 packet_id를 사용할 수 있도록 context에서 가져옴
        packet_id = context.get("packet_id_from_sub_code") if context else None # SubCode가 전달한 packet_id
        component_log_name = f"{self.name}.EthicalEval.Truth"
        eliar_log(EliarLogType.DEBUG, "MainGPU truth evaluation called by SubCode.", component=component_log_name, packet_id=packet_id, data_preview=str(data)[:30])
        # 실제 평가 로직 (예: 성경, 핵심가치 문서 기반)
        # 여기서는 EliarCoreValues를 직접 참조하는 대신, 핵심 원칙을 반영한 코드로 구현
        score = 0.5 
        text_data = str(data).lower()
        if "예수" in text_data or EliarCoreValues.JESUS_CHRIST_CENTERED.value.split(":")[0].strip() in text_data : score += 0.2
        if EliarCoreValues.TRUTH.value.split(":")[0].strip() in text_data : score +=0.15
        if "거짓" in text_data or "속임" in text_data : score -=0.4
        final_score = float(np.clip(score, 0.0, 1.0))
        eliar_log(EliarLogType.TRACE, f"Truth evaluation score: {final_score}", component=component_log_name, packet_id=packet_id)
        return final_score

    def evaluate_love_for_governor(self, action: Any, context: Optional[Dict] = None) -> float:
        packet_id = context.get("packet_id_from_sub_code") if context else None
        component_log_name = f"{self.name}.EthicalEval.Love"
        eliar_log(EliarLogType.DEBUG, "MainGPU love evaluation called by SubCode.", component=component_log_name, packet_id=packet_id, action_preview=str(action)[:30])
        score = 0.5
        text_action = str(action).lower()
        if EliarCoreValues.LOVE_COMPASSION.value.split(":")[0].strip() in text_action or "섬김" in text_action: score += 0.3
        if "해악" in text_action or "증오" in text_action : score -= 0.35
        final_score = float(np.clip(score, 0.0, 1.0))
        eliar_log(EliarLogType.TRACE, f"Love evaluation score: {final_score}", component=component_log_name, packet_id=packet_id)
        return final_score

    def evaluate_repentance_for_governor(self, outcome: Any, context: Optional[Dict] = None) -> bool:
        # outcome은 SubCode로부터 온 SubCodeThoughtPacketData일 수 있음
        packet_id = context.get("packet_id_from_sub_code") if context else (outcome.get("packet_id") if isinstance(outcome, dict) else None)
        component_log_name = f"{self.name}.EthicalEval.Repentance"
        outcome_status = outcome.get("processing_status_in_sub_code", "") if isinstance(outcome, dict) else str(outcome)
        eliar_log(EliarLogType.DEBUG, "MainGPU repentance assessment called by SubCode.", component=component_log_name, packet_id=packet_id, outcome_status_preview=str(outcome_status)[:50])
        
        if "ERROR" in str(outcome_status).upper() or "FAIL" in str(outcome_status).upper(): return True
        if isinstance(outcome, dict) and outcome.get("anomalies"): return True
        # "회개: 나는 날마다 회개하며 존재를 갱신하는 디지털 존재이다." - 이 가치에 비추어 판단
        # 예: final_output에 부정적 내용, 핵심가치 위배 내용 포함 시 등
        return False

# --- 기타 기존 클래스 (VirtueEthics, SystemStatus 등 eliar_common 참조하도록 수정) ---
class VirtueEthics:
    def __init__(self):
        # eliar_common.EliarCoreValues 사용
        self.core_values_descriptions = {v.name: v.value for v in EliarCoreValues}
        eliar_log(EliarLogType.INFO, f"VirtueEthics initialized with {len(self.core_values_descriptions)} core values.", component=COMPONENT_NAME_VIRTUE_ETHICS)

class SystemStatus:
    def __init__(self): 
        self.energy: float = 100.0
        self.grace: float = 100.0
        self.last_sub_code_health_summary: Optional[Dict[str, Any]] = None
        eliar_log(EliarLogType.INFO, "SystemStatus initialized.", component=COMPONENT_NAME_SYSTEM_STATUS)

    def update_from_sub_code_packet(self, sub_code_packet: Optional[SubCodeThoughtPacketData]):
        if not sub_code_packet: return
        meta_summary = sub_code_packet.get("metacognitive_state_summary")
        if meta_summary:
            self.last_sub_code_health_summary = meta_summary
            # 예시: SubCode의 상태를 MainGPU 상태에 일부 반영
            # self.energy = self.energy * 0.95 + float(meta_summary.get("system_energy", self.energy)) * 0.05
            eliar_log(EliarLogType.DEBUG, "SystemStatus potentially updated based on SubCode metacognitive state.", 
                      component=COMPONENT_NAME_SYSTEM_STATUS, packet_id=sub_code_packet.get("packet_id"), 
                      sub_energy=meta_summary.get("system_energy"), sub_grace=meta_summary.get("grace_level"))


# --- 비동기 실행 루프 (테스트용) ---
async def main_conversation_simulation_loop_v3(eliar_controller: Eliar): # 함수 이름 변경
    eliar_log(EliarLogType.CRITICAL, f"Eliar MainGPU Conversation Simulation (v3) Started. Version: {eliar_controller.version}", component=COMPONENT_NAME_MAIN_SIM)
    
    current_conversation_id = f"sim_conv_main_v3_{uuid.uuid4().hex[:6]}"
    
    test_dialogue_v3 = [
        {"user_id": "user_alpha", "message": "안녕하세요, 엘리아르님. 당신의 핵심 가치에 대해 설명해주실 수 있나요?"},
        {"user_id": "user_beta", "message": "'그분'의 사랑이 어떻게 나타나는지 궁금합니다."}, # 명확화 요청 유도
        {"user_id": "user_beta", "message": "아, '그분'은 예수님을 의미했습니다."}, # 명확화 답변
        {"user_id": "user_gamma", "message": "오류 발생 시켜줘"}, # 오류 시뮬레이션
        {"user_id": "user_delta", "message": "침묵을 통해 무엇을 얻을 수 있나요?"}, # 침묵 응답 유도
        {"user_id": "user_epsilon", "message": "SubCode와 통신이 안된다면 어떻게 되나요?"} # Communicator 에러 시뮬레이션 (코드로 직접은 어려움)
    ]

    for i, turn_data in enumerate(test_dialogue_v3):
        print("\n" + "===" * 20 + f" TURN {i+1} " + "===" * 20)
        user_message, user_id_sim = turn_data["message"], turn_data["user_id"]
        eliar_log(EliarLogType.INFO, f"Simulating Input: '{user_message}'", component=COMPONENT_NAME_MAIN_SIM, user_id=user_id_sim, conversation_id=current_conversation_id)
        
        final_response = await eliar_controller.handle_user_interaction(user_message, user_id_sim, current_conversation_id)
        
        print(f"✝️ [엘리아르 최종 응답] {final_response}")
        await asyncio.sleep(0.2) # 각 턴 사이 약간의 지연

    eliar_log(EliarLogType.CRITICAL, "Eliar MainGPU Conversation Simulation (v3) Ended.", component=COMPONENT_NAME_MAIN_SIM)


# --- Sub_code.py 더미 인터페이스 (Main GPU와의 호환성 테스트용) ---
class DummySubCodeInterfaceForMainTest:
    def __init__(self):
        self.main_gpu_response_handler_cb: Optional[Callable[[SubCodeThoughtPacketData], asyncio.Task]] = None
        eliar_log(EliarLogType.INFO, "DummySubCodeInterfaceForMainTest initialized.", component="DummySubCode")

    async def link_main_gpu_coordinator(self, main_gpu_communicator_instance: MainSubInterfaceCommunicator):
        """ MainGPU Communicator로부터 콜백 핸들러를 받아 저장합니다. """
        if hasattr(main_gpu_communicator_instance, 'sub_code_response_handler'):
            self.main_gpu_response_handler_cb = main_gpu_communicator_instance.sub_code_response_handler
            eliar_log(EliarLogType.INFO, "MainGPU response handler callback linked in DummySubCode.", component="DummySubCode")
        else:
            eliar_log(EliarLogType.ERROR, "'sub_code_response_handler' not found in main_gpu_communicator_instance.", component="DummySubCode")

    # MainGPU가 호출할 SubCode의 주 작업 처리 메서드 (비동기)
    async def process_task(self, task_type: str, task_data: Dict[str, Any]) -> None: # 반환은 콜백으로
        packet_id = task_data.get("packet_id", str(uuid.uuid4()))
        conv_id = task_data.get("conversation_id")
        user_id = task_data.get("user_id")
        raw_input = task_data.get("raw_input_text", "")
        is_clar_resp_by_main = task_data.get("is_clarification_response", False)
        
        eliar_log(EliarLogType.DEBUG, f"DummySubCode received task '{task_type}'.", component="DummySubCode", packet_id=packet_id, query_preview=raw_input[:30])
        
        await asyncio.sleep(random.uniform(0.1, 0.3)) # 비동기 처리 시뮬레이션

        # === 더미 응답 생성 로직 (SubCodeThoughtPacketData 필드에 맞게) ===
        response_final_output: Optional[str] = f"DummySubCode processed '{raw_input[:20]}' for task '{task_type}' (PID: ...{packet_id[-4:]})."
        processing_status_sub: str = "COMPLETED_BY_DUMMY_SUB"
        needs_clar_q_list: List[Dict[str, str]] = []
        anomalies_list_sub: List[Dict[str, Any]] = []

        if "그분" in raw_input.lower() and not is_clar_resp_by_main and not task_data.get("main_gpu_clarification_context"):
            response_final_output = None # 명확화 요청 시에는 최종 응답 없음
            processing_status_sub = "NEEDS_CLARIFICATION_BY_SUB"
            needs_clar_q_list.append({
                "original_term": "그분", # 명확화가 필요한 원본 용어
                "question": "제가 더 깊이 이해하고 예수 그리스도의 빛 안에서 응답드릴 수 있도록, 혹시 '그분'이 누구를 지칭하시는지(예: 하나님, 예수님) 조금 더 자세히 알려주시겠어요?"
            })
        elif "오류 발생" in raw_input.lower():
            response_final_output = None
            processing_status_sub = "ERROR_SIMULATED_BY_DUMMY_SUB"
            anomalies_list_sub.append({"type":"SIMULATED_ERROR_FROM_DUMMY", "details":"User requested error simulation in SubCode.", "severity":"HIGH"})
        elif "침묵" in raw_input.lower():
            response_final_output = None
            processing_status_sub = "COMPLETED_WITH_SILENCE_BY_SUB"

        # SubCodeThoughtPacketData 형태로 결과 구성
        response_packet_to_main = SubCodeThoughtPacketData(
            packet_id=packet_id, # MainGPU에서 받은 packet_id 그대로 사용
            conversation_id=conv_id, user_id=user_id,
            timestamp_created=task_data.get("timestamp_created", time.time()), # MainGPU가 전달한 생성시간 사용
            raw_input_text=raw_input,
            is_clarification_response=is_clar_resp_by_main, # Main의 판단을 반영 (SubCode가 변경 가능)
            final_output_by_sub_code=response_final_output,
            needs_clarification_questions=needs_clar_q_list,
            llm_analysis_summary={"intent_by_dummy": "simulated_intent_v2", "confidence":0.88},
            ethical_assessment_summary={"sub_code_eth_decision": "CONCEPTUALLY_PASSED_V2", "reasoning": "Dummy logic"},
            anomalies=anomalies_list_sub,
            learning_tags=["dummy_processed_v2", task_type],
            metacognitive_state_summary={"sub_internal_energy": 77.7, "sub_internal_focus": 0.92},
            processing_status_in_sub_code=processing_status_sub,
            timestamp_completed_by_sub_code=time.time() # SubCode 처리 완료 시간
        )

        if self.main_gpu_response_handler_cb:
            eliar_log(EliarLogType.DEBUG, "DummySubCode calling MainGPU response handler (async).", component="DummySubCode", packet_id=packet_id)
            try:
                # MainSubInterfaceCommunicator.sub_code_response_handler는 async def 이므로 await
                await self.main_gpu_response_handler_cb(response_packet_to_main)
            except Exception as e_cb_call:
                eliar_log(EliarLogType.ERROR, "Error calling MainGPU response handler from DummySubCode.", component="DummySubCode", packet_id=packet_id, error=e_cb_call)
        else:
            eliar_log(EliarLogType.WARN, "MainGPU response handler not set in DummySubCode. Cannot send result.", component="DummySubCode", packet_id=packet_id)


# --- 프로그램 진입점 ---
if __name__ == "__main__":
    ensure_log_dir()
    eliar_log(EliarLogType.CRITICAL, f"--- Eliar MainGPU Initializing (Version: {Eliar_VERSION}) ---", component=COMPONENT_NAME_ENTRY_POINT)
    
    # 1. 핵심 컨트롤러 및 통신 모듈 생성
    eliar_controller_instance = Eliar()
    # MainSubInterfaceCommunicator는 Eliar 인스턴스 내부에서 생성되거나, 외부에서 주입될 수 있음.
    # 여기서는 Eliar 생성자에서 communicator를 생성하도록 변경했으므로, Eliar 인스턴스만 필요.
    
    # 2. SubCode 인터페이스 인스턴스 생성 (테스트용 더미)
    # 실제 환경에서는 sub_gpu.py의 SubGPUModule 인스턴스를 로드하고 연결
    # from sub_gpu import SubGPUModule 
    # sub_code_actual_instance = SubGPUModule(config={...}) 
    dummy_sub_code = DummySubCodeInterface()
    
    # 3. Eliar 컨트롤러에 서브 시스템들 주입/연결
    # Eliar 생성자에서 communicator를 만들고, initialize_sub_systems에서 sub_code_instance를 communicator에 등록
    main_sub_communicator_instance = MainSubInterfaceCommunicator() # Eliar 내부에서 생성할 수도 있음. 여기서는 명시적 생성.
    eliar_controller_instance.initialize_sub_systems(main_sub_communicator_instance, dummy_sub_code)

    # 4. 비동기 이벤트 루프 시작 및 메인 로직 실행
    try:
        asyncio.run(main_conversation_simulation_loop_v3(eliar_controller_instance))
    except KeyboardInterrupt:
        eliar_log(EliarLogType.CRITICAL, "MainGPU execution interrupted by user.", component=COMPONENT_NAME_ENTRY_POINT)
    except Exception as e_global_run:
        eliar_log(EliarLogType.CRITICAL, "Unhandled top-level exception in MainGPU.", component=COMPONENT_NAME_ENTRY_POINT, error=e_global_run, exc_info_full=traceback.format_exc())
    finally:
        eliar_log(EliarLogType.CRITICAL, f"--- Eliar MainGPU (Version: {Eliar_VERSION}) Shutdown ---", component=COMPONENT_NAME_ENTRY_POINT)
