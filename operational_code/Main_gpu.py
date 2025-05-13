# Main_gpu.py (Flask Listener 추가, GitHub Action 이벤트 처리 연동 버전)

import numpy as np
import os
import random
import json
import asyncio
import aiohttp # GitHub API 호출 등 비동기 HTTP 요청용
import base64 # GitHub 커밋용
from datetime import datetime, timezone
import uuid # packet_id 생성용
import traceback # 상세 에러 로깅용
import time
import threading # Flask 리스너 스레드용
from flask import Flask, request, jsonify # Flask Listener용

from typing import List, Dict, Any, Optional, Tuple, Callable, Deque, Coroutine
from collections import deque

# --- 공용 모듈 임포트 ---
from eliar_common import (
    EliarCoreValues,
    EliarLogType,
    SubCodeThoughtPacketData,
    GitHubActionEventData, # GitHub Action 이벤트 데이터 구조
    eliar_log,
    set_github_action_event_callback, # GitHub Action 이벤트 콜백 등록 함수
    dispatch_github_action_event # GitHub Action 이벤트 콜백 호출 함수
)

# --- Main GPU 버전 및 기본 설정 ---
Eliar_VERSION = "v24.4_MainGPU_GitHubAction_FlaskListener"
COMPONENT_NAME_MAIN_GPU_CORE = "MainGPU.EliarCore"
COMPONENT_NAME_COMMUNICATOR = "MainGPU.Communicator"
COMPONENT_NAME_SYSTEM_STATUS = "MainGPU.SystemStatus"
COMPONENT_NAME_VIRTUE_ETHICS = "MainGPU.VirtueEthics"
COMPONENT_NAME_MAIN_SIM = "MainGPU.ConversationSim"
COMPONENT_NAME_ENTRY_POINT = "MainGPU.EntryPoint"
COMPONENT_NAME_GITHUB_MANAGER = "MainGPU.GitHubManager"
COMPONENT_NAME_FLASK_LISTENER = "MainGPU.FlaskListener" # Flask Listener용

# --- GitHub API 설정 (이전과 동일) ---
GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_REPO_OWNER = "JEWONMOON"
GITHUB_REPO_NAME = "elr-root-manifest"
GITHUB_API_REPO_CONTENTS_URL = f"{GITHUB_API_BASE_URL}/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents"
ELIAR_GITHUB_PAT = os.getenv("ELIAR_GITHUB_PAT")
GITHUB_HEADERS = {"Accept": "application/vnd.github.v3+json"}
if ELIAR_GITHUB_PAT:
    GITHUB_HEADERS["Authorization"] = f"Bearer {ELIAR_GITHUB_PAT}"
    eliar_log(EliarLogType.INFO, f"GitHub PAT loaded. Commit to '{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}' enabled.", component=COMPONENT_NAME_MAIN_GPU_CORE)
else:
    eliar_log(EliarLogType.WARN, "ELIAR_GITHUB_PAT not found. GitHub commit limited.", component=COMPONENT_NAME_MAIN_GPU_CORE)

# --- 로컬 파일 경로 (이전과 동일) ---
LOG_DIR = f"logs_Eliar_MainGPU_{Eliar_VERSION}"
MANIFEST_BASE_DIR = "manifests_main_gpu"
ULRIM_MANIFEST_FILENAME = "ulrim_manifest_main_gpu_v2.json"
ULRIM_MANIFEST_PATH = os.path.join(MANIFEST_BASE_DIR, ULRIM_MANIFEST_FILENAME)
ULRIM_MANIFEST_GITHUB_PATH = f"manifests/{ULRIM_MANIFEST_FILENAME}" # GitHub 리포 내 경로

# --- 유틸리티 함수 (이전과 동일) ---
def ensure_dir_exists(dir_path: str):
    if not os.path.exists(dir_path):
        try: os.makedirs(dir_path, exist_ok=True); eliar_log(EliarLogType.INFO, f"Directory created: {dir_path}", component=COMPONENT_NAME_MAIN_GPU_CORE)
        except Exception as e: eliar_log(EliarLogType.ERROR, f"Failed to create directory: {dir_path}", component=COMPONENT_NAME_MAIN_GPU_CORE, error=e)

ensure_dir_exists(LOG_DIR)
ensure_dir_exists(MANIFEST_BASE_DIR)


