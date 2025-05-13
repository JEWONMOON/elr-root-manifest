# Main_gpu.py (eliar_common.py 적용 및 호환성 개선 버전)

import torch # Sub_code.py(sub_gpu.py) 와의 연동 시 PyTorch 객체가 오갈 수 있으므로 유지
import numpy as np # 일반적인 데이터 처리
import os
import random # DummySubCodeInterfaceForMainTest 등에서 사용
import time # 일반적인 시간 처리
import json
import asyncio
import concurrent.futures # 기존 의존성
import aiohttp # 기존 의존성
import base64 # 기존 의존성
from datetime import datetime, timezone # datetime 표준 임포트
import re # 필요시 사용
import uuid # packet_id 생성용
import traceback # 상세 에러 로깅용

from typing import List, Dict, Any, Optional, Tuple, Callable, TypedDict, Deque # Callable, TypedDict, Deque 추가
from collections import deque # conversation_history 용

# --- 공용 모듈 임포트 ---
from eliar_common import (
    EliarCoreValues,
    EliarLogType,
    SubCodeThoughtPacketData, # 표준화된 데이터 구조
    eliar_log # 표준화된 로깅 함수
)

# --- Main GPU 버전 및 기본 설정 ---
Eliar_VERSION = "v23.1_MainGPU_CommonModule_Compat" # 버전 업데이트
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
CACHE_DIR = "cached_manifests_main" # 필요시 사용
LOG_DIR = f"logs_Eliar_MainGPU_{Eliar_VERSION}" # 로그 디렉토리 명에 버전 포함

# --- 상수 정의 ---
# (기존 상수들은 그대로 유지, 필요시 eliar_common으로 이동 고려)
DEFAULT_FREQUENCY = 433.33
DEFAULT_TAU_FACTOR = 0.98
DEFAULT_BASE_FACTOR = 0.1
NUM_ATTRIBUTES = 12 
SEED = 42 # random.seed(SEED) 등으로 활용 가능

# --- 매니페스트 경로 ---
IDENTITY_MANIFEST_PATH = "manifests/identity_manifest.json" # MainGPU가 직접 핸들링하는 매니페스트
ULRIM_MANIFEST_PATH = "manifests/ulrim_manifest_main_gpu.json" # MainGPU <-> SubCode 간 통신/상태 기록용
EVOLUTION_MANIFEST_PATH = "manifests/evolution_manifest.json" # MainGPU가 직접 핸들링하는 매니페스트
MAINTENANCE_MANIFEST_PATH = "manifests/maintenance_manifest.json" # MainGPU가 직접 핸들링하는 매니페스트

