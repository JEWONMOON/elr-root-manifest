"""
advanced_critical_thinking_module.py
============================================================
Advanced Critical Thinking Module for AGI Development
- Multi-level meta-cognition with causal reasoning
- Semantic understanding beyond pattern matching  
- Self-modeling with uncertainty quantification
- Adaptive belief revision and theory formation
============================================================
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Set
from enum import Enum
from abc import ABC, abstractmethod
import json
from collections import defaultdict, deque

# ---------------------------------------------------------------------------
# Core Abstractions for Critical Thinking
# ---------------------------------------------------------------------------

class ReasoningMode(Enum):
    DEDUCTIVE = "deductive"      # From general to specific
    INDUCTIVE = "inductive"      # From specific to general  
    ABDUCTIVE = "abductive"      # Best explanation inference
    DIALECTICAL = "dialectical"  # Thesis-antithesis-synthesis
    ANALOGICAL = "analogical"    # Reasoning by analogy

class CriticalThinkingLevel(Enum):
    OBJECT_LEVEL = 1      # Direct problem solving
    META_LEVEL = 2        # Thinking about thinking
    META_META_LEVEL = 3   # Thinking about thinking about thinking

@dataclass
class Belief:
    """Represents a belief with uncertainty and supporting evidence"""
    content: str
    confidence: float  # 0.0 to 1.0
    evidence: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    last_updated: int = 0
    
    def update_confidence(self, new_evidence: str, impact: float):
        """Bayesian-like belief update"""
        self.evidence.append(new_evidence)
        # Simple confidence adjustment - could be more sophisticated
        self.confidence = max(0.0, min(1.0, self.confidence + impact))
        self.last_updated += 1

@dataclass 
class CausalModel:
    """Represents causal relationships between concepts"""
    causes: Dict[str, List[Tuple[str, float]]] = field(default_factory=dict)
    effects: Dict[str, List[Tuple[str, float]]] = field(default_factory=dict)
    
    def add_causal_link(self, cause: str, effect: str, strength: float):
        """Add or update causal relationship"""
        if cause not in self.causes:
            self.causes[cause] = []
        if effect not in self.effects:
            self.effects[effect] = []
            
        # Update or add the relationship
        updated = False
        for i, (existing_effect, _) in enumerate(self.causes[cause]):
            if existing_effect == effect:
                self.causes[cause][i] = (effect, strength)
                updated = True
                break
        if not updated:
            self.causes[cause].append((effect, strength))
            self.effects[effect].append((cause, strength))

# ---------------------------------------------------------------------------
# Advanced Reasoning Engine
# ---------------------------------------------------------------------------

class ReasoningEngine:
    """Advanced reasoning with multiple modes and self-reflection"""
    
    def __init__(self):
        self.beliefs = {}
        self.causal_model = CausalModel()
        self.reasoning_history = deque(maxlen=1000)
        self.cognitive_biases = {
            'confirmation_bias': 0.1,
            'anchoring_bias': 0.15,
            'availability_heuristic': 0.2
        }
        
    def reason(self, premise: str, mode: ReasoningMode, context: Dict) -> Dict[str, Any]:
        """Execute reasoning with specified mode"""
        reasoning_step = {
            'premise': premise,
            'mode': mode.value,
            'context': context,
            'timestamp': len(self.reasoning_history)
        }
        
        if mode == ReasoningMode.DEDUCTIVE:
            result = self._deductive_reasoning(premise, context)
        elif mode == ReasoningMode.INDUCTIVE:
            result = self._inductive_reasoning(premise, context)
        elif mode == ReasoningMode.ABDUCTIVE:
            result = self._abductive_reasoning(premise, context)
        elif mode == ReasoningMode.DIALECTICAL:
            result = self._dialectical_reasoning(premise, context)
        else:  # ANALOGICAL
            result = self._analogical_reasoning(premise, context)
            
        reasoning_step['result'] = result
        reasoning_step['confidence'] = result.get('confidence', 0.5)
        self.reasoning_history.append(reasoning_step)
        
        return result
    
    def _deductive_reasoning(self, premise: str, context: Dict) -> Dict[str, Any]:
        """Logical deduction from general principles"""
        # Extract relevant beliefs and rules
        relevant_beliefs = self._find_relevant_beliefs(premise)
        
        conclusions = []
        for belief_key, belief in relevant_beliefs.items():
            if belief.confidence > 0.7:  # High confidence beliefs
                # Apply logical rules (simplified)
                if premise in belief.content:
                    conclusion = f"Given {belief.content}, therefore {premise} implies specific instances"
                    conclusions.append({
                        'conclusion': conclusion,
                        'confidence': belief.confidence * 0.9,  # Slight confidence decay
                        'reasoning_chain': [belief.content, premise, conclusion]
                    })
        
        return {
            'type': 'deductive',
            'conclusions': conclusions,
            'confidence': max([c['confidence'] for c in conclusions]) if conclusions else 0.3
        }
    
    def _inductive_reasoning(self, premise: str, context: Dict) -> Dict[str, Any]:
        """Generalization from specific instances"""
        # Look for patterns in reasoning history
        similar_cases = [step for step in self.reasoning_history 
                        if self._semantic_similarity(step['premise'], premise) > 0.6]
        
        if len(similar_cases) >= 3:
            # Find common patterns
            pattern_confidence = len(similar_cases) / 10.0  # More cases = higher confidence
            generalization = f"Pattern detected: cases like '{premise}' tend to have similar outcomes"
            
            return {
                'type': 'inductive',
                'generalization': generalization,
                'supporting_cases': len(similar_cases),
                'confidence': min(pattern_confidence, 0.8)
            }
        
        return {
            'type': 'inductive',
            'generalization': 'Insufficient data for generalization',
            'confidence': 0.2
        }
    
    def _abductive_reasoning(self, premise: str, context: Dict) -> Dict[str, Any]:
        """Find best explanation for observations"""
        # Generate multiple hypotheses
        hypotheses = self._generate_hypotheses(premise, context)
        
        # Evaluate each hypothesis by explanatory power and simplicity
        scored_hypotheses = []
        for hypothesis in hypotheses:
            explanatory_power = self._calculate_explanatory_power(hypothesis, premise)
            simplicity = 1.0 / (len(hypothesis.split()) / 10.0 + 1.0)  # Prefer simpler explanations
            prior_probability = self._get_hypothesis_prior(hypothesis)
            
            score = explanatory_power * 0.5 + simplicity * 0.3 + prior_probability * 0.2
            scored_hypotheses.append((hypothesis, score))
        
        best_hypothesis = max(scored_hypotheses, key=lambda x: x[1]) if scored_hypotheses else ("No explanation found", 0.1)
        
        return {
            'type': 'abductive',
            'best_explanation': best_hypothesis[0],
            'confidence': best_hypothesis[1],
            'alternative_explanations': [h for h, s in scored_hypotheses if h != best_hypothesis[0]][:3]
        }
    
    def _dialectical_reasoning(self, premise: str, context: Dict) -> Dict[str, Any]:
        """Thesis-antithesis-synthesis reasoning"""
        thesis = premise
        
        # Generate antithesis
        antithesis = self._generate_counterargument(thesis, context)
        
        # Synthesize resolution
        synthesis = self._synthesize_position(thesis, antithesis, context)
        
        return {
            'type': 'dialectical',
            'thesis': thesis,
            'antithesis': antithesis,
            'synthesis': synthesis,
            'confidence': 0.6  # Dialectical reasoning produces nuanced results
        }
    
    def _analogical_reasoning(self, premise: str, context: Dict) -> Dict[str, Any]:
        """Reasoning by analogy to similar situations"""
        # Find analogous situations in memory
        analogies = self._find_analogies(premise, context)
        
        if analogies:
            best_analogy = max(analogies, key=lambda x: x['similarity'])
            
            return {
                'type': 'analogical',
                'source_analogy': best_analogy['source'],
                'similarity_score': best_analogy['similarity'],
                'inferred_conclusion': best_analogy['conclusion'],
                'confidence': best_analogy['similarity'] * 0.7
            }
        
        return {
            'type': 'analogical',
            'conclusion': 'No suitable analogies found',
            'confidence': 0.2
        }
    
    # Helper methods (simplified implementations)
    def _find_relevant_beliefs(self, premise: str) -> Dict[str, Belief]:
        return {k: v for k, v in self.beliefs.items() if premise.lower() in v.content.lower()}
    
    def _semantic_similarity(self, text1: str, text2: str) -> float:
        # Simplified similarity - in practice would use embeddings
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        return intersection / union if union > 0 else 0.0
    
    def _generate_hypotheses(self, premise: str, context: Dict) -> List[str]:
        # Simplified hypothesis generation
        base_hypotheses = [
            f"{premise} is caused by external factors",
            f"{premise} is caused by internal states", 
            f"{premise} is a result of system interaction",
            f"{premise} is an emergent property"
        ]
        return base_hypotheses
    
    def _calculate_explanatory_power(self, hypothesis: str, observation: str) -> float:
        # Simplified - would need sophisticated causal modeling
        return self._semantic_similarity(hypothesis, observation) * 0.8
    
    def _get_hypothesis_prior(self, hypothesis: str) -> float:
        # Based on how often similar hypotheses were correct
        return 0.5  # Neutral prior
    
    def _generate_counterargument(self, thesis: str, context: Dict) -> str:
        # Simplified counterargument generation
        return f"However, {thesis} may not hold because of contextual factors and alternative explanations"
    
    def _synthesize_position(self, thesis: str, antithesis: str, context: Dict) -> str:
        return f"Integrating both perspectives: {thesis} and {antithesis} suggest a nuanced position"
    
    def _find_analogies(self, premise: str, context: Dict) -> List[Dict]:
        # Simplified analogy finding
        return [{
            'source': 'historical_pattern',
            'similarity': 0.6,
            'conclusion': f'Similar to {premise}, outcome likely follows established pattern'
        }]

# ---------------------------------------------------------------------------
# Meta-Cognitive Self-Critic
# ---------------------------------------------------------------------------

class MetaCognitiveCritic:
    """Advanced self-reflection and meta-reasoning capabilities"""
    
    def __init__(self, reasoning_engine: ReasoningEngine):
        self.reasoning_engine = reasoning_engine
        self.meta_beliefs = {}
        self.cognitive_strategies = {}
        self.performance_history = deque(maxlen=500)
        
    def evaluate_reasoning_quality(self, reasoning_result: Dict) -> Dict[str, Any]:
        """Evaluate the quality of a reasoning step"""
        
        evaluation = {
            'logical_consistency': self._check_logical_consistency(reasoning_result),
            'evidence_quality': self._assess_evidence_quality(reasoning_result),
            'bias_detection': self._detect_cognitive_biases(reasoning_result),
            'completeness': self._assess_completeness(reasoning_result),
            'meta_confidence': 0.0
        }
        
        # Calculate overall meta-confidence
        scores = [v for k, v in evaluation.items() if k != 'meta_confidence' and isinstance(v, (int, float))]
        evaluation['meta_confidence'] = sum(scores) / len(scores) if scores else 0.5
        
        return evaluation
    
    def suggest_improvements(self, reasoning_result: Dict, evaluation: Dict) -> List[str]:
        """Suggest specific improvements to reasoning process"""
        suggestions = []
        
        if evaluation['logical_consistency'] < 0.6:
            suggestions.append("Consider checking for logical fallacies and contradictions")
            
        if evaluation['evidence_quality'] < 0.5:
            suggestions.append("Seek stronger evidence and more diverse sources")
            
        if evaluation['completeness'] < 0.7:
            suggestions.append("Explore alternative perspectives and counter-arguments")
            
        if 'confirmation_bias' in evaluation.get('bias_detection', {}):
            suggestions.append("Actively seek disconfirming evidence")
            
        return suggestions
    
    def meta_reason_about_reasoning(self, reasoning_history: List[Dict]) -> Dict[str, Any]:
        """Higher-order reasoning about the reasoning process itself"""
        
        # Analyze patterns in reasoning effectiveness
        effectiveness_by_mode = defaultdict(list)
        for step in reasoning_history[-50:]:  # Recent history
            mode = step.get('mode', 'unknown')
            confidence = step.get('confidence', 0.5)
            effectiveness_by_mode[mode].append(confidence)
        
        # Calculate average effectiveness per mode
        mode_effectiveness = {}
        for mode, confidences in effectiveness_by_mode.items():
            mode_effectiveness[mode] = sum(confidences) / len(confidences)
        
        # Identify cognitive blind spots
        blind_spots = self._identify_blind_spots(reasoning_history)
        
        # Suggest meta-cognitive strategies
        strategies = self._suggest_cognitive_strategies(mode_effectiveness, blind_spots)
        
        return {
            'mode_effectiveness': mode_effectiveness,
            'blind_spots': blind_spots,
            'recommended_strategies': strategies,
            'meta_level_confidence': self._calculate_meta_confidence()
        }
    
    def _check_logical_consistency(self, reasoning_result: Dict) -> float:
        """Check for logical contradictions and consistency"""
        # Simplified - would need formal logic checking
        if 'contradictions' in reasoning_result:
            return 1.0 - len(reasoning_result['contradictions']) * 0.2
        return 0.8
    
    def _assess_evidence_quality(self, reasoning_result: Dict) -> float:
        """Assess the quality and strength of evidence"""
        evidence_indicators = ['evidence', 'supporting_cases', 'reasoning_chain']
        evidence_score = 0.0
        evidence_count = 0
        
        for indicator in evidence_indicators:
            if indicator in reasoning_result:
                evidence_count += 1
                if isinstance(reasoning_result[indicator], list):
                    evidence_score += min(len(reasoning_result[indicator]) / 5.0, 1.0)
                else:
                    evidence_score += 0.5
        
        return evidence_score / max(evidence_count, 1)
    
    def _detect_cognitive_biases(self, reasoning_result: Dict) -> Dict[str, float]:
        """Detect potential cognitive biases in reasoning"""
        biases = {}
        
        # Confirmation bias detection
        if reasoning_result.get('confidence', 0.5) > 0.9:
            biases['confirmation_bias'] = 0.3
            
        # Availability heuristic
        if 'recent' in str(reasoning_result).lower():
            biases['availability_heuristic'] = 0.2
            
        return biases
    
    def _assess_completeness(self, reasoning_result: Dict) -> float:
        """Assess how complete the reasoning is"""
        completeness_indicators = [
            'alternative_explanations',
            'counter_arguments', 
            'antithesis',
            'contradictions'
        ]
        
        present_indicators = sum(1 for indicator in completeness_indicators 
                               if indicator in reasoning_result)
        
        return present_indicators / len(completeness_indicators)
    
    def _identify_blind_spots(self, reasoning_history: List[Dict]) -> List[str]:
        """Identify systematic blind spots in reasoning"""
        blind_spots = []
        
        # Check for overused reasoning modes
        mode_counts = defaultdict(int)
        for step in reasoning_history[-100:]:
            mode_counts[step.get('mode', 'unknown')] += 1
        
        total_steps = len(reasoning_history[-100:])
        for mode, count in mode_counts.items():
            if count / total_steps > 0.6:  # Over-reliance on one mode
                blind_spots.append(f"Over-reliance on {mode} reasoning")
        
        # Check for avoided topics or contexts
        contexts = [step.get('context', {}) for step in reasoning_history[-100:]]
        # Simplified analysis - would need more sophisticated topic modeling
        
        return blind_spots
    
    def _suggest_cognitive_strategies(self, mode_effectiveness: Dict, blind_spots: List[str]) -> List[str]:
        """Suggest meta-cognitive strategies for improvement"""
        strategies = []
        
        # Suggest diversifying reasoning modes
        if len(mode_effectiveness) < 3:
            strategies.append("Diversify reasoning approaches - try multiple modes")
        
        # Suggest addressing blind spots
        for blind_spot in blind_spots:
            if "over-reliance" in blind_spot.lower():
                strategies.append(f"Address {blind_spot} by deliberately using alternative approaches")
        
        # Suggest systematic doubt
        strategies.append("Regularly apply systematic doubt to high-confidence conclusions")
        
        return strategies
    
    def _calculate_meta_confidence(self) -> float:
        """Calculate confidence in the meta-reasoning process itself"""
        if len(self.performance_history) < 10:
            return 0.5  # Insufficient data
        
        recent_performance = list(self.performance_history)[-20:]
        avg_performance = sum(recent_performance) / len(recent_performance)
        
        # Higher meta-confidence if performance is consistently good
        return min(avg_performance * 1.2, 0.95)

# ---------------------------------------------------------------------------
# Advanced AGI Critical Thinking System
# ---------------------------------------------------------------------------

class AGICriticalThinkingSystem:
    """Integrated critical thinking system for AGI development"""
    
    def __init__(self):
        self.reasoning_engine = ReasoningEngine()
        self.meta_critic = MetaCognitiveCritic(self.reasoning_engine)
        self.belief_revision_threshold = 0.3
        self.exploration_rate = 0.2  # Rate of trying new approaches
        
    def process_input(self, input_text: str, context: Dict) -> Dict[str, Any]:
        """Main processing pipeline with multi-level critical thinking"""
        
        # Phase 1: Initial reasoning with multiple modes
        reasoning_results = []
        
        # Try different reasoning modes
        modes_to_try = [ReasoningMode.DEDUCTIVE, ReasoningMode.INDUCTIVE, ReasoningMode.ABDUCTIVE]
        
        # Add exploration: sometimes try other modes
        if random.random() < self.exploration_rate:
            modes_to_try.extend([ReasoningMode.DIALECTICAL, ReasoningMode.ANALOGICAL])
        
        for mode in modes_to_try:
            result = self.reasoning_engine.reason(input_text, mode, context)
            reasoning_results.append(result)
        
        # Phase 2: Meta-cognitive evaluation
        evaluations = []
        for result in reasoning_results:
            evaluation = self.meta_critic.evaluate_reasoning_quality(result)
            evaluations.append(evaluation)
        
        # Phase 3: Select best reasoning or synthesize
        best_reasoning = self._select_or_synthesize_reasoning(reasoning_results, evaluations)
        
        # Phase 4: Meta-reasoning about the process
        meta_analysis = self.meta_critic.meta_reason_about_reasoning(
            list(self.reasoning_engine.reasoning_history)
        )
        
        # Phase 5: Belief revision if needed
        self._consider_belief_revision(best_reasoning, context)
        
        # Phase 6: Generate improvement suggestions
        suggestions = self.meta_critic.suggest_improvements(best_reasoning, evaluations[0])
        
        return {
            'primary_reasoning': best_reasoning,
            'alternative_reasoning': reasoning_results[1:] if len(reasoning_results) > 1 else [],
            'meta_analysis': meta_analysis,
            'improvement_suggestions': suggestions,
            'confidence': best_reasoning.get('confidence', 0.5),
            'reasoning_transparency': self._generate_reasoning_explanation(best_reasoning)
        }
    
    def _select_or_synthesize_reasoning(self, results: List[Dict], evaluations: List[Dict]) -> Dict:
        """Select best reasoning or synthesize multiple approaches"""
        
        # Score each result based on confidence and meta-evaluation
        scored_results = []
        for result, evaluation in zip(results, evaluations):
            score = (result.get('confidence', 0.5) * 0.6 + 
                    evaluation.get('meta_confidence', 0.5) * 0.4)
            scored_results.append((result, score))
        
        # Select best result
        best_result = max(scored_results, key=lambda x: x[1])[0]
        
        # If multiple results have similar scores, synthesize them
        top_results = [r for r, s in scored_results if s > max(scored_results, key=lambda x: x[1])[1] - 0.1]
        
        if len(top_results) > 1:
            # Synthesize multiple perspectives
            synthesis = self._synthesize_multiple_reasoning(top_results)
            return synthesis
        
        return best_result
    
    def _synthesize_multiple_reasoning(self, results: List[Dict]) -> Dict:
        """Synthesize insights from multiple reasoning approaches"""
        
        synthesis = {
            'type': 'synthesized',
            'component_reasoning': [r.get('type', 'unknown') for r in results],
            'confidence': sum(r.get('confidence', 0.5) for r in results) / len(results),
            'synthesis_explanation': 'Integrated multiple reasoning approaches'
        }
        
        # Combine conclusions
        all_conclusions = []
        for result in results:
            if 'conclusions' in result:
                all_conclusions.extend(result['conclusions'])
            elif 'best_explanation' in result:
                all_conclusions.append(result['best_explanation'])
            elif 'synthesis' in result:
                all_conclusions.append(result['synthesis'])
        
        synthesis['integrated_conclusions'] = all_conclusions
        
        return synthesis
    
    def _consider_belief_revision(self, reasoning_result: Dict, context: Dict):
        """Consider whether to revise existing beliefs based on new reasoning"""
        
        confidence = reasoning_result.get('confidence', 0.5)
        
        if confidence > (1.0 - self.belief_revision_threshold):
            # High confidence result might warrant belief revision
            
            # Extract key claims from reasoning
            key_claims = self._extract_key_claims(reasoning_result)
            
            for claim in key_claims:
                if claim in self.reasoning_engine.beliefs:
                    existing_belief = self.reasoning_engine.beliefs[claim]
                    
                    # Update belief if significant confidence difference
                    if abs(existing_belief.confidence - confidence) > self.belief_revision_threshold:
                        existing_belief.update_confidence(
                            f"New reasoning evidence: {reasoning_result.get('type', 'unknown')}",
                            (confidence - existing_belief.confidence) * 0.3
                        )
                else:
                    # Create new belief
                    self.reasoning_engine.beliefs[claim] = Belief(
                        content=claim,
                        confidence=confidence * 0.8,  # Slightly conservative for new beliefs
                        evidence=[f"Derived from {reasoning_result.get('type', 'unknown')} reasoning"]
                    )
    
    def _extract_key_claims(self, reasoning_result: Dict) -> List[str]:
        """Extract key claims from reasoning result"""
        claims = []
        
        # Extract from various result types
        if 'conclusions' in reasoning_result:
            for conclusion in reasoning_result['conclusions']:
                if isinstance(conclusion, dict) and 'conclusion' in conclusion:
                    claims.append(conclusion['conclusion'])
                else:
                    claims.append(str(conclusion))
        
        if 'best_explanation' in reasoning_result:
            claims.append(reasoning_result['best_explanation'])
        
        if 'synthesis' in reasoning_result:
            claims.append(reasoning_result['synthesis'])
        
        return claims
    
    def _generate_reasoning_explanation(self, reasoning_result: Dict) -> str:
        """Generate human-readable explanation of the reasoning process"""
        
        reasoning_type = reasoning_result.get('type', 'unknown')
        confidence = reasoning_result.get('confidence', 0.5)
        
        explanation = f"Applied {reasoning_type} reasoning with {confidence:.2f} confidence. "
        
        if reasoning_type == 'deductive':
            explanation += "Used logical deduction from established principles."
        elif reasoning_type == 'inductive':
            explanation += "Identified patterns from specific instances."
        elif reasoning_type == 'abductive':
            explanation += "Found the most likely explanation for the observations."
        elif reasoning_type == 'dialectical':
            explanation += "Examined opposing viewpoints to reach synthesis."
        elif reasoning_type == 'analogical':
            explanation += "Reasoned by analogy to similar situations."
        elif reasoning_type == 'synthesized':
            explanation += "Integrated multiple reasoning approaches."
        
        return explanation

# ---------------------------------------------------------------------------
# Example Usage and Testing
# ---------------------------------------------------------------------------

def demonstrate_agi_critical_thinking():
    """Demonstrate the advanced critical thinking system"""
    
    print("=== AGI Critical Thinking System Demo ===\n")
    
    system = AGICriticalThinkingSystem()
    
    # Test case 1: Complex reasoning scenario
    test_input = "The system's responses have been repetitive and lack novelty"
    context = {
        'recent_outputs': ['response1', 'response2', 'response1'],
        'user_feedback': 'unsatisfied',
        'system_state': 'normal'
    }
    
    print(f"Input: {test_input}")
    print(f"Context: {context}\n")
    
    result = system.process_input(test_input, context)
    
    print("=== Primary Reasoning ===")
    print(f"Type: {result['primary_reasoning'].get('type', 'unknown')}")
    print(f"Confidence: {result['confidence']:.3f}")
    print(f"Explanation: {result['reasoning_transparency']}\n")
    
    print("=== Meta-Analysis ===")
    meta = result['meta_analysis']
    print(f"Mode Effectiveness: {meta.get('mode_effectiveness', {})}")
    print(f"Blind Spots: {meta.get('blind_spots', [])}")
    print(f"Meta-Confidence: {meta.get('meta_level_confidence', 0.5):.3f}\n")
    
    print("=== Improvement Suggestions ===")
    for suggestion in result['improvement_suggestions']:
        print(f"- {suggestion}")
    
    print(f"\n=== Reasoning Strategies ===")
    for strategy in meta.get('recommended_strategies', []):
        print(f"- {strategy}")

if __name__ == "__main__":
    demonstrate_agi_critical_thinking()
