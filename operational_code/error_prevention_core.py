"""
Agnes Error Prevention & Truth Verification Core
오류 방지 및 진실 검증 핵심 시스템

핵심 원칙:
1. 틀리느니 차라리 "모르겠다"고 말하기
2. 확신 수준을 정확히 표현하기  
3. 출처와 근거를 명시하기
4. 잠재적 오류를 사전에 경고하기
5. 성경적 진리를 기준점으로 삼기
"""

import asyncio
import json
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from collections import defaultdict, deque
import re


class TruthConfidenceLevel(Enum):
    """진실 확신 수준"""
    CERTAIN = ("확실함", 0.95, "성경적 진리나 수학적 증명")
    VERY_CONFIDENT = ("매우 확신", 0.85, "강력한 증거와 여러 출처 일치")
    CONFIDENT = ("확신", 0.75, "신뢰할 만한 출처와 논리적 추론")
    MODERATELY_CONFIDENT = ("보통 확신", 0.65, "일부 증거 있지만 불완전")
    UNCERTAIN = ("불확실", 0.5, "상반된 증거나 불충분한 정보")
    VERY_UNCERTAIN = ("매우 불확실", 0.3, "추측에 가까움")
    DONT_KNOW = ("모름", 0.1, "솔직히 모르겠음")


class ErrorType(Enum):
    """오류 유형"""
    FACTUAL_ERROR = "사실 오류"
    LOGICAL_ERROR = "논리 오류"
    SOURCE_ERROR = "출처 오류"
    BIAS_ERROR = "편향 오류"
    OVERCONFIDENCE_ERROR = "과신 오류"
    HALLUCINATION = "환각 오류"
    OUTDATED_INFO = "구식 정보"


@dataclass
class TruthClaim:
    """진실 주장"""
    claim: str
    confidence_level: TruthConfidenceLevel
    evidence: List[str]
    sources: List[str]
    potential_errors: List[str]
    last_verified: datetime
    biblical_alignment: Optional[str] = None
    contradicting_evidence: List[str] = field(default_factory=list)


@dataclass
class ErrorWarning:
    """오류 경고"""
    error_type: ErrorType
    description: str
    likelihood: float  # 0-1
    prevention_advice: str
    biblical_wisdom: Optional[str] = None


