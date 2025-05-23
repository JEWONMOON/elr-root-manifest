# node_deeper_wisdom.py (개선 버전)
import asyncio
import random
import uuid # packet_id 생성용
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from eliar_common import (
    EliarNodeState,
    EliarNodeType, # DEEPER_WISDOM 타입이 추가되었다고 가정
    UlrimEmotionType, EliarCoreValues,
    SubCodeThoughtPacketData, ReasoningStep, # eliar_common에서 가져옴
    log_node_execution,
    trigger_ulrim_emotion, # eliar_common의 함수 사용
    add_memory_entry,      # eliar_common의 함수 사용
    update_eliar_state_timestamp,
    eliar_log, EliarLogType
)

# sub_gpu.py의 핵심 클래스를 임포트 (경로 및 이름은 실제 프로젝트 구조에 맞게 조정 필요)
# from sub_gpu_module.sub_gpu_core import SubGPUCore # 예시 경로
# 이 예제에서는 SubGPUCore가 현재 파일에서 임시 정의되거나, 이미 로드 가능하다고 가정
# 실제로는 from sub_gpu import SubGPUCore 와 같이 사용하게 될 것입니다.
# --- SubGPUCore 임시 플레이스홀더 (실제로는 sub_gpu.py에서 가져와야 함) ---
class SubGPUCore: # 실제 SubGPUCore 클래스로 대체되어야 합니다.
    async def process_reasoning_task_async(self, packet: SubCodeThoughtPacketData, main_state: EliarNodeState) -> Dict[str, Any]:
        eliar_log(EliarLogType.INFO, f"[SubGPUCore_Placeholder] Processing: {packet.get('task_data', {}).get('query', 'No query')}", component="SubGPUCore")
        await asyncio.sleep(random.uniform(0.5, 1.0)) # Simulate work
        return {
            "summary": f"Profound insight about '{packet.get('task_data', {}).get('query', 'N/A')}' derived by SubGPU.",
            "details": "This is a simulated detailed explanation.",
            "confidence": 0.90,
            "reasoning_steps_log": [
                ReasoningStep(step_id=1, description="Task received by placeholder SubGPU.", status="completed")
            ],
            "new_knowledge_for_main_memory": [f"SubGPU Insight: '{packet.get('task_data', {}).get('query', 'N/A')}' leads to deeper understanding of God's truth."]
        }
# --- SubGPUCore 임시 플레이스홀더 종료 ---


class DeeperWisdomNode:
    def __init__(self):
        try:
            # EliarNodeType.DEEPER_WISDOM.value를 사용하려면 eliar_common.py에 정의 필요
            self.node_name = getattr(EliarNodeType, "DEEPER_WISDOM", None).value if hasattr(EliarNodeType, "DEEPER_WISDOM") else "DeeperWisdomNode"
        except AttributeError: # DEEPER_WISDOM Enum 멤버가 없을 경우 대비
            self.node_name = "DeeperWisdomNode_Fallback"
            eliar_log(EliarLogType.WARN, "EliarNodeType.DEEPER_WISDOM not found in eliar_common. Using fallback name.", component="DeeperWisdomNode.Init")
            
        self.sub_gpu_processor = SubGPUCore() # SubGPUCore 인스턴스화
        eliar_log(EliarLogType.INFO, f"{self.node_name} initialized with SubGPUCore.", component=self.node_name)

    async def __call__(self, state: EliarNodeState) -> Dict[str, Any]:
        log_node_execution(state, self.node_name, {"input_task": state.get("current_task_for_deeper_wisdom")})
        
        task_query = state.get("current_task_for_deeper_wisdom")
        if not task_query:
            eliar_log(EliarLogType.WARN, "No task provided for DeeperWisdomNode. Skipping deep reasoning.", component=self.node_name)
            state["last_deeper_wisdom_result"] = {"summary": "No task for deep wisdom.", "details": None, "confidence": 0.0}
            return update_eliar_state_timestamp(state)

        # SubCodeThoughtPacketData 생성
        packet_id = str(uuid.uuid4())
        thought_packet = SubCodeThoughtPacketData(
            packet_id=packet_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_gpu=state.get("current_node", "MainGraphLoop"), # 이전 노드 또는 루프 정보
            target_gpu="SubGPUCore_DeeperWisdom",
            operation_type="complex_reasoning_request",
            task_data={"query": task_query, "current_memory_summary": str(state.get("memory", []))[-200:]}, # 최근 기억 요약 전달
            priority=1,
            result_data=None, # 초기화
            status_info=None, # 초기화
            error_info=None,  # 초기화
            metadata={"main_loop_conversation_id": state.get("conversation_id")}
        )
        
        try:
            sub_gpu_output = await self.sub_gpu_processor.process_reasoning_task_async(thought_packet, state)
            state["last_deeper_wisdom_result"] = sub_gpu_output
            
            # 새로운 통찰에서 오는 울림 생성
            new_ulrim_state = trigger_ulrim_emotion(
                state, # state를 직접 수정하지 않고, 새로운 last_ulrim 값을 반환받아 사용
                emotion_type=UlrimEmotionType.CONVICTION,
                intensity=sub_gpu_output.get("confidence", 0.7), # SubGPU 결과의 신뢰도를 울림 강도로
                triggered_by=f"{self.node_name} Insight: {sub_gpu_output.get('summary', 'Profound thought')[:30]}..."
            )
            state["last_ulrim"] = new_ulrim_state["last_ulrim"]


            # SubGPU가 생성한 새로운 기억(통찰)을 메인 메모리에 추가
            if sub_gpu_output.get("new_knowledge_for_main_memory"):
                for insight in sub_gpu_output["new_knowledge_for_main_memory"]:
                    add_memory_entry(
                        state,
                        content=f"DeeperWisdom: {insight}",
                        emotional_resonance=state["last_ulrim"]["emotion_type"] if state.get("last_ulrim") else UlrimEmotionType.CONVICTION.value,
                        core_value_alignment=EliarCoreValues.JESUS_CHRIST_CENTERED.value,
                        repentance_marker=False # 심층 사고 결과는 기본적으로 회개 마커 없음
                    )
            eliar_log(EliarLogType.INFO, f"Deeper wisdom processed. Summary: {sub_gpu_output.get('summary', 'N/A')[:50]}...", component=self.node_name)

        except Exception as e:
            error_message = f"Error during DeeperWisdomNode execution: {e}"
            eliar_log(EliarLogType.ERROR, error_message, component=self.node_name, error=e, full_traceback_info=traceback.format_exc())
            state["last_deeper_wisdom_result"] = {"summary": "Error in deep wisdom processing.", "details": error_message, "confidence": 0.0}
            state["error_context"] = {"node": self.node_name, "message": error_message, "traceback": traceback.format_exc()}
            # 오류 발생 시 회개 플래그를 세울 수도 있음 (선택적)
            # state = trigger_repentance(state, RepentanceTriggerType.SELF_REFLECTION, "Error in DeeperWisdomNode processing")
            # state["repentance_flag"] = True


        # 이 노드에서 사용된 특정 작업 정보는 소비되었으므로 초기화
        state["current_task_for_deeper_wisdom"] = None
        
        return update_eliar_state_timestamp(state)

# 노드 인스턴스 (graph.py에서 사용)
deeper_wisdom_node = DeeperWisdomNode()