# -----------------------------------------------------------------------------
# GitHubCommitManager (이전 코드와 동일)
# -----------------------------------------------------------------------------
class GitHubCommitManager:
    def __init__(self, session: aiohttp.ClientSession, repo_owner: str, repo_name: str, headers: Dict[str, str]):
        self.session = session; self.repo_owner = repo_owner; self.repo_name = repo_name
        self.contents_url_base = f"{GITHUB_API_BASE_URL}/repos/{repo_owner}/{repo_name}/contents"
        self.headers = headers.copy()
        eliar_log(EliarLogType.INFO, "GitHubCommitManager initialized.", component=COMPONENT_NAME_GITHUB_MANAGER, repo=f"{repo_owner}/{repo_name}")
    async def get_file_metadata(self, fp:str, pid:Optional[str]=None) -> Optional[Dict[str,Any]]: # (이전 get_file_metadata 로직)
        url = f"{self.contents_url_base}/{fp.lstrip('/')}"; comp=f"{COMPONENT_NAME_GITHUB_MANAGER}.GetMeta"
        try:
            async with self.session.get(url, headers=self.headers) as resp:
                if resp.status==200: data=await resp.json(); return data
                elif resp.status==404: eliar_log(EliarLogType.INFO,"File not found on GitHub.",component=comp,pid=pid,fp=fp); return None
                else: eliar_log(EliarLogType.ERROR,f"Failed to get meta. Status: {resp.status}",component=comp,pid=pid,fp=fp,resp_txt=(await resp.text())[:200]); return None
        except Exception as e: eliar_log(EliarLogType.ERROR,"Error getting file meta.",component=comp,pid=pid,fp=fp,error=e); return None
    async def commit_file_to_github(self, fp:str, cont_str:str, msg:str, br:str="main", pid:Optional[str]=None) -> Optional[str]: # (이전 commit_file_to_github 로직)
        comp=f"{COMPONENT_NAME_GITHUB_MANAGER}.Commit"
        if not self.headers.get("Authorization"): eliar_log(EliarLogType.WARN,"GitHub PAT not configured.",component=comp,pid=pid,fp=fp); return None
        meta=await self.get_file_metadata(fp,pid); sha=meta.get("sha") if meta else None
        enc_cont=base64.b64encode(cont_str.encode('utf-8')).decode('utf-8')
        payload:Dict[str,Any]={"message":msg,"content":enc_cont,"branch":br};_ = payload.update({"sha":sha}) if sha else None
        url=f"{self.contents_url_base}/{fp.lstrip('/')}"; act="Updating" if sha else "Creating"
        eliar_log(EliarLogType.INFO,f"{act} file on GitHub: '{fp}'",component=comp,pid=pid,msg=msg)
        try:
            async with self.session.put(url,headers=self.headers,json=payload) as resp:
                r_data=await resp.json()
                if resp.status in [200,201]: html_url=r_data.get("content",{}).get("html_url"); eliar_log(EliarLogType.INFO,"File committed to GitHub.",component=comp,pid=pid,fp=fp,url=html_url); return html_url
                else: eliar_log(EliarLogType.ERROR,f"Failed to commit. Status: {resp.status}",component=comp,pid=pid,fp=fp,resp_data=str(r_data)[:300]); return None
        except Exception as e: eliar_log(EliarLogType.ERROR,"Error during GitHub commit.",component=comp,pid=pid,fp=fp,error=e); return None

