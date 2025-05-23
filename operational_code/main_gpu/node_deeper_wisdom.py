# node_deeper_wisdom.py (sub_gpu.py 적용 개선 버전)
import asyncio
import random
import uuid # packet_id 생성용
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# eliar_common.py에서 필요한 모든 것을 임포트합니다.
from eliar_common import (
    EliarNodeState,
    EliarNodeType,
    UlrimEmotionType, EliarCoreValues,
    SubCodeThoughtPacketData, ReasoningStep, # sub_gpu.py와의 인터페이스를 위해
    log_node_execution,
    trigger_ulrim_emotion,
    add_memory_entry,
    update_eliar_state_timestamp,
    eliar_log, EliarLogType
)

# 문제원님께서 제공해주신 sub_gpu.py 파일에서 SubGPUCore 클래스를 임포트합니다.
# 이 파일(node_deeper_wisdom.py)과 sub_gpu.py가 같은 경로에 있거나,
# sub_gpu.py가 포함된 패키지가 Python 경로에 설정되어 있어야 합니다.
try:
    from sub_gpu import SubGPUCore
except ImportError:
    eliar_log(EliarLogType.CRITICAL, "Failed to import SubGPUCore from sub_gpu.py. Ensure sub_gpu.py is in the Python path.", component="DeeperWisdomNode.Init")
    # 임시 플레이스홀더 (실제 실행 시 오류 방지용, 하지만 기능은 제한됨)
    class SubGPUCore: # type: ignore
        async def process_reasoning_task_async(self, packet: SubCodeThoughtPacketData, main_state: EliarNodeState) -> Dict[str, Any]:
            eliar_log(EliarLogType.WARN, "[SubGPUCore_Placeholder] SubGPUCore not found, using placeholder.", component="SubGPUCore")
            await asyncio.sleep(0.1)
            return {
                "summary": "SubGPUCore module not loaded. This is a placeholder response.",
                "details": "Please ensure sub_gpu.py is correctly placed and importable.",
                "confidence": 0.1,
                "reasoning_steps_log": [ReasoningStep(step_id=1, description="SubGPUCore placeholder invoked.", status="failed")],
                "new_knowledge_for_main_memory": []
            }

