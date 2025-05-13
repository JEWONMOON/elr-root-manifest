# Main_gpu.py (eliar_common.py 적용, 클래스 정의 복원, GitHub 연동 준비 및 호환성 최종 개선 버전)

import numpy as np # 일반적인 데이터 처리
import os
import random # DummySubCodeInterfaceForMainTest 등에서 사용
import json
import asyncio
import concurrent.futures # 기존 의존성 유지
import aiohttp # GitHub API 호출 등 비동기 HTTP 요청용
import base64 # GitHub 커밋용
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
Eliar_VERSION = "v24.2_MainGPU_FullClass_GitHubReady_Compat" # 버전 업데이트
COMPONENT_NAME_MAIN_GPU_CORE = "MainGPU.EliarCore"
COMPONENT_NAME_COMMUNICATOR = "MainGPU.Communicator"
COMPONENT_NAME_SYSTEM_STATUS = "MainGPU.SystemStatus"
COMPONENT_NAME_VIRTUE_ETHICS = "MainGPU.VirtueEthics"
COMPONENT_NAME_MAIN_SIM = "MainGPU.ConversationSim"
COMPONENT_NAME_ENTRY_POINT = "MainGPU.EntryPoint"
COMPONENT_NAME_GITHUB_MANAGER = "MainGPU.GitHubManager" # GitHub 연동용

# --- GitHub API 설정 ---
GITHUB_API_BASE_URL = "https://api.github.com" # 전체 URL 대신 기본 URL 사용
GITHUB_API_REPO_CONTENTS_URL = f"{GITHUB_API_BASE_URL}/repos/JEWONMOON/elr-root-manifest/contents" # 기존 URL 유지
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

# --- 상수 정의 (기존 코드에서 가져옴) ---
DEFAULT_FREQUENCY = 433.33
DEFAULT_TAU_FACTOR = 0.98
DEFAULT_BASE_FACTOR = 0.1
NUM_ATTRIBUTES = 12 
SEED = 42 # 예시: random.seed(SEED) 사용 가능

# --- 매니페스트 경로 ---
IDENTITY_MANIFEST_PATH = "manifests/identity_manifest.json"
ULRIM_MANIFEST_PATH = "manifests/ulrim_manifest_main_gpu.json"
EVOLUTION_MANIFEST_PATH = "manifests/evolution_manifest.json"
MAINTENANCE_MANIFEST_PATH = "manifests/maintenance_manifest.json"
# GitHub 커밋 대상이 될 수 있는 파일 경로 예시
CONVERSATION_LOG_GITHUB_PATH = "manifests/conversation_log.txt" # GitHub 커밋 가이드 예시 경로

BACKGROUND_LOOP_INTERVAL_SECONDS = 0.1
MAINTENANCE_INTERVAL_SECONDS = 60.0

# --- 유틸리티 함수 ---
def ensure_dir_exists(dir_path: str):
    if not os.path.exists(dir_path):
        try:
            os.makedirs(dir_path, exist_ok=True)
            eliar_log(EliarLogType.INFO, f"Directory created: {dir_path}", component=COMPONENT_NAME_MAIN_GPU_CORE)
        except Exception as e:
            eliar_log(EliarLogType.ERROR, f"Failed to create directory: {dir_path}", component=COMPONENT_NAME_MAIN_GPU_CORE, error=e)

ensure_log_dir() # 로그 디렉토리 생성 또는 확인
ensure_dir_exists(os.path.dirname(ULRIM_MANIFEST_PATH)) # 매니페스트 디렉토리 생성