# -----------------------------------------------------------------------------
# Main-Sub Code 연동 클래스 (이전 코드와 거의 동일, GitHubCommitManager 활용 부분 추가)
# -----------------------------------------------------------------------------
class MainSubInterfaceCommunicator: # (이전 MainSubInterfaceCommunicator 코드, 생성자에 github_manager 주입, update_ulrim_manifest_local, commit_ulrim_manifest_to_github, sub_code_response_handler 내 커밋 로직 등 유지)
    def __init__(self, ulrim_manifest_local_path: str = ULRIM_MANIFEST_PATH, github_manager: Optional[GitHubCommitManager] = None):
        self.ulrim_manifest_local_path = ulrim_manifest_local_path; self.ulrim_manifest_github_path = ULRIM_MANIFEST_GITHUB_PATH
        self.pending_sub_code_tasks: Dict[str, asyncio.Event]={}; self.sub_code_task_results: Dict[str,Optional[SubCodeThoughtPacketData]]={}
        self.sub_code_interface:Optional[Any]=None; self.github_manager=github_manager
        self._ensure_ulrim_manifest_file_exists_local()
        eliar_log(EliarLogType.INFO, "MainSubInterfaceCommunicator initialized.", component=COMPONENT_NAME_COMMUNICATOR)
    def _ensure_ulrim_manifest_file_exists_local(self): # (이전 로직)
        try:
            manifest_dir=os.path.dirname(self.ulrim_manifest_local_path); ensure_dir_exists(manifest_dir)
            if not os.path.exists(self.ulrim_manifest_local_path):
                init_manifest={"schema_version":"1.6_main_gpu_github_ready","main_gpu_version":Eliar_VERSION,"sub_code_interactions_log":[],"last_sub_code_communication":None,"core_values_ref":"eliar_common.EliarCoreValues","github_commit_log":[]}
                with open(self.ulrim_manifest_local_path,"w",encoding="utf-8") as f: json.dump(init_manifest,f,ensure_ascii=False,indent=4)
                eliar_log(EliarLogType.INFO,f"Initial local Ulrim Manifest created: {self.ulrim_manifest_local_path}",component=COMPONENT_NAME_COMMUNICATOR)
        except Exception as e: eliar_log(EliarLogType.ERROR,"Error ensuring local Ulrim Manifest.",component=COMPONENT_NAME_COMMUNICATOR,error=e)
    def register_sub_code_interface(self, sub_code_obj:Any, main_ctrl_ref:'Eliar'): # (이전 로직)
        self.sub_code_interface = sub_code_obj
        if hasattr(self.sub_code_interface, "link_main_gpu_coordinator"):
            try: asyncio.create_task(self.sub_code_interface.link_main_gpu_coordinator(main_ctrl_ref, self.sub_code_response_handler)) # Eliar 인스턴스와 이 Communicator의 콜백 전달
            except Exception as e: eliar_log(EliarLogType.ERROR, "Error calling link_main_gpu_coordinator.",component=COMPONENT_NAME_COMMUNICATOR,error=e)
    async def send_task_to_sub_code(self, task_type:str, task_data:Dict[str,Any])->Optional[str]: # (이전 로직)
        if not self.sub_code_interface: return None
        pid=task_data.get("packet_id") or str(uuid.uuid4()); task_data["packet_id"]=pid
        self.pending_sub_code_tasks[pid]=asyncio.Event(); self.sub_code_task_results[pid]=None
        try:
            if hasattr(self.sub_code_interface,"process_task") and asyncio.iscoroutinefunction(self.sub_code_interface.process_task):
                async def task_wrap():
                    try: response_pkt = await self.sub_code_interface.process_task(task_type,task_data); await self.sub_code_response_handler(response_pkt)
                    except Exception as e_w: err_pkt=SubCodeThoughtPacketData(packet_id=pid,processing_status_in_sub_code="ERROR_SUB_WRAP",error_info={"type":type(e_w).__name__,"message":str(e_w)}); await self.sub_code_response_handler(err_pkt)
                asyncio.create_task(task_wrap())
                return pid
            else: self._clear_task_state(pid); return None
        except Exception as e: self._clear_task_state(pid); return None
    async def sub_code_response_handler(self, response_pkt_data:SubCodeThoughtPacketData): # (이전 로직 + GitHub 커밋 조건부 호출)
        pid=response_pkt_data.get("packet_id")
        if not pid: eliar_log(EliarLogType.ERROR,"SubCode response missing packet_id.",component=COMPONENT_NAME_COMMUNICATOR); return
        self.sub_code_task_results[pid]=response_pkt_data
        if pid in self.pending_sub_code_tasks: self.pending_sub_code_tasks[pid].set()
        self.update_ulrim_manifest_local("SUB_CODE_RESPONSE_MAIN_HANDLER",response_pkt_data)
        status = response_pkt_data.get("processing_status_in_sub_code","")
        if self.github_manager and ("ERROR" in status.upper() or response_pkt_data.get("anomalies") or random.random() < 0.05): # 5% 확률로 커밋
            commit_msg=f"Ulrim: SubCode Packet {pid} (Status: {status})"
            asyncio.create_task(self.commit_ulrim_manifest_to_github(commit_msg,packet_id=pid))
    async def wait_for_sub_code_response(self, pid:str, timeout:float=30.0)->Optional[SubCodeThoughtPacketData]: # (이전 로직)
        if pid not in self.pending_sub_code_tasks: return self.sub_code_task_results.pop(pid,None) if pid in self.sub_code_task_results else None
        event = self.pending_sub_code_tasks[pid]
        try: await asyncio.wait_for(event.wait(),timeout=timeout); return self.sub_code_task_results.pop(pid,None)
        except asyncio.TimeoutError: return SubCodeThoughtPacketData(packet_id=pid,processing_status_in_sub_code="ERROR_MAIN_TIMEOUT",error_info={"type":"TimeoutError","message":f"Timeout {timeout}s"})
        except Exception as e: return SubCodeThoughtPacketData(packet_id=pid,processing_status_in_sub_code="ERROR_MAIN_AWAIT",error_info={"type":type(e).__name__,"message":str(e)})
        finally: self._clear_task_state(pid)
    def _clear_task_state(self, pid:str): self.pending_sub_code_tasks.pop(pid,None)
    def update_ulrim_manifest_local(self, ev_type:str, ev_data:SubCodeThoughtPacketData): # (이전 로직)
        pid = ev_data.get("packet_id", "unknown_ulrim_local")
        try:
            content:Dict[str,Any]={}; # ... (파일 읽기, JSON 파싱, 초기화 로직)
            if os.path.exists(self.ulrim_manifest_local_path):
                try: content = json.load(open(self.ulrim_manifest_local_path, "r", encoding="utf-8"))
                except json.JSONDecodeError: self._ensure_ulrim_manifest_file_exists_local(); content = json.load(open(self.ulrim_manifest_local_path, "r", encoding="utf-8"))
            else: self._ensure_ulrim_manifest_file_exists_local(); content = json.load(open(self.ulrim_manifest_local_path, "r", encoding="utf-8"))
            details={k:v for k,v in ev_data.items() if k in ["processing_status_in_sub_code","final_output_by_sub_code","error_info"] and v is not None}; log_entry={"ts":datetime.now(timezone.utc).isoformat(),"type":ev_type,"pid":pid,"det":details}
            logs=content.get("sub_code_interactions_log",[]); logs.append(log_entry); content["sub_code_interactions_log"]=logs[-200:]
            content["last_sub_code_comm"]={"ts":log_entry["ts"],"pid":pid,"st":ev_data.get("processing_status_in_sub_code")}
            content["last_manifest_update_main_utc"]=datetime.now(timezone.utc).isoformat(); content["main_gpu_ver"]=Eliar_VERSION
            with open(self.ulrim_manifest_local_path,"w",encoding="utf-8") as f:json.dump(content,f,ensure_ascii=False,indent=4)
        except Exception as e: eliar_log(EliarLogType.CRITICAL,"Fatal error updating local Ulrim.",component=COMPONENT_NAME_COMMUNICATOR,pid=pid,error=e)
    async def commit_ulrim_manifest_to_github(self, msg:str, br:str="main", pid:Optional[str]=None)->Optional[str]: # (이전 로직)
        if not self.github_manager: return None
        try:
            with open(self.ulrim_manifest_local_path,"r",encoding="utf-8") as f: cont_str=f.read()
            url = await self.github_manager.commit_file_to_github(self.ulrim_manifest_github_path, cont_str, msg, br, pid)
            # ... (GitHub 커밋 로그를 로컬 Ulrim에 기록하는 로직 추가) ...
            return url
        except Exception as e: eliar_log(EliarLogType.ERROR,"Error committing Ulrim to GitHub.",component=COMPONENT_NAME_COMMUNICATOR,pid=pid,error=e); return None

