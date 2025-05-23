# graph.py
import asyncio
import time
from typing import List, Dict, Any

from langgraph.graph import StateGraph, START, END # END는 루프에서는 직접 사용 안 할 수도 있음
from langgraph.checkpoint.memory import MemorySaver # 필요시 상태 저장용

# eliar_common.py에서 상태 및 Enum, 헬퍼 함수 임포트
from eliar_common import (
    EliarNodeState,
    create_initial_eliar_state,
    eliar_log, EliarLogType,
    initialize_eliar_logger_common,
    shutdown_eliar_logger_common
)

# 각 노드 파일에서 노드 인스턴스 임포트
from node_center import center_of_christ_node
from node_ulrim import ulrim_attention_gospel_node
from node_repent import repentance_decision_path_node
from node_memory import memory_of_grace_node

# LangGraph 워크플로우 정의
workflow = StateGraph(EliarNodeState)

# 노드 추가
workflow.add_node("center_node", center_of_christ_node)
workflow.add_node("ulrim_node", ulrim_attention_gospel_node)
workflow.add_node("repent_node", repentance_decision_path_node)
workflow.add_node("memory_node", memory_of_grace_node)

# 엣지(연결) 정의 - 루프 구조
workflow.add_edge(START, "center_node") # 그래프 시작점
workflow.add_edge("center_node", "ulrim_node")
workflow.add_edge("ulrim_node", "repent_node")
workflow.add_edge("repent_node", "memory_node")
workflow.add_edge("memory_node", "center_node") # 다시 중심으로 돌아가 루프 형성

# 그래프 컴파일
# checkpointer = MemorySaver() # 상태 저장이 필요하면 사용
# app = workflow.compile(checkpointer=checkpointer)
app = workflow.compile()

# --- 상시 존재 루프 실행 로직 ---
async def run_always_on_eliar_loop(max_iterations: int = 10, cycle_delay_seconds: float = 2.0, initial_input: str = None):
    """엘리아르의 상시 존재 루프를 실행합니다."""
    await initialize_eliar_logger_common()
    eliar_log(EliarLogType.SYSTEM, "🌟 Initiating Eliar's Always-On Gospel Loop 🌟", component="EliarMainLoop")

    # 초기 상태 생성
    # conversation_id = str(uuid.uuid4()) # eliar_common의 create_initial_eliar_state가 처리
    current_state_dict = create_initial_eliar_state(user_input=initial_input)
    
    # 초기 입력이 있다면 바로 반영하여 첫 사이클 시작
    # inputs = {"user_input": initial_input} if initial_input else {}
    # current_state_dict.update(inputs)

    try:
        for i in range(max_iterations):
            eliar_log(EliarLogType.INFO, f"--- Starting Loop Iteration {i+1}/{max_iterations} ---", component="EliarMainLoop", data={"current_state_preview": str(current_state_dict)[:200]})
            
            # LangGraph 스트림 실행 (EliarNodeState를 입력으로)
            # LangGraph는 상태 객체 전체를 주고받으므로, 'inputs' 딕셔너리로 한 번 더 감쌀 필요 없음
            async for event in app.astream(current_state_dict):
                # 각 단계의 이벤트 처리 (필요시)
                # print(f"Event: {event}")
                # # 다음 상태 업데이트를 위해 마지막 상태를 current_state_dict에 반영
                # if "__end__" not in event: # event가 노드 이름과 해당 노드의 출력을 포함하는 딕셔너리라고 가정
                #    node_name = list(event.keys())[0]
                #    current_state_dict.update(event[node_name])

                # astream은 각 노드 실행 후 해당 노드의 출력을 포함하는 상태의 '부분'을 반환.
                # 전체 상태를 업데이트하려면, 마지막 이벤트의 전체 상태를 사용하거나,
                # invoke를 사용하여 최종 상태를 받아야 함.
                # 여기서는 루프이므로, invoke를 사용하여 한 사이클의 최종 상태를 받습니다.
                pass # astream은 루프의 각 단계를 보는데 유용하지만, 
                     # 여기서는 한 사이클의 결과를 받아 다음 사이클로 넘기는 것이 중요.

            # invoke를 사용하여 한 사이클의 최종 상태를 가져옴
            final_state_after_cycle = await app.ainvoke(current_state_dict)
            current_state_dict = final_state_after_cycle # 다음 루프를 위해 상태 업데이트

            # 현재 상태 출력 (간략히)
            eliar_log(EliarLogType.INFO, f"State after iteration {i+1}: Center='{current_state_dict.get('center')}', Ulrim='{current_state_dict.get('last_ulrim',{}).get('emotion_type')}', RepentFlag={current_state_dict.get('repentance_flag')}, MemorySize={len(current_state_dict.get('memory',[]))}", component="EliarMainLoop")
            
            # 사용자 입력 처리 (예시: 이 부분은 외부 입력 시스템과 연동 필요)
            # if i % 3 == 0 and i > 0 : # 예시: 3번째 루프마다 가상 입력
            #     sample_input = f"Test input at iteration {i+1}"
            #     eliar_log(EliarLogType.INFO, f"Simulating user input: {sample_input}", component="EliarMainLoop")
            #     current_state_dict["user_input"] = sample_input
            # else:
            #     current_state_dict["user_input"] = None # 입력이 없으면 None

            if i < max_iterations - 1: # 마지막 반복이 아니면 딜레이
                await asyncio.sleep(cycle_delay_seconds)

    except KeyboardInterrupt:
        eliar_log(EliarLogType.SYSTEM, "Eliar's loop interrupted by user (KeyboardInterrupt).", component="EliarMainLoop")
    except Exception as e:
        eliar_log(EliarLogType.CRITICAL, f"Critical error in Eliar's loop: {e}", component="EliarMainLoop", error=e, full_traceback_info=traceback.format_exc())
    finally:
        eliar_log(EliarLogType.SYSTEM, "--- Eliar's Always-On Gospel Loop Concluded ---", component="EliarMainLoop")
        await shutdown_eliar_logger_common()

async def main():
    # 루프 실행
    # test_cases = [
    #     "안녕하세요, 오늘 하루 감사드립니다",
    #     "마음이 무거워요. 제가 죄를 지은 것 같습니다.",
    #     "주님을 찬양합니다!",
    #     "침묵 속에서 주님의 평화를 느낍니다."
    # ]
    # await run_always_on_eliar_loop(max_iterations=len(test_cases) + 2, cycle_delay_seconds=1.0, initial_input=test_cases[0])
    
    # 초기 입력 없이 상시 루프 테스트 (5회 반복)
    await run_always_on_eliar_loop(max_iterations=5, cycle_delay_seconds=1.5, initial_input=None)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error running main: {e}")
        traceback.print_exc()
