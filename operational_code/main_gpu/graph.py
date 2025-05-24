# graph.py (Proposal 3: MetaStructureEditorNode 통합 개념 반영)
import asyncio
import random
import traceback
from datetime import datetime, timezone # conversation_id 생성용

# eliar_common.py에서 상태 및 Enum, 헬퍼 함수 임포트
from eliar_common import (
    EliarNodeState,
    create_initial_eliar_state,
    eliar_log, EliarLogType,
    initialize_eliar_logger_common,
    shutdown_eliar_logger_common,
    UlrimEmotionType,
    update_eliar_state_timestamp # MetaStructureEditorNode에서 사용 가정
)

# 각 노드 파일에서 노드 인스턴스 임포트
from node_center import center_of_christ_node
from node_ulrim import ulrim_attention_gospel_node
from node_repent import repentance_decision_path_node
from node_memory import memory_of_grace_node
from node_deeper_wisdom import deeper_wisdom_node

# 새로운 MetaStructureEditorNode 임포트 (존재한다고 가정)
# from meta_structure_editor import meta_structure_editor_node # 실제로는 이 노드에 workflow 참조 전달 필요

# LangGraph 임포트
from langgraph.graph import StateGraph, START, END

# LangGraph 워크플로우 정의
workflow = StateGraph(EliarNodeState)

# --- MetaStructureEditorNode 인스턴스화 (주의: 실제로는 workflow 참조 필요) ---
# 이 부분은 실제 구현 시 workflow 객체가 생성된 후, 해당 참조를 MetaStructureEditorNode에
# 주입하는 방식이 필요합니다. 여기서는 개념적으로만 명시합니다.
# meta_editor_node_instance = MetaStructureEditorNode(langgraph_workflow_reference=workflow)
# 아래에서는 함수 형태로 호출한다고 가정하고, 실제 인스턴스는 다른 곳에서 주입받거나 접근한다고 가정합니다.
# (또는, MetaStructureEditorNode를 호출 가능한 객체가 아닌, 상태를 받아 처리하는 함수로 정의해야 함)

# 임시: MetaStructureEditorNode가 함수라고 가정 (실제로는 클래스 인스턴스 콜러블)
# 실제로는 이 노드가 graph.py 외부에서 workflow 객체를 알아야 합니다.
# 여기서는 개념적 통합을 위해 placeholder 함수로 만듭니다.
def placeholder_meta_structure_editor_node_function(state: EliarNodeState) -> EliarNodeState:
    eliar_log(EliarLogType.WARN, "Placeholder MetaStructureEditorNode called. Real implementation needed.", component="MetaStructureEditorPlaceholder")
    # 이 함수는 상태를 분석하고, workflow를 '어떻게든' 수정하려고 시도해야 합니다.
    # 현재 LangGraph 구조상 노드가 동적으로 그래프를 수정하는 것은 매우 복잡합니다.
    # 여기서는 단순히 상태에 로그만 남기고 통과시킵니다.
    state["last_meta_edit_attempt_timestamp"] = datetime.now(timezone.utc).isoformat()
    return update_eliar_state_timestamp(state)
# ---------------------------------------------------------------------------

# 노드 추가
workflow.add_node("center_node", center_of_christ_node)
workflow.add_node("ulrim_node", ulrim_attention_gospel_node)
workflow.add_node("repent_node", repentance_decision_path_node)
workflow.add_node("memory_node", memory_of_grace_node)
workflow.add_node("deeper_wisdom_node", deeper_wisdom_node)
workflow.add_node("meta_structure_editor_node", placeholder_meta_structure_editor_node_function) # 새로운 노드 추가

# 엣지(연결) 정의
workflow.add_edge(START, "center_node")
workflow.add_edge("center_node", "ulrim_node")

def should_seek_deeper_wisdom(state: EliarNodeState) -> str:
    last_ulrim = state.get("last_ulrim")
    user_input = state.get("user_input")
    conversation_id = state.get("conversation_id")

    if user_input and ("탐구" in user_input or "이해하고 싶어" in user_input or "왜" in user_input):
        eliar_log(EliarLogType.INFO, "Complex query detected. Routing to DeeperWisdomNode.", component="Router", conversation_id=conversation_id)
        state["current_task_for_deeper_wisdom"] = f"Deep inquiry requested: {user_input}"
        return "deeper_wisdom_node"
    
    if last_ulrim and \
       last_ulrim.get("emotion_type") == UlrimEmotionType.CONVICTION.value and \
       last_ulrim.get("intensity", 0) > 0.7:
        if random.random() < 0.2:
            eliar_log(EliarLogType.INFO, "Strong conviction ulrim. Routing to DeeperWisdomNode for deeper reflection.", component="Router", conversation_id=conversation_id)
            state["current_task_for_deeper_wisdom"] = f"Deeper reflection on conviction: {last_ulrim.get('triggered_by')}"
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

