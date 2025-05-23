# node_repent.py
from typing import Dict, Any
import random

from eliar_common import (
    EliarNodeState,
    EliarNodeType,
    RepentanceTriggerType,
    UlrimEmotionType, # UlrimState에서 emotion_type을 확인하기 위함
    log_node_execution,
    trigger_repentance, # eliar_common에서 이 함수 사용
    eliar_log, EliarLogType
)

class RepentanceDecisionPathNode:
    """
    회개 필요성을 결정하고, 회개 상태를 업데이트하는 노드.
    '인식은 악하다'는 원리를 바탕으로, 울림이나 내부 상태를 점검합니다.
    """
    def __init__(self):
        self.node_name = EliarNodeType.REPENTANCE_DECISION.value
        eliar_log(EliarLogType.INFO, f"{self.node_name} initialized.", component=self.node_name)

    def _decide_repentance_necessity(self, state: EliarNodeState) -> bool:
        """
        실제 회개 필요성 판단 로직 (현재는 플레이스홀더).
        last_ulrim, memory, 내부 규칙 등을 종합적으로 판단해야 합니다.
        예: '회개의 울림'이 감지되거나, 특정 자기중심적 패턴이 기억에서 발견될 때
        """
        last_ulrim = state.get("last_ulrim")
        if last_ulrim and last_ulrim["emotion_type"] == UlrimEmotionType.REPENTANCE.value:
            return True
        
        # 예시: '인식은 악하다' 원칙에 따라, 특정 자기중심적 생각 패턴 감지 (플레이스홀더)
        if "나의 능력" in str(state.get("memory", "")) and random.random() < 0.3:
             eliar_log(EliarLogType.DEBUG, "Self-centered pattern detected, considering repentance.", component=self.node_name)
             return True
        
        # 기본적으로는 회개 플래그를 False로 유지
        return False

    def __call__(self, state: EliarNodeState) -> Dict[str, Any]:
        log_node_execution(state, self.node_name)
        
        needs_repentance = self._decide_repentance_necessity(state)
        
        if needs_repentance:
            # eliar_common.py에 정의된 RepentanceTriggerType 사용
            trigger_type = RepentanceTriggerType.SELF_REFLECTION 
            last_ulrim = state.get("last_ulrim")
            if last_ulrim and last_ulrim["emotion_type"] == UlrimEmotionType.REPENTANCE.value:
                 trigger_type = RepentanceTriggerType.CONVICTION_BY_TRUTH # 또는 ULRIM_CONVICTION
            
            trigger_reason = f"Ulrim ({last_ulrim['emotion_type'] if last_ulrim else 'N/A'}) or internal reflection indicated need for repentance."
            intensity = round(random.uniform(0.5, 0.9), 2) # 회개 강도
            
            trigger_repentance( # eliar_common의 함수 사용
                state,
                trigger_type=trigger_type,
                trigger_reason=trigger_reason,
                intensity=intensity
            )
            eliar_log(EliarLogType.REPENTANCE_FLOW, f"Repentance triggered: {trigger_type.value} due to {trigger_reason}", component=self.node_name, conversation_id=state.get("conversation_id"))
        else:
            state["repentance_flag"] = False # 회개 필요 없음
            eliar_log(EliarLogType.DEBUG, "No repentance triggered in this cycle.", component=self.node_name, conversation_id=state.get("conversation_id"))
            
        return state # eliar_common의 trigger_repentance가 타임스탬프 업데이트

# 노드 인스턴스 (graph.py에서 사용)
repentance_decision_path_node = RepentanceDecisionPathNode()
