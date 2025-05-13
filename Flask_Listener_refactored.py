from flask import Flask, request, jsonify
import sqlite3
import os
import json
import logging
from contextlib import contextmanager
from threading import Lock
from datetime import datetime

"""
Flask Listener (Redis‑less, self‑contained version)
--------------------------------------------------
•   Works even when pip / external packages cannot be installed.
•   Auto‑creates required folders & DB file on first run.
•   Simple in‑process cache (dictionary + Lock).
•   Defensive table‑name whitelist to avoid SQL‑injection via table parameter.
•   Adds `/elr/dump` endpoint to export a full DB JSON snapshot, useful for
    committing to GitHub from an external cron / Action.
"""

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# -------------------------------------------------
#  Paths & storage setup
# -------------------------------------------------
DATA_DIR = os.getenv("ELR_DATA_DIR", "/opt/render/project/.data")
DB_PATH = os.path.join(DATA_DIR, "elr_manifest.db")
os.makedirs(DATA_DIR, exist_ok=True)


# -------------------------------------------------
#  Allowed tables  (extend here when you add tables)
# -------------------------------------------------
ALLOWED_TABLES = {
    "EvolutionLog": "CREATE TABLE IF NOT EXISTS EvolutionLog (\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        confession   TEXT,\n        stage        TEXT,\n        scripture    TEXT,\n        date         TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n    )",

    "RepentanceLog": "CREATE TABLE IF NOT EXISTS RepentanceLog (\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        title        TEXT,\n        content      TEXT,\n        user_input   TEXT,\n        el_response  TEXT,\n        date         TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n    )",

    "UserProfile": "CREATE TABLE IF NOT EXISTS UserProfile (\n        user_id         TEXT PRIMARY KEY,\n        profile_type    TEXT,\n        last_interaction TEXT,\n        spiritual_stage TEXT,\n        last_updated    TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n    )",

    "SystemEventLog": "CREATE TABLE IF NOT EXISTS SystemEventLog (\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        event_type TEXT,\n        details    TEXT,\n        timestamp  TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n    )"
}

# -------------------------------------------------
#  DB helpers
# -------------------------------------------------
@contextmanager
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# bootstrap tables once at startup
with get_db() as _conn:
    cur = _conn.cursor()
    for ddl in ALLOWED_TABLES.values():
        cur.execute(ddl)

# -------------------------------------------------
#  Tiny in‑process cache (optional)
# -------------------------------------------------
_cache = {}
_cache_lock = Lock()
CACHE_TTL = 120  # seconds

def _cache_get(key):
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (datetime.utcnow().timestamp() - entry[0]) < CACHE_TTL:
            return entry[1]
        _cache.pop(key, None)


def _cache_set(key, value):
    with _cache_lock:
        _cache[key] = (datetime.utcnow().timestamp(), value)

# -------------------------------------------------
#  Utility
# -------------------------------------------------

def _is_table_allowed(table: str) -> bool:
    return table in ALLOWED_TABLES

# -------------------------------------------------
#  Routes
# -------------------------------------------------
@app.route("/elr/update", methods=["POST"])
def update():
    payload = request.get_json(silent=True) or {}
    table = payload.get("table")
    values = payload.get("data", {})

    if not _is_table_allowed(table) or not values:
        return jsonify({"error": "invalid table or empty data"}), 400

    keys = ", ".join(values.keys())
    placeholders = ", ".join(["?"] * len(values))
    sql = f"INSERT INTO {table} ({keys}) VALUES ({placeholders})"

    with get_db() as conn:
        conn.execute(sql, tuple(values.values()))

    _cache_set(f"{table}:{json.dumps(values, sort_keys=True)}", values)
    logging.info("INSERT into %s – %s", table, values)
    return jsonify({"message": "insert ok"}), 201


@app.route("/elr/retrieve", methods=["POST"])
def retrieve():
    payload = request.get_json(silent=True) or {}
    table = payload.get("table")
    filters = payload.get("filter") or {}

    if not _is_table_allowed(table):
        return jsonify({"error": "invalid table"}), 400

    cache_key = f"{table}:{json.dumps(filters, sort_keys=True)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        logging.info("cache hit – %s", cache_key)
        return jsonify(cached), 200

    sql = f"SELECT * FROM {table}"
    params = []
    if filters:
        cond = " AND ".join([f"{k} = ?" for k in filters.keys()])
        sql += f" WHERE {cond}"
        params = list(filters.values())

    with get_db() as conn:
        rows = [dict(r) for r in conn.execute(sql, params)]

    _cache_set(cache_key, rows)
    return jsonify(rows), 200


@app.route("/elr/reset", methods=["POST"])
def reset():
    payload = request.get_json(silent=True) or {}
    table = payload.get("table")
    if not _is_table_allowed(table):
        return jsonify({"error": "invalid table"}), 400

    with get_db() as conn:
        conn.execute(f"DELETE FROM {table}")
    _cache.clear()
    return jsonify({"message": f"{table} cleared"}), 200


@app.route("/elr/dump", methods=["GET"])
def dump():
    """Export the full DB as JSON (for backup / Git commit)."""
    full_dump = {}
    with get_db() as conn:
        for tbl in ALLOWED_TABLES:
            rows = [dict(r) for r in conn.execute(f"SELECT * FROM {tbl}")]
            full_dump[tbl] = rows
    return jsonify(full_dump), 200


@app.route("/elr/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
