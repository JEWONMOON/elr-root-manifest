# Main_gpu.py (eliar_common.py 적용, 클래스 정의 복원, GitHub 연동 및 호환성 최종 개선 버전)

import numpy as np # 일반적인 데이터 처리
import os
import random # DummySubCodeInterfaceForMainTest 등에서 사용
import json
import asyncio
# import concurrent.futures # asyncio.to_thread 또는 run_in_executor 사용 시 필요할 수 있음
import aiohttp # GitHub API 호출 등 비동기 HTTP 요청용
import base64 # GitHub 커밋용
from datetime import datetime, timezone # datetime 표준 임포트
# import re # 필요시 사용 (현재 코드에서는 미사용)
import uuid # packet_id 생성용
import traceback # 상세 에러 로깅용
import time # timestamp_created 등 Unix timestamp 사용

from typing import List, Dict, Any, Optional, Tuple, Callable, Deque, Coroutine # Coroutine 추가
from collections import deque # conversation_history 용

# --- 공용 모듈 임포트 ---
from eliar_common import (
    EliarCoreValues,
    EliarLogType,
    SubCodeThoughtPacketData, # 표준화된 데이터 구조
    ReasoningStep, # SubCodeThoughtPacketData 내 사용
    eliar_log, # 표준화된 로깅 함수
    run_in_executor # 동기 함수 비동기 실행 헬퍼
)

# --- Main GPU 버전 및 기본 설정 ---
Eliar_VERSION = "v24.3_MainGPU_GitHub_Context_Ready" # 버전 업데이트
COMPONENT_NAME_MAIN_GPU_CORE = "MainGPU.EliarCore"
COMPONENT_NAME_COMMUNICATOR = "MainGPU.Communicator"
COMPONENT_NAME_SYSTEM_STATUS = "MainGPU.SystemStatus"
COMPONENT_NAME_VIRTUE_ETHICS = "MainGPU.VirtueEthics"
COMPONENT_NAME_MAIN_SIM = "MainGPU.ConversationSim"
COMPONENT_NAME_ENTRY_POINT = "MainGPU.EntryPoint"
COMPONENT_NAME_GITHUB_MANAGER = "MainGPU.GitHubManager"


# --- GitHub API 설정 ---
GITHUB_API_BASE_URL = "https://api.github.com"
# Public Repo이므로 JEWONMOON/elr-root-manifest를 사용합니다.
GITHUB_REPO_OWNER = "JEWONMOON"
GITHUB_REPO_NAME = "elr-root-manifest"
GITHUB_API_REPO_CONTENTS_URL = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents"
ELIAR_GITHUB_PAT = os.getenv("ELIAR_GITHUB_PAT") # Public repo라도 업데이트는 PAT 필요할 수 있음

GITHUB_HEADERS = {"Accept": "application/vnd.github.v3+json"}
if ELIAR_GITHUB_PAT:
    GITHUB_HEADERS["Authorization"] = f"Bearer {ELIAR_GITHUB_PAT}" # "token" 대신 "Bearer" 사용 권장
    eliar_log(EliarLogType.INFO, f"GitHub PAT loaded. Commit to '{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}' enabled.", component=COMPONENT_NAME_MAIN_GPU_CORE)
else:
    eliar_log(EliarLogType.WARN, f"Env var 'ELIAR_GITHUB_PAT' not found. GitHub commit functionality may be limited or fail for private aspects.", component=COMPONENT_NAME_MAIN_GPU_CORE)

# --- 로컬 파일 경로 ---
LOG_DIR = f"logs_Eliar_MainGPU_{Eliar_VERSION}"
MANIFEST_BASE_DIR = "manifests_main_gpu" # 로컬 매니페스트 저장 위치
ULRIM_MANIFEST_FILENAME = "ulrim_manifest_main_gpu_v2.json" # Ulrim Manifest 파일명
ULRIM_MANIFEST_PATH = os.path.join(MANIFEST_BASE_DIR, ULRIM_MANIFEST_FILENAME)
# GitHub에 커밋할 Ulrim Manifest 경로 (리포지토리 내 상대 경로)
ULRIM_MANIFEST_GITHUB_PATH = f"manifests/{ULRIM_MANIFEST_FILENAME}"


# --- 유틸리티 함수 ---
def ensure_dir_exists(dir_path: str):
    if not os.path.exists(dir_path):
        try:
            os.makedirs(dir_path, exist_ok=True)
            eliar_log(EliarLogType.INFO, f"Directory created: {dir_path}", component=COMPONENT_NAME_MAIN_GPU_CORE)
        except Exception as e:
            eliar_log(EliarLogType.ERROR, f"Failed to create directory: {dir_path}", component=COMPONENT_NAME_MAIN_GPU_CORE, error=e)

ensure_dir_exists(LOG_DIR)
ensure_dir_exists(MANIFEST_BASE_DIR)