workflow.add_edge("repent_node", "memory_node")
workflow.add_edge("deeper_wisdom_node", "memory_node")

# MemoryNode 이후, MetaStructureEditorNode를 호출할지, 아니면 바로 CenterNode로 갈지 결정
META_EDIT_CYCLE_THRESHOLD = 10 # 예: 10 루프마다 한 번씩 메타 편집 시도
def should_edit_structure(state: EliarNodeState) -> str:
    cycle_count = state.get("total_cycles_completed", 0) # 이 상태는 루프에서 관리되어야 함
    if cycle_count > 0 and cycle_count % META_EDIT_CYCLE_THRESHOLD == 0:
        eliar_log(EliarLogType.INFO, f"Cycle count {cycle_count} reached. Routing to MetaStructureEditorNode.", component="Router", conversation_id=state.get("conversation_id"))
        return "meta_structure_editor_node"
    return "center_node" # 일반적인 다음 루프 시작

workflow.add_conditional_edges(
    "memory_node",
    should_edit_structure,
    {
        "meta_structure_editor_node": "meta_structure_editor_node",
        "center_node": "center_node"
    }
)

# MetaStructureEditorNode 이후에는 항상 CenterNode로 가서 새로운 루프 시작 (구조 변경 후 첫 루프)
workflow.add_edge("meta_structure_editor_node", "center_node")


# 그래프 컴파일
app = workflow.compile()

# --- 상시 존재 루프 실행 로직 (run_always_on_eliar_loop) ---
async def run_always_on_eliar_loop(max_iterations: int = 100, cycle_delay_seconds: float = 2.0, initial_inputs: List[Optional[str]] = None):
    await initialize_eliar_logger_common()
    eliar_log(EliarLogType.SYSTEM, "🌟 Initiating Eliar's Always-On Gospel Loop (Meta-Editing Capable) 🌟", component="EliarMainLoop")

    inputs_iterator = iter(initial_inputs) if initial_inputs else None
    current_input_for_cycle: Optional[str] = None
    loop_conversation_id_base = f"loop_conv_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    
    current_state_dict = None

    try:
        if inputs_iterator:
            try:
                current_input_for_cycle = next(inputs_iterator)
            except StopIteration:
                current_input_for_cycle = None
        
        current_state_dict = create_initial_eliar_state(user_input=current_input_for_cycle, conversation_id=f"{loop_conversation_id_base}_0")
        current_state_dict["total_cycles_completed"] = 0


        for i in range(max_iterations):
            current_state_dict["total_cycles_completed"] = i + 1
            current_state_dict["conversation_id"] = f"{loop_conversation_id_base}_{i+1}"
            
            eliar_log(EliarLogType.INFO, f"--- Starting Loop Iteration {current_state_dict['total_cycles_completed']}/{max_iterations} ---", 
                      component="EliarMainLoop", 
                      data={"current_input_for_cycle": current_input_for_cycle}, 
                      conversation_id=current_state_dict["conversation_id"])
            
            current_state_dict["user_input"] = current_input_for_cycle
            
            # 다음 라우팅 결정 전에 current_task_for_deeper_wisdom 초기화
            current_state_dict.pop("current_task_for_deeper_wisdom", None)


            final_state_after_cycle = await app.ainvoke(current_state_dict)
            current_state_dict = final_state_after_cycle

            if inputs_iterator:
                try:
                    current_input_for_cycle = next(inputs_iterator)
                except StopIteration:
                    current_input_for_cycle = None 
            else: 
                current_input_for_cycle = None

            log_data = {
                "Center": current_state_dict.get('center'),
                "Ulrim_Type": current_state_dict.get('last_ulrim',{}).get('emotion_type'),
                "RepentFlag": current_state_dict.get('repentance_flag'),
                "DeeperWisdom_Summary": current_state_dict.get('sub_reasoning_result', {}).get('summary', 'N/A')[:50] + "...",
                "MemorySize": len(current_state_dict.get('memory',[])),
                "MetaEditAttempt": current_state_dict.get("last_meta_edit_attempt_timestamp")
            }
            eliar_log(EliarLogType.INFO, f"State after iteration {i+1}: {log_data}", component="EliarMainLoop", conversation_id=current_state_dict["conversation_id"])
            current_state_dict.pop("last_meta_edit_attempt_timestamp", None) # 로그 후 초기화
            
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
        "우주의 신비에 대해 더 깊이 탐구하고 싶어요.",
        None, None, None, None, None, None, None, None, None, # 주기적 메타 편집 테스트를 위한 내부 루프
        "오늘 하루도 감사합니다.",
        None, None, None, None, None, None, None, None, None, 
        "제 안에 아직 해결되지 않은 죄의 문제가 있어서 마음이 무겁습니다. 회개합니다.",
    ]
    await run_always_on_eliar_loop(max_iterations=len(sample_inputs) + 20, cycle_delay_seconds=0.5, initial_inputs=sample_inputs)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error running main: {e}")
        traceback.print_exc()
