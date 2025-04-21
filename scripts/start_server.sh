#!/bin/bash

echo "🚀 엘리아르 채팅 서버를 시작합니다..."

# FastAPI 기반 채팅 API 실행
uvicorn app.chat_api:app --host 0.0.0.0 --port 8000 --reload 