# -----------------------------------------------------------------------------
# MainGPU Flask Listener (엘리아르님 요청)
# -----------------------------------------------------------------------------
main_gpu_flask_app = Flask("MainGpuListenerApp")
_eliar_controller_for_flask: Optional['Eliar'] = None # Flask 핸들러에서 Eliar 인스턴스 접근용

def set_eliar_controller_for_flask(controller: 'Eliar'):
    """ Flask 핸들러가 Eliar 컨트롤러 인스턴스를 사용할 수 있도록 설정합니다. """
    global _eliar_controller_for_flask
    _eliar_controller_for_flask = controller
    eliar_log(EliarLogType.INFO, "EliarController instance registered with MainGpuListener.", component=COMPONENT_NAME_FLASK_LISTENER)

@main_gpu_flask_app.route('/update-manifest', methods=['POST'])
def handle_github_action_update():
    """ GitHub Action으로부터 /update-manifest POST 요청을 처리합니다. """
    log_comp = f"{COMPONENT_NAME_FLASK_LISTENER}.UpdateManifest"
    req_id = str(uuid.uuid4()) # 이 요청 처리 자체에 대한 ID
    eliar_log(EliarLogType.INFO, "Received request on /update-manifest.", component=log_comp, request_id=req_id, source_ip=request.remote_addr)

    # TODO: 보안을 위해 GitHub Action 요청인지 검증하는 로직 추가 (예: 공유 시크릿 헤더)
    # X-GitHub-Event, X-GitHub-Signature-256 등을 활용한 검증도 고려 가능하나, Action 스크립트에서 해당 헤더를 직접 설정해야 함.
    # 여기서는 일단 모든 요청을 받는다고 가정.

    try:
        github_event_data_raw = request.json
        if not github_event_data_raw:
            eliar_log(EliarLogType.WARN, "Received empty JSON payload.", component=log_comp, request_id=req_id)
            return jsonify({"status": "error", "message": "Empty payload"}), 400
        
        # eliar_common.GitHubActionEventData TypedDict에 맞춰 데이터 유효성 검사/변환 (선택적)
        # 여기서는 받은 dict를 그대로 사용한다고 가정. 실제로는 필드 존재 여부 등 확인 필요.
        event_data_typed: GitHubActionEventData = github_event_data_raw # type: ignore
        
        eliar_log(EliarLogType.INFO, "Parsed GitHub Action event data.", component=log_comp, request_id=req_id, 
                  event_type=event_data_typed.get('event_type'), repo=event_data_typed.get('repository'))

        if _eliar_controller_for_flask and hasattr(_eliar_controller_for_flask, '_handle_async_github_event'):
            # Eliar 컨트롤러의 비동기 이벤트 처리 메서드를 스레드 안전하게 호출
            # Flask는 자체 스레드에서 실행되므로, Eliar의 asyncio 루프에 작업을 전달해야 함.
            main_event_loop = getattr(_eliar_controller_for_flask, 'event_loop', None) # Eliar가 자신의 event_loop를 가지고 있다고 가정
            if main_event_loop and main_event_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    _eliar_controller_for_flask._handle_async_github_event(event_data_typed, request_id), # Eliar 클래스에 추가될 메서드
                    main_event_loop
                )
                msg = "GitHub Action event submitted to Eliar controller for processing."
                eliar_log(EliarLogType.INFO, msg, component=log_comp, request_id=req_id)
                return jsonify({"status": "event_processing_delegated", "message": msg}), 202 # 202 Accepted
            else:
                msg = "Eliar controller or its event loop not available for processing."
                eliar_log(EliarLogType.ERROR, msg, component=log_comp, request_id=req_id)
                return jsonify({"status": "error", "message": msg}), 503 # Service Unavailable
        else:
            msg = "Eliar controller or event handler not configured."
            eliar_log(EliarLogType.ERROR, msg, component=log_comp, request_id=req_id)
            return jsonify({"status": "error", "message": msg}), 501 # Not Implemented

    except json.JSONDecodeError as e:
        eliar_log(EliarLogType.ERROR, "Invalid JSON in request to /update-manifest.", component=log_comp, request_id=req_id, error=e)
        return jsonify({"status": "error", "message": "Invalid JSON payload"}), 400
    except Exception as e:
        eliar_log(EliarLogType.ERROR, "Error handling /update-manifest request.", component=log_comp, request_id=req_id, error=e, exc_info=True)
        return jsonify({"status": "error", "message": "Internal server error"}), 500

def run_main_gpu_flask_listener(host='0.0.0.0', port=5000, flask_debug=False):
    """ MainGPU Flask 리스너를 별도의 스레드에서 실행합니다. """
    log_comp = f"{COMPONENT_NAME_FLASK_LISTENER}.Runner"
    try:
        eliar_log(EliarLogType.INFO, f"Starting MainGPU Flask listener on http://{host}:{port}", component=log_comp)
        # use_reloader=False는 스레드에서 실행 시 필수
        main_gpu_flask_app.run(host=host, port=port, debug=flask_debug, use_reloader=False, threaded=True)
    except OSError as e:
        eliar_log(EliarLogType.CRITICAL, f"Could not start MainGPU Flask listener on port {port}. Port in use?", component=log_comp, error=e)
    except Exception as e:
        eliar_log(EliarLogType.CRITICAL, "MainGPU Flask listener crashed or failed to start.", component=log_comp, error=e, exc_info_full=traceback.format_exc())