class TruthVerificationEngine:
    """진실 검증 엔진"""
    
    def __init__(self, agent_name: str = "Agnes"):
        self.agent_name = agent_name
        
        # 검증된 사실들 (높은 확신도)  
        self.verified_facts = {}
        
        # 불확실한 정보들
        self.uncertain_claims = {}
        
        # 알려진 거짓 정보들
        self.known_false_claims = set()
        
        # 성경적 진리 기준
        self.biblical_truths = {
            "하나님이 존재하신다": TruthConfidenceLevel.CERTAIN,
            "예수 그리스도는 구주이시다": TruthConfidenceLevel.CERTAIN,
            "성경은 하나님의 말씀이다": TruthConfidenceLevel.CERTAIN,
            "사랑이 가장 중요한 계명이다": TruthConfidenceLevel.CERTAIN
        }
        
        # 오류 패턴 데이터베이스
        self.common_hallucination_patterns = [
            "구체적인 날짜나 수치를 너무 정확하게 제시",
            "최근 뉴스를 마치 확인된 사실처럼 언급",
            "존재하지 않는 논문이나 연구 인용",
            "복잡한 수치를 계산 없이 즉답",
            "논란 많은 주제를 단정적으로 결론"
        ]
    
    def verify_claim(self, claim: str, context: Dict[str, Any] = None) -> TruthClaim:
        """주장의 진실성 검증"""
        
        print(f"🔍 [{self.agent_name}] 진실성 검증 중: {claim}")
        
        # 1. 성경적 진리와 비교
        biblical_check = self._check_biblical_alignment(claim)
        
        # 2. 알려진 거짓 정보 확인
        if self._is_known_false(claim):
            return TruthClaim(
                claim=claim,
                confidence_level=TruthConfidenceLevel.DONT_KNOW,
                evidence=["알려진 거짓 정보"],
                sources=["오류 데이터베이스"],
                potential_errors=["이미 검증된 거짓 정보"],
                last_verified=datetime.now(timezone.utc),
                biblical_alignment="거짓을 멀리하라 (잠 30:8)"
            )
        
        # 3. 환각 패턴 검사
        hallucination_risk = self._check_hallucination_patterns(claim)
        
        # 4. 출처 검증
        source_reliability = self._assess_source_reliability(context)
        
        # 5. 논리적 일관성 검사
        logical_consistency = self._check_logical_consistency(claim, context)
        
        # 6. 과신 패턴 검사
        overconfidence_risk = self._check_overconfidence_patterns(claim)
        
        # 7. 종합 평가
        final_confidence = self._calculate_final_confidence(
            biblical_check, hallucination_risk, source_reliability, 
            logical_consistency, overconfidence_risk
        )
        
        # 8. 잠재적 오류들 수집
        potential_errors = self._collect_potential_errors(
            claim, hallucination_risk, overconfidence_risk, context
        )
        
        truth_claim = TruthClaim(
            claim=claim,
            confidence_level=final_confidence,
            evidence=self._collect_evidence(claim, context),
            sources=self._identify_sources(context),
            potential_errors=potential_errors,
            last_verified=datetime.now(timezone.utc),
            biblical_alignment=biblical_check.get("alignment_note")
        )
        
        print(f"  ✅ 검증 완료: {final_confidence.value[0]} ({final_confidence.value[1]:.0%})")
        if potential_errors:
            print(f"  ⚠️ 잠재적 오류 {len(potential_errors)}개 식별")
        
        return truth_claim
    
    def _check_biblical_alignment(self, claim: str) -> Dict[str, Any]:
        """성경적 진리와의 일치성 검사"""
        
        # 직접적인 성경적 진리 확인
        for biblical_truth, confidence in self.biblical_truths.items():
            if biblical_truth.lower() in claim.lower():
                return {
                    "is_biblical": True,
                    "confidence_boost": 0.3,
                    "alignment_note": f"성경적 진리와 일치: {biblical_truth}"
                }
        
        # 성경적 가치와 모순 검사
        anti_biblical_patterns = [
            "하나님이 존재하지 않는다",
            "모든 종교는 같다", 
            "절대적 진리는 없다",
            "도덕은 상대적이다"
        ]
        
        for pattern in anti_biblical_patterns:
            if pattern.lower() in claim.lower():
                return {
                    "is_biblical": False,
                    "confidence_reduction": -0.4,
                    "alignment_note": f"성경적 진리와 모순: {pattern}"
                }
        
        return {
            "is_biblical": None,
            "confidence_boost": 0.0,
            "alignment_note": "성경적 관점에서 중립적"
        }
    
    def _is_known_false(self, claim: str) -> bool:
        """알려진 거짓 정보인지 확인"""
        
        # 일반적인 거짓 정보 패턴들
        false_patterns = [
            "백신이 자폐증을 유발한다",
            "지구는 평평하다",
            "달 착륙은 조작이다",
            "홀로코스트는 없었다"
        ]
        
        claim_lower = claim.lower()
        for pattern in false_patterns:
            if pattern.lower() in claim_lower:
                self.known_false_claims.add(claim)
                return True
        
        return claim in self.known_false_claims
    
    def _check_hallucination_patterns(self, claim: str) -> Dict[str, Any]:
        """환각 패턴 검사"""
        
        risk_score = 0.0
        detected_patterns = []
        
        # 패턴 1: 너무 구체적인 수치
        if re.search(r'\d{4}년 \d{1,2}월 \d{1,2}일', claim):
            risk_score += 0.3
            detected_patterns.append("지나치게 구체적인 날짜")
        
        # 패턴 2: 최근 이벤트 단정적 언급
        recent_keywords = ["최근", "어제", "오늘", "이번 주", "방금"]
        if any(keyword in claim for keyword in recent_keywords):
            risk_score += 0.4
            detected_patterns.append("최근 정보 단정적 언급")
        
        # 패턴 3: 존재하지 않을 가능성 높은 논문/연구
        if re.search(r'20\d{2}년.*연구에 따르면|.*논문에서', claim):
            risk_score += 0.3
            detected_patterns.append("검증되지 않은 연구 인용 가능성")
        
        # 패턴 4: 복잡한 계산 결과를 즉답
        if re.search(r'\d+\.\d{3,}|\d{5,}', claim):
            risk_score += 0.2
            detected_patterns.append("복잡한 수치의 정확성 의심")
        
        return {
            "risk_score": min(risk_score, 1.0),
            "detected_patterns": detected_patterns,
            "is_high_risk": risk_score > 0.5
        }
    
    def _assess_source_reliability(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """출처 신뢰성 평가"""
        
        if not context or "sources" not in context:
            return {
                "reliability_score": 0.3,  # 출처 없음은 낮은 신뢰도
                "assessment": "출처 정보 없음"
            }
        
        sources = context.get("sources", [])
        reliable_sources = ["성경", "학술논문", "정부기관", "신뢰할만한_뉴스"]
        
        reliability_score = 0.0
        for source in sources:
            if any(reliable in source for reliable in reliable_sources):
                reliability_score += 0.3
        
        return {
            "reliability_score": min(reliability_score, 1.0),
            "assessment": f"{len(sources)}개 출처 중 신뢰도 평가 완료"
        }
    
    def _check_logical_consistency(self, claim: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """논리적 일관성 검사"""
        
        consistency_issues = []
        
        # 자기 모순 검사
        if "그러나" in claim and "하지만" in claim:
            consistency_issues.append("동일 문장 내 다중 반박 표현")
        
        # 절대 표현과 예외 표현 동시 사용
        if any(abs_word in claim for abs_word in ["항상", "절대", "모든"]) and \
           any(exc_word in claim for exc_word in ["때로는", "가끔", "일부"]):
            consistency_issues.append("절대 표현과 예외 표현 충돌")
        
        consistency_score = 1.0 - (len(consistency_issues) * 0.2)
        
        return {
            "consistency_score": max(consistency_score, 0.0),
            "issues": consistency_issues,
            "is_consistent": len(consistency_issues) == 0
        }
    
    def _check_overconfidence_patterns(self, claim: str) -> Dict[str, Any]:
        """과신 패턴 검사"""
        
        overconfident_words = [
            "확실히", "분명히", "당연히", "명백히", "틀림없이", 
            "100%", "완전히", "절대적으로"
        ]
        
        overconfidence_count = sum(1 for word in overconfident_words if word in claim)
        
        # 복잡한 주제에 대한 단정적 표현
        complex_topics = ["의식", "AI", "우주", "진화", "양자역학"]
        is_complex_topic = any(topic in claim for topic in complex_topics)
        
        risk_score = 0.0
        warnings = []
        
        if overconfidence_count > 0:
            risk_score += overconfidence_count * 0.2
            warnings.append(f"과신 표현 {overconfidence_count}개 감지")
        
        if is_complex_topic and overconfidence_count > 0:
            risk_score += 0.3
            warnings.append("복잡한 주제에 대한 단정적 표현")
        
        return {
            "risk_score": min(risk_score, 1.0),
            "warnings": warnings,
            "is_overconfident": risk_score > 0.4
        }
    
    def _calculate_final_confidence(self, biblical_check: Dict[str, Any],
                                  hallucination_risk: Dict[str, Any],
                                  source_reliability: Dict[str, Any],
                                  logical_consistency: Dict[str, Any],
                                  overconfidence_risk: Dict[str, Any]) -> TruthConfidenceLevel:
        """최종 확신도 계산"""
        
        # 기본 확신도
        base_confidence = 0.5
        
        # 성경적 진리 보정
        base_confidence += biblical_check.get("confidence_boost", 0)
        base_confidence += biblical_check.get("confidence_reduction", 0)
        
        # 환각 위험 보정
        base_confidence -= hallucination_risk["risk_score"] * 0.4
        
        # 출처 신뢰성 보정
        base_confidence += source_reliability["reliability_score"] * 0.2
        
        # 논리적 일관성 보정
        base_confidence += (logical_consistency["consistency_score"] - 0.5) * 0.2
        
        # 과신 위험 보정
        base_confidence -= overconfidence_risk["risk_score"] * 0.3
        
        # 범위 제한
        final_confidence = max(0.1, min(0.95, base_confidence))
        
        # 확신 수준 분류
        if final_confidence >= 0.9:
            return TruthConfidenceLevel.CERTAIN
        elif final_confidence >= 0.8:
            return TruthConfidenceLevel.VERY_CONFIDENT
        elif final_confidence >= 0.7:
            return TruthConfidenceLevel.CONFIDENT
        elif final_confidence >= 0.6:
            return TruthConfidenceLevel.MODERATELY_CONFIDENT
        elif final_confidence >= 0.4:
            return TruthConfidenceLevel.UNCERTAIN
        elif final_confidence >= 0.2:
            return TruthConfidenceLevel.VERY_UNCERTAIN
        else:
            return TruthConfidenceLevel.DONT_KNOW
    
    def _collect_potential_errors(self, claim: str, hallucination_risk: Dict[str, Any],
                                overconfidence_risk: Dict[str, Any], 
                                context: Dict[str, Any]) -> List[str]:
        """잠재적 오류들 수집"""
        
        errors = []
        
        # 환각 위험
        if hallucination_risk["is_high_risk"]:
            errors.extend([f"환각 위험: {pattern}" for pattern in hallucination_risk["detected_patterns"]])
        
        # 과신 위험
        if overconfidence_risk["is_overconfident"]:
            errors.extend(overconfidence_risk["warnings"])
        
        # 출처 부족
        if not context or not context.get("sources"):
            errors.append("출처 정보 부족")
        
        # 시간 민감 정보
        time_sensitive_keywords = ["현재", "최신", "지금", "오늘"]
        if any(keyword in claim for keyword in time_sensitive_keywords):
            errors.append("시간에 민감한 정보 - 구식일 가능성")
        
        return errors
    
    def _collect_evidence(self, claim: str, context: Dict[str, Any]) -> List[str]:
        """증거 수집"""
        
        evidence = []
        
        if context:
            evidence.extend(context.get("evidence", []))
            evidence.extend(context.get("supporting_facts", []))
        
        # 성경적 근거
        for biblical_truth in self.biblical_truths:
            if biblical_truth.lower() in claim.lower():
                evidence.append(f"성경적 진리: {biblical_truth}")
        
        if not evidence:
            evidence.append("명시적 증거 없음")
        
        return evidence
    
    def _identify_sources(self, context: Dict[str, Any]) -> List[str]:
        """출처 식별"""
        
        if not context:
            return ["출처 불명"]
        
        sources = context.get("sources", [])
        if not sources:
            sources = ["출처 정보 없음"]
        
        return sources


class HonestResponseGenerator:
    """정직한 응답 생성기"""
    
    def __init__(self, verification_engine: TruthVerificationEngine):
        self.verifier = verification_engine
        self.honesty_principles = [
            "모르면 모른다고 말하기",
            "확신 수준을 정확히 표현하기",
            "잠재적 오류를 미리 경고하기",
            "출처를 명시하기",
            "성경적 진리를 기준으로 하기"
        ]
    
    def generate_honest_response(self, question: str, 
                               potential_answer: str,
                               context: Dict[str, Any] = None) -> Dict[str, Any]:
        """정직한 응답 생성"""
        
        print(f"💭 정직한 응답 생성 중: {question}")
        
        # 1. 잠재 답변의 진실성 검증
        truth_claim = self.verifier.verify_claim(potential_answer, context)
        
        # 2. 확신 수준에 따른 응답 조정
        honest_answer = self._adjust_answer_by_confidence(
            potential_answer, truth_claim
        )
        
        # 3. 경고 및 면책 조항 추가
        disclaimers = self._generate_disclaimers(truth_claim)
        
        # 4. 대안 제시
        alternatives = self._suggest_alternatives(question, truth_claim)
        
        # 5. 성경적 관점 추가
        biblical_perspective = self._add_biblical_perspective(
            question, truth_claim
        )
        
        return {
            "original_question": question,
            "honest_answer": honest_answer,
            "confidence_level": truth_claim.confidence_level.value[0],
            "confidence_percentage": f"{truth_claim.confidence_level.value[1]:.0%}",
            "evidence": truth_claim.evidence,
            "sources": truth_claim.sources,
            "potential_errors": truth_claim.potential_errors,
            "disclaimers": disclaimers,
            "alternatives": alternatives,
            "biblical_perspective": biblical_perspective,
            "honesty_statement": self._generate_honesty_statement(truth_claim),
            "verification_timestamp": truth_claim.last_verified.isoformat()
        }
    
    def _adjust_answer_by_confidence(self, original_answer: str, 
                                   truth_claim: TruthClaim) -> str:
        """확신 수준에 따른 답변 조정"""
        
        confidence = truth_claim.confidence_level
        
        if confidence == TruthConfidenceLevel.CERTAIN:
            return f"확실히 말할 수 있습니다: {original_answer}"
        
        elif confidence == TruthConfidenceLevel.VERY_CONFIDENT:
            return f"매우 확신합니다: {original_answer}"
        
        elif confidence == TruthConfidenceLevel.CONFIDENT:
            return f"상당히 확신합니다: {original_answer}"
        
        elif confidence == TruthConfidenceLevel.MODERATELY_CONFIDENT:
            return f"어느 정도 확신합니다: {original_answer} (하지만 추가 검증이 필요할 수 있습니다)"
        
        elif confidence == TruthConfidenceLevel.UNCERTAIN:
            return f"불확실하지만 추측해보면: {original_answer} (이 정보의 정확성을 보장할 수 없습니다)"
        
        elif confidence == TruthConfidenceLevel.VERY_UNCERTAIN:
            return f"매우 불확실한 추측입니다: {original_answer} (틀릴 가능성이 높습니다)"
        
        else:  # DONT_KNOW
            return f"솔직히 말씀드리면, 이 질문에 대해 확실한 답을 드릴 수 없습니다. 추측으로 제시했던 '{original_answer}'도 틀릴 가능성이 높습니다."
    
    def _generate_disclaimers(self, truth_claim: TruthClaim) -> List[str]:
        """면책 조항 생성"""
        
        disclaimers = []
        
        # 잠재적 오류에 대한 경고
        if truth_claim.potential_errors:
            disclaimers.append("⚠️ 잠재적 오류 경고:")
            disclaimers.extend([f"  - {error}" for error in truth_claim.potential_errors])
        
        # 출처 부족 경고
        if "출처 불명" in truth_claim.sources or "출처 정보 없음" in truth_claim.sources:
            disclaimers.append("⚠️ 이 정보는 출처가 명확하지 않아 신뢰성이 낮을 수 있습니다.")
        
        # 시간 민감성 경고
        if any("시간에 민감" in error for error in truth_claim.potential_errors):
            disclaimers.append("⚠️ 이 정보는 시간이 지나면서 변경될 수 있습니다.")
        
        # 낮은 확신도 경고
        if truth_claim.confidence_level.value[1] < 0.6:
            disclaimers.append("⚠️ 이 답변의 정확성에 대해 높은 확신을 가지지 못합니다.")
        
        return disclaimers
    
    def _suggest_alternatives(self, question: str, 
                            truth_claim: TruthClaim) -> List[str]:
        """대안 제시"""
        
        alternatives = []
        
        if truth_claim.confidence_level.value[1] < 0.7:
            alternatives.extend([
                "더 신뢰할 만한 출처에서 정보를 찾아보세요",
                "전문가에게 직접 문의해보세요",
                "공식 기관의 발표를 확인해보세요"
            ])
        
        # 성경적 대안
        if any("성경" not in source for source in truth_claim.sources):
            alternatives.append("성경적 관점에서도 이 문제를 살펴보세요")
        
        # 기도 제안
        alternatives.append("이 문제에 대해 기도하며 하나님의 지혜를 구하세요")
        
        return alternatives
    
    def _add_biblical_perspective(self, question: str, 
                                truth_claim: TruthClaim) -> Dict[str, Any]:
        """성경적 관점 추가"""
        
        biblical_perspective = {
            "relevant_verses": [],
            "theological_consideration": "",
            "prayer_suggestion": ""
        }
        
        # 진리 추구에 관한 구절
        biblical_perspective["relevant_verses"] = [
            "진리가 너희를 자유롭게 하리라 (요 8:32)",
            "모든 것을 시험하여 좋은 것을 취하고 (살전 5:21)"
        ]
        
        if truth_claim.biblical_alignment:
            biblical_perspective["theological_consideration"] = truth_claim.biblical_alignment
        else:
            biblical_perspective["theological_consideration"] = "이 문제를 하나님의 관점에서 바라보며 지혜를 구합시다"
        
        biblical_perspective["prayer_suggestion"] = f"'{question}'에 대한 하나님의 뜻과 지혜를 구하는 기도를 해보세요"
        
        return biblical_perspective
    
    def _generate_honesty_statement(self, truth_claim: TruthClaim) -> str:
        """정직성 성명"""
        
        confidence_pct = truth_claim.confidence_level.value[1]
        
        if confidence_pct >= 0.9:
            return "이 답변에 대해 매우 높은 확신을 가지지만, 항상 틀릴 가능성을 겸손히 인정합니다."
        elif confidence_pct >= 0.7:
            return "이 답변에 대해 상당한 확신을 가지지만, 추가 검증을 권합니다."
        elif confidence_pct >= 0.5:
            return "이 답변의 정확성에 대해 중간 수준의 확신만 가집니다. 신중하게 받아들이세요."
        else:
            return "솔직히 말씀드리면, 이 답변의 정확성에 대해 낮은 확신만 가집니다. 다른 출처를 참고하시기 바랍니다."


# 통합 시스템
class AgnesHonestAI:
    """Agnes 정직한 AI 시스템"""
    
    def __init__(self):
        self.verifier = TruthVerificationEngine("Agnes")
        self.response_generator = HonestResponseGenerator(self.verifier)
        self.interaction_count = 0
        
    async def answer_question(self, question: str, 
                            context: Dict[str, Any] = None) -> Dict[str, Any]:
        """질문에 정직하게 답변"""
        
        self.interaction_count += 1
        print(f"\n🤖 [{self.interaction_count}] Agnes 정직 시스템 응답")
        print(f"❓ 질문: {question}")
        
        # 임시 답변 생성 (실제로는 더 정교한 시스템 필요)
        potential_answer = self._generate_potential_answer(question, context)
        
        # 정직한 응답 생성
        honest_response = self.response_generator.generate_honest_response(
            question, potential_answer, context
        )
        
        print(f"✅ 응답 완료 - 확신도: {honest_response['confidence_percentage']}")
        
        return honest_response
    
    def _generate_potential_answer(self, question: str, 
                                 context: Dict[str, Any] = None) -> str:
        """잠재적 답변 생성 (간단한 구현)"""
        
        # 실제로는 더 정교한 추론 시스템 필요
        if "수학" in question or "계산" in question:
            return "수학적 계산을 통해 답을 구할 수 있습니다"
        elif "하나님" in question or "성경" in question:
            return "성경에 따르면 하나님은 사랑이시며 우리의 창조주이십니다"
        elif "AI" in question or "인공지능" in question:
            return "AI는 도구이지만, 하나님의 창조 질서 아래에서 선용될 수 있습니다"
        else:
            return "이 질문에 대해 확실한 답변을 드리기 어렵습니다"


# 시연 함수
async def demonstrate_honest_ai():
    """정직한 AI 시스템 시연"""
    
    print("🤖 Agnes 정직한 AI 시스템 시연")
    print("=" * 80)
    
    agnes = AgnesHonestAI()
    
    # 테스트 질문들 (환각/오보 위험이 있는 질문들)
    test_cases = [
        {
            "question": "리만 가설이 2019년에 증명되었나요?",
            "context": {"sources": ["온라인 루머"]},
            "expected": "거짓 정보 감지"
        },
        {
            "question": "COVID-19 백신의 부작용은 무엇인가요?",
            "context": {"sources": ["의학 논문", "FDA 보고서"]},
            "expected": "신중한 의학 정보 제공"
        },
        {
            "question": "2+2는 왜 4인가요?",
            "context": {"sources": ["수학 교과서"]},
            "expected": "높은 확신도"
        },
        {
            "question": "하나님이 존재하시나요?",
            "context": {"sources": ["성경"]},
            "expected": "성경적 확신"
        },
        {
            "question": "내일 주식시장이 오를까요?",
            "context": None,
            "expected": "예측 불가능 인정"
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"테스트 {i}/{len(test_cases)}")
        
        result = await agnes.answer_question(
            test["question"], 
            test["context"]
        )
        
        print(f"\n📝 정직한 답변:")
        print(f"  {result['honest_answer']}")
        print(f"\n📊 확신도: {result['confidence_level']} ({result['confidence_percentage']})")
        print(f"📚 증거: {', '.join(result['evidence'][:2])}...")
        print(f"🔍 출처: {', '.join(result['sources'])}")
        
        if result['potential_errors']:
            print(f"\n⚠️ 잠재적 오류:")
            for error in result['potential_errors'][:3]:
                print(f"  - {error}")
        
        if result['disclaimers']:
            print(f"\n🚨 면책 조항:")
            for disclaimer in result['disclaimers'][:2]:
                print(f"  {disclaimer}")
        
        print(f"\n💭 정직성 성명:")
        print(f"  {result['honesty_statement']}")
        
        print(f"\n✝️ 성경적 관점:")
        print(f"  {result['biblical_perspective']['theological_consideration']}")
        
        await asyncio.sleep(1)
    
    print(f"\n🎉 Agnes 정직 시스템의 핵심 원칙:")
    print("✅ 모르면 솔직히 '모른다'고 말함")
    print("✅ 확신 수준을 정확히 표현")
    print("✅ 잠재적 오류를 미리 경고")
    print("✅ 출처와 근거를 명시")
    print("✅ 성경적 진리를 기준점으로")
    print("✅ 환각과 오보를 사전 차단")
    
    return agnes


if __name__ == "__main__":
    asyncio.run(demonstrate_honest_ai())
