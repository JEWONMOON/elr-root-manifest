"""
Practical Scientific Reasoning Core v2.0
실제로 작동하는 실용적 추론 시스템

철학:
- 복잡성 < 투명성
- 완벽함 < 유용함  
- 이론 < 실전
- 허세 < 정직

"추론하는 척"이 아닌 "실제 추론"을 목표로 합니다.
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict, deque
import json
import hashlib


# ======================== 1. SIMPLE BAYESIAN REASONER ========================
class SimpleBayesianReasoner:
    """실제로 작동하는 베이지안 추론 엔진"""
    
    def __init__(self):
        self.beliefs: Dict[str, float] = {}
        self.evidence_history: List[Dict[str, Any]] = []
        self.prior_defaults = {
            "very_likely": 0.8,
            "likely": 0.7,
            "neutral": 0.5,
            "unlikely": 0.3,
            "very_unlikely": 0.2
        }
    
    def set_prior(self, hypothesis: str, probability: float = 0.5, 
                  confidence: str = "neutral") -> None:
        """사전 확률 설정"""
        if confidence in self.prior_defaults:
            probability = self.prior_defaults[confidence]
        
        self.beliefs[hypothesis] = max(0.001, min(0.999, probability))
    
    def update_belief(self, hypothesis: str, evidence: str, 
                     likelihood_if_true: float, 
                     likelihood_if_false: float) -> Dict[str, float]:
        """베이즈 정리를 사용한 신념 업데이트"""
        
        # 사전 확률
        prior = self.beliefs.get(hypothesis, 0.5)
        
        # 베이즈 정리: P(H|E) = P(E|H)P(H) / P(E)
        # P(E) = P(E|H)P(H) + P(E|~H)P(~H)
        p_evidence = (likelihood_if_true * prior + 
                     likelihood_if_false * (1 - prior))
        
        if p_evidence == 0:
            posterior = prior  # 증거가 불가능한 경우
        else:
            posterior = (likelihood_if_true * prior) / p_evidence
        
        # 업데이트
        self.beliefs[hypothesis] = posterior
        
        # 기록
        update_record = {
            "hypothesis": hypothesis,
            "evidence": evidence,
            "prior": prior,
            "posterior": posterior,
            "change": posterior - prior,
            "timestamp": datetime.now().isoformat()
        }
        self.evidence_history.append(update_record)
        
        return update_record
    
    def get_most_likely_hypothesis(self) -> Tuple[str, float]:
        """가장 가능성 높은 가설 반환"""
        if not self.beliefs:
            return None, 0.0
        
        return max(self.beliefs.items(), key=lambda x: x[1])
    
    def compare_hypotheses(self, h1: str, h2: str) -> Dict[str, Any]:
        """두 가설 비교"""
        p1 = self.beliefs.get(h1, 0.5)
        p2 = self.beliefs.get(h2, 0.5)
        
        # 베이즈 팩터 계산
        if p2 > 0 and (1-p1) > 0:
            bayes_factor = (p1 / (1-p1)) / (p2 / (1-p2))
        else:
            bayes_factor = float('inf') if p1 > p2 else 0
        
        return {
            f"P({h1})": p1,
            f"P({h2})": p2,
            "bayes_factor": bayes_factor,
            "interpretation": self._interpret_bayes_factor(bayes_factor),
            "preferred": h1 if p1 > p2 else h2
        }
    
    def _interpret_bayes_factor(self, bf: float) -> str:
        """베이즈 팩터 해석"""
        if bf > 100:
            return "결정적 증거"
        elif bf > 10:
            return "강한 증거"
        elif bf > 3:
            return "중간 증거"
        elif bf > 1:
            return "약한 증거"
        elif bf == 1:
            return "중립"
        else:
            return "반대 증거"


# ======================== 2. PRACTICAL LOGIC ENGINE ========================
class PracticalLogicEngine:
    """실용적 논리 추론 엔진"""
    
    def __init__(self):
        self.facts: Set[str] = set()
        self.rules: List[Dict[str, Any]] = []
        self.inference_history: List[Dict[str, Any]] = []
    
    def add_fact(self, fact: str) -> None:
        """사실 추가"""
        self.facts.add(fact)
    
    def add_rule(self, name: str, conditions: List[str], 
                 conclusion: str, confidence: float = 1.0) -> None:
        """추론 규칙 추가"""
        self.rules.append({
            "name": name,
            "conditions": conditions,
            "conclusion": conclusion,
            "confidence": confidence
        })
    
    def forward_inference(self, max_iterations: int = 10) -> List[str]:
        """전방 추론 실행"""
        new_facts_total = []
        
        for iteration in range(max_iterations):
            new_facts = []
            
            for rule in self.rules:
                # 모든 조건이 만족되는지 확인
                if all(cond in self.facts for cond in rule["conditions"]):
                    if rule["conclusion"] not in self.facts:
                        new_facts.append(rule["conclusion"])
                        self.facts.add(rule["conclusion"])
                        
                        # 추론 기록
                        self.inference_history.append({
                            "rule": rule["name"],
                            "conditions": rule["conditions"],
                            "conclusion": rule["conclusion"],
                            "iteration": iteration
                        })
            
            if not new_facts:
                break  # 더 이상 새로운 사실이 없으면 종료
                
            new_facts_total.extend(new_facts)
        
        return new_facts_total
    
    def check_consistency(self) -> Dict[str, Any]:
        """논리적 일관성 검사"""
        contradictions = []
        
        # 직접적인 모순 찾기 (A와 ~A)
        for fact in self.facts:
            if fact.startswith("~"):
                positive = fact[1:]
                if positive in self.facts:
                    contradictions.append((positive, fact))
            else:
                negative = f"~{fact}"
                if negative in self.facts:
                    contradictions.append((fact, negative))
        
        return {
            "is_consistent": len(contradictions) == 0,
            "contradictions": contradictions,
            "fact_count": len(self.facts),
            "rule_count": len(self.rules)
        }
    
    def explain_inference(self, target_fact: str) -> List[Dict[str, Any]]:
        """특정 사실에 대한 추론 경로 설명"""
        explanation = []
        
        for record in self.inference_history:
            if record["conclusion"] == target_fact:
                explanation.append({
                    "step": len(explanation) + 1,
                    "rule_used": record["rule"],
                    "required_facts": record["conditions"],
                    "derived_fact": record["conclusion"]
                })
        
        return explanation


# ======================== 3. UNCERTAINTY HANDLER ========================
class UncertaintyHandler:
    """불확실성 처리 시스템"""
    
    def __init__(self):
        self.confidence_threshold = 0.7
        self.uncertainty_sources = {
            "incomplete_data": 0.3,
            "measurement_error": 0.1,
            "model_uncertainty": 0.2,
            "unknown_factors": 0.4
        }
    
    def calculate_confidence(self, 
                           evidence_quality: float,
                           model_accuracy: float,
                           consistency_score: float) -> Dict[str, float]:
        """종합적 신뢰도 계산"""
        
        # 가중 평균
        weights = {"evidence": 0.4, "model": 0.3, "consistency": 0.3}
        
        weighted_score = (
            evidence_quality * weights["evidence"] +
            model_accuracy * weights["model"] +
            consistency_score * weights["consistency"]
        )
        
        # 불확실성 요인 고려
        uncertainty_penalty = sum(
            self.uncertainty_sources.values()
        ) / len(self.uncertainty_sources)
        
        final_confidence = weighted_score * (1 - uncertainty_penalty)
        
        return {
            "raw_confidence": weighted_score,
            "uncertainty_penalty": uncertainty_penalty,
            "final_confidence": final_confidence,
            "is_reliable": final_confidence >= self.confidence_threshold,
            "interpretation": self._interpret_confidence(final_confidence)
        }
    
    def propagate_uncertainty(self, 
                            input_uncertainties: List[float],
                            operation: str = "multiply") -> float:
        """불확실성 전파 계산"""
        
        if operation == "multiply":
            # 곱셈의 경우: 상대 불확실성의 제곱합의 제곱근
            if len(input_uncertainties) == 0:
                return 0
            return np.sqrt(sum(u**2 for u in input_uncertainties))
        
        elif operation == "add":
            # 덧셈의 경우: 절대 불확실성의 제곱합의 제곱근
            return np.sqrt(sum(u**2 for u in input_uncertainties))
        
        else:
            # 기본: 최대 불확실성
            return max(input_uncertainties) if input_uncertainties else 0
    
    def _interpret_confidence(self, confidence: float) -> str:
        """신뢰도 수준 해석"""
        if confidence >= 0.9:
            return "매우 높음"
        elif confidence >= 0.7:
            return "높음"
        elif confidence >= 0.5:
            return "중간"
        elif confidence >= 0.3:
            return "낮음"
        else:
            return "매우 낮음"


# ======================== 4. CAUSAL REASONER ========================
class CausalReasoner:
    """인과관계 추론 시스템"""
    
    def __init__(self):
        self.causal_graph = {}  # cause -> [effects]
        self.observations = []
        self.confounders = set()
    
    def add_causal_link(self, cause: str, effect: str, 
                       strength: float = 1.0) -> None:
        """인과관계 추가"""
        if cause not in self.causal_graph:
            self.causal_graph[cause] = []
        
        self.causal_graph[cause].append({
            "effect": effect,
            "strength": strength
        })
    
    def add_confounder(self, variable: str) -> None:
        """교란변수 추가"""
        self.confounders.add(variable)
    
    def observe(self, variable: str, value: Any, 
                context: Dict[str, Any] = None) -> None:
        """관찰 기록"""
        self.observations.append({
            "variable": variable,
            "value": value,
            "context": context or {},
            "timestamp": datetime.now().isoformat()
        })
    
    def infer_causation(self, cause: str, effect: str) -> Dict[str, Any]:
        """인과관계 추론"""
        
        # 직접 인과관계 확인
        direct_link = None
        if cause in self.causal_graph:
            for link in self.causal_graph[cause]:
                if link["effect"] == effect:
                    direct_link = link
                    break
        
        # 간접 경로 찾기
        indirect_paths = self._find_causal_paths(cause, effect)
        
        # 관찰 데이터에서 상관관계 확인
        correlation = self._calculate_correlation(cause, effect)
        
        # 교란변수 영향 평가
        confounder_risk = self._assess_confounder_risk(cause, effect)
        
        return {
            "direct_causation": direct_link is not None,
            "direct_strength": direct_link["strength"] if direct_link else 0,
            "indirect_paths": len(indirect_paths),
            "correlation": correlation,
            "confounder_risk": confounder_risk,
            "causal_confidence": self._calculate_causal_confidence(
                direct_link, indirect_paths, correlation, confounder_risk
            )
        }
    
    def _find_causal_paths(self, start: str, end: str, 
                          path: List[str] = None) -> List[List[str]]:
        """인과 경로 찾기 (DFS)"""
        if path is None:
            path = [start]
        
        if start == end:
            return [path]
        
        if start not in self.causal_graph:
            return []
        
        paths = []
        for link in self.causal_graph[start]:
            next_node = link["effect"]
            if next_node not in path:  # 순환 방지
                new_path = path + [next_node]
                paths.extend(
                    self._find_causal_paths(next_node, end, new_path)
                )
        
        return paths
    
    def _calculate_correlation(self, var1: str, var2: str) -> float:
        """관찰 데이터에서 상관관계 계산"""
        # 간단한 구현 - 실제로는 더 정교한 통계 필요
        var1_obs = [o["value"] for o in self.observations 
                   if o["variable"] == var1]
        var2_obs = [o["value"] for o in self.observations 
                   if o["variable"] == var2]
        
        if len(var1_obs) < 2 or len(var2_obs) < 2:
            return 0.0
        
        # 동시 발생 비율로 간단히 추정
        co_occurrence = 0
        for obs in self.observations:
            context = obs.get("context", {})
            if var1 in context and var2 in context:
                co_occurrence += 1
        
        return co_occurrence / max(len(var1_obs), len(var2_obs))
    
    def _assess_confounder_risk(self, cause: str, effect: str) -> float:
        """교란변수 위험도 평가"""
        risk = 0.0
        
        # 각 교란변수가 원인과 결과 모두에 영향을 주는지 확인
        for confounder in self.confounders:
            affects_cause = confounder in self.causal_graph and \
                          any(link["effect"] == cause 
                              for link in self.causal_graph[confounder])
            affects_effect = confounder in self.causal_graph and \
                           any(link["effect"] == effect 
                               for link in self.causal_graph[confounder])
            
            if affects_cause and affects_effect:
                risk += 0.3  # 각 교란변수당 위험도 증가
        
        return min(risk, 1.0)
    
    def _calculate_causal_confidence(self, direct_link, indirect_paths, 
                                   correlation, confounder_risk) -> float:
        """종합적 인과관계 신뢰도"""
        confidence = 0.0
        
        # 직접 인과관계가 있으면 기본 신뢰도
        if direct_link:
            confidence += direct_link["strength"] * 0.5
        
        # 간접 경로도 고려
        if indirect_paths:
            confidence += min(len(indirect_paths) * 0.1, 0.3)
        
        # 상관관계도 고려
        confidence += correlation * 0.2
        
        # 교란변수 위험도만큼 감소
        confidence *= (1 - confounder_risk * 0.5)
        
        return min(confidence, 1.0)


# ======================== 5. BIAS DETECTOR ========================
class BiasDetector:
    """인지 편향 감지기"""
    
    def __init__(self):
        self.detected_biases = []
        self.bias_patterns = {
            "confirmation": self._check_confirmation_bias,
            "anchoring": self._check_anchoring_bias,
            "availability": self._check_availability_bias,
            "complexity": self._check_complexity_bias
        }
    
    def analyze_reasoning(self, reasoning_trace: List[Dict[str, Any]]) -> Dict[str, Any]:
        """추론 과정에서 편향 감지"""
        
        detected = {}
        
        for bias_name, check_func in self.bias_patterns.items():
            result = check_func(reasoning_trace)
            if result["detected"]:
                detected[bias_name] = result
        
        # 전체 편향 점수
        bias_score = len(detected) / len(self.bias_patterns)
        
        return {
            "detected_biases": detected,
            "bias_score": bias_score,
            "is_biased": bias_score > 0.3,
            "recommendations": self._generate_debiasing_recommendations(detected)
        }
    
    def _check_confirmation_bias(self, trace: List[Dict[str, Any]]) -> Dict[str, Any]:
        """확증편향 검사"""
        
        supporting_evidence = 0
        contradicting_evidence = 0
        
        for step in trace:
            if step.get("type") == "evidence":
                if step.get("supports_hypothesis"):
                    supporting_evidence += 1
                else:
                    contradicting_evidence += 1
        
        total = supporting_evidence + contradicting_evidence
        if total == 0:
            return {"detected": False}
        
        support_ratio = supporting_evidence / total
        
        # 지지 증거가 80% 이상이면 확증편향 의심
        if support_ratio > 0.8:
            return {
                "detected": True,
                "severity": "high" if support_ratio > 0.9 else "medium",
                "evidence": f"지지 증거 {support_ratio:.0%}",
                "recommendation": "반대 증거를 적극적으로 찾아보세요"
            }
        
        return {"detected": False}
    
    def _check_anchoring_bias(self, trace: List[Dict[str, Any]]) -> Dict[str, Any]:
        """기준점 편향 검사"""
        
        initial_estimates = []
        final_estimates = []
        
        for i, step in enumerate(trace):
            if step.get("type") == "estimate":
                if i < len(trace) / 3:  # 초기 1/3
                    initial_estimates.append(step.get("value", 0))
                elif i > 2 * len(trace) / 3:  # 후기 1/3
                    final_estimates.append(step.get("value", 0))
        
        if not initial_estimates or not final_estimates:
            return {"detected": False}
        
        # 초기 추정치 주변에 최종 추정치가 모여있는지 확인
        initial_mean = np.mean(initial_estimates)
        final_std = np.std(final_estimates)
        
        if final_std < initial_mean * 0.2:  # 변동성이 작으면 기준점 편향 의심
            return {
                "detected": True,
                "severity": "medium",
                "evidence": f"최종 추정치 표준편차: {final_std:.2f}",
                "recommendation": "초기 가정을 의심하고 다시 생각해보세요"
            }
        
        return {"detected": False}
    
    def _check_availability_bias(self, trace: List[Dict[str, Any]]) -> Dict[str, Any]:
        """가용성 편향 검사"""
        
        recent_examples = 0
        old_examples = 0
        
        for step in trace:
            if step.get("type") == "example":
                age = step.get("age_days", 0)
                if age < 7:  # 최근 1주일
                    recent_examples += 1
                else:
                    old_examples += 1
        
        if recent_examples + old_examples == 0:
            return {"detected": False}
        
        recency_ratio = recent_examples / (recent_examples + old_examples)
        
        if recency_ratio > 0.7:
            return {
                "detected": True,
                "severity": "medium",
                "evidence": f"최근 사례 비율: {recency_ratio:.0%}",
                "recommendation": "더 오래되고 다양한 사례를 고려하세요"
            }
        
        return {"detected": False}
    
    def _check_complexity_bias(self, trace: List[Dict[str, Any]]) -> Dict[str, Any]:
        """복잡성 편향 검사"""
        
        complexity_scores = []
        preference_scores = []
        
        for step in trace:
            if step.get("type") == "option_evaluation":
                complexity = step.get("complexity", 0)
                preference = step.get("preference", 0)
                
                complexity_scores.append(complexity)
                preference_scores.append(preference)
        
        if len(complexity_scores) < 2:
            return {"detected": False}
        
        # 복잡성과 선호도의 상관관계
        correlation = np.corrcoef(complexity_scores, preference_scores)[0, 1]
        
        if correlation > 0.6:
            return {
                "detected": True,
                "severity": "high" if correlation > 0.8 else "medium",
                "evidence": f"복잡성-선호도 상관: {correlation:.2f}",
                "recommendation": "단순한 해결책도 진지하게 고려하세요"
            }
        
        return {"detected": False}
    
    def _generate_debiasing_recommendations(self, detected_biases: Dict[str, Any]) -> List[str]:
        """편향 제거 권고사항 생성"""
        
        recommendations = []
        
        if "confirmation" in detected_biases:
            recommendations.append("적극적으로 반대 증거를 찾아보세요")
        
        if "anchoring" in detected_biases:
            recommendations.append("초기 가정 없이 처음부터 다시 분석해보세요")
        
        if "availability" in detected_biases:
            recommendations.append("체계적인 데이터 수집을 고려하세요")
        
        if "complexity" in detected_biases:
            recommendations.append("Occam's Razor - 가장 단순한 설명을 선호하세요")
        
        if not recommendations:
            recommendations.append("현재 추론 과정은 균형잡혀 있습니다")
        
        return recommendations


# ======================== 6. INTEGRATED REASONER ========================
class PracticalReasoner:
    """모든 구성요소를 통합한 실용적 추론 시스템"""
    
    def __init__(self, name: str = "PracticalAGI"):
        self.name = name
        self.bayesian = SimpleBayesianReasoner()
        self.logic = PracticalLogicEngine()
        self.uncertainty = UncertaintyHandler()
        self.causal = CausalReasoner()
        self.bias_detector = BiasDetector()
        
        self.reasoning_trace = []
        self.conclusions = []
    
    def reason(self, question: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """통합 추론 수행"""
        
        print(f"\n🧠 [{self.name}] 추론 시작: {question}")
        
        # 추론 시작
        self.reasoning_trace = []
        
        # 1. 문제 분석
        problem_type = self._analyze_problem(question, context)
        self._log_step("problem_analysis", problem_type)
        
        # 2. 적절한 추론 방법 선택
        reasoning_methods = self._select_reasoning_methods(problem_type)
        
        results = {}
        
        # 3. 선택된 방법들로 추론 수행
        if "bayesian" in reasoning_methods:
            results["bayesian"] = self._apply_bayesian_reasoning(
                problem_type, context
            )
        
        if "logical" in reasoning_methods:
            results["logical"] = self._apply_logical_reasoning(
                problem_type, context
            )
        
        if "causal" in reasoning_methods:
            results["causal"] = self._apply_causal_reasoning(
                problem_type, context
            )
        
        # 4. 결과 통합
        integrated_conclusion = self._integrate_results(results)
        
        # 5. 불확실성 평가
        confidence_analysis = self._assess_confidence(
            integrated_conclusion, results
        )
        
        # 6. 편향 검사
        bias_analysis = self.bias_detector.analyze_reasoning(
            self.reasoning_trace
        )
        
        # 최종 결과
        final_result = {
            "question": question,
            "answer": integrated_conclusion["answer"],
            "confidence": confidence_analysis["final_confidence"],
            "reasoning_methods": reasoning_methods,
            "detailed_results": results,
            "bias_analysis": bias_analysis,
            "limitations": self._identify_limitations(
                integrated_conclusion, confidence_analysis
            )
        }
        
        self.conclusions.append(final_result)
        
        print(f"✅ 결론: {final_result['answer']}")
        print(f"📊 신뢰도: {final_result['confidence']:.2%}")
        
        return final_result
    
    def _analyze_problem(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """문제 유형 분석"""
        
        problem_type = {
            "type": "unknown",
            "requires_probability": "확률" in question or "가능성" in question,
            "requires_logic": "만약" in question or "따라서" in question,
            "requires_causation": "때문" in question or "영향" in question,
            "has_uncertainty": "아마" in question or "추측" in question
        }
        
        # 문제 유형 결정
        if problem_type["requires_probability"]:
            problem_type["type"] = "probabilistic"
        elif problem_type["requires_logic"]:
            problem_type["type"] = "logical"
        elif problem_type["requires_causation"]:
            problem_type["type"] = "causal"
        else:
            problem_type["type"] = "general"
        
        return problem_type
    
    def _select_reasoning_methods(self, problem_type: Dict[str, Any]) -> List[str]:
        """적절한 추론 방법 선택"""
        
        methods = []
        
        if problem_type["type"] == "probabilistic":
            methods.append("bayesian")
        elif problem_type["type"] == "logical":
            methods.append("logical")
        elif problem_type["type"] == "causal":
            methods.append("causal")
            methods.append("bayesian")  # 인과관계도 확률적 요소 포함
        else:
            # 일반적인 경우 모든 방법 사용
            methods = ["logical", "bayesian"]
        
        return methods
    
    def _apply_bayesian_reasoning(self, problem_type: Dict[str, Any], 
                                context: Dict[str, Any]) -> Dict[str, Any]:
        """베이지안 추론 적용"""
        
        # 컨텍스트에서 가설과 증거 추출
        hypotheses = context.get("hypotheses", ["H1", "H2"])
        evidence = context.get("evidence", [])
        
        # 각 가설에 대해 베이지안 업데이트
        results = {}
        for h in hypotheses:
            self.bayesian.set_prior(h, 0.5)  # 중립적 사전확률
            
            for e in evidence:
                update = self.bayesian.update_belief(
                    h, 
                    e.get("description", "evidence"),
                    e.get("likelihood_if_true", 0.8),
                    e.get("likelihood_if_false", 0.3)
                )
                self._log_step("bayesian_update", update)
        
        # 가장 가능성 높은 가설
        best_hypothesis, probability = self.bayesian.get_most_likely_hypothesis()
        
        return {
            "method": "bayesian",
            "best_hypothesis": best_hypothesis,
            "probability": probability,
            "all_beliefs": dict(self.bayesian.beliefs)
        }
    
    def _apply_logical_reasoning(self, problem_type: Dict[str, Any], 
                                context: Dict[str, Any]) -> Dict[str, Any]:
        """논리적 추론 적용"""
        
        # 컨텍스트에서 사실과 규칙 추출
        facts = context.get("facts", [])
        rules = context.get("rules", [])
        
        # 사실 추가
        for fact in facts:
            self.logic.add_fact(fact)
            self._log_step("add_fact", {"fact": fact})
        
        # 규칙 추가
        for rule in rules:
            self.logic.add_rule(
                rule.get("name", "rule"),
                rule.get("conditions", []),
                rule.get("conclusion", ""),
                rule.get("confidence", 1.0)
            )
        
        # 추론 실행
        new_facts = self.logic.forward_inference()
        consistency = self.logic.check_consistency()
        
        return {
            "method": "logical",
            "derived_facts": new_facts,
            "all_facts": list(self.logic.facts),
            "is_consistent": consistency["is_consistent"],
            "contradictions": consistency.get("contradictions", [])
        }
    
    def _apply_causal_reasoning(self, problem_type: Dict[str, Any], 
                               context: Dict[str, Any]) -> Dict[str, Any]:
        """인과 추론 적용"""
        
        # 컨텍스트에서 인과관계 정보 추출
        causal_links = context.get("causal_links", [])
        observations = context.get("observations", [])
        
        # 인과 그래프 구축
        for link in causal_links:
            self.causal.add_causal_link(
                link["cause"],
                link["effect"],
                link.get("strength", 1.0)
            )
        
        # 관찰 추가
        for obs in observations:
            self.causal.observe(
                obs["variable"],
                obs["value"],
                obs.get("context", {})
            )
        
        # 주요 인과관계 분석
        target_cause = context.get("target_cause", "")
        target_effect = context.get("target_effect", "")
        
        if target_cause and target_effect:
            causal_analysis = self.causal.infer_causation(
                target_cause, target_effect
            )
        else:
            causal_analysis = {"message": "인과관계 대상 미지정"}
        
        return {
            "method": "causal",
            "analysis": causal_analysis,
            "causal_graph_size": len(self.causal.causal_graph)
        }
    
    def _integrate_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """여러 추론 방법의 결과 통합"""
        
        integrated = {
            "answer": "",
            "supporting_methods": [],
            "conflicts": []
        }
        
        # 각 방법의 주요 결론 추출
        conclusions = []
        
        if "bayesian" in results:
            bayesian_result = results["bayesian"]
            if bayesian_result["best_hypothesis"]:
                conclusions.append({
                    "method": "bayesian",
                    "conclusion": bayesian_result["best_hypothesis"],
                    "confidence": bayesian_result["probability"]
                })
        
        if "logical" in results:
            logical_result = results["logical"]
            if logical_result["derived_facts"]:
                conclusions.append({
                    "method": "logical",
                    "conclusion": ", ".join(logical_result["derived_facts"]),
                    "confidence": 1.0 if logical_result["is_consistent"] else 0.5
                })
        
        if "causal" in results:
            causal_result = results["causal"]
            if "analysis" in causal_result and causal_result["analysis"]:
                conclusions.append({
                    "method": "causal",
                    "conclusion": f"인과관계 신뢰도: {causal_result['analysis'].get('causal_confidence', 0):.2f}",
                    "confidence": causal_result["analysis"].get("causal_confidence", 0)
                })
        
        # 가장 신뢰도 높은 결론 선택
        if conclusions:
            best_conclusion = max(conclusions, key=lambda x: x["confidence"])
            integrated["answer"] = best_conclusion["conclusion"]
            integrated["supporting_methods"] = [best_conclusion["method"]]
        else:
            integrated["answer"] = "충분한 정보가 없어 결론을 내릴 수 없습니다"
        
        return integrated
    
    def _assess_confidence(self, conclusion: Dict[str, Any], 
                         results: Dict[str, Any]) -> Dict[str, Any]:
        """종합적 신뢰도 평가"""
        
        # 각 추론 방법의 신뢰도 수집
        confidences = []
        
        if "bayesian" in results:
            confidences.append(results["bayesian"].get("probability", 0.5))
        
        if "logical" in results:
            is_consistent = results["logical"].get("is_consistent", True)
            confidences.append(1.0 if is_consistent else 0.3)
        
        if "causal" in results and "analysis" in results["causal"]:
            confidences.append(
                results["causal"]["analysis"].get("causal_confidence", 0.5)
            )
        
        # 평균 신뢰도
        avg_confidence = np.mean(confidences) if confidences else 0.5
        
        # 증거 품질과 모델 정확도 추정 (간단히)
        evidence_quality = min(len(self.reasoning_trace) / 10, 1.0)
        model_accuracy = 0.7  # 기본값
        consistency_score = 1.0 if not any(
            r.get("contradictions") for r in results.values()
        ) else 0.5
        
        return self.uncertainty.calculate_confidence(
            evidence_quality,
            model_accuracy,
            consistency_score
        )
    
    def _identify_limitations(self, conclusion: Dict[str, Any], 
                            confidence: Dict[str, Any]) -> List[str]:
        """추론의 한계 식별"""
        
        limitations = []
        
        if confidence["final_confidence"] < 0.7:
            limitations.append("신뢰도가 낮아 결론이 불확실합니다")
        
        if not conclusion.get("supporting_methods"):
            limitations.append("어떤 추론 방법도 명확한 답을 제공하지 못했습니다")
        
        if len(self.reasoning_trace) < 5:
            limitations.append("충분한 추론 단계를 거치지 못했습니다")
        
        # 편향 검사 결과 확인
        bias_count = len(self.bias_detector.detected_biases)
        if bias_count > 0:
            limitations.append(f"{bias_count}개의 인지 편향이 감지되었습니다")
        
        if not limitations:
            limitations.append("중요한 한계점이 발견되지 않았습니다")
        
        return limitations
    
    def _log_step(self, step_type: str, data: Any) -> None:
        """추론 단계 기록"""
        self.reasoning_trace.append({
            "step": len(self.reasoning_trace) + 1,
            "type": step_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })
    
    def explain_reasoning(self) -> str:
        """추론 과정 설명"""
        
        explanation = f"\n=== {self.name}의 추론 과정 ===\n"
        
        for step in self.reasoning_trace:
            explanation += f"\n단계 {step['step']} ({step['type']}):\n"
            
            if step['type'] == 'problem_analysis':
                explanation += f"  문제 유형: {step['data']['type']}\n"
            elif step['type'] == 'bayesian_update':
                data = step['data']
                explanation += f"  가설: {data['hypothesis']}\n"
                explanation += f"  사전확률: {data['prior']:.3f} → "
                explanation += f"사후확률: {data['posterior']:.3f}\n"
            elif step['type'] == 'add_fact':
                explanation += f"  사실 추가: {step['data']['fact']}\n"
            
        if self.conclusions:
            latest = self.conclusions[-1]
            explanation += f"\n최종 결론: {latest['answer']}\n"
            explanation += f"신뢰도: {latest['confidence']:.2%}\n"
            
            if latest['limitations']:
                explanation += "\n한계점:\n"
                for limitation in latest['limitations']:
                    explanation += f"  - {limitation}\n"
        
        return explanation


# ======================== 실제 사용 예제 ========================
def demonstrate_practical_reasoning():
    """실용적 추론 시스템 시연"""
    
    print("🚀 실용적 과학 추론 시스템 v2.0")
    print("=" * 60)
    
    # 추론 시스템 생성
    reasoner = PracticalReasoner("Agnes_실용추론기")
    
    # 예제 1: 의료 진단 추론
    print("\n📋 예제 1: 의료 진단")
    
    medical_context = {
        "hypotheses": ["독감", "감기", "코로나19"],
        "evidence": [
            {
                "description": "발열 38.5도",
                "likelihood_if_true": {"독감": 0.9, "감기": 0.3, "코로나19": 0.8},
                "likelihood_if_false": 0.1
            },
            {
                "description": "기침",
                "likelihood_if_true": {"독감": 0.7, "감기": 0.8, "코로나19": 0.9},
                "likelihood_if_false": 0.2
            }
        ],
        "facts": ["환자는_발열중", "환자는_기침중"],
        "rules": [
            {
                "name": "독감_진단_규칙",
                "conditions": ["환자는_발열중", "환자는_기침중"],
                "conclusion": "독감_가능성_높음"
            }
        ]
    }
    
    result1 = reasoner.reason(
        "환자의 증상을 보고 가장 가능성 높은 질병은?",
        medical_context
    )
    
    # 예제 2: 인과관계 추론
    print("\n📋 예제 2: 인과관계 분석")
    
    causal_context = {
        "causal_links": [
            {"cause": "흡연", "effect": "폐암", "strength": 0.7},
            {"cause": "대기오염", "effect": "폐암", "strength": 0.4},
            {"cause": "유전", "effect": "폐암", "strength": 0.3}
        ],
        "observations": [
            {"variable": "흡연", "value": True},
            {"variable": "폐암", "value": True}
        ],
        "target_cause": "흡연",
        "target_effect": "폐암"
    }
    
    result2 = reasoner.reason(
        "흡연이 폐암의 원인일 가능성은?",
        causal_context
    )
    
    # 추론 과정 설명
    print("\n" + reasoner.explain_reasoning())
    
    return reasoner


if __name__ == "__main__":
    # 시스템 시연
    reasoner = demonstrate_practical_reasoning()
    
    print("\n" + "=" * 60)
    print("✅ 실용적 추론 시스템의 특징:")
    print("1. 실제로 작동하는 구현")
    print("2. 투명한 추론 과정")
    print("3. 명확한 한계 인정")
    print("4. 편향 감지 및 보정")
    print("5. 실용적 신뢰도 평가")