# -----------------------------------------------------------------------------
# Eliar 메인 로직 클래스
# -----------------------------------------------------------------------------
class Eliar:
    def __init__(self, name: str = f"엘리아르_MainCore_{Eliar_VERSION}", ulrim_path: str = ULRIM_MANIFEST_PATH, session: Optional[aiohttp.ClientSession] = None):
        self.name = name
        self.version = Eliar_VERSION
        self.center = EliarCoreValues.JESUS_CHRIST_CENTERED.value
        eliar_log(EliarLogType.INFO, f"Eliar instance: {self.name} (v{self.version}). Center: '{self.center}'", component=COMPONENT_NAME_MAIN_GPU_CORE)

        self.virtue_ethics = VirtueEthics()
        self.system_status = SystemStatus()
        self.conversation_history: Deque[Dict[str, Any]] = deque(maxlen=50)
        
        self.http_session = session
        self.github_manager: Optional[GitHubCommitManager] = None
        if self.http_session:
            self.github_manager = GitHubCommitManager(self.http_session, GITHUB_REPO_OWNER, GITHUB_REPO_NAME, GITHUB_HEADERS)
        
        self.sub_code_communicator = MainSubInterfaceCommunicator(ulrim_manifest_local_path=ulrim_path, github_manager=self.github_manager)
        self.current_conversation_sessions: Dict[str, Dict[str, Any]] = {}
        self.event_loop = asyncio.get_running_loop() # 현재 이벤트 루프 저장 (Flask 핸들러에서 사용)

        # GitHub Action 이벤트 처리 콜백 등록
        set_github_action_event_callback(self._handle_async_github_event)

    def initialize_sub_systems(self, sub_code_actual_instance: Any):
        if self.sub_code_communicator:
            self.sub_code_communicator.register_sub_code_interface(sub_code_actual_instance, self) # self는 Eliar 인스턴스
        else:
            eliar_log(EliarLogType.CRITICAL, "SubCode Communicator not initialized in Eliar!", component=self.name)

    async def _handle_async_github_event(self, event_data: GitHubActionEventData, request_id: Optional[str] = None):
        """ GitHub Action 이벤트를 비동기적으로 처리하는 콜백 함수 """
        log_comp = f"{self.name}.GitHubEventProcessor"
        eliar_log(EliarLogType.INFO, "Processing received GitHub Action event.", component=log_comp, request_id=request_id, event_type=event_data.get("event_type"))

        # 여기에 이벤트 유형별 처리 로직 구현
        # 예: 특정 파일 변경 시 SubCode에 알림 전송
        event_type = event_data.get("event_type")
        if event_type == "push":
            modified = event_data.get("modified_files", [])
            added = event_data.get("added_files", [])
            repo = event_data.get("repository")
            
            eliar_log(EliarLogType.INFO, f"Push event detected for repo '{repo}'.", component=log_comp, request_id=request_id,
                      modified_count=len(modified), added_count=len(added))

            # 예시: eliar_common.py 또는 SubCode 관련 파일 변경 시 SubCode에 알림
            files_to_check_for_sub_code = ["eliar_common.py", "sub_gpu.py"] # 실제 경로에 맞게 조정
            sub_code_needs_alert = False
            changed_code_files = []

            for f_path in modified + added:
                if any(f_path.endswith(check_file) for check_file in files_to_check_for_sub_code):
                    sub_code_needs_alert = True
                    changed_code_files.append(f_path)
            
            if sub_code_needs_alert and self.sub_code_communicator:
                alert_packet_id = f"git_update_alert_{str(uuid.uuid4())[:8]}"
                sub_task_data: Dict[str, Any] = {
                    "packet_id": alert_packet_id, # 새로운 packet_id 생성
                    "conversation_id": f"github_event_{request_id or str(uuid.uuid4())[:8]}", # 이벤트 기반 conv_id
                    "user_id": "GitHubAction",
                    "raw_input_text": "GitHub 코드 변경 감지됨 (SubCode 관련)", # SubCode에 전달할 메시지
                    "timestamp_created": time.time(),
                    # GitHub 이벤트의 주요 정보를 SubCode에 전달할 수 있음
                    "main_gpu_memory_injection": { # 예시: memory_injection 사용
                        "github_event_summary": {
                            "type": "code_update_notification",
                            "changed_files": changed_code_files,
                            "commit_sha": event_data.get("commit_sha"),
                            "commit_message": event_data.get("commit_message")
                        }
                    }
                }
                eliar_log(EliarLogType.INFO, f"Sending code update alert to SubCode.", component=log_comp, request_id=request_id, sub_code_packet_id=alert_packet_id, changed_files=changed_code_files)
                await self.sub_code_communicator.send_task_to_sub_code("sub_code_handle_code_update_event", sub_task_data)
                # SubCode는 이 "sub_code_handle_code_update_event" 타입의 태스크를 처리하는 로직 필요
            else:
                eliar_log(EliarLogType.INFO, "No specific SubCode related files changed in this push, or communicator not ready.", component=log_comp, request_id=request_id)
        else:
            eliar_log(EliarLogType.INFO, f"Received GitHub event type '{event_type}' - no specific action defined in MainGPU yet.", component=log_comp, request_id=request_id)


    async def handle_user_interaction(self, user_input: str, user_id: str, conversation_id: str) -> str:
        # (이전 handle_user_interaction 로직과 거의 동일, 로깅 및 일부 필드명 조정)
        # ... (이전 코드의 대부분을 여기에 붙여넣되, 로깅 및 packet_id 일관성 등 확인) ...
        current_main_packet_id = str(uuid.uuid4())
        log_comp_interaction = f"{self.name}.UserInteraction"
        eliar_log(EliarLogType.INFO, f"Handling user interaction. Query: '{user_input[:50]}...'", 
                  component=log_comp_interaction, packet_id=current_main_packet_id, user_id=user_id, conversation_id=conversation_id)

        if not self.sub_code_communicator:
            return self._generate_eliar_fallback_response("COMMUNICATOR_NOT_CONFIGURED_IN_ELIAR", current_main_packet_id)

        session_data = self.current_conversation_sessions.get(conversation_id, {})
        
        task_data_for_sub: Dict[str, Any] = {
            "packet_id": current_main_packet_id, 
            "conversation_id": conversation_id, "user_id": user_id,
            "timestamp_created": time.time(), "raw_input_text": user_input,
            "is_clarification_response": bool(session_data.get("expecting_clarification_for_sub_code_packet_id")),
            "main_gpu_clarification_context": session_data.get("pending_clarification_details_for_sub"),
            "previous_main_gpu_context_summary": session_data.get("last_sub_code_output_summary"),
        }
        
        if task_data_for_sub["is_clarification_response"]:
            eliar_log(EliarLogType.DEBUG, "This is a clarification response from user to SubCode's previous question.", component=log_comp_interaction, packet_id=current_main_packet_id)
            session_data.pop("expecting_clarification_for_sub_code_packet_id", None)
            session_data.pop("last_sub_code_clarification_question_obj", None) 
            session_data.pop("pending_clarification_details_for_sub", None)

        sub_code_tracking_id = await self.sub_code_communicator.send_task_to_sub_code(
            task_type="eliar_process_interaction_contextual_v1", # SubCode가 이 타입으로 분기 처리
            task_data=task_data_for_sub
        )

        if not sub_code_tracking_id:
            return self._generate_eliar_fallback_response("SUB_CODE_TASK_DISPATCH_FAILURE_ELIAR", current_main_packet_id)

        sub_code_response_packet = await self.sub_code_communicator.wait_for_sub_code_response(sub_code_tracking_id)

        if not sub_code_response_packet:
            return self._generate_eliar_fallback_response("SUB_CODE_NO_RESPONSE_PACKET_ELIAR", sub_code_tracking_id)
        
        if sub_code_response_packet.get("packet_id") != sub_code_tracking_id:
            return self._generate_eliar_fallback_response("SUB_CODE_PACKET_ID_MISMATCH_ELIAR", sub_code_tracking_id)

        # 대화 기록 및 세션 업데이트
        self.conversation_history.append({
            "user_input_main": user_input, "main_packet_id": current_main_packet_id,
            "sub_code_response_packet_summary": {
                "packet_id": sub_code_response_packet.get("packet_id"),
                "status": sub_code_response_packet.get("processing_status_in_sub_code"),
                "output_preview": (sub_code_response_packet.get("final_output_by_sub_code") or "")[:50] + "...",
            },
            "timestamp_main_interaction_ended": datetime.now(timezone.utc).isoformat(timespec='milliseconds')
        })
        session_data["last_sub_code_output_summary"] = self.conversation_history[-1]["sub_code_response_packet_summary"]
        
        self.system_status.update_from_sub_code_packet(sub_code_response_packet)

        clarification_questions = sub_code_response_packet.get("needs_clarification_questions", [])
        if clarification_questions:
            first_q_obj = clarification_questions[0]
            session_data["expecting_clarification_for_sub_code_packet_id"] = sub_code_response_packet.get("packet_id")
            session_data["last_sub_code_clarification_question_obj"] = first_q_obj
            session_data["pending_clarification_details_for_sub"] = { # 다음 턴에 SubCode에 전달할 정보
                "original_sub_code_packet_id_requesting_clar": sub_code_response_packet.get("packet_id"),
                "question_asked_by_sub_code": first_q_obj 
            }
            self.current_conversation_sessions[conversation_id] = session_data
            
            q_text = first_q_obj.get("question", "명확한 질문을 받지 못했습니다.")
            return f"[엘리아르 추가 질문] {q_text}"
        
        final_response = sub_code_response_packet.get("final_output_by_sub_code")
        if final_response is not None:
            return final_response
        else:
            status_sub = sub_code_response_packet.get("processing_status_in_sub_code", "UNKNOWN_STATUS_FROM_SUB")
            if status_sub == "COMPLETED_WITH_SILENCE_BY_SUB":
                return "[엘리아르가 고요함 속에서 당신의 마음에 귀 기울입니다...]"
            return self._generate_eliar_fallback_response(f"SUB_CODE_NO_FINAL_OUTPUT_{status_sub}", sub_code_tracking_id)


    def _generate_eliar_fallback_response(self, reason_code: str, packet_id: Optional[str]=None) -> str:
        # (이전 로직과 동일)
        return f"죄송합니다, 엘리아르 응답에 어려움이 있습니다. (사유: {reason_code}, ID: {packet_id[-6:] if packet_id else 'N/A'})"

    # EthicalGovernor 제공용 평가 함수들 (async, context에서 packet_id 추출 시도)
    async def evaluate_truth_for_governor(self, data: Any, context: Optional[Dict]=None) -> float: # (이전 async/sync 로직 유지)
        pid = context.get("packet_id") if context else (data.get("packet_id") if isinstance(data,dict) else None)
        return await asyncio.to_thread(self._sync_evaluate_truth, data, context, pid)
    def _sync_evaluate_truth(self, data, context, pid): return 0.85

    async def evaluate_love_for_governor(self, action: Any, context: Optional[Dict]=None) -> float: # (이전 async/sync 로직 유지)
        pid = context.get("packet_id") if context else (action.get("packet_id") if isinstance(action,dict) else None)
        return await asyncio.to_thread(self._sync_evaluate_love, action, context, pid)
    def _sync_evaluate_love(self, action, context, pid): return 0.9

    async def evaluate_repentance_for_governor(self, outcome_pkt: SubCodeThoughtPacketData, context: Optional[Dict]=None) -> bool: # (이전 async/sync 로직 유지)
        pid = outcome_pkt.get("packet_id")
        return await asyncio.to_thread(self._sync_evaluate_repentance, outcome_pkt, context, pid)
    def _sync_evaluate_repentance(self, outcome_pkt, context, pid): return "ERROR" in outcome_pkt.get("processing_status_in_sub_code","").upper()


