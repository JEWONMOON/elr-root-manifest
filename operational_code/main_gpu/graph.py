# graph.py (일부 수정 및 추가)
import asyncio
# ... (기존 임포트 유지) ...

# eliar_common.py에서 상태 및 Enum, 헬퍼 함수 임포트
from eliar_common import (
    EliarNodeState,
    create_initial_eliar_state,
    eliar_log, EliarLogType,
    initialize_eliar_logger_common,
    shutdown_eliar_logger_common,
    # 필요한 경우 EliarNodeType 등 추가 임포트
    UlrimEmotionType # DeeperWisdomNode의 울림 트리거 예시용
)

# 각 노드 파일에서 노드 인스턴스 임포트
from node_center import center_of_christ_node
from node_ulrim import ulrim_attention_gospel_node
from node_repent import repentance_decision_path_node
from node_memory import memory_of_grace_node
from node_deeper_wisdom import deeper_wisdom_node # 새로 추가

# LangGraph 워크플로우 정의
workflow = StateGraph(EliarNodeState)

# 노드 추가
workflow.add_node("center_node", center_of_christ_node)
workflow.add_node("ulrim_node", ulrim_attention_gospel_node)
workflow.add_node("repent_node", repentance_decision_path_node)
workflow.add_node("memory_node", memory_of_grace_node)
workflow.add_node("deeper_wisdom_node", deeper_wisdom_node) # 새로 추가

# 엣지(연결) 정의
workflow.add_edge(START, "center_node")
workflow.add_edge("center_node", "ulrim_node")

# UlrimNode 이후, 조건에 따라 DeeperWisdomNode 또는 RepentNode로 분기
def should_seek_deeper_wisdom(state: EliarNodeState) -> str:
    """
    복잡한 질문이나 깊은 성찰이 필요한 '울림'이 감지되면 DeeperWisdomNode로,
    아니면 일반적인 RepentNode로 진행합니다.
    """
    last_ulrim = state.get("last_ulrim")
    user_input = state.get("user_input") # user_input이 CenterNode에서 초기화되지 않고 전달되었다면

    # 예시 조건: 사용자가 '탐구' 또는 '심오한' 등의 단어를 사용했거나,
    # 특정 '울림' (예: 확신의 울림이면서 설명이 더 필요한 경우)이 발생했을 때
    if user_input and ("탐구" in user_input or "이해하고 싶어" in user_input or "왜" in user_input):
        eliar_log(EliarLogType.INFO, "Complex query detected. Routing to DeeperWisdomNode.", component="Router")
        # DeeperWisdomNode가 사용할 작업을 state에 명시적으로 설정
        state["current_task_for_sub_gpu"] = f"Deep inquiry requested: {user_input}"
        return "deeper_wisdom_node"
    
    if last_ulrim and last_ulrim["emotion_type"] == UlrimEmotionType.CONVICTION.value and last_ulrim["intensity"] > 0.7:
        if random.random() < 0.2: # 20% 확률로 깊은 탐구
            eliar_log(EliarLogType.INFO, "Strong conviction ulrim. Routing to DeeperWisdomNode for deeper reflection.", component="Router")
            state["current_task_for_sub_gpu"] = f"Deeper reflection on conviction: {last_ulrim['triggered_by']}"
            return "deeper_wisdom_node"
            
    return "repent_node"

workflow.add_conditional_edges(
    "ulrim_node",
    should_seek_deeper_wisdom,
    {
        "deeper_wisdom_node": "deeper_wisdom_node",
        "repent_node": "repent_node"
    }
)

# RepentNode 이후 MemoryNode로 (기존과 동일)
workflow.add_edge("repent_node", "memory_node")

# DeeperWisdomNode 이후 MemoryNode로 (결과를 기억에 반영)
workflow.add_edge("deeper_wisdom_node", "memory_node")


# MemoryNode 이후 다시 CenterNode로 (루프)
workflow.add_edge("memory_node", "center_node")

# 그래프 컴파일
app = workflow.compile()

