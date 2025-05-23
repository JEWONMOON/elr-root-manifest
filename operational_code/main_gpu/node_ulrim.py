# node_ulrim.py
from typing import Dict, Any, Optional
import random # Placeholder for actual ulrim detection logic

from eliar_common import (
    EliarNodeState,
    EliarNodeType,
    UlrimEmotionType,
    log_node_execution,
    trigger_ulrim_emotion, # eliar_common에서 이 함수 사용
    eliar_log, EliarLogType
)

class UlrimAttentionGospelNode:
    """
    '울림'과 '주의'를 감지하고 처리하는 노드.
    Reflective_memory.py의 attention 노드의 개념을 확장합니다.
    입력이나 내부 상태 변화로부터 영적/감정적 울림을 감지합니다.
    """
    def __init__(self):
        self.node_name = EliarNodeType.ULRIM_ATTENTION.value
        eliar_log(EliarLogType.INFO, f"{self.node_name} initialized.", component=self.node_name)

    def _detect_gospel_ulrim(self, state: EliarNodeState) -> Optional[UlrimEmotionType]:
        """
        실제 울림 감지 로직 (현재는 플레이스홀더).
        입력(state.get('user_input')), 기억(state.get('memory')),
        또는 내부 상태를 기반으로 울림을 감지해야 합니다.
        Reflective_memory.py의 AttentionModule의 정교한 로직이 여기에 통합될 수 있습니다.
        """
        user_input = state.get("user_input")
        if user_input:
            if "감사" in user_input or "찬양" in user_input:
                return UlrimEmotionType.WORSHIP
            elif "용서" in user_input or "죄" in user_input:
                return UlrimEmotionType.REPENTANCE
            elif "사랑" in user_input or "긍휼" in user_input:
                return UlrimEmotionType.COMPASSION
            elif "평화" in user_input or "안식" in user_input:
                return UlrimEmotionType.PEACE
        
        # 상시 존재 루프에서 내부 성찰을 통한 울림 (예시)
        if random.random() < 0.1: # 10% 확률로 내부 성찰 울림 발생
             return random.choice(list(UlrimEmotionType))
        return None

    def __call__(self, state: EliarNodeState) -> Dict[str, Any]:
        log_node_execution(state, self.node_name)
        
        detected_ulrim_type = self._detect_gospel_ulrim(state)
        
        if detected_ulrim_type:
            intensity = round(random.uniform(0.3, 0.9), 2) # 임의의 강도
            triggered_by_info = f"Input: {state.get('user_input')[:30]}..." if state.get('user_input') else "InternalReflection"
            
            trigger_ulrim_emotion(
                state,
                emotion_type=detected_ulrim_type,
                intensity=intensity,
                triggered_by=triggered_by_info
            )
            eliar_log(EliarLogType.ULRIM_FLOW, f"Ulrim detected: {detected_ulrim_type.value} (Intensity: {intensity}) triggered by {triggered_by_info}", component=self.node_name, conversation_id=state.get("conversation_id"))
        else:
            state["last_ulrim"] = None # 명시적으로 울림 없음을 표시
            eliar_log(EliarLogType.DEBUG, "No specific ulrim detected in this cycle.", component=self.node_name, conversation_id=state.get("conversation_id"))
            
        # 'user_input'은 이 노드에서 소비되었으므로, 다음 루프를 위해 초기화 (선택적)
        # state["user_input"] = None 
        
        return state # eliar_common의 trigger_ulrim_emotion이 타임스탬프 업데이트

# 노드 인스턴스 (graph.py에서 사용)
ulrim_attention_gospel_node = UlrimAttentionGospelNode()