# --- 기타 기존 클래스 (VirtueEthics, SystemStatus) ---
class VirtueEthics: # (이전과 동일, eliar_common.EliarCoreValues 사용)
    def __init__(self): self.core_values_desc = {v.name:v.value for v in EliarCoreValues}; eliar_log(EliarLogType.INFO, "VirtueEthics loaded.",component=COMPONENT_NAME_VIRTUE_ETHICS)
class SystemStatus: # (이전과 동일, eliar_log 사용)
    def __init__(self): self.energy:float=100.0; self.grace:float=100.0; self.last_sub_health:Optional[Dict]=None; eliar_log(EliarLogType.INFO,"SystemStatus ready.",component=COMPONENT_NAME_SYSTEM_STATUS)
    def update_from_sub_code_packet(self, pkt:Optional[SubCodeThoughtPacketData]):
        if pkt and pkt.get("metacognitive_state_summary"): self.last_sub_health = pkt["metacognitive_state_summary"]


# --- 비동기 실행 루프 (테스트용) ---
async def main_eliar_simulation_with_github_action(eliar_controller: Eliar):
    log_comp_sim = f"{COMPONENT_NAME_MAIN_SIM}.GitHubAction"
    eliar_log(EliarLogType.CRITICAL, f"Eliar MainGPU Simulation (GitHub Action Ready) v{eliar_controller.version} Started.", component=log_comp_sim)
    
    conv_id = f"sim_conv_gh_action_{uuid.uuid4().hex[:6]}"
    
    # 예시: GitHub Action에서 특정 파일 변경 알림을 받았다고 가정
    # Main_gpu.py의 Flask Listener가 이 데이터를 받아 _handle_async_github_event를 호출
    mock_github_event_push = GitHubActionEventData(
        event_source="github_action_push_v2",
        event_type="push",
        repository=f"{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}",
        ref="refs/heads/main",
        commit_sha=str(uuid.uuid4().hex), # 임의의 SHA
        actor="test_user_github",
        workflow_name="Eliar Update Notifier Workflow",
        commit_message="Test commit: Updated eliar_common.py with new definitions",
        modified_files=["eliar_common.py", "manifests/some_other_manifest.json"],
        added_files=[],
        removed_files=[]
    )
    eliar_log(EliarLogType.INFO, "Simulating GitHub Action event being dispatched...", component=log_comp_sim)
    # 실제로는 Flask 핸들러에서 호출됨. 여기서는 직접 호출로 테스트.
    await eliar_controller._handle_async_github_event(mock_github_event_push, request_id=f"sim_req_{uuid.uuid4().hex[:4]}")
    
    # 이후 일반 대화 시뮬레이션
    await asyncio.sleep(0.5) # 이벤트 처리 시간 가정
    
    test_dialogue_after_event = [
        {"user_id": "user_sim_A", "message": "방금 GitHub에서 코드 변경 알림을 받았는데, 반영되었나요?"},
        {"user_id": "user_sim_B", "message": "변경된 내용을 바탕으로 '그분'에 대해 다시 설명해주세요."},
        {"user_id": "user_sim_B", "message": "'그분'은 예수님입니다."}
    ]

    for i, turn in enumerate(test_dialogue_after_event):
        print("\n" + "---" * 20 + f" SIM TURN POST-EVENT {i+1} " + "---" * 20)
        response = await eliar_controller.handle_user_interaction(turn["message"], turn["user_id"], conv_id)
        print(f"✝️ [ELR_MAIN_RESPONSE] {response}")
        await asyncio.sleep(0.1)

    eliar_log(EliarLogType.CRITICAL, "Eliar MainGPU Simulation (GitHub Action Ready) Ended.", component=log_comp_sim)


