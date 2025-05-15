#!/usr/bin/env python3
"""
send_event_to_main_gpu.py
GitHub Action 러너에서 실행-–> Render Listener(/webhook/github) 로
간결한 JSON 을 POST 한다.
"""
import json, os, sys, pathlib, textwrap
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def load_event_payload(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fp:
            return json.load(fp)
    except Exception as exc:
        sys.exit(f"[ERROR] GITHUB_EVENT_PATH 읽기 실패: {exc}")

def build_summary(commits: list) -> str:
    if not commits:
        return "커밋 없음"
    first_msg = commits[0].get("message", "")[:60].replace("\n", " ")
    more = f" 외 {len(commits)-1}건" if len(commits) > 1 else ""
    return f'"{first_msg}"{more}'

def main() -> None:
    endpoint = os.getenv("ELIAR_MAIN_GPU_ENDPOINT_URL")
    event_path = os.getenv("GITHUB_EVENT_PATH")  # GitHub가 자동 제공
    if not endpoint:
        sys.exit("[ERROR] ELIAR_MAIN_GPU_ENDPOINT_URL secret이 설정되지 않았습니다.")
    if not event_path or not pathlib.Path(event_path).exists():
        sys.exit(f"[ERROR] GITHUB_EVENT_PATH({event_path}) 파일이 없습니다.")

    raw = load_event_payload(event_path)
    commits = raw.get("commits", [])
    head_commit = raw.get("head_commit") or (commits[0] if commits else {})

    payload = {
        "event_source": "github_action_push_v3",
        "event_type": os.getenv("GITHUB_EVENT_NAME"),
        "repository": os.getenv("GITHUB_REPOSITORY"),
        "ref": os.getenv("GITHUB_REF"),
        "commit_sha": os.getenv("GITHUB_SHA"),
        "actor": os.getenv("GITHUB_ACTOR"),
        "summary": build_summary(commits),
        "files_changed": {
            "added": head_commit.get("added", []),
            "modified": head_commit.get("modified", []),
            "removed": head_commit.get("removed", []),
        },
    }

    print("➡️  POST to:", endpoint)
    print("📦 Payload:\n", textwrap.indent(json.dumps(payload, ensure_ascii=False, indent=2), "  "))

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    # 3회 재시도(백오프) – Render가 슬립 상태일 때 대비
    retry = Retry(total=3, backoff_factor=1.5, status_forcelist=[502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))

    try:
        r = session.post(endpoint, json=payload, timeout=30)
        r.raise_for_status()
        print(f"✅ 전송 성공 – status {r.status_code}")
    except requests.RequestException as exc:
        sys.exit(f"[ERROR] 전송 실패: {exc}")

if __name__ == "__main__":
    main()