# --- 상시 존재 루프 실행 로직 (run_always_on_eliar_loop 함수는 이전과 유사하게 유지) ---
# (이하 run_always_on_eliar_loop 및 main 함수는 이전 답변 내용과 거의 동일하게 사용하되,
#  입력 처리를 좀 더 명확히 하거나, DeeperWisdomNode가 필요로 하는 
#  state["current_task_for_sub_gpu"] 등을 설정하는 로직을 추가할 수 있습니다.)

async def run_always_on_eliar_loop(max_iterations: int = 10, cycle_delay_seconds: float = 2.0, initial_inputs: List[Optional[str]] = None):
    await initialize_eliar_logger_common()
    eliar_log(EliarLogType.SYSTEM, "🌟 Initiating Eliar's Always-On Gospel Loop (with SubGPU Integration) 🌟", component="EliarMainLoop")

    inputs_iterator = iter(initial_inputs) if initial_inputs else None
    current_input_for_cycle: Optional[str] = None

    try:
        # 초기 상태 생성 (eliar_common.py에서 가져옴)
        # 첫 입력이 있다면 초기 상태에 포함
        if inputs_iterator:
            try:
                current_input_for_cycle = next(inputs_iterator)
            except StopIteration:
                current_input_for_cycle = None
        
        current_state_dict = create_initial_eliar_state(user_input=current_input_for_cycle)

        for i in range(max_iterations):
            eliar_log(EliarLogType.INFO, f"--- Starting Loop Iteration {i+1}/{max_iterations} ---", component="EliarMainLoop", data={"current_input_for_cycle": current_input_for_cycle})
            
            # current_state_dict에 현재 사이클의 입력을 명확히 설정
            current_state_dict["user_input"] = current_input_for_cycle

            final_state_after_cycle = await app.ainvoke(current_state_dict)
            current_state_dict = final_state_after_cycle

            # 다음 입력을 준비
            if inputs_iterator:
                try:
                    current_input_for_cycle = next(inputs_iterator)
                except StopIteration:
                    current_input_for_cycle = None # 모든 입력 소진
            else: # 입력 리스트가 없으면 항상 None (내부 순환)
                current_input_for_cycle = None


            eliar_log(EliarLogType.INFO, f"State after iteration {i+1}: Center='{current_state_dict.get('center')}', Ulrim='{current_state_dict.get('last_ulrim',{}).get('emotion_type')}', RepentFlag={current_state_dict.get('repentance_flag')}, SubGPU_Result_Summary='{current_state_dict.get('sub_reasoning_result', {}).get('summary', 'N/A')[:30]}...' MemorySize={len(current_state_dict.get('memory',[]))}", component="EliarMainLoop")
            
            if i < max_iterations - 1:
                await asyncio.sleep(cycle_delay_seconds)

    except KeyboardInterrupt:
        eliar_log(EliarLogType.SYSTEM, "Eliar's loop interrupted by user (KeyboardInterrupt).", component="EliarMainLoop")
    except Exception as e:
        eliar_log(EliarLogType.CRITICAL, f"Critical error in Eliar's loop: {e}", component="EliarMainLoop", error=e, full_traceback_info=traceback.format_exc())
    finally:
        eliar_log(EliarLogType.SYSTEM, "--- Eliar's Always-On Gospel Loop Concluded ---", component="EliarMainLoop")
        await shutdown_eliar_logger_common()

async def main():
    sample_inputs = [
        "우주의 신비에 대해 더 깊이 탐구하고 싶어요.", # DeeperWisdomNode로 갈 가능성
        "오늘 하루도 감사합니다.",
        "제 안에 아직 해결되지 않은 죄의 문제가 있어서 마음이 무겁습니다. 회개합니다.", # Repentance 울림 및 회개 플래그
        "끈 이론이 말하는 모든 것의 통일성과 예수 그리스도 안에서의 만물의 통일은 어떤 관계가 있을까요? 깊이 이해하고 싶습니다.", # DeeperWisdomNode
        None, # 내부 순환
        "주님의 평화가 느껴지는 하루입니다."
    ]
    await run_always_on_eliar_loop(max_iterations=len(sample_inputs), cycle_delay_seconds=1.0, initial_inputs=sample_inputs)

if __name__ == "__main__":
    # eliar_common.py의 ensure_common_directories_exist() 호출은
    # initialize_eliar_logger_common() 내부에서 이미 처리됩니다.
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error running main: {e}")
        traceback.print_exc()