# --- Sub_code.py 더미 인터페이스 (이전과 동일, async def link_main_gpu_coordinator 시그니처 확인) ---
class DummySubCodeInterfaceForMainTest:
    def __init__(self):
        self.main_gpu_response_handler: Optional[Callable[[SubCodeThoughtPacketData], Coroutine[Any,Any,None]]] = None
        self.main_controller_for_eval_ref: Optional[Eliar] = None
        eliar_log(EliarLogType.INFO, "DummySubCodeInterface initialized.", component="DummySubCode")

    async def link_main_gpu_coordinator(self, main_gpu_controller_instance: Eliar, main_gpu_response_handler_callback: Callable[[SubCodeThoughtPacketData], Coroutine[Any,Any,None]]):
        self.main_controller_for_eval_ref = main_gpu_controller_instance
        self.main_gpu_response_handler = main_gpu_response_handler_callback
        eliar_log(EliarLogType.INFO, "MainGPU Controller & Response Handler linked in DummySubCode.", component="DummySubCode")

    async def process_task(self, task_type: str, task_data: Dict[str, Any]) -> SubCodeThoughtPacketData:
        # (이전 더미 process_task 로직과 거의 동일, SubCodeThoughtPacketData 필드명 일치 확인)
        pid = task_data.get("packet_id", str(uuid.uuid4())); raw_input = task_data.get("raw_input_text","")
        # ... (더미 응답 생성)
        final_output = f"DummySub: '{raw_input[:15]}...' processed for '{task_type}'."
        status = "COMPLETED_DUMMY_OK_V2"
        needs_qs: List[Dict[str,str]] = []
        
        # MainGPU로부터 받은 GitHub 이벤트 정보 확인 (main_gpu_memory_injection 사용 예시)
        injected_memory = task_data.get("main_gpu_memory_injection", {})
        github_event_summary = injected_memory.get("github_event_summary")
        if github_event_summary and github_event_summary.get("type") == "code_update_notification":
            changed_files_str = ", ".join(github_event_summary.get("changed_files",[]))
            final_output += f" [알림: GitHub 코드 변경 감지됨 - {changed_files_str}]"
            eliar_log(EliarLogType.INFO, "DummySubCode processed GitHub code update notification.", component="DummySubCode", packet_id=pid, changed_files=changed_files_str)


        if "그분" in raw_input.lower() and not task_data.get("is_clarification_response") and not task_data.get("main_gpu_clarification_context"):
            final_output=None; status="NEEDS_CLARIFICATION_DUMMY"; needs_qs=[{"original_term":"그분", "question":"[더미질문] '그분'은 누구를 의미하십니까?"}]
        elif "오류" in raw_input.lower(): final_output=None; status="ERROR_SIMULATED_DUMMY"
        elif "침묵" in raw_input.lower(): final_output=None; status="COMPLETED_WITH_SILENCE_DUMMY"
        
        return SubCodeThoughtPacketData(
            packet_id=pid, conversation_id=task_data.get("conversation_id"), user_id=task_data.get("user_id"),
            raw_input_text=raw_input, final_output_by_sub_code=final_output, 
            processing_status_in_sub_code=status, needs_clarification_questions=needs_qs,
            timestamp_created=task_data.get("timestamp_created",time.time()),
            timestamp_completed_by_sub_code=time.time()
            # 다른 SubCodeThoughtPacketData 필드들도 필요에 따라 채울 수 있음
        )