# -----------------------------------------------------------------------------
# GitHub API 연동 관리 클래스 (새로운 기능)
# -----------------------------------------------------------------------------
class GitHubCommitManager:
    def __init__(self, session: aiohttp.ClientSession, base_repo_url: str, headers: Dict[str, str]):
        self.session = session
        self.base_repo_url = base_repo_url # 예: "https://api.github.com/repos/JEWONMOON/elr-root-manifest"
        self.headers = headers
        eliar_log(EliarLogType.INFO, "GitHubCommitManager initialized.", component=COMPONENT_NAME_GITHUB_MANAGER, base_url=base_repo_url)

    async def get_file_sha(self, file_path: str, packet_id: Optional[str] = None) -> Optional[str]:
        """ GitHub에서 파일의 SHA 값을 가져옵니다. 파일이 없으면 None을 반환합니다. """
        url = f"{self.base_repo_url}/contents/{file_path.lstrip('/')}"
        log_comp = f"{COMPONENT_NAME_GITHUB_MANAGER}.GetSHA"
        try:
            eliar_log(EliarLogType.DEBUG, f"Attempting to get SHA for file.", component=log_comp, packet_id=packet_id, file_path=file_path, url=url)
            async with self.session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    sha = data.get("sha")
                    eliar_log(EliarLogType.INFO, f"Successfully retrieved SHA for file.", component=log_comp, packet_id=packet_id, file_path=file_path, sha=sha)
                    return sha
                elif response.status == 404:
                    eliar_log(EliarLogType.INFO, f"File not found on GitHub (will create new).", component=log_comp, packet_id=packet_id, file_path=file_path)
                    return None # 파일이 없으면 새로 생성해야 하므로 SHA 없음
                else:
                    error_text = await response.text()
                    eliar_log(EliarLogType.ERROR, f"Failed to get file SHA. Status: {response.status}", component=log_comp, packet_id=packet_id, file_path=file_path, response_text=error_text[:200])
                    return None
        except aiohttp.ClientError as e:
            eliar_log(EliarLogType.ERROR, f"Network error while getting file SHA.", component=log_comp, packet_id=packet_id, file_path=file_path, error=e)
            return None
        except Exception as e:
            eliar_log(EliarLogType.ERROR, f"Unexpected error getting file SHA.", component=log_comp, packet_id=packet_id, file_path=file_path, error=e)
            return None

    async def commit_file_to_github(self, file_path: str, content_str: str, commit_message: str, branch: str = "main", packet_id: Optional[str] = None) -> Optional[str]:
        """
        주어진 내용을 GitHub 리포지토리에 커밋합니다.
        성공 시 커밋된 파일의 HTML URL을, 실패 시 None을 반환합니다.
        """
        log_comp = f"{COMPONENT_NAME_GITHUB_MANAGER}.CommitFile"
        if not ELIAR_GITHUB_PAT:
            eliar_log(EliarLogType.WARN, "GitHub PAT not configured. Cannot commit file.", component=log_comp, packet_id=packet_id, file_path=file_path)
            return None

        current_sha = await self.get_file_sha(file_path, packet_id=packet_id)
        
        encoded_content = base64.b64encode(content_str.encode('utf-8')).decode('utf-8')
        
        payload: Dict[str, Any] = {
            "message": commit_message,
            "content": encoded_content,
            "branch": branch
        }
        if current_sha: # 파일 업데이트 시 SHA 포함
            payload["sha"] = current_sha

        url = f"{self.base_repo_url}/contents/{file_path.lstrip('/')}"
        eliar_log(EliarLogType.INFO, f"Attempting to commit file to GitHub.", component=log_comp, packet_id=packet_id, file_path=file_path, message=commit_message, updating_existing_file=bool(current_sha))

        try:
            async with self.session.put(url, headers=self.headers, json=payload) as response:
                response_data = await response.json()
                if response.status == 201 or response.status == 200: # 201: Created, 200: Updated
                    html_url = response_data.get("content", {}).get("html_url")
                    commit_sha = response_data.get("commit", {}).get("sha")
                    eliar_log(EliarLogType.INFO, "File successfully committed to GitHub.", component=log_comp, packet_id=packet_id, file_path=file_path, html_url=html_url, commit_sha=commit_sha)
                    return html_url
                else:
                    eliar_log(EliarLogType.ERROR, f"Failed to commit file to GitHub. Status: {response.status}", component=log_comp, packet_id=packet_id, file_path=file_path, response_data=response_data)
                    return None
        except aiohttp.ClientError as e:
            eliar_log(EliarLogType.ERROR, "Network error during GitHub commit.", component=log_comp, packet_id=packet_id, file_path=file_path, error=e)
            return None
        except Exception as e:
            eliar_log(EliarLogType.ERROR, "Unexpected error during GitHub commit.", component=log_comp, packet_id=packet_id, file_path=file_path, error=e)
            return None

