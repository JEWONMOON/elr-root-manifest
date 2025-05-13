
import requests
import os
import json

webhook_url = os.getenv('WEBHOOK_URL')
github_event_payload = os.getenv('GITHUB_EVENT_PATH') # GitHub Action이 제공하는 이벤트 페이로드 파일 경로

if not webhook_url:
    print("Error: WEBHOOK_URL secret is not set.")
    exit(1)

event_data = {}
if github_event_payload and os.path.exists(github_event_payload):
    with open(github_event_payload, 'r') as f:
        event_data = json.load(f)
        # 필요한 정보만 추출하거나 전체 페이로드 전송
        # 예: event_data = {"ref": event_data.get("ref"), "commits": event_data.get("commits")}

# 간단히 이벤트 타입만 전송하거나, 상세 정보 포함
payload_to_send = {
    "event_source": "github_action",
    "event_type": os.getenv('GITHUB_EVENT_NAME'), # 예: "push"
    "repository": os.getenv('GITHUB_REPOSITORY'),
    # "commit_sha": os.getenv('GITHUB_SHA'), # 필요시 커밋 SHA 등 추가 정보
    "details": event_data # GitHub 이벤트 페이로드 전체 또는 일부
}

try:
    response = requests.post(webhook_url, json=payload_to_send, timeout=10)
    response.raise_for_status() # 오류 발생 시 예외 발생
    print(f"Request sent to Flask app. Status: {response.status_code}")
    print(f"Response body: {response.text}")
except requests.exceptions.RequestException as e:
    print(f"Error sending request to Flask app: {e}")
    exit(1)