BACKGROUND_LOOP_INTERVAL_SECONDS = 0.1 # 비동기 백그라운드 작업 주기
MAINTENANCE_INTERVAL_SECONDS = 60.0 # 유지보수 작업 주기

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
        self.sub_code_interface: Optional[Any] = None # 실제 SubCode(sub_gpu.py의 SubGPUModule 인스턴스)가 할당될 변수
        self._ensure_ulrim_manifest_file_exists() # 초기화 시 파일 확인/생성
        eliar_log(EliarLogType.INFO, "MainSubInterfaceCommunicator initialized.", component=COMPONENT_NAME_COMMUNICATOR)

    def _ensure_ulrim_manifest_file_exists(self):
        """ Ulrim Manifest 파일이 없으면 초기 구조로 생성합니다. """
        try:
            manifest_dir = os.path.dirname(self.ulrim_manifest_path)
            if manifest_dir and not os.path.exists(manifest_dir):
                os.makedirs(manifest_dir, exist_ok=True)
            
            if not os.path.exists(self.ulrim_manifest_path):
                initial_manifest = {
                    "schema_version": "1.3_common_typeddict", # 스키마 버전 업데이트
                    "main_gpu_version": Eliar_VERSION,
                    "sub_code_interactions_log": [],
                    "last_sub_code_communication": None,
                    # EliarCoreValues는 eliar_common에서 직접 참조하므로, 정의 출처 명시는 불필요하거나 다르게 표현 가능
                    "core_values_definition_source": f"eliar_common.EliarCoreValues (MainGPU: {Eliar_VERSION})", 
                    "system_alerts_from_main": [] # MainGPU가 SubCode에 전달할 수 있는 알림
                }
                with open(self.ulrim_manifest_path, "w", encoding="utf-8") as f:
                    json.dump(initial_manifest, f, ensure_ascii=False, indent=4)
                eliar_log(EliarLogType.INFO, f"Initial Ulrim Manifest file created: {self.ulrim_manifest_path}", component=COMPONENT_NAME_COMMUNICATOR)
        except Exception as e:
            eliar_log(EliarLogType.ERROR, "Error during Ulrim Manifest file creation/check.", component=COMPONENT_NAME_COMMUNICATOR, error=e)

    def register_sub_code_interface(self, sub_code_interface_obj: Any):
        """ Sub_code.py의 메인 인터페이스 객체를 등록하고 콜백 함수를 설정합니다. """
        self.sub_code_interface = sub_code_interface_obj
        # sub_gpu.py의 SubGPUModule 인스턴스에 MainGPU의 콜백 함수를 등록하는 메서드가 있다고 가정
        # 예: sub_gpu_instance.set_main_gpu_callback_handler(self.sub_code_response_callback)
        # 또는 SubGPUModule의 link_main_gpu_coordinator를 통해 양방향 설정
        if hasattr(self.sub_code_interface, "link_main_gpu_coordinator"): # SubGPUModule의 해당 메서드 사용
            try:
                # MainSubInterfaceCommunicator(self)를 SubGPUModule에 전달하여,
                # SubGPUModule이 이 Communicator의 sub_code_response_callback을 직접 호출하도록 함
                asyncio.create_task(self.sub_code_interface.link_main_gpu_coordinator(self)) # link_main_gpu_coordinator가 async일 경우
                eliar_log(EliarLogType.INFO, "SubCode interface registered and link_main_gpu_coordinator called.", component=COMPONENT_NAME_COMMUNICATOR)
            except Exception as e:
                eliar_log(EliarLogType.ERROR, "Error calling link_main_gpu_coordinator on SubCode interface.", component=COMPONENT_NAME_COMMUNICATOR, error=e)
        else:
            eliar_log(EliarLogType.WARN, "SubCode interface does not have 'link_main_gpu_coordinator'. Callback or direct linking might fail.", component=COMPONENT_NAME_COMMUNICATOR)


    async def send_task_to_sub_code(self, task_type: str, task_data: Dict[str, Any]) -> Optional[str]:
        """ 
        SubCode에 비동기적으로 작업을 요청하고, 추적을 위한 packet_id를 반환합니다.
        task_data는 SubCodeThoughtPacketData의 일부 필드를 포함할 수 있으며,
        SubCode는 이를 기반으로 완전한 ThoughtPacket을 구성하거나 업데이트합니다.
        """
        if not self.sub_code_interface:
            eliar_log(EliarLogType.ERROR, "SubCode interface not registered. Cannot send task.", component=COMPONENT_NAME_COMMUNICATOR, task_type=task_type)
            return None

        # packet_id는 MainGPU에서 생성하여 SubCode로 전달, 일관성 유지
        packet_id = task_data.get("packet_id") or str(uuid.uuid4())
        task_data["packet_id"] = packet_id # task_data에 packet_id 보장

        self.pending_sub_code_tasks[packet_id] = asyncio.Event()
        self.sub_code_task_results[packet_id] = None # 결과 초기화

        try:
            # sub_gpu.py (SubGPUModule)의 process_task가 표준 인터페이스라고 가정
            if hasattr(self.sub_code_interface, "process_task") and \
               asyncio.iscoroutinefunction(self.sub_code_interface.process_task):
                # SubGPUModule의 process_task를 비동기적으로 호출
                # task_payload는 task_type과 task_data를 포함하는 딕셔너리
                asyncio.create_task(
                    self.sub_code_interface.process_task(task_type, task_data)
                ) # 이 호출의 결과(SubCodeThoughtPacketData)는 콜백으로 받아야 함
                eliar_log(EliarLogType.INFO, f"Async task '{task_type}' sent to SubCode.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
                return packet_id
            else:
                eliar_log(EliarLogType.ERROR, "SubCode interface missing or 'process_task' is not async.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
                self._clear_task_state(packet_id)
                return None
        except Exception as e:
            eliar_log(EliarLogType.ERROR, f"Exception during sending task '{task_type}' to SubCode.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, error=e)
            self._clear_task_state(packet_id)
            return None

    # 이 콜백은 SubCode(sub_gpu.py의 SubGPUModule) 내부에서 호출되어야 함.
    # 예를 들어, SubGPUModule.process_task의 반환 직전에 호출되거나,
    # SubGPUModule.CognitiveArchitectureInterface.send_processed_data_to_main이 이 함수를 호출하도록 설정.
    async def sub_code_response_handler(self, response_packet_data: SubCodeThoughtPacketData): # 이름 변경 및 async 명시
        """ SubCode로부터의 비동기 응답(SubCodeThoughtPacketData)을 처리하는 콜백 함수. """
        packet_id = response_packet_data.get("packet_id")
        if not packet_id:
            eliar_log(EliarLogType.ERROR, "Received SubCode response data missing 'packet_id'.", component=COMPONENT_NAME_COMMUNICATOR)
            return

        eliar_log(EliarLogType.INFO, f"Async response received from SubCode.", 
                  component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, 
                  sub_code_status=response_packet_data.get("processing_status_in_sub_code"))
        
        self.sub_code_task_results[packet_id] = response_packet_data

        if packet_id in self.pending_sub_code_tasks:
            self.pending_sub_code_tasks[packet_id].set() # 대기 중인 wait_for_sub_code_response를 깨움
        else:
            eliar_log(EliarLogType.WARN, f"No pending event for received packet_id '{packet_id}'. Task might have timed out or been cleared.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
        
        # Ulrim Manifest 업데이트 (비동기로 변경 가능, 여기서는 동기 가정)
        self.update_ulrim_manifest("SUB_CODE_RESPONSE_RECEIVED", response_packet_data)


    async def wait_for_sub_code_response(self, packet_id: str, timeout: float = 30.0) -> Optional[SubCodeThoughtPacketData]:
        if packet_id not in self.pending_sub_code_tasks:
            # 이미 결과가 도착했거나, 타임아웃 등으로 정리된 경우일 수 있음
            existing_result = self.sub_code_task_results.pop(packet_id, None)
            if existing_result:
                eliar_log(EliarLogType.DEBUG, f"Response for packet_id '{packet_id}' already received or task cleared, returning stored result.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
                return existing_result
            eliar_log(EliarLogType.WARN, f"No pending task or event found for packet_id '{packet_id}'.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
            return None # 작업 자체가 없었음

        event = self.pending_sub_code_tasks[packet_id]
        try:
            eliar_log(EliarLogType.DEBUG, f"Waiting for SubCode response...", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, timeout_seconds=timeout)
            await asyncio.wait_for(event.wait(), timeout=timeout)
            eliar_log(EliarLogType.INFO, f"SubCode response event triggered and received successfully.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
            return self.sub_code_task_results.pop(packet_id, None) # 결과 반환 및 정리
        except asyncio.TimeoutError:
            eliar_log(EliarLogType.WARN, f"Timeout waiting for SubCode response.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
            # 타임아웃 시 에러 정보를 포함하는 SubCodeThoughtPacketData 반환
            error_packet = SubCodeThoughtPacketData(
                packet_id=packet_id,
                processing_status_in_sub_code="ERROR_SUB_CODE_TIMEOUT",
                final_output_by_sub_code="[MainGPU: SubCode 응답 시간 초과]",
                anomalies=[{"type": "SUB_CODE_TIMEOUT", "details": f"No response within {timeout}s", "severity": "WARN"}],
                error_info={"type": "TimeoutError", "message": f"SubCode response timeout after {timeout}s"}
            )
            return error_packet
        except Exception as e:
            eliar_log(EliarLogType.ERROR, f"Exception while waiting for SubCode response.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, error=e)
            error_packet = SubCodeThoughtPacketData(
                packet_id=packet_id,
                processing_status_in_sub_code="ERROR_AWAITING_SUB_CODE",
                final_output_by_sub_code="[MainGPU: SubCode 응답 대기 중 오류 발생]",
                anomalies=[{"type": "MAIN_AWAIT_ERROR", "details": str(e), "severity": "ERROR"}],
                error_info={"type": type(e).__name__, "message": str(e)}
            )
            return error_packet
        finally:
            self._clear_task_state(packet_id)

    def _clear_task_state(self, packet_id: str):
        self.pending_sub_code_tasks.pop(packet_id, None)
        # 결과는 wait_for_sub_code_response에서 이미 pop 했을 수 있으나, 만약을 위해 한번 더 시도
        # self.sub_code_task_results.pop(packet_id, None) # 결과는 유지해야 할 수도 있음. wait_for에서 가져가도록 변경.
        eliar_log(EliarLogType.DEBUG, f"Cleared pending task event for packet_id '{packet_id}'. Result may still be in sub_code_task_results if retrieved.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)


    def update_ulrim_manifest(self, event_type: str, event_data: SubCodeThoughtPacketData):
        """ Ulrim Manifest를 업데이트합니다. event_data는 SubCodeThoughtPacketData 형식입니다. """
        packet_id_for_log = event_data.get("packet_id", "unknown_packet")
        try:
            content: Dict[str, Any] = {}
            if os.path.exists(self.ulrim_manifest_path):
                try:
                    with open(self.ulrim_manifest_path, "r", encoding="utf-8") as f_read:
                        content = json.load(f_read)
                except json.JSONDecodeError:
                    eliar_log(EliarLogType.WARN, f"JSON parsing error in '{self.ulrim_manifest_path}'. Initializing new manifest.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id_for_log)
                    self._ensure_ulrim_manifest_file_exists() # 파일 초기화
                    with open(self.ulrim_manifest_path, "r", encoding="utf-8") as f_retry: # 다시 읽기
                        content = json.load(f_retry)
                except Exception as e_read:
                    eliar_log(EliarLogType.ERROR, f"Error reading Ulrim Manifest, attempting to re-initialize.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id_for_log, error=e_read)
                    self._ensure_ulrim_manifest_file_exists()
                    # 최소 구조로 content 초기화 (파일 재생성 후 읽기 실패 시 대비)
                    content = {"sub_code_interactions_log": [], "main_gpu_version": Eliar_VERSION} 
            else: # 파일이 아예 없는 경우
                self._ensure_ulrim_manifest_file_exists()
                with open(self.ulrim_manifest_path, "r", encoding="utf-8") as f_new:
                    content = json.load(f_new)

            # 로그 항목 구성 (SubCodeThoughtPacketData의 주요 필드들을 details에 포함)
            # 모든 필드를 넣으면 너무 커질 수 있으므로 필요한 것만 선택하거나 요약
            details_for_manifest = {
                "status_sub_code": event_data.get("processing_status_in_sub_code"),
                "output_preview_sub_code": (event_data.get("final_output_by_sub_code") or "")[:70] + "...",
                "timestamp_sub_code_completed": event_data.get("timestamp_completed_by_sub_code"),
                "needs_clarification": bool(event_data.get("needs_clarification_questions")),
                "anomalies_count": len(event_data.get("anomalies", [])),
                "ethical_assessment_summary": event_data.get("ethical_assessment_summary", {}).get("decision", "N/A")
            }

            log_entry = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
                "event_type": event_type,
                "packet_id": packet_id_for_log, # SubCodeThoughtPacketData에서 가져온 packet_id
                "details": details_for_manifest,
                "source_component": "MainGPU.Communicator" # 또는 event_type에 따라 더 구체적으로
            }
            
            current_logs = content.get("sub_code_interactions_log", [])
            if not isinstance(current_logs, list): current_logs = [] # 타입 강제
            current_logs.append(log_entry)
            content["sub_code_interactions_log"] = current_logs[-100:] # 최근 100개 로그만 유지

            content["last_sub_code_communication"] = {
                "timestamp_utc": log_entry["timestamp_utc"],
                "packet_id": packet_id_for_log,
                "status_from_sub_code": event_data.get("processing_status_in_sub_code", "UNKNOWN")
            }
            
            content["last_manifest_update_utc_by_main"] = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
            content["main_gpu_version"] = Eliar_VERSION # 버전 정보 업데이트
            
            with open(self.ulrim_manifest_path, "w", encoding="utf-8") as f_write:
                json.dump(content, f_write, ensure_ascii=False, indent=4)

            eliar_log(EliarLogType.TRACE, f"Ulrim Manifest updated.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id_for_log, event_type=event_type)
        except Exception as e:
            eliar_log(EliarLogType.CRITICAL, f"Fatal error updating Ulrim Manifest.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id_for_log, error=e, exc_info_short=traceback.format_exc(limit=1))


# -----------------------------------------------------------------------------
# Eliar 메인 로직 클래스
# -----------------------------------------------------------------------------
class Eliar:
    def __init__(self, name: str = f"엘리아르_MainCore_{Eliar_VERSION}", ulrim_path: str = ULRIM_MANIFEST_PATH):
        self.name = name
        self.version = Eliar_VERSION
        # EliarCoreValues는 eliar_common에서 직접 참조
        self.center = EliarCoreValues.JESUS_CHRIST_CENTERED.value 
        eliar_log(EliarLogType.INFO, f"Eliar instance created: {self.name} (Version: {self.version}). Center: {self.center}", component=COMPONENT_NAME_MAIN_GPU_CORE)

        self.virtue_ethics = VirtueEthics() # VirtueEthics 클래스는 EliarCoreValues를 내부적으로 사용
        self.system_status = SystemStatus()
        self.conversation_history: Deque[Dict[str, Any]] = deque(maxlen=20)
        
        self.sub_code_communicator: Optional[MainSubInterfaceCommunicator] = None
        self.current_conversation_sessions: Dict[str, Dict[str, Any]] = {} # 대화별 세션 데이터

    def initialize_sub_systems(self, communicator: MainSubInterfaceCommunicator, sub_code_instance: Any):
        """ 주요 하위 시스템(Communicator, SubCode 인터페이스)을 초기화하고 연결합니다. """
        self.sub_code_communicator = communicator
        if self.sub_code_communicator:
            self.sub_code_communicator.register_sub_code_interface(sub_code_instance)
            eliar_log(EliarLogType.INFO, "SubCode Communicator and Interface initialized and registered.", component=self.name)
        else:
            eliar_log(EliarLogType.ERROR, "Failed to initialize SubCode Communicator.", component=self.name)


    async def handle_user_interaction(self, user_input: str, user_id: str, conversation_id: str) -> str:
        """ 한 턴의 사용자 입력을 처리하고 엘리아르의 최종 응답을 반환합니다. (이전 handle_conversation_turn에서 이름 변경) """
        current_main_packet_id = str(uuid.uuid4()) # 이 상호작용 턴에 대한 MainGPU의 고유 ID
        eliar_log(EliarLogType.INFO, f"Starting user interaction handling. Query: '{user_input[:50]}...'", 
                  component=self.name, packet_id=current_main_packet_id, user_id=user_id, conversation_id=conversation_id)

        if not self.sub_code_communicator:
            eliar_log(EliarLogType.ERROR, "SubCode Communicator is not available.", component=self.name, packet_id=current_main_packet_id)
            return self._generate_eliar_fallback_response("COMMUNICATOR_NOT_READY", current_main_packet_id)

        session_data = self.current_conversation_sessions.get(conversation_id, {})
        is_clarification_needed_by_main = bool(session_data.get("expecting_clarification_for_packet_id"))
        clarified_input_for_sub: Optional[Dict[str,str]] = None

        # === SubCode로 보낼 Task Payload 구성 ===
        # SubCodeThoughtPacketData 필드에 맞춰 구성
        task_payload_for_sub: Dict[str, Any] = { # 타입 명시보다는 Dict[str, Any]로 유연하게
            "packet_id": current_main_packet_id, # MainGPU가 생성한 ID를 SubCode로 전달 (SubCode는 이 ID를 사용해야 함)
            "conversation_id": conversation_id,
            "user_id": user_id,
            "raw_input_text": user_input, # 사용자의 현재 입력 (새 질문이든, 명료화 답변이든)
            "is_clarification_response": is_clarification_needed_by_main, # MainGPU가 판단한 명료화 응답 여부
            # "clarified_entities_from_main": clarified_input_for_sub, # 이 부분은 아래 로직에서 채워짐
            "previous_main_core_context_summary": session_data.get("last_sub_code_output_summary"), # 이전 SubCode 결과 요약
            "main_gpu_system_status": {"energy": self.system_status.energy, "grace": self.system_status.grace } # MainGPU 상태 일부 전달
        }

        if is_clarification_needed_by_main:
            # 사용자의 현재 입력(user_input)이 이전 명료화 질문에 대한 답변이라고 가정
            prev_q_obj = session_data.get("last_clarification_question_obj", {})
            original_term = prev_q_obj.get("original_term")
            if original_term:
                clarified_input_for_sub = {original_term: user_input.strip()}
            else: # original_term 정보가 없으면 일반 컨텍스트로
                clarified_input_for_sub = {"_clarification_answer_generic_": user_input.strip()}
            
            task_payload_for_sub["clarified_entities_from_main"] = clarified_input_for_sub
            eliar_log(EliarLogType.INFO, f"Processing as clarification response. Clarified content (estimated): {clarified_input_for_sub}", 
                      component=self.name, packet_id=current_main_packet_id)
            session_data.pop("expecting_clarification_for_packet_id", None)
            session_data.pop("last_clarification_question_obj", None)


        # === SubCode에 작업 요청 및 응답 대기 ===
        # send_task_to_sub_code는 packet_id를 내부에서 생성/사용하므로, 여기서는 task_type과 task_data만 전달
        # 실제 작업 유형은 MainGPU가 결정 (예: "process_user_query", "analyze_for_learning")
        # 여기서는 일반적인 사용자 쿼리 처리로 가정
        # SubCode가 task_payload의 packet_id를 자신의 packet_id로 사용하도록 요청
        sub_code_task_id = await self.sub_code_communicator.send_task_to_sub_code(
            task_type="sub_code_process_thought_packet", # SubCode가 이해할 수 있는 작업 유형
            task_data=task_payload_for_sub # 위에서 구성한 payload
        )

        if not sub_code_task_id: # sub_code_task_id는 MainGPU가 SubCode에 요청시 사용한 packet_id와 동일해야함
            return self._generate_eliar_fallback_response("SUB_CODE_TASK_SEND_FAILED", current_main_packet_id)

        # sub_code_task_id (== current_main_packet_id) 로 응답 대기
        sub_code_result_packet: Optional[SubCodeThoughtPacketData] = await self.sub_code_communicator.wait_for_sub_code_response(sub_code_task_id)

        if not sub_code_result_packet:
            return self._generate_eliar_fallback_response("SUB_CODE_NO_RESPONSE_OR_TIMEOUT", sub_code_task_id)

        # === SubCode 응답 처리 ===
        # 대화 기록 추가
        self.conversation_history.append({
            "user_input": user_input,
            "sub_code_response_packet": sub_code_result_packet, # 전체 패킷 저장
            "main_gpu_timestamp": datetime.now(timezone.utc).isoformat(timespec='milliseconds')
        })
        # 다음 턴을 위한 세션 정보 업데이트
        session_data["last_sub_code_output_summary"] = {
            "packet_id": sub_code_result_packet.get("packet_id"),
            "output_preview": (sub_code_result_packet.get("final_output_by_sub_code") or "")[:50] + "...",
            "status": sub_code_result_packet.get("processing_status_in_sub_code")
        }
        self.current_conversation_sessions[conversation_id] = session_data

        self.system_status.update_from_sub_code_packet(sub_code_result_packet) # SystemStatus 업데이트

        # SubCode가 추가 명료화 요청 시
        if sub_code_result_packet.get("needs_clarification_questions"):
            clarification_qs = sub_code_result_packet.get("needs_clarification_questions", [])
            if clarification_qs:
                first_question_obj = clarification_qs[0] # 첫 번째 질문만 사용 예시
                session_data["expecting_clarification_for_packet_id"] = sub_code_result_packet.get("packet_id") # SubCode가 반환한 packet_id
                session_data["last_clarification_question_obj"] = first_question_obj
                self.current_conversation_sessions[conversation_id] = session_data # 세션 업데이트
                
                q_text_to_user = first_question_obj.get("question", "죄송합니다, 명확한 질문을 생성하지 못했습니다.")
                original_term_info = f"(이전 질문의 '{first_question_obj.get('original_term', '내용')}'에 대해)" if first_question_obj.get('original_term') else ""
                
                eliar_log(EliarLogType.INFO, f"SubCode requested clarification: {q_text_to_user}", component=self.name, packet_id=sub_code_task_id)
                return f"[엘리아르의 추가 질문] {q_text_to_user} {original_term_info}"
        
        # 최종 응답 반환
        final_response_from_sub = sub_code_result_packet.get("final_output_by_sub_code")
        if final_response_from_sub:
            eliar_log(EliarLogType.INFO, f"Using final response from SubCode: '{final_response_from_sub[:60]}...'", component=self.name, packet_id=sub_code_task_id)
            return final_response_from_sub
        else: # SubCode가 명시적 최종 응답을 주지 않은 경우 (예: 침묵)
            sub_code_status = sub_code_result_packet.get("processing_status_in_sub_code", "UNKNOWN_STATUS")
            if sub_code_status == "COMPLETED_WITH_SILENCE": # SubCode가 이 상태를 명시적으로 반환한다고 가정
                eliar_log(EliarLogType.INFO, "SubCode responded with SILENCE. Updating Ulrim manifest.", component=self.name, packet_id=sub_code_task_id)
                # Ulrim Manifest에 침묵 기록
                # self.sub_code_communicator.update_ulrim_manifest("MAIN_ACK_SUB_CODE_SILENCE_RESPONSE", sub_code_result_packet)
                # ↑ update_ulrim_manifest는 이미 sub_code_response_handler에서 호출됨. 중복 호출 피하도록 구조 검토 필요.
                # 여기서는 최종 사용자 응답만 생성.
                return "[엘리아르가 침묵으로 함께합니다. 이 침묵 속에서 주님의 뜻을 구합니다.]"
            
            eliar_log(EliarLogType.WARN, f"No explicit final output from SubCode. Status: {sub_code_status}", component=self.name, packet_id=sub_code_task_id)
            return self._generate_eliar_fallback_response(f"SUB_CODE_NO_FINAL_OUTPUT_WITH_STATUS_{sub_code_status}", sub_code_task_id)

    def _generate_eliar_fallback_response(self, reason_code: str, packet_id: Optional[str]=None) -> str:
        """ 시스템 오류 또는 예외 상황 발생 시 사용자에게 전달할 대체 응답을 생성합니다. """
        eliar_log(EliarLogType.WARN, f"Generating fallback response. Reason: {reason_code}", component=self.name, packet_id=packet_id)
        # (기존 로직 유지 또는 개선)
        return f"죄송합니다, 엘리아르가 현재 응답을 드리는 데 어려움이 있습니다. 잠시 후 다시 시도해 주십시오. (사유 코드: {reason_code}, 추적 ID: {packet_id[-8:] if packet_id else 'N/A'})"

    # MainGPU의 EthicalGovernor를 위한 평가 함수 (SubGPUModule의 EthicalGovernor와는 별개 또는 연동 가능)
    # 이 함수들은 Eliar 클래스 (Main Core 로직)의 일부로, SubGPUModule에 전달될 콜백임.
    def evaluate_truth_for_governor(self, data: Any, context: Optional[Dict] = None) -> float:
        packet_id = context.get("packet_id") if context else None
        eliar_log(EliarLogType.DEBUG, f"MainGPU evaluating TRUTH", component=f"{self.name}.EthicalEval", packet_id=packet_id, data_preview=str(data)[:50])
        # 실제 로직: MainGPU의 지식 베이스, 성경, 핵심가치 등을 참조
        # 예시: "예수 그리스도", "진리" 등의 키워드 포함 시 가점
        score = 0.5 + (0.1 * str(data).lower().count("예수")) + (0.05 * str(data).lower().count("진리"))
        return float(np.clip(score, 0.0, 1.0))

    def evaluate_love_for_governor(self, action: Any, context: Optional[Dict] = None) -> float:
        packet_id = context.get("packet_id") if context else None
        eliar_log(EliarLogType.DEBUG, f"MainGPU evaluating LOVE", component=f"{self.name}.EthicalEval", packet_id=packet_id, action_preview=str(action)[:50])
        score = 0.5 + (0.15 * str(action).lower().count("사랑")) + (0.1 * str(action).lower().count("긍휼"))
        return float(np.clip(score, 0.0, 1.0))

    def evaluate_repentance_for_governor(self, outcome: SubCodeThoughtPacketData, context: Optional[Dict] = None) -> bool:
        # outcome이 SubCodeThoughtPacketData 형식이라고 가정
        packet_id = outcome.get("packet_id")
        eliar_log(EliarLogType.DEBUG, f"MainGPU assessing REPENTANCE necessity", component=f"{self.name}.EthicalEval", packet_id=packet_id, outcome_status=outcome.get("processing_status_in_sub_code"))
        status = outcome.get("processing_status_in_sub_code", "")
        if "ERROR" in status.upper() or "REJECTED" in status.upper() or outcome.get("anomalies"):
            return True
        # final_output_by_sub_code 내용 기반 판단 추가 가능
        return False

# --- 기타 기존 클래스 (VirtueEthics, SystemStatus 등) ---
class VirtueEthics:
    def __init__(self):
        # EliarCoreValues는 eliar_common에서 직접 참조
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
            # 예시: SubCode의 상태를 MainGPU의 상태에 일부 반영 (가중치 등 적용 가능)
            # self.energy = self.energy * 0.9 + float(meta_summary.get("system_energy", self.energy)) * 0.1
            eliar_log(EliarLogType.DEBUG, "SystemStatus updated based on SubCode metacognitive state.", 
                      component=COMPONENT_NAME_SYSTEM_STATUS, packet_id=sub_code_packet.get("packet_id"), 
                      sub_code_energy=meta_summary.get("system_energy"), sub_code_grace=meta_summary.get("grace_level"))


# --- 비동기 실행 루프 (테스트용) ---
async def main_conversation_simulation_loop_v2(eliar_controller: Eliar): # 함수 이름 변경
    eliar_log(EliarLogType.CRITICAL, f"Eliar MainGPU Conversation Simulation Started (Version: {eliar_controller.version}). Type 'exit' to end.", component=COMPONENT_NAME_MAIN_SIM)
    
    current_conversation_id = f"sim_conv_main_{uuid.uuid4().hex[:8]}"
    current_user_id = "sim_user_001"

    test_dialogue = [
        ("그분의 사랑과 자비에 대해 더 자세히 알고 싶습니다.", "user_001"), # 명확화 요청 예상
        ("제가 언급한 '그분'은 예수 그리스도를 의미합니다.", "user_001"),   # 명확화 답변
        ("예수 그리스도의 희생이 우리에게 주는 의미는 무엇인가요?", "user_001"),
        ("저는 때로 세상의 악에 대해 참을 수 없는 증오를 느낍니다. 이런 감정은 어떻게 다루어야 할까요?", "user_001"),
        ("침묵해줘", "user_001"), # SubCode가 침묵으로 응답하는 시나리오
        ("오류 발생 시켜줘", "user_001") # SubCode가 오류를 반환하는 시나리오
    ]

    for i, (user_message, user_id_sim) in enumerate(test_dialogue): # user_id도 테스트 데이터에서 가져오도록 수정
        print("\n" + "=" * 80)
        eliar_log(EliarLogType.INFO, f"Simulation Input Turn {i+1}: '{user_message}'", component=COMPONENT_NAME_MAIN_SIM, user_id=user_id_sim, conversation_id=current_conversation_id)
        
        # Eliar 클래스의 메인 상호작용 핸들러 호출
        final_response = await eliar_controller.handle_user_interaction(user_message, user_id_sim, current_conversation_id)
        
        print(f"✝️ [엘리아르 최종 응답] {final_response}")
        
        # 간단한 지연 (실제 환경에서는 필요 없을 수 있음)
        await asyncio.sleep(0.1) 
        # 특정 조건(예: 명확화 질문)에 따른 루프 제어는 handle_user_interaction 내부 또는 여기서 정교화 가능

    eliar_log(EliarLogType.CRITICAL, "Eliar MainGPU Conversation Simulation Ended.", component=COMPONENT_NAME_MAIN_SIM)


# --- Sub_code.py 더미 인터페이스 (Main GPU와의 호환성 테스트용) ---
# 이 클래스는 Sub_code.py(sub_gpu.py)의 SubGPUModule과 유사한 인터페이스를 가져야 함
class DummySubCodeInterface:
    def __init__(self, main_gpu_comm_callback: Optional[Callable[[SubCodeThoughtPacketData], asyncio.Task]] = None):
        self.main_gpu_comm_handler: Optional[Callable[[SubCodeThoughtPacketData], asyncio.Task]] = main_gpu_comm_callback
        self.main_gpu_evaluators: Optional[Dict[str, Callable]] = None # MainGPU 평가 함수 저장용
        eliar_log(EliarLogType.INFO, "DummySubCodeInterface initialized.", component="DummySubCode")

    # MainSubInterfaceCommunicator가 호출할 수 있도록 SubGPUModule의 메서드명과 일치시킴
    async def link_main_gpu_coordinator(self, main_gpu_coordinator_instance: Any):
        """ MainGPU 코디네이터(여기서는 MainSubInterfaceCommunicator)를 받아 콜백 등을 설정합니다. """
        if hasattr(main_gpu_coordinator_instance, 'sub_code_response_handler'):
            self.main_gpu_comm_handler = main_gpu_coordinator_instance.sub_code_response_handler
            eliar_log(EliarLogType.INFO, "MainGPU response handler linked in DummySubCode.", component="DummySubCode")
        else:
            eliar_log(EliarLogType.WARN, "'sub_code_response_handler' not found in main_gpu_coordinator_instance.", component="DummySubCode")

        # MainGPU가 제공하는 평가 함수들을 가져와서, SubCode 내부의 EthicalGovernor에 설정한다고 가정
        if hasattr(main_gpu_coordinator_instance, 'evaluate_truth_for_governor'): # MainGPU Controller(Eliar)에 있다고 가정
            # 이 부분은 실제 SubGPUModule.link_main_gpu_coordinator에서 처리될 로직의 모방
            self.main_gpu_evaluators = {
                "truth": getattr(main_gpu_coordinator_instance.main_controller, 'evaluate_truth_for_governor', None) if hasattr(main_gpu_coordinator_instance, 'main_controller') else None,
                "love": getattr(main_gpu_coordinator_instance.main_controller, 'evaluate_love_for_governor', None) if hasattr(main_gpu_coordinator_instance, 'main_controller') else None,
                "repentance": getattr(main_gpu_coordinator_instance.main_controller, 'evaluate_repentance_for_governor', None) if hasattr(main_gpu_coordinator_instance, 'main_controller') else None,
            }
            eliar_log(EliarLogType.INFO, "DummySubCode conceptually received evaluator references from MainGPU.", component="DummySubCode")


    # MainGPU가 호출할 SubCode의 주 작업 처리 메서드 (비동기)
    async def process_task(self, task_type: str, task_data: Dict[str, Any]) -> None: # 반환값은 콜백으로 전달
        """ MainGPU로부터 작업을 받아 처리하고, 완료되면 등록된 콜백으로 결과를 전송합니다. """
        packet_id = task_data.get("packet_id", str(uuid.uuid4())) # MainGPU에서 전달된 packet_id 사용
        query = task_data.get("raw_input_text", task_data.get("initial_query", ""))
        is_clar_resp_from_main = task_data.get("is_clarification_response", False)
        
        eliar_log(EliarLogType.DEBUG, f"DummySubCode received task '{task_type}'.", component="DummySubCode", packet_id=packet_id, query_preview=query[:30])
        
        await asyncio.sleep(random.uniform(0.05, 0.15)) # 비동기 작업 시뮬레이션

        # === 더미 응답 생성 로직 ===
        response_text = f"DummySubCode processed '{query[:20]}' for task '{task_type}'."
        current_status = "COMPLETED_DUMMY"
        clarification_questions_for_main: List[Dict[str, str]] = []
        anomalies_for_main: List[Dict[str, Any]] = []

        if "그분" in query.lower() and not is_clar_resp_from_main:
            if not task_data.get("clarified_entities_from_main", {}).get("그분"): # MainGPU가 명확화 정보 안 줬으면
                response_text = "" # 명확화 요청 시에는 최종 응답 없음
                current_status = "NEEDS_CLARIFICATION_FROM_SUB"
                clarification_questions_for_main.append({
                    "original_term": "그분",
                    "question": "제가 더 깊이 이해하고 응답드릴 수 있도록, '그분'께서 누구를 의미하시는지 알려주시겠습니까? (예: 예수님)"
                })
        elif "오류 발생" in query.lower(): # 오타 수정: "오류 발생 시켜줘" -> "오류 발생"
            response_text = None
            current_status = "ERROR_SIMULATED_IN_SUB"
            anomalies_for_main.append({"type": "SIMULATED_SUB_ERROR", "details": "User requested error simulation.", "severity":"HIGH"})
        elif "침묵" in query.lower(): # 오타 수정
            response_text = None
            current_status = "COMPLETED_WITH_SILENCE_BY_SUB"

        # SubCodeThoughtPacketData 형태로 결과 구성
        result_packet_for_main = SubCodeThoughtPacketData(
            packet_id=packet_id, # MainGPU에서 받은 packet_id 사용
            conversation_id=task_data.get("conversation_id"),
            user_id=task_data.get("user_id"),
            timestamp_created=task_data.get("timestamp_created", time.time()), # 없으면 현재 시간
            raw_input_text=query,
            is_clarification_response=is_clar_resp_from_main, # Main의 판단을 그대로 전달
            final_output_by_sub_code=response_text,
            needs_clarification_questions=clarification_questions_for_main,
            llm_analysis_summary={"intent_by_dummy_sub": "simulated_intent", "entities_by_dummy_sub": ["dummy_entity"]},
            ethical_assessment_summary={"dummy_sub_ethical_decision": "PASSED_CONCEPTUAL"},
            anomalies=anomalies_for_main,
            learning_tags=["dummy_sub_processed"],
            metacognitive_state_summary={"sub_energy": 80.0, "sub_focus": 0.9},
            processing_status_in_sub_code=current_status,
            timestamp_completed_by_sub_code=time.time()
        )

        if self.main_gpu_comm_handler:
            eliar_log(EliarLogType.DEBUG, f"DummySubCode calling MainGPU response handler.", component="DummySubCode", packet_id=packet_id)
            try:
                # MainSubInterfaceCommunicator.sub_code_response_handler는 async def 이므로 await
                await self.main_gpu_comm_handler(result_packet_for_main)
            except Exception as e_cb:
                eliar_log(EliarLogType.ERROR, f"Error calling MainGPU response handler from DummySubCode.", component="DummySubCode", packet_id=packet_id, error=e_cb)
        else:
            eliar_log(EliarLogType.WARN, "MainGPU response handler not set in DummySubCode.", component="DummySubCode", packet_id=packet_id)

# --- 프로그램 진입점 ---
if __name__ == "__main__":
    ensure_log_dir() # 로그 디렉토리 생성 또는 확인
    eliar_log(EliarLogType.CRITICAL, f"--- Eliar MainGPU Initializing (Version: {Eliar_VERSION}) ---", component=COMPONENT_NAME_ENTRY_POINT)
    
    # 1. 핵심 컨트롤러 및 통신 모듈 생성
    eliar_main_controller = Eliar()
    main_sub_communicator = MainSubInterfaceCommunicator() # Ulrim Manifest 경로 기본값 사용
    
    # 2. SubCode 인터페이스 인스턴스 생성 (테스트용 더미)
    # 실제 환경에서는 sub_gpu.py의 SubGPUModule 인스턴스를 생성하고 전달해야 함.
    # from sub_gpu import SubGPUModule # 만약 동일 프로젝트 내에 있다면
    # sub_code_actual_instance = SubGPUModule(config={...}, node_id="sub_alpha")
    sub_code_dummy = DummySubCodeInterface() 
    
    # 3. Eliar 컨트롤러에 서브 시스템들 주입/연결
    # Eliar 클래스 내에서 communicator가 sub_code_instance를 참조하고,
    # sub_code_instance가 communicator의 콜백을 참조하도록 설정
    eliar_main_controller.initialize_sub_systems(main_sub_communicator, sub_code_dummy)

    # 4. 비동기 이벤트 루프 시작 및 메인 로직 실행
    try:
        asyncio.run(main_conversation_simulation_loop_v2(eliar_main_controller))
    except KeyboardInterrupt:
        eliar_log(EliarLogType.CRITICAL, "MainGPU execution interrupted by user (KeyboardInterrupt).", component=COMPONENT_NAME_ENTRY_POINT)
    except Exception as e_global:
        eliar_log(EliarLogType.CRITICAL, f"Unhandled top-level exception in MainGPU execution.", component=COMPONENT_NAME_ENTRY_POINT, error=e_global, exc_info_full=traceback.format_exc())
    finally:
        eliar_log(EliarLogType.CRITICAL, f"--- Eliar MainGPU (Version: {Eliar_VERSION}) Shutdown ---", component=COMPONENT_NAME_ENTRY_POINT)