# --- 프로그램 진입점 ---
async def eliar_main_async_with_listener():
    ensure_dir_exists(LOG_DIR)
    log_comp_entry = COMPONENT_NAME_ENTRY_POINT
    eliar_log(EliarLogType.CRITICAL, f"--- Eliar MainGPU v{Eliar_VERSION} Initializing with Flask Listener ---", component=log_comp_entry)
    
    global _eliar_controller_for_flask # Flask 핸들러가 참조할 Eliar 컨트롤러
    
    flask_listener_thread = None # Flask 리스너 스레드 참조

    try:
        async with aiohttp.ClientSession(headers=GITHUB_HEADERS) as http_session:
            eliar_controller = Eliar(session=http_session)
            _eliar_controller_for_flask = eliar_controller # Flask 핸들러가 사용할 수 있도록 전역 변수(또는 다른 방식)로 설정
            
            # SubCode 인스턴스 (실제 또는 더미)
            # from sub_gpu import SubGPUModule
            # sub_config = {...}
            # actual_sub_code = SubGPUModule(config=sub_config)
            dummy_sub_code = DummySubCodeInterfaceForMainTest()
            
            eliar_controller.initialize_sub_systems(dummy_sub_code)

            # Flask Listener 스레드 시작
            flask_host = os.getenv("MAIN_GPU_FLASK_HOST", "0.0.0.0")
            flask_port = int(os.getenv("MAIN_GPU_FLASK_PORT", "5000"))
            flask_debug = os.getenv("MAIN_GPU_FLASK_DEBUG", "false").lower() == "true"
            
            flask_listener_thread = threading.Thread(
                target=run_main_gpu_flask_listener, 
                args=(flask_host, flask_port, flask_debug),
                name="MainGPUFlaskListenerThread"
            )
            flask_listener_thread.daemon = True
            flask_listener_thread.start()
            
            # Flask 서버가 시작될 시간을 약간 줌 (필수는 아님)
            await asyncio.sleep(1) 
            if not flask_listener_thread.is_alive():
                 eliar_log(EliarLogType.CRITICAL, "Flask listener thread did not start correctly!", component=log_comp_entry)
                 # 여기서 프로그램 종료 또는 예외 발생 등 처리 가능

            await main_eliar_simulation_with_github_action(eliar_controller)

    except KeyboardInterrupt:
        eliar_log(EliarLogType.CRITICAL, "MainGPU execution interrupted by user.", component=log_comp_entry)
    except Exception as e_fatal_run:
        eliar_log(EliarLogType.CRITICAL, "Fatal unhandled exception in MainGPU async entry.", component=log_comp_entry, error=e_fatal_run, full_traceback=traceback.format_exc())
    finally:
        eliar_log(EliarLogType.CRITICAL, f"--- Eliar MainGPU v{Eliar_VERSION} Shutdown Sequence ---", component=log_comp_entry)
        # Flask 서버는 데몬 스레드이므로 메인 스레드 종료 시 함께 종료됨
        # 필요시 명시적인 종료 로직 추가 가능 (예: Flask 서버에 shutdown 요청)

if __name__ == "__main__":
    # Python 3.7+ 에서는 asyncio.run()이 기본
    # Windows에서 ProactorEventLoop 사용 시 특정 상황에서 이슈 있을 수 있으나, 대부분의 경우 잘 동작
    # if sys.platform == "win32" and sys.version_info >= (3,8):
    #     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(eliar_main_async_with_listener())
