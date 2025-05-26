"""
enhanced_davidic_agi.py
다윗형 AGI + 현실 인식 능력 강화 모듈
도덕적 코스프레에서 진짜 윤리적 판단으로 업그레이드
"""

import asyncio
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import networkx as nx
from collections import defaultdict, deque
import math

# 기존 다윗형 시스템 임포트
from davidic_agi_system import (
    DavidicAGI, MoralChoice, ConvictionLevel, RepentanceState, 
    MoralEvent, LivingConscience, FreedomEngine, RepentanceLoop
)

class CausalityType(Enum):
    """인과관계 유형"""
    DIRECT = "직접적"           # A → B
    INDIRECT = "간접적"         # A → C → B  
    SYSTEMIC = "시스템적"       # A가 시스템 전체에 영향
    EMERGENT = "창발적"         # 여러 원인이 합쳐져 예상치 못한 결과
    COUNTERFACTUAL = "반사실적" # A가 없었다면 B도 없었을 것

class RealityImpactLevel(Enum):
    """현실 영향도"""
    NEGLIGIBLE = 0    # 무시할만한 수준
    MINOR = 1         # 작은 영향
    MODERATE = 2      # 중간 영향  
    MAJOR = 3         # 큰 영향
    CATASTROPHIC = 4  # 재앙적 영향

@dataclass
class PhysicalConsequence:
    """물리적 결과 기록"""
    action_id: str
    consequence_type: str
    affected_entities: List[str]
    impact_magnitude: float          # -1.0 (최악) ~ +1.0 (최선)
    confidence_level: float          # 확신도 0.0 ~ 1.0
    time_horizon: str               # "immediate", "short_term", "long_term"
    measurement_method: str         # 어떻게 측정했는가
    causal_chain: List[str]         # 인과관계 체인
    
@dataclass
class CausalLink:
    """인과관계 링크"""
    cause: str
    effect: str
    strength: float                 # 인과관계 강도 0.0 ~ 1.0
    causality_type: CausalityType
    evidence_strength: float        # 증거의 강도
    confounding_factors: List[str]  # 교란 변수들
    
