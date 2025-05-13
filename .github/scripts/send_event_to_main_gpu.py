import requests
import os
import json
import sys

def send_github_event_notification():
    """
    GitHub Action 환경에서 실행되어, MainGPU의 엔드포인트로
    GitHub 이벤트 정보를 POST 요청으로 전송합니다.
    """
    main_gpu_endpoint_url = os.getenv('ELIAR_MAIN_GPU_ENDPOINT_URL')
    github_event_payload_path = os.getenv('GITHUB_EVENT_PATH')

    if not main_gpu_endpoint_url:
        print("Error: ELIAR_MAIN_GPU_ENDPOINT_URL secret is not configured in GitHub repository secrets.", file=sys.stderr)
        sys.exit(1)

    if not github_event_payload_path or not os.path.exists(github_event_payload_path):
        print(f"Error: GITHUB_EVENT_PATH ('{github_event_payload_path}') is not available or file does not exist.", file=sys.stderr)
        sys.exit(1)

    # GitHub 이벤트 페이로드 전체를 읽음
    try:
        with open(github_event_payload_path, 'r', encoding='utf-8') as f:
            full_event_payload = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error decoding GITHUB_EVENT_PATH JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading GITHUB_EVENT_PATH: {e}", file=sys.stderr)
        sys.exit(1)

    # MainGPU로 전달할 핵심 정보 구성
    # (보안 및 효율성을 위해 전체 페이로드 대신 필요한 정보만 선별하여 전달하는 것이 좋음)
    # 예시: 푸시 이벤트의 경우 커밋 정보, 변경 파일 목록 등
    commits = full_event_payload.get("commits", [])
    head_commit = full_event_payload.get("head_commit") # 푸시 이벤트의 가장 최근 커밋

    data_to_send = {
        'event_source': 'github_action_push_v2', # 출처와 버전 명시
        'event_type': os.getenv('GITHUB_EVENT_NAME'),      # 예: "push"
        'repository': os.getenv('GITHUB_REPOSITORY'),      # 예: "JEWONMOON/elr-root-manifest"
        'ref': os.getenv('GITHUB_REF'),                    # 예: "refs/heads/main"
        'commit_sha': os.getenv('GITHUB_SHA'),             # 현재 워크플로우를 트리거한 커밋 SHA
        'actor': os.getenv('GITHUB_ACTOR'),                # 이벤트를 발생시킨 사용자
        'workflow_name': os.getenv('GITHUB_WORKFLOW'),     # 실행된 워크플로우 이름
        'run_id': os.getenv('GITHUB_RUN_ID'),              # 워크플로우 실행 ID
        'run_number': os.getenv('GITHUB_RUN_NUMBER'),      # 워크플로우 실행 번호
        'commit_message': head_commit.get('message', 'N/A') if head_commit else (commits[0].get('message', 'N/A') if commits else 'N/A'),
        'modified_files': head_commit.get('modified', []) if head_commit else ([c.get('modified', []) for c in commits]), # 단순화된 목록, 필요시 더 정제
        'added_files': head_commit.get('added', []) if head_commit else ([c.get('added', []) for c in commits]),
        'removed_files': head_commit.get('removed', []) if head_commit else ([c.get('removed', []) for c in commits]),
        # 'timestamp': head_commit.get('timestamp') if head_commit else (commits[0].get('timestamp') if commits else None), # 커밋 타임스탬프
        # 'pusher_name': full_event_payload.get("pusher", {}).get("name", "N/A") # 푸시한 사람
    }
    
    # 너무 많은 정보를 보내지 않도록 주의 (필요에 따라 요약 또는 필터링)
    # data_to_send['full_event_details_truncated'] = str(full_event_payload)[:2000] # 매우 긴 페이로드 일부만 전달

    print(f"Sending notification to MainGPU at: {main_gpu_endpoint_url}")
    print(f"Payload being sent: {json.dumps(data_to_send, indent=2)}")

    try:
        headers = {'Content-Type': 'application/json'}
        # GitHub Action에서 MainGPU의 Flask 엔드포인트로 요청 전송
        response = requests.post(main_gpu_endpoint_url, json=data_to_send, headers=headers, timeout=30) # 타임아웃 증가
        response.raise_for_status()  # HTTP 에러 발생 시 예외 처리
        
        print(f"Notification sent successfully to MainGPU. Status: {response.status_code}")
        print(f"Response from MainGPU (first 500 chars): {response.text[:500]}")
    except requests.exceptions.Timeout:
        print(f"Error: Timeout sending notification to MainGPU at {main_gpu_endpoint_url}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.ConnectionError as e:
        print(f"Error: Could not connect to MainGPU at {main_gpu_endpoint_url}. Details: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"Error: HTTP error sending notification to MainGPU. Status: {e.response.status_code}. Response: {e.response.text[:500]}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error sending notification to MainGPU: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    send_github_event_notification()