# -----------------------------------------------------------------------------
# Main-Sub Code 연동 클래스 (이전 코드 기반 + GitHub 연동 고려)
# -----------------------------------------------------------------------------
class MainSubInterfaceCommunicator:
    def __init__(self, ulrim_manifest_path_for_main: str = ULRIM_MANIFEST_PATH, github_manager: Optional[GitHubCommitManager] = None):
        self.ulrim_manifest_path = ulrim_manifest_path_for_main
        self.pending_sub_code_tasks: Dict[str, asyncio.Event] = {}
        self.sub_code_task_results: Dict[str, Optional[SubCodeThoughtPacketData]] = {}
        self.sub_code_interface: Optional[Any] = None
        self.github_manager = github_manager # GitHubCommitManager 인스턴스
        self._ensure_ulrim_manifest_file_exists()
        eliar_log(EliarLogType.INFO, "MainSubInterfaceCommunicator initialized.", component=COMPONENT_NAME_COMMUNICATOR, github_manager_assigned=bool(github_manager))

    def _ensure_ulrim_manifest_file_exists(self):
        # (이전 _ensure_ulrim_manifest_file_exists 로직과 동일)
        try:
            manifest_dir = os.path.dirname(self.ulrim_manifest_path)
            if manifest_dir and not os.path.exists(manifest_dir): os.makedirs(manifest_dir, exist_ok=True)
            if not os.path.exists(self.ulrim_manifest_path):
                initial_manifest = { "schema_version": "1.5_common_eliar_full_compat", "main_gpu_version": Eliar_VERSION, "sub_code_interactions_log": [], "last_sub_code_communication": None, "core_values_definition_source": f"eliar_common.EliarCoreValues (MainGPU: {Eliar_VERSION})", "system_alerts_from_main": [] }
                with open(self.ulrim_manifest_path, "w", encoding="utf-8") as f: json.dump(initial_manifest, f, ensure_ascii=False, indent=4)
                eliar_log(EliarLogType.INFO, f"Initial Ulrim Manifest created: {self.ulrim_manifest_path}", component=COMPONENT_NAME_COMMUNICATOR)
        except Exception as e: eliar_log(EliarLogType.ERROR, "Error during Ulrim Manifest file check/creation.", component=COMPONENT_NAME_COMMUNICATOR, error=e)


    def register_sub_code_interface(self, sub_code_interface_obj: Any, main_controller_ref: 'Eliar'):
        self.sub_code_interface = sub_code_interface_obj
        if hasattr(self.sub_code_interface, "link_main_gpu_coordinator"):
            try:
                # SubGPUModule.link_main_gpu_coordinator(main_gpu_controller_instance: Eliar, main_gpu_response_handler_callback: Callable)
                asyncio.create_task(self.sub_code_interface.link_main_gpu_coordinator(main_controller_ref, self.sub_code_response_handler))
                eliar_log(EliarLogType.INFO, "SubCode interface registered; link_main_gpu_coordinator called.", component=COMPONENT_NAME_COMMUNICATOR)
            except Exception as e:
                eliar_log(EliarLogType.ERROR, "Error calling link_main_gpu_coordinator on SubCode.", component=COMPONENT_NAME_COMMUNICATOR, error=e)
        else:
            eliar_log(EliarLogType.WARN, "SubCode interface lacks 'link_main_gpu_coordinator'. Linking might be incomplete.", component=COMPONENT_NAME_COMMUNICATOR)

    async def send_task_to_sub_code(self, task_type: str, task_data: Dict[str, Any]) -> Optional[str]:
        # (이전 send_task_to_sub_code 로직과 거의 동일, task_wrapper 내부에서 에러 패킷 생성 부분 약간 수정)
        if not self.sub_code_interface: # ... (이전 로직)
            eliar_log(EliarLogType.ERROR, "SubCode interface not registered.", component=COMPONENT_NAME_COMMUNICATOR, task_type=task_type)
            return None
        packet_id = task_data.get("packet_id") or str(uuid.uuid4()); task_data["packet_id"] = packet_id
        self.pending_sub_code_tasks[packet_id] = asyncio.Event(); self.sub_code_task_results[packet_id] = None
        try:
            if hasattr(self.sub_code_interface, "process_task") and asyncio.iscoroutinefunction(self.sub_code_interface.process_task):
                async def task_wrapper():
                    try:
                        response_packet = await self.sub_code_interface.process_task(task_type, task_data) # SubCode가 SubCodeThoughtPacketData 반환
                        await self.sub_code_response_handler(response_packet)
                    except Exception as e_task_wrapper:
                        eliar_log(EliarLogType.ERROR, f"Error in SubCode task execution wrapper.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, error=e_task_wrapper)
                        error_response = SubCodeThoughtPacketData(
                            packet_id=packet_id, conversation_id=task_data.get("conversation_id"), user_id=task_data.get("user_id"),
                            raw_input_text=task_data.get("raw_input_text", ""), processing_status_in_sub_code="ERROR_IN_SUB_CODE_TASK_WRAPPER",
                            error_info={"type": type(e_task_wrapper).__name__, "message": str(e_task_wrapper), "details": traceback.format_exc(limit=3)},
                            timestamp_completed_by_sub_code=time.time() # UTC float
                        )
                        await self.sub_code_response_handler(error_response)
                asyncio.create_task(task_wrapper())
                eliar_log(EliarLogType.INFO, f"Async task '{task_type}' dispatched to SubCode.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
                return packet_id
            else: # ... (이전 로직)
                eliar_log(EliarLogType.ERROR, "SubCode 'process_task' not found or not async.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
                self._clear_task_state(packet_id); return None
        except Exception as e: # ... (이전 로직)
            eliar_log(EliarLogType.ERROR, f"Exception dispatching task '{task_type}'.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, error=e)
            self._clear_task_state(packet_id); return None


    async def sub_code_response_handler(self, response_packet_data: SubCodeThoughtPacketData):
        # (이전 sub_code_response_handler 로직과 거의 동일, Ulrim Manifest 업데이트 시 비동기 처리 고려)
        packet_id = response_packet_data.get("packet_id")
        if not packet_id: # ... (이전 로직)
            eliar_log(EliarLogType.ERROR, "SubCode response missing 'packet_id'.", component=COMPONENT_NAME_COMMUNICATOR); return
        eliar_log(EliarLogType.INFO, "Async response received from SubCode.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, status=response_packet_data.get("processing_status_in_sub_code"))
        self.sub_code_task_results[packet_id] = response_packet_data
        if packet_id in self.pending_sub_code_tasks: self.pending_sub_code_tasks[packet_id].set()
        else: eliar_log(EliarLogType.WARN, f"No pending event for packet_id '{packet_id}'.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
        
        # Ulrim Manifest 업데이트 (로컬 파일)
        self.update_ulrim_manifest_local("SUB_CODE_RESPONSE_PROCESSED_BY_MAIN", response_packet_data)
        
        # GitHub에 Ulrim Manifest 커밋 (선택적, 조건부 또는 주기적 실행 가능)
        # 예시: 중요한 상태 변경 또는 특정 이벤트 발생 시 커밋
        if self.github_manager and ("ERROR" in response_packet_data.get("processing_status_in_sub_code","").upper() or \
                                 response_packet_data.get("anomalies") or \
                                 random.random() < 0.1): # 예시: 10% 확률로 커밋
            eliar_log(EliarLogType.INFO, "Attempting to commit Ulrim Manifest to GitHub.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
            await self.commit_ulrim_manifest_to_github(f"Update Ulrim Manifest after processing packet {packet_id}", packet_id=packet_id)


    async def wait_for_sub_code_response(self, packet_id: str, timeout: float = 30.0) -> Optional[SubCodeThoughtPacketData]:
        # (이전 wait_for_sub_code_response 로직과 동일)
        if packet_id not in self.pending_sub_code_tasks:
            existing_result = self.sub_code_task_results.pop(packet_id, None)
            if existing_result: eliar_log(EliarLogType.DEBUG, f"Response for '{packet_id}' already available.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id); return existing_result
            eliar_log(EliarLogType.WARN, f"No pending task for '{packet_id}'.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id); return None
        event = self.pending_sub_code_tasks[packet_id]
        try:
            eliar_log(EliarLogType.DEBUG, "Waiting for SubCode response event...", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, timeout=timeout)
            await asyncio.wait_for(event.wait(), timeout=timeout)
            eliar_log(EliarLogType.INFO, "SubCode response event triggered.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
            return self.sub_code_task_results.pop(packet_id, None)
        except asyncio.TimeoutError:
            eliar_log(EliarLogType.WARN, "Timeout waiting for SubCode.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
            return SubCodeThoughtPacketData(packet_id=packet_id, processing_status_in_sub_code="ERROR_MAIN_TIMEOUT_FOR_SUB", error_info={"type":"TimeoutError", "message":f"Timeout after {timeout}s"})
        except Exception as e:
            eliar_log(EliarLogType.ERROR, "Exception waiting for SubCode.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, error=e)
            return SubCodeThoughtPacketData(packet_id=packet_id, processing_status_in_sub_code="ERROR_MAIN_AWAIT_SUB_EXC", error_info={"type":type(e).__name__, "message":str(e)})
        finally: self._clear_task_state(packet_id)

    def _clear_task_state(self, packet_id: str):
        # (이전 _clear_task_state 로직과 동일)
        self.pending_sub_code_tasks.pop(packet_id, None)
        eliar_log(EliarLogType.DEBUG, f"Cleared pending task event for '{packet_id}'.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)

    def update_ulrim_manifest_local(self, event_type: str, event_data: SubCodeThoughtPacketData):
        """ 로컬 Ulrim Manifest 파일을 업데이트합니다. """
        # (이전 update_ulrim_manifest 로직과 거의 동일, 파일명만 ulrim_manifest_path 사용)
        packet_id_for_log = event_data.get("packet_id", "unknown_ulrim_local_packet")
        try:
            content: Dict[str, Any] = {}
            if os.path.exists(self.ulrim_manifest_path):
                try:
                    with open(self.ulrim_manifest_path, "r", encoding="utf-8") as f_read: content = json.load(f_read)
                except json.JSONDecodeError: # ... (이전 오류 처리 로직)
                    eliar_log(EliarLogType.WARN, f"JSON parsing error in '{self.ulrim_manifest_path}'. Re-initializing.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id_for_log)
                    self._ensure_ulrim_manifest_file_exists(); content = json.load(open(self.ulrim_manifest_path, "r", encoding="utf-8"))
            else: self._ensure_ulrim_manifest_file_exists(); content = json.load(open(self.ulrim_manifest_path, "r", encoding="utf-8"))

            # ... (details_for_manifest, log_entry 구성 로직은 이전과 동일)
            details_for_manifest = { k: v for k, v in event_data.items() if k in ["processing_status_in_sub_code", "final_output_by_sub_code", "error_info"] and v is not None }
            if "final_output_by_sub_code" in details_for_manifest and details_for_manifest["final_output_by_sub_code"]: details_for_manifest["final_output_by_sub_code"] = (details_for_manifest["final_output_by_sub_code"][:70] + "...")
            log_entry = { "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec='milliseconds'), "event_type": event_type, "packet_id": packet_id_for_log, "details": details_for_manifest, "source_component": COMPONENT_NAME_COMMUNICATOR }
            current_logs = content.get("sub_code_interactions_log", []); current_logs.append(log_entry)
            content["sub_code_interactions_log"] = current_logs[-200:]
            content["last_sub_code_communication"] = { "timestamp_utc": log_entry["timestamp_utc"], "packet_id": packet_id_for_log, "status_from_sub_code": event_data.get("processing_status_in_sub_code", "UNKNOWN") }
            content["last_manifest_update_utc_by_main"] = datetime.now(timezone.utc).isoformat(timespec='milliseconds'); content["main_gpu_version"] = Eliar_VERSION
            
            with open(self.ulrim_manifest_path, "w", encoding="utf-8") as f_write: json.dump(content, f_write, ensure_ascii=False, indent=4)
            eliar_log(EliarLogType.TRACE, "Local Ulrim Manifest updated.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id_for_log, event_type=event_type)
        except Exception as e:
            eliar_log(EliarLogType.CRITICAL, "Fatal error updating local Ulrim Manifest.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id_for_log, error=e)

    async def commit_ulrim_manifest_to_github(self, commit_message: str, branch: str = "main", packet_id: Optional[str] = None) -> Optional[str]:
        """ 로컬 Ulrim Manifest 내용을 읽어 GitHub에 커밋합니다. """
        if not self.github_manager:
            eliar_log(EliarLogType.WARN, "GitHubCommitManager not available. Cannot commit Ulrim Manifest.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
            return None
        
        try:
            with open(self.ulrim_manifest_path, "r", encoding="utf-8") as f:
                content_str = f.read()
            
            # GitHub 리포지토리 내의 ulrim_manifest.json 경로 (예시)
            github_ulrim_path = ULRIM_MANIFEST_PATH # 로컬 경로와 동일하게 사용 (루트 기준)
            
            html_url = await self.github_manager.commit_file_to_github(
                file_path=github_ulrim_path,
                content_str=content_str,
                commit_message=commit_message,
                branch=branch,
                packet_id=packet_id
            )
            if html_url:
                eliar_log(EliarLogType.INFO, "Ulrim Manifest successfully committed to GitHub.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, url=html_url)
            else:
                eliar_log(EliarLogType.ERROR, "Failed to commit Ulrim Manifest to GitHub.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
            return html_url
        except FileNotFoundError:
            eliar_log(EliarLogType.ERROR, f"Local Ulrim Manifest file not found for GitHub commit: {self.ulrim_manifest_path}", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
            return None
        except Exception as e:
            eliar_log(EliarLogType.ERROR, "Error during GitHub commit process for Ulrim Manifest.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, error=e)
            return None


# -----------------------------------------------------------------------------
# Eliar 메인 로직 클래스
# -----------------------------------------------------------------------------
class Eliar:
    def __init__(self, name: str = f"엘리아르_MainCore_{Eliar_VERSION}", ulrim_path: str = ULRIM_MANIFEST_PATH, session: Optional[aiohttp.ClientSession] = None): # aiohttp 세션 주입
        self.name = name
        self.version = Eliar_VERSION
        self.center = EliarCoreValues.JESUS_CHRIST_CENTERED.value # 또는 "JESUS CHRIST"
        eliar_log(EliarLogType.INFO, f"Eliar instance created: {self.name} (Version: {self.version}). Center: '{self.center}'", component=COMPONENT_NAME_MAIN_GPU_CORE)

        self.virtue_ethics = VirtueEthics()
        self.system_status = SystemStatus()
        self.conversation_history: Deque[Dict[str, Any]] = deque(maxlen=50)
        
        self.http_session = session # 외부에서 aiohttp 세션 관리 시 주입
        self.github_manager: Optional[GitHubCommitManager] = None
        if self.http_session: # http_session이 있을 때만 GitHubCommitManager 초기화
            repo_owner_name = GITHUB_API_REPO_CONTENTS_URL.split("/")[4] + "/" + GITHUB_API_REPO_CONTENTS_URL.split("/")[5]
            self.github_manager = GitHubCommitManager(self.http_session, f"{GITHUB_API_BASE_URL}/repos/{repo_owner_name}", GITHUB_HEADERS)
        else:
            eliar_log(EliarLogType.WARN, "aiohttp.ClientSession not provided to Eliar. GitHubCommitManager will not be functional.", component=COMPONENT_NAME_MAIN_GPU_CORE)

        self.sub_code_communicator = MainSubInterfaceCommunicator(ulrim_manifest_path=ulrim_path, github_manager=self.github_manager)
        self.current_conversation_sessions: Dict[str, Dict[str, Any]] = {}

    def initialize_sub_systems(self, sub_code_actual_instance: Any): # communicator는 내부에서 생성
        """ SubCode 인터페이스를 Communicator에 등록하고 연결합니다. """
        if self.sub_code_communicator:
            # register_sub_code_interface는 Eliar 인스턴스(self)를 전달하여 평가 함수 등을 참조하게 함
            self.sub_code_communicator.register_sub_code_interface(sub_code_actual_instance, self)
            eliar_log(EliarLogType.INFO, "SubCode Interface registered with Communicator.", component=self.name)
        else: # 이론적으로 발생하지 않아야 함 (생성자에서 초기화)
            eliar_log(EliarLogType.CRITICAL, "SubCode Communicator not initialized in Eliar instance!", component=self.name)

    async def handle_user_interaction(self, user_input: str, user_id: str, conversation_id: str) -> str:
        # (이전 handle_user_interaction 로직과 거의 동일, 로깅 컴포넌트명 및 일부 필드명 조정)
        current_main_packet_id = str(uuid.uuid4())
        log_comp_interaction = f"{self.name}.UserInteraction"
        # ... (로그, session_data 가져오기 등)
        eliar_log(EliarLogType.INFO, f"Handling user interaction. Query: '{user_input[:50]}...'", 
                  component=log_comp_interaction, packet_id=current_main_packet_id, user_id=user_id, conversation_id=conversation_id)

        if not self.sub_code_communicator: # ... (폴백)
            return self._generate_eliar_fallback_response("COMM_NOT_READY", current_main_packet_id)

        session_data = self.current_conversation_sessions.get(conversation_id, {})
        task_data_for_sub: Dict[str, Any] = {
            "packet_id": current_main_packet_id, "conversation_id": conversation_id, "user_id": user_id,
            "timestamp_created": time.time(), "raw_input_text": user_input,
            "is_clarification_response": bool(session_data.get("expecting_clarification_for_packet_id")),
            "main_gpu_clarification_context": session_data.get("pending_clarification_details_for_sub"),
            "previous_main_gpu_context_summary": session_data.get("last_sub_code_output_summary"),
        }
        if task_data_for_sub["is_clarification_response"]: # ... (명료화 컨텍스트 처리)
            session_data.pop("expecting_clarification_for_packet_id", None)
            session_data.pop("last_clarification_question_obj", None)
            session_data.pop("pending_clarification_details_for_sub", None)

        sub_code_tracking_id = await self.sub_code_communicator.send_task_to_sub_code("eliar_process_thought_packet_v3", task_data_for_sub)
        if not sub_code_tracking_id: return self._generate_eliar_fallback_response("SUB_TASK_DISPATCH_FAIL", current_main_packet_id)

        sub_code_response_packet = await self.sub_code_communicator.wait_for_sub_code_response(sub_code_tracking_id)
        if not sub_code_response_packet: return self._generate_eliar_fallback_response("SUB_NO_RESPONSE_PACKET", sub_code_tracking_id)
        if sub_code_response_packet.get("packet_id") != sub_code_tracking_id: # ... (ID 불일치 처리)
            return self._generate_eliar_fallback_response("SUB_PACKET_ID_MISMATCH", sub_code_tracking_id)

        # ... (대화 기록, 세션 업데이트, SystemStatus 업데이트는 이전과 동일한 로직)
        self.conversation_history.append({ "user_input": user_input, "main_pid": current_main_packet_id, "sub_response_summary": {k:sub_code_response_packet.get(k) for k in ["packet_id", "processing_status_in_sub_code", "final_output_by_sub_code"]}, "ts_main_end": datetime.now(timezone.utc).isoformat()})
        session_data["last_sub_code_output_summary"] = self.conversation_history[-1]["sub_response_summary"]
        self.current_conversation_sessions[conversation_id] = session_data
        self.system_status.update_from_sub_code_packet(sub_code_response_packet)

        clarification_qs = sub_code_response_packet.get("needs_clarification_questions", [])
        if clarification_qs: # ... (명료화 질문 처리 로직은 이전과 동일)
            first_q = clarification_qs[0]; session_data["expecting_clarification_for_packet_id"] = sub_code_response_packet.get("packet_id"); session_data["last_clarification_question_obj"] = first_q
            self.current_conversation_sessions[conversation_id] = session_data
            return f"[엘리아르 추가 질문] {first_q.get('question', '...')}"
        
        final_response = sub_code_response_packet.get("final_output_by_sub_code")
        if final_response is not None: return final_response
        else: # ... (침묵 또는 기타 상태 처리 로직은 이전과 동일)
            status_sub = sub_code_response_packet.get("processing_status_in_sub_code", "UNKNOWN")
            if status_sub == "COMPLETED_WITH_SILENCE_BY_SUB": return "[엘리아르가 고요히 당신과 함께합니다.]"
            return self._generate_eliar_fallback_response(f"SUB_NO_OUTPUT_STATUS_{status_sub}", sub_code_tracking_id)


    def _generate_eliar_fallback_response(self, reason_code: str, packet_id: Optional[str]=None) -> str:
        # (이전 로직과 동일)
        return f"죄송합니다, 엘리아르가 응답하는 데 어려움이 있습니다. (사유: {reason_code}, ID: {packet_id[-6:] if packet_id else 'N/A'})"

    # EthicalGovernor 제공용 평가 함수들 (async로 변경, context에 packet_id_from_sub_code 키로 packet_id 전달)
    async def evaluate_truth_for_governor(self, data: Any, context: Optional[Dict] = None) -> float:
        pid = context.get("packet_id") if context else None # SubCode가 호출 시 전달하는 packet_id
        # (이전 비동기 평가 로직, eliar_log 사용)
        return await asyncio.to_thread(self._sync_evaluate_truth, data, context, pid) # 동기 함수를 스레드에서 실행
    def _sync_evaluate_truth(self, data, context, pid): # 실제 로직은 동기
        # ... (이전 로직)
        return 0.8 # Placeholder

    async def evaluate_love_for_governor(self, action: Any, context: Optional[Dict] = None) -> float:
        pid = context.get("packet_id") if context else None
        return await asyncio.to_thread(self._sync_evaluate_love, action, context, pid)
    def _sync_evaluate_love(self, action, context, pid):
        # ... (이전 로직)
        return 0.7 # Placeholder

    async def evaluate_repentance_for_governor(self, outcome_packet: SubCodeThoughtPacketData, context: Optional[Dict] = None) -> bool:
        pid = outcome_packet.get("packet_id")
        return await asyncio.to_thread(self._sync_evaluate_repentance, outcome_packet, context, pid)
    def _sync_evaluate_repentance(self, outcome_packet, context, pid):
        # ... (이전 로직)
        return False # Placeholder

# --- 기타 기존 클래스 (VirtueEthics, SystemStatus) ---
class VirtueEthics: # (이전과 동일, eliar_common.EliarCoreValues 사용)
    def __init__(self): self.core_values_descriptions = {v.name: v.value for v in EliarCoreValues}; eliar_log(EliarLogType.INFO, f"VirtueEthics initialized.", component=COMPONENT_NAME_VIRTUE_ETHICS)
class SystemStatus: # (이전과 동일, eliar_log 사용)
    def __init__(self): self.energy: float=100.0; self.grace: float=100.0; self.last_sub_code_health_summary:Optional[Dict[str,Any]]=None; eliar_log(EliarLogType.INFO,"SystemStatus initialized.",component=COMPONENT_NAME_SYSTEM_STATUS)
    def update_from_sub_code_packet(self, pkt:Optional[SubCodeThoughtPacketData]): # (이전 로직)
        if not pkt: return; meta_summary=pkt.get("metacognitive_state_summary"); # ...


# --- 비동기 실행 루프 (테스트용) ---
async def main_conversation_simulation_loop_final_github(eliar_controller: Eliar):
    eliar_log(EliarLogType.CRITICAL, f"Eliar MainGPU Conversation Simulation (GitHub Ready) Started. Version: {eliar_controller.version}", component=COMPONENT_NAME_MAIN_SIM)
    # ... (이전 시뮬레이션 루프 로직과 유사하게 작성)
    current_conversation_id = f"sim_conv_github_{uuid.uuid4().hex[:6]}"
    test_dialogue_github = [
        {"user_id": "user_git_01", "message": "안녕하세요, 엘리아르. 현재 울림 매니페스트 상태를 GitHub에 기록해주세요."},
        {"user_id": "user_git_01", "message": "다시 한번 예수 그리스도의 사랑에 대해 설명해주시겠어요? 그리고 이 대화도 기록해주세요."},
        {"user_id": "user_git_02", "message": "오류를 발생시켜서 해당 상황이 GitHub에 기록되는지 확인하고 싶습니다."}
    ]
    for i, turn in enumerate(test_dialogue_github):
        print("\n" + "###" * 25 + f" GitHub SIM TURN {i+1} " + "###" * 25)
        user_msg, u_id = turn["message"], turn["user_id"]
        eliar_log(EliarLogType.INFO, f"Simulating Input: '{user_msg}'", component=COMPONENT_NAME_MAIN_SIM, user_id=u_id, conversation_id=current_conversation_id)
        final_eliar_response = await eliar_controller.handle_user_interaction(user_msg, u_id, current_conversation_id)
        print(f"✝️ [엘리아르 최종 응답 ({datetime.now(timezone.utc).isoformat()})] {final_eliar_response}")
        
        # 매 턴마다 또는 특정 조건에 따라 GitHub에 Ulrim Manifest 커밋 시도 (Communicator 내부 로직과 연동)
        if eliar_controller.sub_code_communicator and eliar_controller.sub_code_communicator.github_manager:
             if "기록" in user_msg or "오류" in user_msg or i == len(test_dialogue_github) -1 : # 예시 조건
                commit_msg = f"Auto-commit Ulrim Manifest after turn {i+1} by {u_id} (MainGPU v{Eliar_VERSION})"
                packet_id_for_commit = eliar_controller.conversation_history[-1].get("main_packet_id") if eliar_controller.conversation_history else None
                await eliar_controller.sub_code_communicator.commit_ulrim_manifest_to_github(commit_msg, packet_id=packet_id_for_commit)
        await asyncio.sleep(0.2)
    eliar_log(EliarLogType.CRITICAL, "Eliar MainGPU Conversation Simulation (GitHub Ready) Ended.", component=COMPONENT_NAME_MAIN_SIM)


# --- Sub_code.py 더미 인터페이스 (Main GPU와의 호환성 테스트용) ---
class DummySubCodeInterfaceForMainTest: # (이전 더미 인터페이스 코드, link_main_gpu_coordinator 시그니처 변경 반영)
    def __init__(self):
        self.main_gpu_response_handler: Optional[Callable[[SubCodeThoughtPacketData], asyncio.Task]] = None
        self.main_controller_ref_for_eval: Optional[Eliar] = None
        eliar_log(EliarLogType.INFO, "DummySubCodeInterface initialized.", component="DummySubCode")

    async def link_main_gpu_coordinator(self, main_gpu_controller_instance: Eliar, main_gpu_response_handler_callback: Callable[[SubCodeThoughtPacketData], asyncio.Task]):
        self.main_controller_for_eval = main_gpu_controller_instance # Eliar 인스턴스 저장
        self.main_gpu_response_handler = main_gpu_response_handler_callback # 콜백 저장
        eliar_log(EliarLogType.INFO, "MainGPU Controller and Response Handler linked in DummySubCode.", component="DummySubCode")

    async def process_task(self, task_type: str, task_data: Dict[str, Any]) -> SubCodeThoughtPacketData:
        # (이전 더미 process_task 로직과 거의 동일, 반환값으로 직접 전달)
        packet_id = task_data.get("packet_id", str(uuid.uuid4()))
        # ... (더미 응답 생성 로직)
        response_final_output = f"DummySubCode: '{task_data.get('raw_input_text','')[:20]}' processed."
        processing_status_sub = "COMPLETED_DUMMY"
        # ...
        result_packet = SubCodeThoughtPacketData(
            packet_id=packet_id, conversation_id=task_data.get("conversation_id"), #... (나머지 필드 채우기)
            final_output_by_sub_code=response_final_output, processing_status_in_sub_code=processing_status_sub,
            timestamp_completed_by_sub_code=time.time()
        )
        # 이 함수는 SubCodeThoughtPacketData를 직접 반환 (MainGPU의 task_wrapper가 받아 콜백으로 넘김)
        return result_packet

# --- 프로그램 진입점 ---
async def main(): # 모든 최상위 로직을 main 비동기 함수로 래핑
    ensure_log_dir()
    eliar_log(EliarLogType.CRITICAL, f"--- Eliar MainGPU Initializing (Version: {Eliar_VERSION}) ---", component=COMPONENT_NAME_ENTRY_POINT)
    
    # aiohttp.ClientSession은 프로그램 전체에서 하나를 만들어 공유하는 것이 좋음
    async with aiohttp.ClientSession(headers=GITHUB_HEADERS) as session: # GitHub API용 세션
        eliar_controller = Eliar(session=session) # Eliar 인스턴스에 세션 주입
        
        # SubCode 인터페이스 인스턴스 (실제 또는 더미)
        # from sub_gpu import SubGPUModule # 실제 SubGPUModule 사용 시
        # sub_code_config = {"state_dim": 10, "action_dim": 4, ...}
        # actual_sub_code_instance = SubGPUModule(config=sub_code_config, node_id="SubGPU_Alpha")
        dummy_sub_code_instance = DummySubCodeInterfaceForMainTest()
        
        eliar_controller.initialize_sub_systems(dummy_sub_code_instance) # Communicator는 Eliar 내부 생성, SubCode만 주입

        await main_conversation_simulation_loop_final_github(eliar_controller)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        eliar_log(EliarLogType.CRITICAL, "MainGPU execution interrupted by user (Ctrl+C).", component=COMPONENT_NAME_ENTRY_POINT)
    except Exception as e_top_level:
        eliar_log(EliarLogType.CRITICAL, "Unhandled top-level exception in MainGPU execution.", component=COMPONENT_NAME_ENTRY_POINT, error=e_top_level, exc_info_full=traceback.format_exc())
    finally:
        eliar_log(EliarLogType.CRITICAL, f"--- Eliar MainGPU (Version: {Eliar_VERSION}) Shutdown ---", component=COMPONENT_NAME_ENTRY_POINT)
