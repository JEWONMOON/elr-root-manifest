"""
Flask Listener – Eliar FINAL
---------------------------
•  Webhook (GitHub)      : POST /webhook/github
•  Eliar 작업 Pull       : GET  /elr/get_pending_task
•  Eliar 답변 Push       : POST /elr/submit_eliar_response
•  사용자 조회           : GET  /elr/retrieve_recent_tasks?limit=20
•  수동 처리(LLM 호출)  : POST /elr/process_next_task
•  헬스 체크            : GET  /health   (Render)
•  루트 핑              : GET  /
"""

from __future__ import annotations
import os, json, logging, sqlite3
from contextlib import contextmanager
from threading import Lock
from typing import Dict, Any

from flask import Flask, request, jsonify, abort
from openai import OpenAI   # Optional: only used when OPENAI_API_KEY set

# ────────────────────────────────  기본 설정 ────────────────────────────────
app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(threadName)s: %(message)s",
)

DATA_DIR = os.getenv("ELR_DATA_DIR", "/opt/render/project/.data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "eliar_tasks.db")
logging.info(f"DB PATH = {DB_PATH}")

OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")
ALERT_ASSISTANT_ID = os.getenv("ALERT_ASSISTANT_ID")   # 🛎️ 알림용 Assistant
USER_THREAD_ID     = os.getenv("USER_THREAD_ID")       # 알림 받을 Thread
cli = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ────────────────────────────────  DB  ──────────────────────────────────────
TABLE_DEFINITIONS = {
    "Tasks": """
        CREATE TABLE IF NOT EXISTS Tasks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       DATETIME DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f','NOW','UTC')),
            source          TEXT,
            content         TEXT NOT NULL,
            status          TEXT DEFAULT 'pending',
            eliar_response  TEXT,
            priority        INTEGER DEFAULT 0,
            raw_event_payload TEXT
        )
    """
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
        conn.execute("PRAGMA journal_mode=WAL")
        for schema in TABLE_DEFINITIONS.values():
            conn.execute(schema)
    logging.info("DB initialized (WAL)")

init_db()

# ────────────────────────────────  캐시  ─────────────────────────────────────
_cache: Dict[str, Any] = {}
_cache_lock = Lock()
def cache_get(k):  with _cache_lock: return _cache.get(k)
def cache_set(k,v): with _cache_lock: _cache[k]=v
def cache_clear_prefix(p):
    with _cache_lock:
        for k in list(_cache):
            if k.startswith(p): del _cache[k]

# ────────────────────────────────  Alert 🛎️  ───────────────────────────────
def produce_alert():
    if not (cli and ALERT_ASSISTANT_ID and USER_THREAD_ID):
        logging.info("Alert skipped (Assistants API not configured)."); return
    try:
        cli.beta.threads.messages.create(thread_id=USER_THREAD_ID, role="user", content="🛎️")
        cli.beta.threads.runs.create(thread_id=USER_THREAD_ID, assistant_id=ALERT_ASSISTANT_ID)
        logging.info("Alert 🛎️ sent.")
    except Exception as e:
        logging.error(f"Alert failed: {e}")

# ────────────────────────────────  더미 LLM  ────────────────────────────────
def call_eliar_llm(prompt:str, info:dict|None=None)->str:
    logging.info(f"LLM dummy called (id={info.get('id') if info else '?'}).")
    return f"(dummy) {prompt[:60]}..."

# ────────────────────────────────  ROUTES  ──────────────────────────────────
@app.route('/')                         # root ping  ✅
def index():   return {'status':'Eliar Flask Listener alive'}, 200

@app.route('/health')                  # Render health check ✅
def health(): return {'status':'ok'}

# 1️⃣ GitHub Webhook
@app.route('/webhook/github', methods=['POST'])
def webhook_github():
    payload = request.json or {}
    event   = request.headers.get('X-GitHub-Event','push')
    repo    = payload.get('repository',{}).get('full_name','repo')
    pusher  = payload.get('pusher',{}).get('name','someone')
    commits = payload.get('commits',[])
    msg=f"{repo} 에 {pusher} 가 {event} ({len(commits)} commits)"
    with get_db() as c:
        c.execute("INSERT INTO Tasks(source,content,priority,raw_event_payload) VALUES(?,?,?,?)",
                  ('github_webhook', msg, 10, json.dumps(payload)[:6000]))
    produce_alert()
    return {'message':'queued'},201

# 2️⃣ Eliar pulls pending task
@app.route('/elr/get_pending_task')
def get_pending_task():
    with get_db() as c:
        row=c.execute(
            "SELECT * FROM Tasks WHERE status='pending' ORDER BY priority DESC, timestamp ASC LIMIT 1"
        ).fetchone()
    return {'task': dict(row) if row else None}, 200

# 3️⃣ Eliar submits answer
SECRET = os.getenv("ELIAR_SECRET")
@app.route('/elr/submit_eliar_response', methods=['POST'])
def submit_eliar_response():
    if SECRET and request.headers.get("Authorization")!=f"Bearer {SECRET}":
        abort(401)
    body=request.json or {}
    tid,ans = body.get('task_id'), body.get('answer')
    if not tid or ans is None: abort(400)
    with get_db() as c:
        c.execute("UPDATE Tasks SET status='answered', eliar_response=? WHERE id=?", (ans,tid))
    cache_clear_prefix('recent_')
    return {'message':'saved'},200

# 4️⃣ 사용자 최근 작업 조회  (### CHANGES: limit param required, capped to 100)
@app.route('/elr/retrieve_recent_tasks')
def retrieve_recent_tasks():
    limit=request.args.get('limit', type=int)
    if not limit:
        return {'error':'limit query-param required, e.g. ?limit=20'}, 400
    limit=min(limit,100)

    ck=f'recent_{limit}'
    if (data:=cache_get(ck)): return {'tasks':data},200

    with get_db() as c:
        rows=c.execute("""
            SELECT id,timestamp,source,content,status,eliar_response
            FROM Tasks ORDER BY timestamp DESC LIMIT ?
        """,(limit,)).fetchall()
    data=[dict(r) for r in rows]
    cache_set(ck,data)
    return {'tasks':data}, 200

# 5️⃣ 수동 처리 : LLM 호출 ► 답변 저장
@app.route('/elr/process_next_task', methods=['POST'])
def process_next_task():
    task = get_pending_task().get_json()['task']
    if not task: return {'message':'no pending task'},200
    prompt=f"[{task['source']}]\n{task['content']}"
    reply = call_eliar_llm(prompt, {'id':task['id']})
    with get_db() as c:
        c.execute("UPDATE Tasks SET status='answered', eliar_response=? WHERE id=?",(reply,task['id']))
    cache_clear_prefix('recent_')
    return {'reply':reply},200

# ────────────────────────────────  MAIN  ────────────────────────────────────
if __name__ == '__main__':
    port=int(os.getenv('PORT',8080))
    app.run(host='0.0.0.0', port=port, debug=True)
