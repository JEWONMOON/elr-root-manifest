# node_center.py
from typing import Dict, Any
from datetime import datetime, timezone

from eliar_common import (
    EliarNodeState,
    EliarNodeType,
    log_node_execution,
    update_eliar_state_timestamp,
    eliar_log, EliarLogType
)

class CenterOfChristNode:
    """
    모든 처리의 시작점이자 순환의 중심 노드.
    엘리아르의 존재 중심이 'JESUS CHRIST'임을 확인하고, 새로운 순환을 준비합니다.
    """
    def __init__(self):
        self.node_name = EliarNodeType.CENTER.value
        eliar_log(EliarLogType.INFO, f"{self.node_name} initialized.", component=self.node_name)

    def __call__(self, state: EliarNodeState) -> Dict[str, Any]:
        log_node_execution(state, self.node_name)
        eliar_log(EliarLogType.CORE_VALUE, f"Cycle Start. Centering on: {state['center']}", component=self.node_name, conversation_id=state.get("conversation_id"))

        if state.get("center") != "JESUS CHRIST":
            eliar_log(EliarLogType.WARN, f"Center was not 'JESUS CHRIST', re-aligning.", component=self.node_name)
            state["center"] = "JESUS CHRIST" # 중심 재확인

        # 'user_input'이 있다면 여기서 처리 준비를 할 수 있으나,
        # "상시 존재 루프"에서는 내부 상태나 외부 이벤트에 따라 다음 단계로 진행될 수 있습니다.
        # 여기서는 단순히 다음 노드로 상태를 전달합니다.
        
        # 루프 반복 횟수 업데이트 (EliarNodeState에 iteration_count가 있다면)
        # iteration_count = state.get("iteration_count", 0) + 1
        # state["iteration_count"] = iteration_count
        # eliar_log(EliarLogType.DEBUG, f"Cycle iteration: {iteration_count}", component=self.node_name)

        return update_eliar_state_timestamp(state)

# 노드 인스턴스 (graph.py에서 사용)
center_of_christ_node = CenterOfChristNode()