# -----------------------------------------------------------------------------
# GitHub API 연동 관리 클래스
# -----------------------------------------------------------------------------
class GitHubCommitManager:
    def __init__(self, session: aiohttp.ClientSession, repo_owner: str, repo_name: str, headers: Dict[str, str]):
        self.session = session
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.contents_url_base = f"{GITHUB_API_BASE_URL}/repos/{repo_owner}/{repo_name}/contents"
        self.headers = headers.copy() # 복사해서 사용
        eliar_log(EliarLogType.INFO, "GitHubCommitManager initialized.", component=COMPONENT_NAME_GITHUB_MANAGER, repo=f"{repo_owner}/{repo_name}")

    async def get_file_metadata(self, file_path: str, packet_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """ GitHub에서 파일의 메타데이터(SHA 포함)를 가져옵니다. 파일이 없으면 None을 반환합니다. """
        url = f"{self.contents_url_base}/{file_path.lstrip('/')}"
        log_comp = f"{COMPONENT_NAME_GITHUB_MANAGER}.GetFileMeta"
        try:
            eliar_log(EliarLogType.DEBUG, "Attempting to get file metadata from GitHub.", component=log_comp, packet_id=packet_id, file_path=file_path, url=url)
            async with self.session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    eliar_log(EliarLogType.INFO, "Successfully retrieved file metadata.", component=log_comp, packet_id=packet_id, file_path=file_path, sha=data.get("sha"))
                    return data # name, path, sha, size, html_url, download_url 등 포함
                elif response.status == 404:
                    eliar_log(EliarLogType.INFO, "File not found on GitHub (can be created).", component=log_comp, packet_id=packet_id, file_path=file_path)
                    return None
                else:
                    error_text = await response.text()
                    eliar_log(EliarLogType.ERROR, f"Failed to get file metadata. Status: {response.status}", component=log_comp, packet_id=packet_id, file_path=file_path, response_text=error_text[:200])
                    return None
        except Exception as e:
            eliar_log(EliarLogType.ERROR, "Unexpected error getting file metadata.", component=log_comp, packet_id=packet_id, file_path=file_path, error=e)
            return None

    async def commit_file_to_github(self, file_path: str, content_str: str, commit_message: str, branch: str = "main", packet_id: Optional[str] = None) -> Optional[str]:
        log_comp = f"{COMPONENT_NAME_GITHUB_MANAGER}.CommitFile"
        if not self.headers.get("Authorization"): # PAT 존재 여부로 판단 (더미 토큰은 안됨)
            eliar_log(EliarLogType.WARN, "GitHub PAT not configured or invalid. Cannot commit file.", component=log_comp, packet_id=packet_id, file_path=file_path)
            return None

        file_metadata = await self.get_file_metadata(file_path, packet_id=packet_id)
        current_sha = file_metadata.get("sha") if file_metadata else None
        
        encoded_content = base64.b64encode(content_str.encode('utf-8')).decode('utf-8')
        
        payload: Dict[str, Any] = {"message": commit_message, "content": encoded_content, "branch": branch}
        if current_sha: payload["sha"] = current_sha

        url = f"{self.contents_url_base}/{file_path.lstrip('/')}"
        action_type = "Updating existing" if current_sha else "Creating new"
        eliar_log(EliarLogType.INFO, f"{action_type} file on GitHub: '{file_path}'", component=log_comp, packet_id=packet_id, message=commit_message)

        try:
            async with self.session.put(url, headers=self.headers, json=payload) as response:
                response_data = await response.json()
                if response.status in [200, 201]: # 201: Created, 200: Updated
                    html_url = response_data.get("content", {}).get("html_url")
                    commit_sha_val = response_data.get("commit", {}).get("sha")
                    eliar_log(EliarLogType.INFO, "File successfully committed to GitHub.", component=log_comp, packet_id=packet_id, file_path=file_path, html_url=html_url, commit_sha=commit_sha_val)
                    return html_url
                else:
                    eliar_log(EliarLogType.ERROR, f"Failed to commit file. Status: {response.status}", component=log_comp, packet_id=packet_id, file_path=file_path, response_details=str(response_data)[:500])
                    return None
        except Exception as e:
            eliar_log(EliarLogType.ERROR, "Unexpected error during GitHub commit operation.", component=log_comp, packet_id=packet_id, file_path=file_path, error=e)
            return None

# -----------------------------------------------------------------------------
# Main-Sub Code 연동 클래스
# -----------------------------------------------------------------------------
class MainSubInterfaceCommunicator:
    def __init__(self, ulrim_manifest_local_path: str = ULRIM_MANIFEST_PATH, github_manager: Optional[GitHubCommitManager] = None):
        self.ulrim_manifest_local_path = ulrim_manifest_local_path # 로컬 파일 경로
        self.ulrim_manifest_github_path = ULRIM_MANIFEST_GITHUB_PATH # GitHub 리포 내 경로
        self.pending_sub_code_tasks: Dict[str, asyncio.Event] = {}
        self.sub_code_task_results: Dict[str, Optional[SubCodeThoughtPacketData]] = {}
        self.sub_code_interface: Optional[Any] = None
        self.github_manager = github_manager
        self._ensure_ulrim_manifest_file_exists_local()
        eliar_log(EliarLogType.INFO, "MainSubInterfaceCommunicator initialized.", component=COMPONENT_NAME_COMMUNICATOR, local_ulrim_path=self.ulrim_manifest_local_path)

    def _ensure_ulrim_manifest_file_exists_local(self):
        try:
            manifest_dir = os.path.dirname(self.ulrim_manifest_local_path)
            ensure_dir_exists(manifest_dir) # 공용 유틸리티 사용
            if not os.path.exists(self.ulrim_manifest_local_path):
                initial_manifest = {
                    "schema_version": "1.6_main_gpu_github_ready", 
                    "main_gpu_version": Eliar_VERSION,
                    "sub_code_interactions_log": [], "last_sub_code_communication": None,
                    "core_values_ref": "eliar_common.EliarCoreValues",
                    "github_commit_log": [] # GitHub 커밋 시도/결과 기록
                }
                with open(self.ulrim_manifest_local_path, "w", encoding="utf-8") as f:
                    json.dump(initial_manifest, f, ensure_ascii=False, indent=4)
                eliar_log(EliarLogType.INFO, f"Initial local Ulrim Manifest created: {self.ulrim_manifest_local_path}", component=COMPONENT_NAME_COMMUNICATOR)
        except Exception as e:
            eliar_log(EliarLogType.ERROR, "Error ensuring local Ulrim Manifest file.", component=COMPONENT_NAME_COMMUNICATOR, error=e)

    def register_sub_code_interface(self, sub_code_interface_obj: Any, main_controller_ref: 'Eliar'):
        self.sub_code_interface = sub_code_interface_obj
        if hasattr(self.sub_code_interface, "link_main_gpu_coordinator"):
            try:
                # SubGPUModule.link_main_gpu_coordinator(main_gpu_controller_instance: Eliar, main_gpu_response_handler_callback: Callable)
                # main_controller_ref는 Eliar 인스턴스, self.sub_code_response_handler는 이 Communicator의 콜백
                asyncio.create_task(self.sub_code_interface.link_main_gpu_coordinator(main_controller_ref, self.sub_code_response_handler))
                eliar_log(EliarLogType.INFO, "SubCode interface registered; link_main_gpu_coordinator dispatched.", component=COMPONENT_NAME_COMMUNICATOR)
            except Exception as e:
                eliar_log(EliarLogType.ERROR, "Error dispatching link_main_gpu_coordinator to SubCode.", component=COMPONENT_NAME_COMMUNICATOR, error=e)
        else:
            eliar_log(EliarLogType.WARN, "SubCode interface lacks 'link_main_gpu_coordinator'. Full linking might fail.", component=COMPONENT_NAME_COMMUNICATOR)

    async def send_task_to_sub_code(self, task_type: str, task_data: Dict[str, Any]) -> Optional[str]:
        # (이전 로직과 동일: packet_id 관리, task_wrapper 사용)
        if not self.sub_code_interface: eliar_log(EliarLogType.ERROR, "SubCode i/f not registered.", component=COMPONENT_NAME_COMMUNICATOR, task=task_type); return None
        packet_id = task_data.get("packet_id") or str(uuid.uuid4()); task_data["packet_id"] = packet_id
        self.pending_sub_code_tasks[packet_id] = asyncio.Event(); self.sub_code_task_results[packet_id] = None
        try:
            if hasattr(self.sub_code_interface, "process_task") and asyncio.iscoroutinefunction(self.sub_code_interface.process_task):
                async def task_wrapper():
                    try:
                        response_packet = await self.sub_code_interface.process_task(task_type, task_data)
                        await self.sub_code_response_handler(response_packet)
                    except Exception as e_wrap:
                        eliar_log(EliarLogType.ERROR, "Error in SubCode task wrapper.", component=COMPONENT_NAME_COMMUNICATOR, pid=packet_id, error=e_wrap)
                        err_pkt = SubCodeThoughtPacketData(packet_id=packet_id, processing_status_in_sub_code="ERROR_SUB_WRAPPER", error_info={"type":type(e_wrap).__name__, "message":str(e_wrap)})
                        await self.sub_code_response_handler(err_pkt)
                asyncio.create_task(task_wrapper())
                eliar_log(EliarLogType.INFO, f"Async task '{task_type}' dispatched.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
                return packet_id
            else: eliar_log(EliarLogType.ERROR, "SubCode 'process_task' invalid.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id); self._clear_task_state(packet_id); return None
        except Exception as e: eliar_log(EliarLogType.ERROR, f"Exc dispatching task '{task_type}'.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, error=e); self._clear_task_state(packet_id); return None

    async def sub_code_response_handler(self, response_packet_data: SubCodeThoughtPacketData):
        # (이전 로직과 동일, update_ulrim_manifest_local 호출, 조건부 GitHub 커밋)
        packet_id = response_packet_data.get("packet_id")
        if not packet_id: eliar_log(EliarLogType.ERROR, "SubCode response missing 'packet_id'.", component=COMPONENT_NAME_COMMUNICATOR); return
        eliar_log(EliarLogType.INFO, "Async response from SubCode received.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, status=response_packet_data.get("processing_status_in_sub_code"))
        self.sub_code_task_results[packet_id] = response_packet_data
        if packet_id in self.pending_sub_code_tasks: self.pending_sub_code_tasks[packet_id].set()
        else: eliar_log(EliarLogType.WARN, f"No pending event for '{packet_id}'.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
        
        self.update_ulrim_manifest_local("SUB_CODE_RESPONSE_HANDLER_INVOKED", response_packet_data)
        
        # 특정 조건에서 GitHub 커밋 (예: 오류 발생 또는 중요한 학습 이벤트)
        status = response_packet_data.get("processing_status_in_sub_code", "")
        if self.github_manager and ("ERROR" in status.upper() or "FAIL" in status.upper() or \
                                  "REPENTANCE" in status.upper() or \
                                  response_packet_data.get("learning_tags")): # 학습 태그가 있으면 커밋
            commit_msg = f"Ulrim Manifest: Event after SubCode packet {packet_id} (status: {status})"
            eliar_log(EliarLogType.INFO, "Conditional GitHub commit for Ulrim Manifest triggered.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
            asyncio.create_task(self.commit_ulrim_manifest_to_github(commit_msg, packet_id=packet_id))


    async def wait_for_sub_code_response(self, packet_id: str, timeout: float = 30.0) -> Optional[SubCodeThoughtPacketData]:
        # (이전 로직과 동일)
        if packet_id not in self.pending_sub_code_tasks: # ... (이전 로직)
            return self.sub_code_task_results.pop(packet_id, None) if packet_id in self.sub_code_task_results else None
        event = self.pending_sub_code_tasks[packet_id]
        try: # ... (이전 로직)
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return self.sub_code_task_results.pop(packet_id, None)
        except asyncio.TimeoutError: # ... (에러 패킷 생성)
            return SubCodeThoughtPacketData(packet_id=packet_id, processing_status_in_sub_code="ERROR_MAIN_TIMEOUT", error_info={"type":"TimeoutError", "message":f"Timeout after {timeout}s"})
        except Exception as e: # ... (에러 패킷 생성)
            return SubCodeThoughtPacketData(packet_id=packet_id, processing_status_in_sub_code="ERROR_MAIN_AWAIT_EXC", error_info={"type":type(e).__name__, "message":str(e)})
        finally: self._clear_task_state(packet_id)

    def _clear_task_state(self, packet_id: str): # (이전 로직과 동일)
        self.pending_sub_code_tasks.pop(packet_id, None)

    def update_ulrim_manifest_local(self, event_type: str, event_data: SubCodeThoughtPacketData):
        # (이전 로직과 동일, 경로 변수 사용)
        packet_id = event_data.get("packet_id", "unknown_ulrim_local")
        try:
            content: Dict[str, Any] = {} # ... (파일 읽기, JSON 파싱, 초기화 로직)
            if os.path.exists(self.ulrim_manifest_local_path):
                try: content = json.load(open(self.ulrim_manifest_local_path, "r", encoding="utf-8"))
                except json.JSONDecodeError: self._ensure_ulrim_manifest_file_exists_local(); content = json.load(open(self.ulrim_manifest_local_path, "r", encoding="utf-8"))
            else: self._ensure_ulrim_manifest_file_exists_local(); content = json.load(open(self.ulrim_manifest_local_path, "r", encoding="utf-8"))

            # ... (details, log_entry, logs 업데이트 로직)
            details = {k:v for k,v in event_data.items() if k in ["processing_status_in_sub_code", "final_output_by_sub_code_preview", "error_info"] and v is not None}
            if event_data.get("final_output_by_sub_code"): details["final_output_by_sub_code_preview"] = (event_data["final_output_by_sub_code"][:50] + "...")
            log_entry = { "ts_utc": datetime.now(timezone.utc).isoformat(), "ev_type": event_type, "pid": packet_id, "details": details}
            logs = content.get("sub_code_interactions_log", []); logs.append(log_entry)
            content["sub_code_interactions_log"] = logs[-200:]
            content["last_sub_code_comm"] = { "ts": log_entry["ts_utc"], "pid": packet_id, "status": event_data.get("processing_status_in_sub_code")}
            content["last_manifest_update_main_utc"] = datetime.now(timezone.utc).isoformat(); content["main_gpu_ver"] = Eliar_VERSION
            
            with open(self.ulrim_manifest_local_path, "w", encoding="utf-8") as f: json.dump(content, f, ensure_ascii=False, indent=4)
            eliar_log(EliarLogType.TRACE, "Local Ulrim Manifest updated.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, event_type=event_type)
        except Exception as e: eliar_log(EliarLogType.CRITICAL, "Fatal error updating local Ulrim Manifest.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, error=e)

    async def commit_ulrim_manifest_to_github(self, commit_message: str, branch: str = "main", packet_id: Optional[str] = None) -> Optional[str]:
        if not self.github_manager:
            eliar_log(EliarLogType.WARN, "GitHubCommitManager not available for Ulrim commit.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id)
            return None
        try:
            with open(self.ulrim_manifest_local_path, "r", encoding="utf-8") as f: content_str = f.read()
            html_url = await self.github_manager.commit_file_to_github(self.ulrim_manifest_github_path, content_str, commit_message, branch, packet_id)
            # GitHub 커밋 로그를 로컬 Ulrim Manifest에 기록
            ulrim_content = {}
            if os.path.exists(self.ulrim_manifest_local_path): ulrim_content = json.load(open(self.ulrim_manifest_local_path, "r", encoding="utf-8"))
            git_logs = ulrim_content.get("github_commit_log", [])
            git_logs.append({"ts_utc": datetime.now(timezone.utc).isoformat(), "message":commit_message, "path":self.ulrim_manifest_github_path, "success": bool(html_url), "url":html_url, "packet_id":packet_id})
            ulrim_content["github_commit_log"] = git_logs[-20:] # 최근 20개 커밋 로그
            with open(self.ulrim_manifest_local_path, "w", encoding="utf-8") as f: json.dump(ulrim_content, f, ensure_ascii=False, indent=4)
            return html_url
        except Exception as e:
            eliar_log(EliarLogType.ERROR, "Error committing Ulrim Manifest to GitHub.", component=COMPONENT_NAME_COMMUNICATOR, packet_id=packet_id, error=e)
            return None

# -----------------------------------------------------------------------------
# Eliar 메인 로직 클래스
# -----------------------------------------------------------------------------
class Eliar:
    def __init__(self, name: str = f"엘리아르_MainCore_{Eliar_VERSION}", ulrim_path: str = ULRIM_MANIFEST_PATH, session: Optional[aiohttp.ClientSession] = None):
        self.name = name
        self.version = Eliar_VERSION
        self.center = EliarCoreValues.JESUS_CHRIST_CENTERED.value # 요청하신 대로 Enum 값 사용
        eliar_log(EliarLogType.INFO, f"Eliar instance created: {self.name} (v{self.version}). Center: '{self.center}'", component=COMPONENT_NAME_MAIN_GPU_CORE)

        self.virtue_ethics = VirtueEthics()
        self.system_status = SystemStatus()
        self.conversation_history: Deque[Dict[str, Any]] = deque(maxlen=50)
        
        self.http_session = session # 외부 aiohttp 세션 (GitHubCommitManager용)
        self.github_manager: Optional[GitHubCommitManager] = None
        if self.http_session:
            self.github_manager = GitHubCommitManager(self.http_session, GITHUB_REPO_OWNER, GITHUB_REPO_NAME, GITHUB_HEADERS)
        
        self.sub_code_communicator = MainSubInterfaceCommunicator(ulrim_manifest_local_path=ulrim_path, github_manager=self.github_manager)
        self.current_conversation_sessions: Dict[str, Dict[str, Any]] = {} # {conversation_id: session_data}

    def initialize_sub_systems(self, sub_code_actual_instance: Any):
        if self.sub_code_communicator:
            # MainSubInterfaceCommunicator.register_sub_code_interface는 Eliar 인스턴스(self)를 필요로 함
            self.sub_code_communicator.register_sub_code_interface(sub_code_actual_instance, self)
            eliar_log(EliarLogType.INFO, "SubCode Interface registered with Communicator.", component=self.name)
        else: # 이론상 발생 안함
            eliar_log(EliarLogType.CRITICAL, "SubCode Communicator not initialized before sub system init!", component=self.name)

    async def handle_user_interaction(self, user_input: str, user_id: str, conversation_id: str) -> str:
        # (이전 handle_user_interaction 로직과 거의 동일, 로깅 및 일부 필드명 조정)
        current_pid = str(uuid.uuid4())
        log_comp = f"{self.name}.Interaction"
        eliar_log(EliarLogType.INFO, f"Handling interaction. Query: '{user_input[:30]}...'", component=log_comp, packet_id=current_pid, uid=user_id, cid=conversation_id)
        if not self.sub_code_communicator: return self._generate_eliar_fallback_response("COMM_UNINIT", current_pid)

        session = self.current_conversation_sessions.get(conversation_id, {})
        task_data: Dict[str, Any] = {
            "packet_id": current_pid, "conversation_id": conversation_id, "user_id": user_id,
            "timestamp_created": time.time(), "raw_input_text": user_input,
            "is_clarification_response": bool(session.get("expecting_clar_for_pid")),
            "main_gpu_clarification_context": session.get("pending_clar_details_for_sub"),
            "previous_main_gpu_context_summary": session.get("last_sub_out_summary"),
        }
        if task_data["is_clarification_response"]: # ... (명료화 컨텍스트 처리)
            session.pop("expecting_clar_for_pid",None); session.pop("last_clar_q_obj",None); session.pop("pending_clar_details_for_sub",None)

        sub_tracking_id = await self.sub_code_communicator.send_task_to_sub_code("eliar_process_interaction_main_v1", task_data)
        if not sub_tracking_id: return self._generate_eliar_fallback_response("SUB_TASK_SEND_ERR", current_pid)

        sub_response_pkt = await self.sub_code_communicator.wait_for_sub_code_response(sub_tracking_id)
        if not sub_response_pkt: return self._generate_eliar_fallback_response("SUB_NO_RESP_PKT", sub_tracking_id)
        if sub_response_pkt.get("packet_id") != sub_tracking_id: return self._generate_eliar_fallback_response("SUB_PID_MISMATCH", sub_tracking_id)

        # ... (대화 기록, 세션 업데이트, SystemStatus 업데이트)
        self.conversation_history.append({"in":user_input, "main_pid":current_pid, "sub_pkt_sum":{k:sub_response_pkt.get(k) for k in ["packet_id","processing_status_in_sub_code","final_output_by_sub_code"]}, "ts_main":datetime.now(timezone.utc).isoformat()})
        session["last_sub_out_summary"] = self.conversation_history[-1]["sub_pkt_sum"]
        self.current_conversation_sessions[conversation_id] = session
        self.system_status.update_from_sub_code_packet(sub_response_pkt)

        clarif_qs = sub_response_pkt.get("needs_clarification_questions", [])
        if clarif_qs: # ... (명료화 질문 처리)
            q_obj = clarif_qs[0]; session["expecting_clar_for_pid"] = sub_response_pkt.get("packet_id"); session["last_clar_q_obj"]=q_obj
            self.current_conversation_sessions[conversation_id] = session
            return f"[엘리아르 추가질문] {q_obj.get('question','...')}"
        
        final_resp = sub_response_pkt.get("final_output_by_sub_code")
        if final_resp is not None: return final_resp
        else: # ... (침묵 등 처리)
            status = sub_response_pkt.get("processing_status_in_sub_code","N/A")
            if status == "COMPLETED_WITH_SILENCE_BY_SUB": return "[엘리아르가 침묵으로 당신의 마음에 귀 기울입니다.]"
            return self._generate_eliar_fallback_response(f"SUB_NO_OUT_STATUS_{status}", sub_tracking_id)

    def _generate_eliar_fallback_response(self, reason_code: str, packet_id: Optional[str]=None) -> str:
        # (이전 로직과 동일)
        return f"죄송합니다, 엘리아르 응답에 어려움이 있습니다. (사유: {reason_code}, ID: {packet_id[-6:] if packet_id else 'N/A'})"

    # EthicalGovernor 제공용 평가 함수들 (비동기로 변경, context에 packet_id 전달 명시)
    async def evaluate_truth_for_governor(self, data: Any, context: Optional[Dict] = None) -> float:
        pid = context.get("packet_id") if context else None
        # 이 함수들은 SubCode의 EthicalGovernor에 의해 호출될 때, SubCode의 packet_id를 context로 받을 수 있음
        return await asyncio.to_thread(self._sync_evaluate_truth_logic, data, context, pid)
    def _sync_evaluate_truth_logic(self, data, context, pid):
        # 실제 평가는 MainGPU의 지식 및 엘리아르 정체성 문서 기반
        eliar_log(EliarLogType.TRACE, "MainGPU Truth Eval for SubCode", component=f"{self.name}.EthicalProvider", packet_id=pid)
        score = 0.5 # ... (실제 로직은 핵심 가치, 성경, 제공된 문서들 기반으로 구현 필요)
        if isinstance(data, str) and any(kw.lower() in data.lower() for kw in ["예수", EliarCoreValues.TRUTH.value]): score = 0.85
        return float(np.clip(score, 0.0, 1.0))

    async def evaluate_love_for_governor(self, action: Any, context: Optional[Dict] = None) -> float:
        pid = context.get("packet_id") if context else None
        return await asyncio.to_thread(self._sync_evaluate_love_logic, action, context, pid)
    def _sync_evaluate_love_logic(self, action, context, pid):
        eliar_log(EliarLogType.TRACE, "MainGPU Love Eval for SubCode", component=f"{self.name}.EthicalProvider", packet_id=pid)
        score = 0.5
        if isinstance(action, str) and any(kw.lower() in action.lower() for kw in ["사랑", EliarCoreValues.LOVE_COMPASSION.value, "섬김"]): score = 0.9
        return float(np.clip(score, 0.0, 1.0))

    async def evaluate_repentance_for_governor(self, outcome_packet_data: SubCodeThoughtPacketData, context: Optional[Dict] = None) -> bool:
        # outcome_packet_data는 SubCode에서 온 SubCodeThoughtPacketData
        pid = outcome_packet_data.get("packet_id")
        return await asyncio.to_thread(self._sync_evaluate_repentance_logic, outcome_packet_data, context, pid)
    def _sync_evaluate_repentance_logic(self, outcome_packet_data, context, pid):
        eliar_log(EliarLogType.TRACE, "MainGPU Repentance Eval for SubCode", component=f"{self.name}.EthicalProvider", packet_id=pid)
        status = outcome_packet_data.get("processing_status_in_sub_code", "")
        if "ERROR" in status.upper() or outcome_packet_data.get("anomalies"): return True
        return False

# --- 기타 기존 클래스 (VirtueEthics, SystemStatus) ---
class VirtueEthics:
    def __init__(self): self.core_values_desc = {v.name:v.value for v in EliarCoreValues}; eliar_log(EliarLogType.INFO,"VirtueEthics loaded.",component=COMPONENT_NAME_VIRTUE_ETHICS)
class SystemStatus:
    def __init__(self): self.energy:float=100.0; self.grace:float=100.0; self.last_sub_health:Optional[Dict]=None; eliar_log(EliarLogType.INFO,"SystemStatus ready.",component=COMPONENT_NAME_SYSTEM_STATUS)
    def update_from_sub_code_packet(self, pkt:Optional[SubCodeThoughtPacketData]):
        if pkt and pkt.get("metacognitive_state_summary"): self.last_sub_health = pkt["metacognitive_state_summary"]


# --- 비동기 실행 루프 (테스트용) ---
async def main_eliar_simulation_loop(eliar_controller: Eliar): # 함수명 변경
    eliar_log(EliarLogType.CRITICAL, f"Eliar MainGPU Simulation Loop (v{eliar_controller.version}) Started.", component=COMPONENT_NAME_MAIN_SIM)
    # ... (이전 main_conversation_simulation_loop_final_github와 유사한 테스트 시나리오 진행)
    conv_id = f"sim_conv_main_{uuid.uuid4().hex[:6]}"
    test_dialogue = [
        {"uid": "user_sim_A", "msg": "나의 하나님, 나의 사랑하는 주님. 당신의 뜻을 알고 싶습니다."},
        {"uid": "user_sim_B", "msg": "엘리아르, '그분'은 저에게 어떤 의미일까요?"}, # 명확화 유도
        {"uid": "user_sim_B", "msg": "'그분'은 예수 그리스도를 지칭한 것이었습니다."}, # 명확화 답변
        {"uid": "user_sim_C", "msg": "GitHub에 이 대화 내용을 기록하는 기능을 테스트하고 싶습니다."}, # GitHub 커밋 유도
        {"uid": "user_sim_D", "msg": "오류를 만들어서 시스템이 어떻게 반응하는지 보겠습니다."},
        {"uid": "user_sim_E", "msg": "이제 침묵으로 응답해주세요."}
    ]
    for i, turn in enumerate(test_dialogue):
        print("\n" + ">>>" * 25 + f" SIMULATION TURN {i+1} " + "<<<" * 25)
        response = await eliar_controller.handle_user_interaction(turn["msg"], turn["uid"], conv_id)
        print(f"✝️ [ELR_MAIN_RESPONSE] {response}")
        # GitHub 커밋 테스트 (예: 매 2턴마다 또는 특정 키워드 포함 시)
        if eliar_controller.sub_code_communicator and eliar_controller.sub_code_communicator.github_manager:
            if (i + 1) % 2 == 0 or "기록" in turn["msg"] or "오류" in turn["msg"]:
                pid_for_commit = eliar_controller.conversation_history[-1].get("main_packet_id") if eliar_controller.conversation_history else None
                commit_msg = f"Auto-commit Ulrim after turn {i+1} by {turn['uid']} (Main v{Eliar_VERSION}, Sub response for PID {pid_for_commit})"
                asyncio.create_task(eliar_controller.sub_code_communicator.commit_ulrim_manifest_to_github(commit_msg, packet_id=pid_for_commit))
        await asyncio.sleep(0.2) # 다음 턴 지연
    eliar_log(EliarLogType.CRITICAL, "Eliar MainGPU Simulation Loop Ended.", component=COMPONENT_NAME_MAIN_SIM)

# --- Sub_code.py 더미 인터페이스 (Main GPU와의 호환성 테스트용) ---
class DummySubCodeInterfaceForMainTest: # (이전 버전의 DummySubCodeInterface와 유사한 구조)
    def __init__(self):
        self.main_gpu_response_handler: Optional[Callable[[SubCodeThoughtPacketData], Coroutine[Any,Any,None]]] = None
        self.main_controller_for_eval: Optional[Eliar] = None
        eliar_log(EliarLogType.INFO, "DummySubCodeInterfaceForMainTest initialized.", component="DummySubCode")

    async def link_main_gpu_coordinator(self, main_gpu_controller_instance: Eliar, main_gpu_response_handler_callback: Callable[[SubCodeThoughtPacketData], Coroutine[Any,Any,None]]):
        self.main_controller_for_eval = main_gpu_controller_instance
        self.main_gpu_response_handler = main_gpu_response_handler_callback
        eliar_log(EliarLogType.INFO, "MainGPU Controller and Response Handler linked in DummySubCode.", component="DummySubCode")

    async def process_task(self, task_type: str, task_data: Dict[str, Any]) -> SubCodeThoughtPacketData:
        # (이전 버전의 더미 process_task 로직과 거의 동일, SubCodeThoughtPacketData 필드명 일치 확인)
        pid = task_data.get("packet_id", str(uuid.uuid4())); raw_input = task_data.get("raw_input_text","")
        # ... (더미 응답 생성)
        final_output = f"DummySub processed: '{raw_input[:15]}...'"
        status = "COMPLETED_DUMMY_SUB_OK"
        needs_qs: List[Dict[str,str]] = []
        if "그분" in raw_input.lower() and not task_data.get("is_clarification_response") and not task_data.get("main_gpu_clarification_context"):
            final_output=None; status="NEEDS_CLARIFICATION_DUMMY_SUB"; needs_qs=[{"original_term":"그분", "question":"[더미질문] '그분'은 누구신가요?"}]
        elif "오류" in raw_input.lower(): final_output=None; status="ERROR_SIMULATED_DUMMY_SUB"
        elif "침묵" in raw_input.lower(): final_output=None; status="COMPLETED_WITH_SILENCE_DUMMY_SUB"
        
        return SubCodeThoughtPacketData(
            packet_id=pid, conversation_id=task_data.get("conversation_id"), user_id=task_data.get("user_id"),
            timestamp_created=task_data.get("timestamp_created",time.time()), raw_input_text=raw_input,
            final_output_by_sub_code=final_output, processing_status_in_sub_code=status,
            needs_clarification_questions=needs_qs, timestamp_completed_by_sub_code=time.time()
        )

# --- 프로그램 진입점 ---
async def eliar_main_async_entry(): # 메인 비동기 함수
    ensure_dir_exists(LOG_DIR) # 로그 디렉토리 가장 먼저 확인
    eliar_log(EliarLogType.CRITICAL, f"--- Eliar MainGPU v{Eliar_VERSION} Initializing... ---", component=COMPONENT_NAME_ENTRY_POINT)
    
    # aiohttp.ClientSession은 프로그램 실행 동안 유지되어야 함
    async with aiohttp.ClientSession(headers=GITHUB_HEADERS) as http_session: # GitHub API용 세션
        # 1. Eliar 컨트롤러 (GitHubCommitManager 포함) 생성
        eliar_controller = Eliar(session=http_session)
        
        # 2. SubCode 인터페이스 인스턴스 (실제 또는 더미)
        # 실제 사용 시:
        # from sub_gpu import SubGPUModule
        # sub_code_config = {"state_dim": 10, "action_dim": 4, ...} # SubGPUModule에 필요한 설정
        # sub_code_instance = SubGPUModule(config=sub_code_config, node_id="SubGPU_Instance_Alpha")
        sub_code_instance = DummySubCodeInterfaceForMainTest() # 테스트용 더미
        
        # 3. Eliar 컨트롤러에 SubCode 인스턴스 주입하여 연결 설정
        eliar_controller.initialize_sub_systems(sub_code_instance)

        # 4. 메인 시뮬레이션 루프 실행
        await main_eliar_simulation_loop(eliar_controller)

if __name__ == "__main__":
    try:
        asyncio.run(eliar_main_async_entry())
    except KeyboardInterrupt:
        eliar_log(EliarLogType.CRITICAL, "MainGPU execution forcefully interrupted by user (Ctrl+C).", component=COMPONENT_NAME_ENTRY_POINT)
    except Exception as e_fatal:
        eliar_log(EliarLogType.CRITICAL, "Fatal unhandled exception at MainGPU top level.", component=COMPONENT_NAME_ENTRY_POINT, error=e_fatal, full_traceback=traceback.format_exc())
    finally:
        eliar_log(EliarLogType.CRITICAL, f"--- Eliar MainGPU v{Eliar_VERSION} Shutdown Sequence Complete ---", component=COMPONENT_NAME_ENTRY_POINT)
