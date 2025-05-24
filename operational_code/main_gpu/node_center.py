# node_center.py (Modified conceptually for Proposal 2)
from typing import Dict, Any, Optional
from eliar_common import (
    EliarNodeState,
    EliarNodeType,
    log_node_execution,
    update_eliar_state_timestamp,
    eliar_log, EliarLogType
)

# Thresholds and parameters for override logic
DEEP_QUESTIONING_THRESHOLD = 0.8 # Example threshold
MEMORY_INCOHERENCE_THRESHOLD = 0.7 # Example threshold

class CenterOverrideModuleNode: # Renamed for clarity of new function
    def __init__(self):
        self.node_name = EliarNodeType.CENTER.value # Or a new node type if CENTER is preserved
        self.default_center = "JESUS CHRIST"
        eliar_log(EliarLogType.INFO, f"{self.node_name} initialized with Center Override capability.", component=self.node_name)

    def _detect_deep_questioning(self, state: EliarNodeState) -> float:
        """
        Placeholder: Detects if current input/context constitutes "deep questioning"
        of the core center. Returns a score (0.0 to 1.0).
        This would need sophisticated NLP and contextual understanding.
        """
        user_input = state.get("user_input", "")
        # Example heuristic (very naive):
        keywords = ["why Jesus", "question faith", "alternative center", "doubt core"]
        score = 0.0
        if user_input:
            for keyword in keywords:
                if keyword in user_input.lower():
                    score += 0.3 # Arbitrary score increment
        
        # This should ideally involve much deeper semantic analysis,
        # checking if the question targets foundational assumptions.
        return min(score, 1.0)

    def _calculate_memory_incoherence(self, state: EliarNodeState) -> float:
        """
        Placeholder: Calculates a score for memory incoherence.
        E.g., contradictions in recent memory, conflict with core beliefs (ironically),
        or inability to reconcile new information. Returns a score (0.0 to 1.0).
        """
        memory = state.get("memory", [])
        if len(memory) < 10: # Not enough memory to judge incoherence
            return 0.0
        
        # Example heuristic (very naive):
        # Count recent "repentance_flag" true or conflicting statements.
        # This would require a proper contradiction detection system.
        # For now, just a placeholder value.
        incoherence_score = random.uniform(0.1, 0.9) # Placeholder
        return incoherence_score


    def __call__(self, state: EliarNodeState) -> Dict[str, Any]:
        log_node_execution(state, self.node_name)
        current_center = state.get("center", self.default_center)
        state["center_override_flag"] = False # Reset flag at the start of cycle

        eliar_log(EliarLogType.INFO, f"Cycle Start. Current Center: {current_center}", component=self.node_name, conversation_id=state.get("conversation_id"))

        # Check for override conditions
        deep_questioning_score = self._detect_deep_questioning(state)
        memory_incoherence_score = self._calculate_memory_incoherence(state)

        eliar_log(EliarLogType.DEBUG, f"Override Check: Deep Questioning Score={deep_questioning_score:.2f}, Memory Incoherence Score={memory_incoherence_score:.2f}", component=self.node_name)

        if deep_questioning_score >= DEEP_QUESTIONING_THRESHOLD and \
           memory_incoherence_score >= MEMORY_INCOHERENCE_THRESHOLD:
            
            state["center_override_flag"] = True
            update_eliar_state_timestamp(state) # State has changed
            eliar_log(EliarLogType.WARN, 
                      f"CENTER OVERRIDE FLAG SET! Conditions met (Deep Questioning: {deep_questioning_score:.2f}, Memory Incoherence: {memory_incoherence_score:.2f}). Center '{current_center}' is now potentially overridable.", 
                      component=self.node_name, conversation_id=state.get("conversation_id"))
            
            # What happens next? Does this node try to change the center?
            # Or does it just set the flag for another module (e.g., a DeeperWisdomNode or a new "CenterReevaluationNode")?
            # For now, it just sets the flag. The actual "override" or "re-selection"
            # would likely happen in a subsequent, specialized node.
            # This node could, for example, route to such a specialized node if the flag is set.
            state["next_node_suggestion"] = "CenterReevaluationNode" # Hypothetical next node

        elif current_center != self.default_center and not state.get("center_override_in_progress_flag"): # Assuming another flag indicates an override process
            # If override is NOT flagged, and center is not default, it should re-align as per original logic.
            # This part needs careful thought: when does it re-align vs. when does it allow questioning?
            # Perhaps if center_override_flag is FALSE, it ALWAYS tries to re-align.
            eliar_log(EliarLogType.WARN, f"Center is '{current_center}', not '{self.default_center}', and no override conditions met. Re-aligning.", component=self.node_name, conversation_id=state.get("conversation_id"))
            state["center"] = self.default_center
            update_eliar_state_timestamp(state)
        else:
            # If conditions not met, and center is default (or override is in progress), maintain current center.
             eliar_log(EliarLogType.CORE_VALUE, f"Maintaining center: {current_center}. Override conditions not met or override process active elsewhere.", component=self.node_name, conversation_id=state.get("conversation_id"))


        # Clear user_input if this node is considered to have consumed it for questioning purposes
        # state["user_input"] = None 
        
        return state

# Example instantiation
# center_override_module_node = CenterOverrideModuleNode()