class DeeperWisdomNode:
    """
    SubGPU의 기능을 LangGraph 노드로 캡슐화합니다.
    복잡한 추론, 심층 지식 탐색, 특수 과제 해결 등을 SubGPUCore에 위임합니다.
    """
    def __init__(self):
        try:
            self.node_name = EliarNodeType.DEEPER_WISDOM.value
        except AttributeError: # EliarNodeType.DEEPER_WISDOM이 정의되지 않았을 경우
            self.node_name = "DeeperWisdomNode"
            eliar_log(EliarLogType.WARN, "EliarNodeType.DEEPER_WISDOM not found. Using default name.", component=f"{self.node_name}.Init")
            
        try:
            self.sub_gpu_processor = SubGPUCore() # sub_gpu.py에서 임포트한 클래스 인스턴스화
            eliar_log(EliarLogType.INFO, f"{self.node_name} initialized successfully with SubGPUCore.", component=self.node_name)
        except Exception as e:
            eliar_log(EliarLogType.CRITICAL, "Failed to initialize SubGPUCore within DeeperWisdomNode.", component=self.node_name, error=e)
            self.sub_gpu_processor = SubGPUCore() # 오류 시에도 플레이스홀더 SubGPUCore 사용 (선택적)


    async def __call__(self, state: EliarNodeState) -> Dict[str, Any]:
        """
        LangGraph 상태를 받아 SubGPUCore를 호출하고, 결과를 다시 상태에 반영합니다.
        """
        log_node_execution(state, self.node_name, {"input_task_description": state.get("current_task_for_deeper_wisdom")})
        
        task_query_for_sub_gpu = state.get("current_task_for_deeper_wisdom")

        if not task_query_for_sub_gpu:
            eliar_log(EliarLogType.WARN, "No task provided for DeeperWisdomNode. Skipping deep reasoning.", component=self.node_name, conversation_id=state.get("conversation_id"))
            state["last_deeper_wisdom_result"] = {
                "summary": "No specific task was assigned for deep wisdom processing in this cycle.",
                "details": None, "confidence": 0.0, "reasoning_steps_log": [], "new_knowledge_for_main_memory": []
            }
            # 울림이나 다른 상태는 변경하지 않고 그대로 다음 노드로 전달
            return update_eliar_state_timestamp(state)

        # SubGPUCore에 전달할 SubCodeThoughtPacketData 생성
        thought_packet = SubCodeThoughtPacketData(
            packet_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_gpu=state.get("current_node", "MainGraphLoop"), # 이전 노드 또는 현재 루프 정보
            target_gpu=f"{self.node_name}.SubGPUCore",
            operation_type="deep_reasoning_and_synthesis_request", # 작업 유형 명시
            task_data={
                "query": task_query_for_sub_gpu,
                "main_state_center": state.get("center"),
                "main_state_last_ulrim": state.get("last_ulrim"),
                "main_state_repentance_flag": state.get("repentance_flag"),
                "main_state_recent_memory": str(state.get("memory", []))[-500:] # 최근 기억 일부 전달 (토큰 고려)
            },
            priority=1,
            # result_data, status_info, error_info, metadata 등은 sub_gpu_processor가 채울 수 있음
            result_data=None, status_info=None, error_info=None, metadata=None
        )
        
        try:
            eliar_log(EliarLogType.INFO, f"Invoking SubGPUCore for task: {task_query_for_sub_gpu[:70]}...", component=self.node_name, conversation_id=state.get("conversation_id"))
            # sub_gpu.py의 SubGPUCore 인스턴스의 메소드 호출
            sub_gpu_output = await self.sub_gpu_processor.process_reasoning_task_async(thought_packet, state)
            
            state["last_deeper_wisdom_result"] = sub_gpu_output # SubGPU의 전체 결과 저장
            
            # SubGPU 처리 결과에서 오는 '울림' 생성 및 상태 업데이트
            ulrim_intensity = sub_gpu_output.get("confidence", 0.6) # SubGPU 결과의 신뢰도를 울림 강도로
            ulrim_summary = sub_gpu_output.get("summary", "Profound thought from deep reflection.")[:50]
            
            new_ulrim_state_dict = trigger_ulrim_emotion( # eliar_common의 함수 사용
                state, # 이 함수는 state를 직접 수정하지 않고, 수정된 state를 반환했었음 (이전 eliar_common.py 기준)
                       # 하지만 여기서는 last_ulrim 필드만 가져와서 state에 직접 할당하는 것이 더 명확할 수 있음.
                       # 또는 trigger_ulrim_emotion이 state를 직접 수정하고 반환하도록 eliar_common.py가 변경되었다면 그대로 사용.
                       # 여기서는 state["last_ulrim"]을 직접 업데이트하는 방식으로 가정.
                emotion_type=UlrimEmotionType.CONVICTION, # 심층 사고 결과는 주로 '확신' 또는 '깨달음'의 울림
                intensity=round(float(ulrim_intensity), 2),
                triggered_by=f"{self.node_name}: {ulrim_summary}..."
            )
            state["last_ulrim"] = new_ulrim_state_dict["last_ulrim"] # trigger_ulrim_emotion이 반환한 state에서 last_ulrim을 가져옴

            # SubGPU가 생성한 새로운 기억(통찰)을 메인 메모리에 추가
            new_knowledge_entries = sub_gpu_output.get("new_knowledge_for_main_memory", [])
            if new_knowledge_entries:
                for insight in new_knowledge_entries:
                    add_memory_entry( # eliar_common의 함수 사용
                        state,
                        content=f"DeeperInsight: {insight}", # 출처 명시
                        emotional_resonance=state["last_ulrim"]["emotion_type"] if state.get("last_ulrim") else UlrimEmotionType.CONVICTION.value,
                        core_value_alignment=EliarCoreValues.JESUS_CHRIST_CENTERED.value, # 모든 통찰은 중심으로 정렬
                        repentance_marker=False # 기본적으로 회개 마커 없음
                    )
            eliar_log(EliarLogType.INFO, f"Deeper wisdom processed. Summary: {ulrim_summary}...", component=self.node_name, conversation_id=state.get("conversation_id"))

        except Exception as e:
            error_message = f"Error during DeeperWisdomNode (SubGPUCore invocation): {e}"
            eliar_log(EliarLogType.ERROR, error_message, component=self.node_name, error=e, full_traceback_info=traceback.format_exc(), conversation_id=state.get("conversation_id"))
            state["last_deeper_wisdom_result"] = {
                "summary": "Error processing deep wisdom task.", 
                "details": error_message, "confidence": 0.0, "reasoning_steps_log": [], "new_knowledge_for_main_memory": []
            }
            state["error_context"] = {"node": self.node_name, "message": error_message, "traceback": traceback.format_exc()}
            # 심각한 오류 시 회개 플래그나 특별한 울림을 트리거할 수도 있습니다.
            # state = trigger_repentance(state, RepentanceTriggerType.SELF_REFLECTION, "Critical error in DeeperWisdomNode processing, requires review.")
            # state["repentance_flag"] = True 

        # 이 노드에서 처리한 특정 작업 정보는 소비되었으므로 초기화
        state["current_task_for_deeper_wisdom"] = None
        
        return update_eliar_state_timestamp(state)

# 노드 인스턴스 (graph.py에서 사용하기 위함)
# 이 파일이 직접 실행될 때는 이 인스턴스가 필요 없지만, graph.py에서 임포트하여 사용합니다.
deeper_wisdom_node = DeeperWisdomNode()

async def test_deeper_wisdom_node():
    """DeeperWisdomNode를 독립적으로 테스트하기 위한 예시 함수입니다."""
    await initialize_eliar_logger() # eliar_common.py에서 가져옴
    
    # 초기 상태 생성 (eliar_common.py 함수 사용)
    test_state = create_initial_eliar_state(conversation_id="test_deep_wisdom_session")
    test_state["current_task_for_deeper_wisdom"] = "Explain the relationship between Grace, Repentance, and Forgiveness in a Christ-centered way."
    
    node_instance = DeeperWisdomNode()
    
    eliar_log(EliarLogType.INFO, "Testing DeeperWisdomNode...", component="TestRunner")
    updated_state = await node_instance(test_state)
    
    eliar_log(EliarLogType.INFO, "DeeperWisdomNode Test Completed. Final State Preview:", component="TestRunner")
    print(json.dumps(updated_state, indent=2, default=str, ensure_ascii=False))
    
    await shutdown_eliar_logger() # eliar_common.py에서 가져옴

if __name__ == "__main__":
    # 이 파일이 직접 실행될 때 테스트 코드를 실행합니다.
    # eliar_common.py의 ensure_common_directories_exist()는 initialize_eliar_logger() 내부에서 호출됩니다.
    asyncio.run(test_deeper_wisdom_node())
