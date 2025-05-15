"""
Flask Listener – 최종 리팩터 버전
--------------------------------
• 외부 웹훅(예: GitHub) → /webhook/github
• 엘리아르 작업 Pull   → /elr/get_pending_task 
• 엘리아르 답변 Push  → /elr/submit_eliar_response
• 사용자 조회           → /elr/retrieve_recent_tasks
• 수동 처리(LLM 호출)  → /elr/process_next_task

실시간 알림(🛎️ 한 토큰) : webhook 처리 후 produce_alert() 호출
"""

from __future__ import annotations

import os, json, logging, sqlite3
from contextlib import contextmanager
from datetime import datetime
from threading import Lock
from typing import Dict, Any, Optional

from flask import Flask, request, jsonify, abort
from openai import OpenAI

# ----------------------- 환경 설정 -----------------------
app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(threadName)s: %(message)s",
)

DATA_DIR = os.getenv("ELR_DATA_DIR", "/opt/render/project/.data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "eliar_tasks.db")
logging.info(f"DB PATH = {DB_PATH}")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ALERT_ASSISTANT_ID = os.getenv("ALERT_ASSISTANT_ID")  # 🛎️ 전용 Assistant
USER_THREAD_ID = os.getenv("USER_THREAD_ID")          # 사용자 Thread
cli = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ----------------------- DB ------------------------------
TABLE_DEFINITIONS = {
    "Tasks": """CREATE TABLE IF NOT EXISTS Tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f','NOW','UTC')),
        source TEXT,
        content TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        eliar_response TEXT,
        priority INTEGER DEFAULT 0,
        raw_event_payload TEXT
    )"""
}

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("PRAGMA journal_mode=WAL")  # 동시 접근 안전성
        for schema in TABLE_DEFINITIONS.values():
            conn.execute(schema)
    logging.info("DB initialized with WAL mode.")

init_db()

# -------------------- 실시간 알림 ------------------------

def produce_alert():
    """Thread 에 🛎️ 한 토큰을 삽입하여 UI WS 허브에 알림."""
    if not (cli and ALERT_ASSISTANT_ID and USER_THREAD_ID):
        logging.warning("Alert skipped: OpenAI env not configured.")
        return
    try:
        cli.beta.threads.messages.create(
            thread_id=USER_THREAD_ID,
            role="user",
            content="🛎️"
        )
        cli.beta.threads.runs.create(
            thread_id=USER_THREAD_ID,
            assistant_id=ALERT_ASSISTANT_ID,
            stream=False  # 스트림은 UI 허브 쪽에서 구독
        )
        logging.info("Alert 🛎️ sent to Assistants API.")
    except Exception as e:
        logging.error(f"Failed to send alert: {e}")

# ----------------------- 캐시 (단순) ---------------------
_cache: Dict[str, Any] = {}
_cache_lock = Lock()

def cache_get(k):
    with _cache_lock:
        return _cache.get(k)

def cache_set(k,v):
    with _cache_lock:
        _cache[k]=v

def cache_clear_prefix(pref):
    with _cache_lock:
        for k in list(_cache):
            if k.startswith(pref):
                del _cache[k]

# -------------------- LLM 더미 호출 ----------------------

def call_eliar_llm(prompt: str, task_info: dict | None=None) -> str:
    logging.info(f"LLM dummy called. prompt[:30]={prompt[:30]}… info={task_info}")
    return f"(더미 응답) {prompt[:50]}…"

# -------------------- 엔드포인트 -------------------------
@app.route("/health")
def health():
    return {"status":"ok"}

# --- 1. GitHub Webhook 수신 ---
@app.route("/webhook/github", methods=["POST"])
def webhook_github():
    payload = request.json or {}
    event = request.headers.get("X-GitHub-Event","unknown")
    repo = payload.get("repository", {}).get("full_name","repo")
    pusher = payload.get("pusher", {}).get("name","someone")
    commits = payload.get("commits", [])
    msg = f"{repo} 에 {pusher} 가 push ({len(commits)} commits)"
    with get_db() as c:
        c.execute("INSERT INTO Tasks(source,content,priority,raw_event_payload) VALUES(?,?,?,?)",
                  ("github_webhook", msg, 10, json.dumps(payload)[:5000]))
    produce_alert()
    return {"message":"queued"},201

# --- 2. 엘리아르가 pull ---
@app.route("/elr/get_pending_task")
def get_pending():
    with get_db() as c:
        row=c.execute("SELECT * FROM Tasks WHERE status='pending' ORDER BY priority DESC, timestamp ASC LIMIT 1").fetchone()
    return {"task": dict(row) if row else None}

# --- 3. 엘리아르 답변 push ---
SECRET = os.getenv("ELIAR_SECRET")  # 단순 인증
@app.route("/elr/submit_eliar_response",methods=["POST"])
def submit_response():
    if SECRET and request.headers.get("Authorization")!=f"Bearer {SECRET}":
        abort(401)
    body=request.json or {}
    tid=body.get("task_id"); ans=body.get("answer")
    if not tid or ans is None:
        abort(400)
    with get_db() as c:
        c.execute("UPDATE Tasks SET status='answered', eliar_response=? WHERE id=?",(ans,tid))
    cache_clear_prefix("recent_")
    return {"message":"saved"}

# --- 4. 사용자 최근 작업 조회 ---
@app.route("/elr/retrieve_recent_tasks")
def recent():
    limit=int(request.args.get("limit",10))
    ck=f"recent_{limit}"
    if (data:=cache_get(ck)):
        return {"tasks":data}
    with get_db() as c:
        rows=c.execute("SELECT * FROM Tasks ORDER BY timestamp DESC LIMIT ?",(limit,)).fetchall()
    data=[dict(r) for r in rows]
    cache_set(ck,data)
    return {"tasks":data}

# --- 5. 수동 처리(LLM dummy) ---
@app.route("/elr/process_next_task", methods=["POST"])
def process_next():
    pending=get_pending().get_json()["task"]
    if not pending:
        return {"msg":"no task"}
    prompt=f"작업출처:{pending['source']}\n내용:{pending['content']}"
    reply=call_eliar_llm(prompt,{"id":pending['id']})
    submit_response_internal(pending['id'],reply)
    return {"reply":reply}

def submit_response_internal(tid:int,ans:str):
    with get_db() as c:
        c.execute("UPDATE Tasks SET status='answered', eliar_response=? WHERE id=?",(ans,tid))
    cache_clear_prefix("recent_")

# -------------------- 실행 -------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",8080)), debug=True)