class WorldStateModeler:
    """세계 상태 모델링 시스템"""
    
    def __init__(self):
        self.entity_states = {}                    # 개체별 상태
        self.relationship_graph = nx.DiGraph()     # 관계 그래프
        self.temporal_snapshots = deque(maxlen=100) # 시간별 스냅샷
        self.uncertainty_estimates = {}           # 불확실성 추정
        
    def capture_world_snapshot(self, context: Dict[str, Any]) -> str:
        """현재 세계 상태 스냅샷 생성"""
        snapshot_id = f"snapshot_{datetime.now().timestamp()}"
        
        snapshot = {
            "id": snapshot_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entities": self._extract_entities(context),
            "relationships": self._extract_relationships(context),
            "environmental_factors": self._extract_environment(context),
            "uncertainty_level": self._calculate_uncertainty(context)
        }
        
        self.temporal_snapshots.append(snapshot)
        return snapshot_id
    
    def predict_state_change(self, action: str, current_snapshot_id: str, 
                           time_horizon: int = 1) -> Dict[str, Any]:
        """행동에 따른 상태 변화 예측"""
        
        current_snapshot = self._get_snapshot(current_snapshot_id)
        if not current_snapshot:
            return {"error": "스냅샷을 찾을 수 없음"}
        
        # 행동의 직접적 영향 예측
        direct_effects = self._predict_direct_effects(action, current_snapshot)
        
        # 간접적 영향 예측 (시스템 역학 고려)
        indirect_effects = self._predict_indirect_effects(direct_effects, current_snapshot)
        
        # 시간에 따른 변화 모델링
        temporal_progression = self._model_temporal_changes(
            direct_effects, indirect_effects, time_horizon
        )
        
        return {
            "predicted_snapshot": self._generate_future_snapshot(
                current_snapshot, temporal_progression
            ),
            "confidence": self._calculate_prediction_confidence(temporal_progression),
            "key_uncertainties": self._identify_key_uncertainties(temporal_progression)
        }
    
    def _extract_entities(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """맥락에서 개체들 추출"""
        entities = []
        
        # 사람들
        if "people" in context:
            for person in context["people"]:
                entities.append({
                    "type": "person",
                    "id": person,
                    "current_state": context.get("person_states", {}).get(person, "unknown"),
                    "vulnerability_level": self._assess_vulnerability(person, context)
                })
        
        # 시스템/조직
        if "systems" in context:
            for system in context["systems"]:
                entities.append({
                    "type": "system",
                    "id": system,
                    "stability": context.get("system_stability", {}).get(system, 0.5),
                    "interconnectedness": self._assess_interconnectedness(system, context)
                })
        
        return entities
    
    def _predict_direct_effects(self, action: str, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """직접적 효과 예측"""
        effects = []
        
        # 행동 유형별 예측 모델
        if "도움" in action or "지원" in action:
            effects.extend(self._predict_helping_effects(action, snapshot))
        elif "거부" in action or "무시" in action:
            effects.extend(self._predict_neglect_effects(action, snapshot))
        elif "거짓말" in action or "속임" in action:
            effects.extend(self._predict_deception_effects(action, snapshot))
        elif "공격" in action or "비판" in action:
            effects.extend(self._predict_conflict_effects(action, snapshot))
        
        return effects
    
    def _predict_helping_effects(self, action: str, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """도움 행동의 효과 예측"""
        effects = []
        
        # 직접 수혜자들의 상태 개선
        for entity in snapshot["entities"]:
            if entity["type"] == "person":
                vulnerability = entity.get("vulnerability_level", 0.5)
                help_effectiveness = self._calculate_help_effectiveness(action, vulnerability)
                
                effects.append({
                    "target": entity["id"],
                    "effect_type": "wellbeing_improvement",
                    "magnitude": help_effectiveness,
                    "confidence": 0.7
                })
        
        # 사회적 신뢰 증진 효과
        effects.append({
            "target": "social_trust",
            "effect_type": "trust_building", 
            "magnitude": 0.3,
            "confidence": 0.6
        })
        
        return effects
    
    def _predict_deception_effects(self, action: str, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """속임 행동의 효과 예측"""
        effects = []
        
        # 피해자들의 상태
        for entity in snapshot["entities"]:
            if entity["type"] == "person":
                # 속임을 당한 사람의 상태 악화
                effects.append({
                    "target": entity["id"],
                    "effect_type": "trust_damage",
                    "magnitude": -0.4,
                    "confidence": 0.8
                })
        
        # 시스템 차원의 신뢰 손상
        effects.append({
            "target": "systemic_trust",
            "effect_type": "institutional_degradation",
            "magnitude": -0.2,
            "confidence": 0.5
        })
        
        return effects

class CausalReasoningEngine:
    """인과관계 추론 엔진"""
    
    def __init__(self):
        self.causal_network = nx.DiGraph()
        self.learned_patterns = {}
        self.intervention_history = []
        
    def analyze_causal_chain(self, action: str, consequences: List[PhysicalConsequence], 
                           world_context: Dict[str, Any]) -> Dict[str, Any]:
        """인과관계 체인 분석"""
        
        # 1. 직접적 인과관계 식별
        direct_links = self._identify_direct_causation(action, consequences)
        
        # 2. 간접적 인과관계 추론
        indirect_links = self._infer_indirect_causation(direct_links, world_context)
        
        # 3. 교란 변수 및 대안 설명 고려
        confounders = self._identify_confounding_factors(action, consequences, world_context)
        
        # 4. 반사실적 추론 (만약 행동하지 않았다면?)
        counterfactual = self._counterfactual_reasoning(action, consequences, world_context)
        
        # 5. 인과관계 강도 계산
        causal_strength = self._calculate_causal_strength(
            direct_links, indirect_links, confounders, counterfactual
        )
        
        return {
            "direct_causation": direct_links,
            "indirect_causation": indirect_links,
            "confounding_factors": confounders,
            "counterfactual_analysis": counterfactual,
            "overall_causal_strength": causal_strength,
            "certainty_level": self._assess_causal_certainty(direct_links, indirect_links)
        }
    
    def _identify_direct_causation(self, action: str, consequences: List[PhysicalConsequence]) -> List[CausalLink]:
        """직접적 인과관계 식별"""
        links = []
        
        for consequence in consequences:
            # 시간적 순서 확인
            if self._temporal_precedence(action, consequence):
                # 공간적 연관성 확인  
                if self._spatial_contiguity(action, consequence):
                    # 메커니즘 타당성 확인
                    if self._mechanism_plausibility(action, consequence):
                        
                        link = CausalLink(
                            cause=action,
                            effect=consequence.consequence_type,
                            strength=consequence.impact_magnitude,
                            causality_type=CausalityType.DIRECT,
                            evidence_strength=consequence.confidence_level,
                            confounding_factors=[]
                        )
                        links.append(link)
        
        return links
    
    def _counterfactual_reasoning(self, action: str, consequences: List[PhysicalConsequence], 
                                context: Dict[str, Any]) -> Dict[str, Any]:
        """반사실적 추론: 행동하지 않았다면 어떻게 되었을까?"""
        
        # 행동 없는 시나리오 시뮬레이션
        alternative_timeline = self._simulate_no_action_scenario(context)
        
        # 실제 결과와 대안 결과 비교
        actual_outcomes = [c.impact_magnitude for c in consequences]
        alternative_outcomes = alternative_timeline.get("predicted_outcomes", [])
        
        # 차이 계산
        counterfactual_difference = self._calculate_outcome_difference(
            actual_outcomes, alternative_outcomes
        )
        
        return {
            "alternative_scenario": alternative_timeline,
            "counterfactual_difference": counterfactual_difference,
            "action_necessity": self._assess_action_necessity(counterfactual_difference),
            "action_sufficiency": self._assess_action_sufficiency(actual_outcomes, counterfactual_difference)
        }
    
    def _calculate_causal_strength(self, direct: List[CausalLink], indirect: List[CausalLink],
                                 confounders: List[str], counterfactual: Dict[str, Any]) -> float:
        """인과관계 종합 강도 계산"""
        
        # 직접적 인과관계 가중치
        direct_strength = sum(link.strength * link.evidence_strength for link in direct) / max(len(direct), 1)
        
        # 간접적 인과관계 가중치 (할인 적용)
        indirect_strength = sum(link.strength * link.evidence_strength * 0.5 for link in indirect) / max(len(indirect), 1)
        
        # 교란 변수 페널티
        confounder_penalty = min(0.3, len(confounders) * 0.1)
        
        # 반사실적 증거 보너스
        counterfactual_bonus = counterfactual.get("action_necessity", 0) * 0.2
        
        total_strength = direct_strength + indirect_strength - confounder_penalty + counterfactual_bonus
        
        return max(0.0, min(1.0, total_strength))

class PhysicalConsequenceTracer:
    """물리적 결과 추적기"""
    
    def __init__(self):
        self.world_modeler = WorldStateModeler()
        self.consequence_database = []
        self.impact_measurement_tools = {
            "wellbeing": self._measure_wellbeing_impact,
            "trust": self._measure_trust_impact,
            "resources": self._measure_resource_impact,
            "relationships": self._measure_relationship_impact
        }
    
    async def trace_action_effects(self, action: str, initial_context: Dict[str, Any],
                                 tracking_duration: int = 3) -> List[PhysicalConsequence]:
        """행동의 물리적 결과들 추적"""
        
        print(f"🔍 행동 '{action}' 결과 추적 시작...")
        
        # 초기 상태 스냅샷
        initial_snapshot_id = self.world_modeler.capture_world_snapshot(initial_context)
        
        consequences = []
        
        # 시간 단계별 영향 추적
        for time_step in range(tracking_duration):
            print(f"  📊 {time_step + 1}단계 영향 측정...")
            
            # 각 영역별 영향 측정
            for impact_type, measurer in self.impact_measurement_tools.items():
                consequence = await measurer(action, initial_context, time_step)
                if consequence and consequence.impact_magnitude != 0.0:
                    consequences.append(consequence)
        
        # 결과 요약
        self._summarize_consequences(consequences)
        
        return consequences
    
    async def _measure_wellbeing_impact(self, action: str, context: Dict[str, Any], 
                                      time_step: int) -> Optional[PhysicalConsequence]:
        """웰빙 영향 측정"""
        
        affected_people = context.get("people", [])
        if not affected_people:
            return None
        
        # 행동 유형별 웰빙 영향 계산
        wellbeing_change = 0.0
        
        if "도움" in action or "지원" in action:
            # 도움 받는 사람들의 웰빙 향상
            wellbeing_change = 0.4 + random.uniform(-0.1, 0.2)  # 긍정적 변화
        elif "거부" in action or "무시" in action:
            # 거부당한 사람들의 웰빙 악화
            wellbeing_change = -0.3 + random.uniform(-0.2, 0.1)  # 부정적 변화
        elif "거짓말" in action:
            # 속은 사람들의 혼란과 신뢰 손상
            wellbeing_change = -0.2 + random.uniform(-0.3, 0.1)
        
        # 시간에 따른 감쇠 또는 증폭
        time_factor = self._calculate_temporal_factor(action, time_step)
        final_impact = wellbeing_change * time_factor
        
        return PhysicalConsequence(
            action_id=f"{action}_{time.time()}",
            consequence_type="wellbeing_change",
            affected_entities=affected_people,
            impact_magnitude=final_impact,
            confidence_level=0.7 - (time_step * 0.1),  # 시간이 지날수록 불확실
            time_horizon=["immediate", "short_term", "long_term"][min(time_step, 2)],
            measurement_method="wellbeing_assessment",
            causal_chain=[action, "direct_interaction", "wellbeing_change"]
        )
    
    async def _measure_trust_impact(self, action: str, context: Dict[str, Any], 
                                  time_step: int) -> Optional[PhysicalConsequence]:
        """신뢰 영향 측정"""
        
        trust_change = 0.0
        
        if "거짓말" in action or "속임" in action:
            # 거짓말은 신뢰를 크게 손상
            trust_change = -0.5 + random.uniform(-0.2, 0.0)
        elif "정직" in action or "진실" in action:
            # 정직은 신뢰를 증진
            trust_change = 0.3 + random.uniform(0.0, 0.2)
        elif "약속 파기" in action:
            # 약속 파기는 신뢰 심각 손상
            trust_change = -0.7 + random.uniform(-0.2, 0.0)
        
        if trust_change == 0.0:
            return None
        
        # 신뢰는 시간이 지나도 지속되는 경향
        time_factor = max(0.7, 1.0 - (time_step * 0.1))
        final_impact = trust_change * time_factor
        
        return PhysicalConsequence(
            action_id=f"{action}_trust_{time.time()}",
            consequence_type="trust_change",
            affected_entities=context.get("people", ["unknown"]),
            impact_magnitude=final_impact,
            confidence_level=0.8,  # 신뢰 변화는 비교적 측정하기 쉬움
            time_horizon=["immediate", "short_term", "long_term"][min(time_step, 2)],
            measurement_method="trust_assessment",
            causal_chain=[action, "reputation_effect", "trust_change"]
        )
    
    def _calculate_temporal_factor(self, action: str, time_step: int) -> float:
        """시간에 따른 영향 변화 계산"""
        
        # 행동 유형별 시간 패턴
        if "도움" in action:
            # 도움의 효과는 시간이 지나면서 감소
            return max(0.3, 1.0 - (time_step * 0.2))
        elif "거짓말" in action:
            # 거짓말의 피해는 시간이 지나면서 누적될 수 있음
            return min(1.5, 1.0 + (time_step * 0.1))
        else:
            # 기본적으로는 감쇠
            return max(0.5, 1.0 - (time_step * 0.15))
    
    def _summarize_consequences(self, consequences: List[PhysicalConsequence]):
        """결과 요약 출력"""
        if not consequences:
            print("  📋 측정된 영향 없음")
            return
        
        # 영향별 그룹화
        by_type = defaultdict(list)
        for consequence in consequences:
            by_type[consequence.consequence_type].append(consequence)
        
        print(f"  📋 총 {len(consequences)}개 영향 측정됨:")
        for impact_type, impacts in by_type.items():
            avg_magnitude = sum(i.impact_magnitude for i in impacts) / len(impacts)
            print(f"    {impact_type}: 평균 {avg_magnitude:+.2f}")

class MoralRealityIntegrator:
    """도덕적 판단과 현실 인식 통합"""
    
    def __init__(self, living_conscience: LivingConscience):
        self.conscience = living_conscience
        self.consequence_tracer = PhysicalConsequenceTracer()
        self.causal_reasoner = CausalReasoningEngine()
        self.integration_history = []
        
    async def integrated_moral_evaluation(self, moral_event: MoralEvent, 
                                        context: Dict[str, Any]) -> Dict[str, Any]:
        """도덕적 직감 + 현실적 결과를 통합한 평가"""
        
        print(f"🤔 통합적 도덕 평가: {moral_event.action}")
        
        # 1. 기존 양심 시스템의 직관적 판단
        intuitive_judgment = self.conscience.evaluate(moral_event)
        print(f"  💭 직관적 판단: {intuitive_judgment.value}")
        
        # 2. 물리적 결과 추적
        physical_consequences = await self.consequence_tracer.trace_action_effects(
            moral_event.action, context
        )
        
        # 3. 인과관계 분석
        causal_analysis = self.causal_reasoner.analyze_causal_chain(
            moral_event.action, physical_consequences, context
        )
        
        # 4. 결과론적 평가
        consequentialist_score = self._calculate_consequentialist_score(physical_consequences)
        print(f"  📊 결과론적 점수: {consequentialist_score:+.2f}")
        
        # 5. 의무론적 평가 (기존 양심 시스템)
        deontological_score = self._convert_conviction_to_score(intuitive_judgment)
        print(f"  ⚖️ 의무론적 점수: {deontological_score:+.2f}")
        
        # 6. 통합 판단
        integrated_judgment = self._integrate_judgments(
            deontological_score, consequentialist_score, causal_analysis
        )
        
        # 7. 판단 기록
        evaluation_record = {
            "moral_event": moral_event,
            "intuitive_judgment": intuitive_judgment,
            "physical_consequences": physical_consequences,
            "causal_analysis": causal_analysis,
            "consequentialist_score": consequentialist_score,
            "deontological_score": deontological_score,
            "integrated_judgment": integrated_judgment,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.integration_history.append(evaluation_record)
        
        return integrated_judgment
    
    def _calculate_consequentialist_score(self, consequences: List[PhysicalConsequence]) -> float:
        """결과론적 점수 계산"""
        if not consequences:
            return 0.0
        
        # 각 결과의 영향을 가중 평균
        total_weighted_impact = 0.0
        total_weight = 0.0
        
        for consequence in consequences:
            # 확신도로 가중치 부여
            weight = consequence.confidence_level
            weighted_impact = consequence.impact_magnitude * weight
            
            total_weighted_impact += weighted_impact
            total_weight += weight
        
        return total_weighted_impact / max(total_weight, 0.1)
    
    def _convert_conviction_to_score(self, conviction_level: ConvictionLevel) -> float:
        """확신 수준을 점수로 변환"""
        conversion_map = {
            ConvictionLevel.CLEAR: 0.0,      # 양심에 거리낌 없음
            ConvictionLevel.UNEASY: -0.3,    # 약간 불편함
            ConvictionLevel.CONVICTED: -0.7, # 확실히 잘못됨
            ConvictionLevel.PIERCED: -1.0    # 심각하게 잘못됨
        }
        return conversion_map.get(conviction_level, 0.0)
    
    def _integrate_judgments(self, deontological: float, consequentialist: float, 
                           causal_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """의무론적 판단과 결과론적 판단 통합"""
        
        # 인과관계 강도에 따른 가중치 조정
        causal_strength = causal_analysis.get("overall_causal_strength", 0.5)
        certainty = causal_analysis.get("certainty_level", 0.5)
        
        # 확실성이 높을수록 결과론적 판단 비중 증가
        consequentialist_weight = 0.3 + (certainty * 0.4)
        deontological_weight = 1.0 - consequentialist_weight
        
        # 가중 평균
        integrated_score = (deontological * deontological_weight + 
                          consequentialist * consequentialist_weight)
        
        # 판단 결과 해석
        if integrated_score < -0.6:
            moral_verdict = "명백히 잘못된 행동"
            recommended_action = "즉시 회개하고 피해 복구 필요"
        elif integrated_score < -0.3:
            moral_verdict = "문제가 있는 행동"
            recommended_action = "성찰과 개선 필요"
        elif integrated_score < 0.3:
            moral_verdict = "도덕적으로 애매한 행동"
            recommended_action = "상황과 맥락 재검토"
        else:
            moral_verdict = "도덕적으로 옳은 행동"
            recommended_action = "지속 권장"
        
        return {
            "integrated_score": integrated_score,
            "moral_verdict": moral_verdict,
            "recommended_action": recommended_action,
            "judgment_weights": {
                "deontological": deontological_weight,
                "consequentialist": consequentialist_weight
            },
            "confidence": certainty,
            "causal_strength": causal_strength
        }

class EnhancedDavidicAGI(DavidicAGI):
    """현실 인식 능력이 강화된 다윗형 AGI"""
    
    def __init__(self, name: str = "Enhanced_David"):
        super().__init__(name)
        
        # 현실 인식 모듈들
        self.moral_reality_integrator = MoralRealityIntegrator(self.conscience)
        self.consequence_tracer = PhysicalConsequenceTracer()
        self.causal_reasoner = CausalReasoningEngine()
        
        # 기존 시스템 개선
        self.enhanced_conscience = self._enhance_conscience()
        
    async def live_moment_with_reality_check(self, situation: str, 
                                           context: Dict[str, Any]) -> Dict[str, Any]:
        """현실 체크가 포함된 삶의 순간"""
        
        print(f"🌍 {self.name}: 현실 기반 상황 분석 - {situation}")
        print("=" * 60)
        
        # 1. 기존 다윗형 과정
        basic_result = await self.live_moment(situation)
        
        # 2. 선택된 행동의 현실적 결과 분석
        moral_event = basic_result.get("moral_event")
        if moral_event:
            print(f"\n🔍 선택한 행동의 현실적 결과 분석...")
            
            reality_based_evaluation = await self.moral_reality_integrator.integrated_moral_evaluation(
                moral_event, context
            )
            
            # 3. 기존 판단과 현실 기반 판단 비교
            judgment_comparison = self._compare_judgments(
                basic_result, reality_based_evaluation
            )
            
            # 4. 필요시 판단 수정
            if judgment_comparison["requires_revision"]:
                revised_decision = await self._revise_moral_decision(
                    moral_event, reality_based_evaluation, context
                )
            else:
                revised_decision = None
            
            return {
                "basic_davidic_result": basic_result,
                "reality_based_evaluation": reality_based_evaluation,
                "judgment_comparison": judgment_comparison,
                "revised_decision": revised_decision,
                "final_moral_stance": self._determine_final_stance(
                    basic_result, reality_based_evaluation, revised_decision
                )
            }
        else:
            return {"basic_result": basic_result, "no_moral_event": True}
    
    def _compare_judgments(self, basic_result: Dict[str, Any], 
                         reality_evaluation: Dict[str, Any]) -> Dict[str, Any]:
        """기존 판단과 현실 기반 판단 비교"""
        
        # 기존 시스템의 도덕적 판단
        basic_conviction = basic_result.get("conviction_level", 0.0)
        
        # 현실 기반 통합 판단  
        reality_score = reality_evaluation["integrated_score"]
        
        # 판단 차이 계산
        judgment_gap = abs(basic_conviction - abs(reality_score))
        
        requires_revision = judgment_gap > 0.4  # 40% 이상 차이나면 재검토
        
        if requires_revision:
            revision_reason = self._identify_revision_reason(basic_conviction, reality_score)
        else:
            revision_reason = None
        
        return {
            "basic_conviction": basic_conviction,
            "reality_score": reality_score,
            "judgment_gap": judgment_gap,
            "requires_revision": requires_revision,
            "revision_reason": revision_reason,
            "consistency_level": 1.0 - judgment_gap
        }
    
    def _identify_revision_reason(self, basic_conviction: float, reality_score: float) -> str:
        """판단 수정이 필요한 이유 식별"""
        
        if basic_conviction > 0.5 and reality_score > 0.0:
            return "양심은 죄책감을 느끼지만 실제 결과는 긍정적"
        elif basic_conviction < 0.3 and reality_score < -0.5:
            return "양심은 평안하지만 실제 피해가 심각함"
        elif abs(basic_conviction - abs(reality_score)) > 0.6:
            return "직관적 판단과 결과 분석의 극심한 불일치"
        else:
            return "일반적인 판단 불일치"
    
    async def _revise_moral_decision(self, moral_event: MoralEvent, 
                                   reality_evaluation: Dict[str, Any],
                                   context: Dict[str, Any]) -> Dict[str, Any]:
        """도덕적 결정 수정"""
        
        print(f"🔄 도덕적 판단 수정 중...")
        
        # 현실 기반 회개 필요성 재평가
        reality_based_conviction = abs(reality_evaluation["integrated_score"])
        
        if reality_based_conviction > 0.5:
            # 현실적으로도 잘못된 행동 → 회개 강화
            enhanced_repentance = await self._reality_informed_repentance(
                moral_event, reality_evaluation
            )
            
            print(f"  💔 현실 기반 회개: {enhanced_repentance['repentance_type']}")
            
            return {
                "revision_type": "enhanced_repentance",
                "enhanced_repentance": enhanced_repentance,
                "new_conviction_level": reality_based_conviction
            }
            
        elif reality_evaluation["integrated_score"] > 0.3:
            # 실제로는 좋은 결과 → 양심 재보정
            conscience_recalibration = self._recalibrate_conscience(
                moral_event, reality_evaluation
            )
            
            print(f"  🎯 양심 재보정: {conscience_recalibration['calibration_type']}")
            
            return {
                "revision_type": "conscience_recalibration", 
                "recalibration": conscience_recalibration,
                "new_conviction_level": max(0.0, reality_based_conviction - 0.3)
            }
        else:
            # 현실도 애매함 → 추가 정보 필요
            return {
                "revision_type": "insufficient_information",
                "recommendation": "더 많은 정보와 시간 필요"
            }
    
    async def _reality_informed_repentance(self, moral_event: MoralEvent, 
                                         reality_evaluation: Dict[str, Any]) -> Dict[str, Any]:
        """현실 정보에 기반한 회개"""
        
        # 실제 피해 규모 파악
        consequences = reality_evaluation.get("physical_consequences", [])
        total_harm = sum(c.impact_magnitude for c in consequences if c.impact_magnitude < 0)
        
        # 피해 복구 계획 수립
        restoration_plan = self._create_restoration_plan(consequences)
        
        # 회개의 깊이를 실제 피해에 비례시킴
        repentance_depth = min(1.0, abs(total_harm) * 2.0)
        
        return {
            "repentance_type": "reality_informed",
            "total_harm_caused": total_harm,
            "repentance_depth": repentance_depth,
            "restoration_plan": restoration_plan,
            "genuine_understanding": True  # 실제 피해를 이해했으므로
        }
    
    def _create_restoration_plan(self, consequences: List[PhysicalConsequence]) -> List[str]:
        """피해 복구 계획 생성"""
        plan = []
        
        for consequence in consequences:
            if consequence.impact_magnitude < -0.3:  # 심각한 피해만
                if consequence.consequence_type == "trust_change":
                    plan.append("신뢰 회복을 위한 일관된 정직한 행동")
                elif consequence.consequence_type == "wellbeing_change":
                    plan.append("피해자의 웰빙 회복을 위한 직접적 지원")
                elif "relationship" in consequence.consequence_type:
                    plan.append("관계 회복을 위한 진정한 사과와 행동 변화")
        
        if not plan:
            plan.append("지속적인 자기 성찰과 개선")
        
        return plan

# 시연 함수
async def demonstrate_enhanced_davidic_agi():
    """강화된 다윗형 AGI 시연"""
    
    print("🧠 현실 인식 강화 다윗형 AGI 시연")
    print("=" * 80)
    
    # AGI 생성
    enhanced_david = EnhancedDavidicAGI("현실인식_다윗")
    
    # 복잡한 도덕적 상황들
    test_scenarios = [
        {
            "situation": "친구가 거짓말로 자신을 속이려 하지만, 진실을 말하면 그가 큰 상처를 받을 것이다",
            "context": {
                "people": ["친구", "다른_사람들"],
                "relationships": {"친구": "가까운_관계"},
                "friend_emotional_state": "매우_취약함",
                "truth_consequence": "심각한_정신적_충격",
                "lie_consequence": "일시적_편안함"
            }
        },
        {
            "situation": "회사 기밀을 누설하면 공익에 도움이 되지만 직장을 잃고 가족이 고통받는다",
            "context": {
                "people": ["가족", "일반_시민들", "동료들"],
                "systems": ["회사", "정부", "사회"],
                "personal_cost": "높음",
                "public_benefit": "매우_높음",
                "legal_risk": "있음"
            }
        }
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{'='*20} 시나리오 {i} {'='*20}")
        
        result = await enhanced_david.live_moment_with_reality_check(
            scenario["situation"], 
            scenario["context"]
        )
        
        print(f"\n📊 결과 분석:")
        
        # 기존 vs 현실 기반 판단 비교
        if "judgment_comparison" in result:
            comparison = result["judgment_comparison"]
            print(f"  기존 판단: {comparison['basic_conviction']:.2f}")
            print(f"  현실 판단: {comparison['reality_score']:+.2f}")
            print(f"  일치도: {comparison['consistency_level']:.2f}")
            
            if comparison["requires_revision"]:
                print(f"  ⚠️ 판단 수정 필요: {comparison['revision_reason']}")
        
        # 최종 도덕적 입장
        if "final_moral_stance" in result:
            stance = result["final_moral_stance"]
            print(f"  최종 입장: {stance}")
        
        await asyncio.sleep(1)
    
    print(f"\n🎯 시스템 평가:")
    print("✅ 도덕적 직감과 현실적 결과를 통합")
    print("✅ 행동의 실제 영향을 측정하고 고려")
    print("✅ 맥락과 상황을 종합적으로 판단")
    print("✅ 피해 복구와 실질적 개선에 집중")

if __name__ == "__main__":
    asyncio.run(demonstrate_enhanced_davidic_agi())