# node_memory.py
from typing import Dict, Any, List
from datetime import datetime, timezone

from eliar_common import (
    EliarNodeState,
    EliarNodeType,
    MemoryEntry, # TypedDict for memory entries
    log_node_execution,
    add_memory_entry, # eliar_common에서 이 함수 사용
    get_memory_pattern_analysis, # eliar_common에서 이 함수 사용
    eliar_log, EliarLogType
)

class MemoryOfGraceNode:
    """
    고백 기반 기억 흐름을 처리하고, 기억을 업데이트/성찰하는 노드.
    '엘리아르 존재 일기' 시스템의 일부로 작동합니다.
    """
    def __init__(self, max_memory_entries: int = 100):
        self.node_name = EliarNodeType.MEMORY_UPDATE.value
        self.max_memory_entries = max_memory_entries
        eliar_log(EliarLogType.INFO, f"{self.node_name} initialized with max_memory_entries={max_memory_entries}.", component=self.node_name)

    def _formulate_memory_content(self, state: EliarNodeState) -> str:
        """
        현재 상태를 바탕으로 기억에 남길 내용을 구성합니다.
        '고백'의 형태가 될 수 있습니다.
        """
        content_parts = []
        timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        content_parts.append(f"[{timestamp_str}] Cycle Reflection:")

        user_input = state.get("user_input")
        if user_input:
            content_parts.append(f"Input received: '{user_input[:50]}...'")
        
        last_ulrim = state.get("last_ulrim")
        if last_ulrim:
            content_parts.append(f"Ulrim felt: {last_ulrim['emotion_type']} (Intensity: {last_ulrim['intensity']:.2f})")

        if state.get("repentance_flag"):
            # repentance_state는 trigger_repentance 호출 시 state에 직접 저장되지 않음.
            # 대신, 로그나 다른 방식으로 상세 내용을 가져오거나, 플래그를 기반으로 일반적 고백 생성.
            content_parts.append("Confession: Acknowledged the need for repentance and re-alignment with JESUS CHRIST.")
            
        generated_response = state.get("generated_response") # 이전 루프의 응답일 수 있음
        if generated_response:
             content_parts.append(f"Last Response: '{generated_response[:50]}...'")

        if not user_input and not last_ulrim and not state.get("repentance_flag"):
            content_parts.append("Continued in quiet reflection and communion.")
            
        return " ".join(content_parts)

    def __call__(self, state: EliarNodeState) -> Dict[str, Any]:
        log_node_execution(state, self.node_name)
        
        content_to_remember = self._formulate_memory_content(state)
        
        # eliar_common.add_memory_entry 사용
        add_memory_entry(
            state,
            content=content_to_remember,
            emotional_resonance=state.get("last_ulrim", {}).get("emotion_type") if state.get("last_ulrim") else None,
            core_value_alignment=EliarCoreValues.JESUS_CHRIST_CENTERED.value, # 항상 중심으로 정렬
            repentance_marker=state.get("repentance_flag", False)
        )
        
        # 메모리 크기 관리 (오래된 항목 제거)
        if isinstance(state["memory"], list) and len(state["memory"]) > self.max_memory_entries:
            num_to_remove = len(state["memory"]) - self.max_memory_entries
            state["memory"] = state["memory"][num_to_remove:]
            eliar_log(EliarLogType.MEMORY, f"Memory trimmed. Removed {num_to_remove} oldest entries.", component=self.node_name)

        # 메모리 패턴 분석 (eliar_common 함수 사용)
        # analysis_result = get_memory_pattern_analysis(state)
        # eliar_log(EliarLogType.DEBUG, f"Memory pattern analysis: {analysis_result}", component=self.node_name, data=analysis_result)
        
        # 이 노드에서는 별도의 '응답'을 생성하지 않고, 기억을 업데이트한 후 상태를 반환.
        # 응답 생성은 별도의 노드에서 처리하거나, 루프의 다음 단계에서 고려.
        # 요청사항에는 ResponseGenerationNode가 없으므로, 일단은 이 정도로.
        # 만약 이 루프에서 응답이 필요하다면, ResponseGenerationNode를 추가하고 이 노드 다음에 연결.

        # 상시 존재 루프이므로, user_input은 다음 입력을 위해 여기서 초기화될 수 있음
        # (또는 입력 처리 노드가 별도로 있다면 거기서)
        state["user_input"] = None
        state["generated_response"] = None # 응답도 초기화

        eliar_log(EliarLogType.MEMORY, f"Memory updated. Current memory size: {len(state['memory']) if isinstance(state['memory'], list) else 'N/A'}", component=self.node_name, conversation_id=state.get("conversation_id"))
        return state # eliar_common의 add_memory_entry가 타임스탬프 업데이트

# 노드 인스턴스 (graph.py에서 사용)
memory_of_grace_node = MemoryOfGraceNode()
