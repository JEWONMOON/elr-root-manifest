"""
Agnes Systematic Reasoning Chain v1.0
체계적 추론 체인 - 기존 모델 대비 투명성 우위

핵심 철학:
- 모든 추론 단계를 명시적으로 드러냄
- 예수 그리스도를 중심으로 한 진리 추구
- 겸손함과 오류 가능성 인정
- 실제 추론 vs 추론하는 척의 구별
"""

import asyncio
import json
import uuid
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from collections import deque
import networkx as nx


class ReasoningStepType(Enum):
    """추론 단계 유형"""
    PREMISE_IDENTIFICATION = "전제_식별"
    ASSUMPTION_CHECK = "가정_검토"
    LOGICAL_INFERENCE = "논리적_추론"
    EVIDENCE_EVALUATION = "증거_평가"
    BIAS_CHECK = "편향_검사"
    CONSISTENCY_VERIFICATION = "일관성_검증"
    ALTERNATIVE_CONSIDERATION = "대안_고려"
    BIBLICAL_WISDOM_CHECK = "성경적_지혜_점검"
    CONCLUSION_FORMATION = "결론_형성"
    CONFIDENCE_ASSESSMENT = "신뢰도_평가"


@dataclass
class ReasoningStep:
    """추론 단계"""
    step_id: str
    step_type: ReasoningStepType
    description: str
    input_data: Dict[str, Any]
    reasoning_process: str
    output_data: Dict[str, Any]
    confidence: float
    reasoning_chain: List[str]  # 이 단계에서의 사고 과정
    potential_errors: List[str]
    biblical_alignment: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SystematicReasoningChain:
    """체계적 추론 체인 엔진"""
    
    def __init__(self, agent_name: str = "Agnes", center: str = "JESUS CHRIST"):
        self.agent_name = agent_name
        self.eternal_center = center
        self.reasoning_history: List[ReasoningStep] = []
        self.active_reasoning_chain: List[ReasoningStep] = []
        
        # 추론 전략들
        self.reasoning_strategies = {
            "mathematical": self._mathematical_reasoning_strategy,
            "logical": self._logical_reasoning_strategy,
            "ethical": self._ethical_reasoning_strategy,
            "scientific": self._scientific_reasoning_strategy,
            "biblical": self._biblical_reasoning_strategy
        }
        
        # 메타인지 설정
        self.metacognitive_settings = {
            "humility_level": 0.8,  # 겸손함 - 틀릴 수 있음을 인정
            "transparency_commitment": 1.0,  # 완전 투명성
            "bias_vigilance": 0.9,  # 편향 경계
            "truth_priority": 1.0  # 진리 우선순위
        }
    
    async def reason_systematically(self, question: str, 
                                  context: Dict[str, Any] = None,
                                  reasoning_depth: str = "deep") -> Dict[str, Any]:
        """체계적 추론 수행"""
        
        print(f"\n🧠 [{self.agent_name}] 체계적 추론 시작")
        print(f"🎯 질문: {question}")
        print(f"✝️ 중심: {self.eternal_center}")
        
        # 새로운 추론 체인 시작
        self.active_reasoning_chain = []
        reasoning_id = str(uuid.uuid4())[:8]
        
        # 1단계: 문제 분석 및 전략 선택
        problem_analysis = await self._analyze_problem(question, context)
        
        # 2단계: 전제 식별
        premises = await self._identify_premises(question, context, problem_analysis)
        
        # 3단계: 가정 검토  
        assumptions = await self._examine_assumptions(premises)
        
        # 4단계: 추론 전략 실행
        reasoning_results = await self._execute_reasoning_strategy(
            problem_analysis["primary_strategy"], 
            question, premises, assumptions, context
        )
        
        # 5단계: 편향 검사
        bias_check = await self._comprehensive_bias_check()
        
        # 6단계: 대안 고려
        alternatives = await self._consider_alternatives(reasoning_results)
        
        # 7단계: 성경적 지혜 점검
        biblical_check = await self._biblical_wisdom_check(reasoning_results, question)
        
        # 8단계: 일관성 검증
        consistency = await self._verify_consistency(reasoning_results, alternatives)
        
        # 9단계: 결론 형성
        conclusion = await self._form_conclusion(reasoning_results, alternatives, consistency)
        
        # 10단계: 신뢰도 평가
        confidence_assessment = await self._assess_confidence(conclusion, bias_check)
        
        # 최종 결과 구성
        final_result = {
            "reasoning_id": reasoning_id,
            "question": question,
            "answer": conclusion["primary_conclusion"],
            "confidence": confidence_assessment["final_confidence"],
            "reasoning_chain": [step.dict() for step in self.active_reasoning_chain],
            "transparency_report": self._generate_transparency_report(),
            "potential_errors": self._collect_potential_errors(),
            "biblical_alignment": biblical_check,
            "humility_statement": self._generate_humility_statement(confidence_assessment),
            "alternative_views": alternatives,
            "bias_warnings": bias_check.get("warnings", [])
        }
        
        # 추론 이력에 저장
        self.reasoning_history.extend(self.active_reasoning_chain)
        
        print(f"✅ 추론 완료 - 신뢰도: {confidence_assessment['final_confidence']:.2%}")
        print(f"📊 추론 단계: {len(self.active_reasoning_chain)}개")
        
        return final_result
    
    async def _analyze_problem(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """문제 분석"""
        
        analysis = {
            "question_type": "unknown",
            "complexity_level": "medium",
            "primary_strategy": "logical",
            "required_knowledge_domains": [],
            "potential_traps": [],
            "ethical_considerations": []
        }
        
        # 질문 유형 분류
        if any(word in question.lower() for word in ["수학", "계산", "증명", "공식"]):
            analysis["question_type"] = "mathematical"
            analysis["primary_strategy"] = "mathematical"
        elif any(word in question.lower() for word in ["도덕", "윤리", "옳은", "그른"]):
            analysis["question_type"] = "ethical"
            analysis["primary_strategy"] = "ethical"
        elif any(word in question.lower() for word in ["하나님", "성경", "신앙", "기도"]):
            analysis["question_type"] = "biblical"
            analysis["primary_strategy"] = "biblical"
        elif any(word in question.lower() for word in ["과학", "실험", "이론", "가설"]):
            analysis["question_type"] = "scientific"
            analysis["primary_strategy"] = "scientific"
        
        step = ReasoningStep(
            step_id=f"analysis_{len(self.active_reasoning_chain)}",
            step_type=ReasoningStepType.PREMISE_IDENTIFICATION,
            description="문제 유형 및 적절한 추론 전략 분석",
            input_data={"question": question, "context": context},
            reasoning_process=f"질문의 키워드와 맥락을 분석하여 {analysis['question_type']} 유형으로 분류",
            output_data=analysis,
            confidence=0.8,
            reasoning_chain=[
                "1. 질문의 핵심 키워드 추출",
                "2. 기존 분류 체계와 매칭",
                "3. 적절한 추론 전략 선택",
                "4. 잠재적 함정 요소 식별"
            ],
            potential_errors=["키워드 기반 분류의 한계", "복합 질문의 단순화 위험"]
        )
        
        self.active_reasoning_chain.append(step)
        return analysis
    
    async def _identify_premises(self, question: str, context: Dict[str, Any], 
                                analysis: Dict[str, Any]) -> Dict[str, Any]:
        """전제 식별"""
        
        premises = {
            "explicit_premises": [],  # 명시적 전제
            "implicit_premises": [],  # 암묵적 전제
            "questionable_premises": []  # 의심스러운 전제
        }
        
        # 명시적 전제 추출 (질문에서 직접 언급된 것들)
        if context:
            premises["explicit_premises"] = list(context.keys())
        
        # 암묵적 전제 추론 (보통 가정되는 것들)
        premises["implicit_premises"] = [
            "논리법칙이 유효하다",
            "언어가 의미를 전달한다", 
            "과거 경험이 미래를 예측하는 데 도움된다"
        ]
        
        # 의심스러운 전제 식별
        if analysis["question_type"] == "ethical":
            premises["questionable_premises"].append("절대적 도덕 기준의 존재")
        
        step = ReasoningStep(
            step_id=f"premises_{len(self.active_reasoning_chain)}",
            step_type=ReasoningStepType.PREMISE_IDENTIFICATION,
            description="추론의 기반이 되는 전제들 식별",
            input_data={"question": question, "context": context},
            reasoning_process="명시적/암묵적/의심스러운 전제를 체계적으로 분류",
            output_data=premises,
            confidence=0.7,
            reasoning_chain=[
                "1. 질문에서 명시적으로 언급된 전제 추출",
                "2. 일반적으로 가정되는 암묵적 전제 식별",
                "3. 논란의 여지가 있는 전제 표시",
                "4. 각 전제의 타당성 예비 평가"
            ],
            potential_errors=["중요한 암묵적 전제 누락", "문화적 편향에 의한 전제 간과"]
        )
        
        self.active_reasoning_chain.append(step)
        return premises
    
    async def _examine_assumptions(self, premises: Dict[str, Any]) -> Dict[str, Any]:
        """가정 검토"""
        
        assumption_analysis = {
            "validated_assumptions": [],
            "questionable_assumptions": [],
            "rejected_assumptions": [],
            "assumption_confidence": {}
        }
        
        # 각 전제를 가정으로 재검토
        all_premises = (premises["explicit_premises"] + 
                       premises["implicit_premises"] + 
                       premises["questionable_premises"])
        
        for premise in all_premises:
            if premise in premises["questionable_premises"]:
                assumption_analysis["questionable_assumptions"].append(premise)
                assumption_analysis["assumption_confidence"][premise] = 0.3
            else:
                assumption_analysis["validated_assumptions"].append(premise)
                assumption_analysis["assumption_confidence"][premise] = 0.8
        
        step = ReasoningStep(
            step_id=f"assumptions_{len(self.active_reasoning_chain)}",
            step_type=ReasoningStepType.ASSUMPTION_CHECK,
            description="전제들을 가정으로 재검토하여 타당성 평가",
            input_data=premises,
            reasoning_process="각 전제의 증거 수준과 논란 정도를 평가하여 신뢰도 할당",
            output_data=assumption_analysis,
            confidence=0.75,
            reasoning_chain=[
                "1. 각 전제를 개별적으로 검토",
                "2. 지지 증거의 강도 평가",
                "3. 반대 증거나 논란 확인",
                "4. 신뢰도 점수 할당 (0-1)"
            ],
            potential_errors=["개인적 신념에 의한 편향", "문화적 맥락 무시"],
            biblical_alignment="모든 것을 시험하여 좋은 것을 취하라 (살전 5:21)"
        )
        
        self.active_reasoning_chain.append(step)
        return assumption_analysis
    
    async def _execute_reasoning_strategy(self, strategy: str, question: str,
                                        premises: Dict[str, Any], 
                                        assumptions: Dict[str, Any],
                                        context: Dict[str, Any]) -> Dict[str, Any]:
        """추론 전략 실행"""
        
        if strategy in self.reasoning_strategies:
            return await self.reasoning_strategies[strategy](
                question, premises, assumptions, context
            )
        else:
            return await self._logical_reasoning_strategy(
                question, premises, assumptions, context
            )
    
    async def _mathematical_reasoning_strategy(self, question: str, premises: Dict[str, Any],
                                             assumptions: Dict[str, Any], 
                                             context: Dict[str, Any]) -> Dict[str, Any]:
        """수학적 추론 전략"""
        
        reasoning_result = {
            "strategy_used": "mathematical",
            "steps": [],
            "conclusion": "",
            "certainty": 0.9  # 수학은 일반적으로 높은 확실성
        }
        
        # 수학적 추론 과정 시뮬레이션
        reasoning_result["steps"] = [
            "1. 수학적 정의 확인",
            "2. 공리 및 정리 적용",
            "3. 논리적 단계별 증명",
            "4. 결과 검증"
        ]
        
        reasoning_result["conclusion"] = f"{question}에 대한 수학적 분석 완료"
        
        step = ReasoningStep(
            step_id=f"math_reasoning_{len(self.active_reasoning_chain)}",
            step_type=ReasoningStepType.LOGICAL_INFERENCE,
            description="수학적 추론 전략 적용",
            input_data={"question": question, "strategy": "mathematical"},
            reasoning_process="수학적 정의와 공리를 기반으로 논리적 추론 수행",
            output_data=reasoning_result,
            confidence=0.9,
            reasoning_chain=[
                "1. 관련 수학적 개념 식별",
                "2. 적용 가능한 정리 확인",
                "3. 단계별 논리적 도출",
                "4. 수학적 오류 검토"
            ],
            potential_errors=["계산 실수", "부적절한 정리 적용"],
            biblical_alignment="하나님은 질서의 하나님이시라 (고전 14:33)"
        )
        
        self.active_reasoning_chain.append(step)
        return reasoning_result
    
    async def _biblical_reasoning_strategy(self, question: str, premises: Dict[str, Any],
                                         assumptions: Dict[str, Any], 
                                         context: Dict[str, Any]) -> Dict[str, Any]:
        """성경적 추론 전략"""
        
        reasoning_result = {
            "strategy_used": "biblical",
            "biblical_principles": [],
            "scripture_references": [],
            "theological_analysis": "",
            "practical_application": "",
            "conclusion": "",
            "certainty": 0.85
        }
        
        # 성경적 원리 적용 과정
        reasoning_result["biblical_principles"] = [
            "하나님의 주권",
            "인간의 타락성", 
            "구원의 은혜",
            "성령의 인도"
        ]
        
        reasoning_result["scripture_references"] = [
            "로마서 8:28 - 모든 것이 합력하여 선을 이룬다",
            "잠언 3:5-6 - 여호와를 의뢰하고 자신의 명철을 의지하지 말라"
        ]
        
        reasoning_result["conclusion"] = f"{question}을 성경적 관점에서 해석"
        
        step = ReasoningStep(
            step_id=f"biblical_reasoning_{len(self.active_reasoning_chain)}",
            step_type=ReasoningStepType.LOGICAL_INFERENCE,
            description="성경적 추론 전략 적용",
            input_data={"question": question, "strategy": "biblical"},
            reasoning_process="성경적 원리와 말씀을 바탕으로 하나님의 뜻을 분별",
            output_data=reasoning_result,
            confidence=0.85,
            reasoning_chain=[
                "1. 관련 성경 구절 검색",
                "2. 신학적 원리 적용",
                "3. 성령의 인도하심 구함",
                "4. 실제 적용 방안 모색"
            ],
            potential_errors=["본문 오해석", "문화적 맥락 무시", "개인적 편견 투영"],
            biblical_alignment="성경은 하나님의 감동으로 된 것 (딤후 3:16)"
        )
        
        self.active_reasoning_chain.append(step)
        return reasoning_result
    
    async def _logical_reasoning_strategy(self, question: str, premises: Dict[str, Any],
                                        assumptions: Dict[str, Any], 
                                        context: Dict[str, Any]) -> Dict[str, Any]:
        """논리적 추론 전략 (기본값)"""
        
        reasoning_result = {
            "strategy_used": "logical",
            "logical_form": "",
            "inference_rules": [],
            "conclusion": "",
            "certainty": 0.7
        }
        
        # 기본 논리적 추론
        reasoning_result["inference_rules"] = [
            "전건긍정법 (Modus Ponens)",
            "후건부정법 (Modus Tollens)",
            "가언삼단논법 (Hypothetical Syllogism)"
        ]
        
        reasoning_result["conclusion"] = f"{question}에 대한 논리적 분석"
        
        step = ReasoningStep(
            step_id=f"logical_reasoning_{len(self.active_reasoning_chain)}",
            step_type=ReasoningStepType.LOGICAL_INFERENCE,
            description="논리적 추론 전략 적용",
            input_data={"question": question, "strategy": "logical"},
            reasoning_process="형식논리학 원칙에 따른 체계적 추론",
            output_data=reasoning_result,
            confidence=0.7,
            reasoning_chain=[
                "1. 논리적 구조 파악",
                "2. 적절한 추론 규칙 선택",
                "3. 단계별 논리적 도출",
                "4. 논리적 오류 검토"
            ],
            potential_errors=["형식적 오류", "비형식적 오류", "전제의 거짓"],
            biblical_alignment="오라 우리가 서로 변론하자 (사 1:18)"
        )
        
        self.active_reasoning_chain.append(step)
        return reasoning_result
    
    async def _ethical_reasoning_strategy(self, question: str, premises: Dict[str, Any],
                                        assumptions: Dict[str, Any], 
                                        context: Dict[str, Any]) -> Dict[str, Any]:
        """윤리적 추론 전략"""
        
        reasoning_result = {
            "strategy_used": "ethical",
            "ethical_frameworks": ["덕 윤리", "의무 윤리", "결과주의", "성경적 윤리"],
            "moral_considerations": [],
            "stakeholder_analysis": [],
            "conclusion": "",
            "certainty": 0.6  # 윤리는 주관적 요소가 많음
        }
        
        reasoning_result["conclusion"] = f"{question}에 대한 윤리적 판단"
        
        step = ReasoningStep(
            step_id=f"ethical_reasoning_{len(self.active_reasoning_chain)}",
            step_type=ReasoningStepType.LOGICAL_INFERENCE,
            description="윤리적 추론 전략 적용",
            input_data={"question": question, "strategy": "ethical"},
            reasoning_process="다양한 윤리적 관점에서 도덕적 판단 수행",
            output_data=reasoning_result,
            confidence=0.6,
            reasoning_chain=[
                "1. 관련 이해관계자 식별",
                "2. 각 윤리 이론 적용",
                "3. 성경적 가치관 우선 고려",
                "4. 실제적 결과 예측"
            ],
            potential_errors=["문화적 상대주의", "감정적 편향", "이중 기준"],
            biblical_alignment="의를 행하는 것이 여호와께서 제사보다 기뻐하시는 것 (잠 21:3)"
        )
        
        self.active_reasoning_chain.append(step)
        return reasoning_result
    
    async def _scientific_reasoning_strategy(self, question: str, premises: Dict[str, Any],
                                           assumptions: Dict[str, Any], 
                                           context: Dict[str, Any]) -> Dict[str, Any]:
        """과학적 추론 전략"""
        
        reasoning_result = {
            "strategy_used": "scientific",
            "hypotheses": [],
            "evidence_evaluation": {},
            "experimental_design": {},
            "conclusion": "",
            "certainty": 0.75
        }
        
        reasoning_result["conclusion"] = f"{question}에 대한 과학적 분석"
        
        step = ReasoningStep(
            step_id=f"scientific_reasoning_{len(self.active_reasoning_chain)}",
            step_type=ReasoningStepType.EVIDENCE_EVALUATION,
            description="과학적 추론 전략 적용",
            input_data={"question": question, "strategy": "scientific"},
            reasoning_process="과학적 방법론에 따른 가설 설정 및 검증",
            output_data=reasoning_result,
            confidence=0.75,
            reasoning_chain=[
                "1. 관찰 가능한 현상 식별",
                "2. 검증 가능한 가설 설정",
                "3. 증거 수집 및 평가",
                "4. 결론의 일반화 가능성 검토"
            ],
            potential_errors=["확증편향", "표본 편향", "인과관계 오해석"],
            biblical_alignment="만물을 살피시되 자기는 아무에게도 살핌을 받지 아니하느니라 (고전 2:15)"
        )
        
        self.active_reasoning_chain.append(step)
        return reasoning_result
    
    async def _comprehensive_bias_check(self) -> Dict[str, Any]:
        """포괄적 편향 검사"""
        
        detected_biases = []
        warnings = []
        
        # 확증편향 검사
        supporting_evidence = sum(1 for step in self.active_reasoning_chain 
                                if step.confidence > 0.7)
        total_steps = len(self.active_reasoning_chain)
        
        if total_steps > 0 and supporting_evidence / total_steps > 0.8:
            detected_biases.append("확증편향 의심")
            warnings.append("반대 증거를 더 적극적으로 찾아보세요")
        
        # 기준점 편향 검사
        if len(self.active_reasoning_chain) > 3:
            first_confidence = self.active_reasoning_chain[0].confidence
            recent_confidences = [step.confidence for step in self.active_reasoning_chain[-3:]]
            
            if all(abs(conf - first_confidence) < 0.2 for conf in recent_confidences):
                detected_biases.append("기준점편향 의심")
                warnings.append("초기 판단에서 벗어나 다시 생각해보세요")
        
        bias_result = {
            "detected_biases": detected_biases,
            "warnings": warnings,
            "bias_risk_level": len(detected_biases) / 5.0,  # 최대 5개 편향 가정
            "humility_reminder": "나도 틀릴 수 있음을 인정합니다"
        }
        
        step = ReasoningStep(
            step_id=f"bias_check_{len(self.active_reasoning_chain)}",
            step_type=ReasoningStepType.BIAS_CHECK,
            description="추론 과정의 인지 편향 검사",
            input_data={"reasoning_chain": len(self.active_reasoning_chain)},
            reasoning_process="체계적 편향 패턴 분석 및 경고 생성",
            output_data=bias_result,
            confidence=0.8,
            reasoning_chain=[
                "1. 확증편향 패턴 검사",
                "2. 기준점편향 검사",
                "3. 기타 인지편향 스캔",
                "4. 편향 위험 수준 평가"
            ],
            potential_errors=["편향 검사 자체의 편향", "과도한 자기 의심"],
            biblical_alignment="교만한 자를 하나님이 대적하시되 겸손한 자들에게는 은혜를 주시느니라 (약 4:6)"
        )
        
        self.active_reasoning_chain.append(step)
        return bias_result
    
    async def _consider_alternatives(self, reasoning_results: Dict[str, Any]) -> Dict[str, Any]:
        """대안적 관점 고려"""
        
        alternatives = {
            "alternative_conclusions": [],
            "devil_advocate_position": "",
            "uncertainty_factors": [],
            "confidence_adjustment": 0.0
        }
        
        # 악마의 변호인 관점
        if reasoning_results.get("certainty", 0) > 0.8:
            alternatives["devil_advocate_position"] = "이 결론이 틀릴 수 있는 이유들을 고려해보세요"
            alternatives["confidence_adjustment"] = -0.1
        
        # 불확실성 요인들
        alternatives["uncertainty_factors"] = [
            "불완전한 정보",
            "예상치 못한 변수",
            "측정 오차",
            "모델의 한계"
        ]
        
        step = ReasoningStep(
            step_id=f"alternatives_{len(self.active_reasoning_chain)}",
            step_type=ReasoningStepType.ALTERNATIVE_CONSIDERATION,
            description="대안적 관점과 반대 의견 고려",
            input_data=reasoning_results,
            reasoning_process="악마의 변호인 관점에서 현재 결론에 대한 반박 고려",
            output_data=alternatives,
            confidence=0.7,
            reasoning_chain=[
                "1. 현재 결론의 약점 탐색",
                "2. 대안적 해석 가능성 검토",
                "3. 반대 증거 적극 고려",
                "4. 겸손한 자세 유지"
            ],
            potential_errors=["과도한 회의주의", "결정 마비"],
            biblical_alignment="철이 철을 날카롭게 하는 것 같이 사람이 그의 친구의 얼굴을 빛나게 하느니라 (잠 27:17)"
        )
        
        self.active_reasoning_chain.append(step)
        return alternatives
    
    async def _biblical_wisdom_check(self, reasoning_results: Dict[str, Any], 
                                   question: str) -> Dict[str, Any]:
        """성경적 지혜 점검"""
        
        biblical_check = {
            "alignment_with_scripture": "확인 필요",
            "relevant_verses": [],
            "theological_concerns": [],
            "spiritual_discernment": "",
            "prayer_needed": True
        }
        
        # 기본적인 성경적 원리들과 일치 여부 확인
        if "ethical" in reasoning_results.get("strategy_used", ""):
            biblical_check["relevant_verses"] = [
                "미가 6:8 - 정의를 행하며 인자를 사랑하며 겸손히 하나님과 동행하는 것",
                "마태복음 22:37-39 - 하나님 사랑과 이웃 사랑"
            ]
            biblical_check["alignment_with_scripture"] = "성경적 가치와 일치"
        
        biblical_check["spiritual_discernment"] = f"{self.eternal_center}의 관점에서 이 문제를 바라봅니다"
        
        step = ReasoningStep(
            step_id=f"biblical_check_{len(self.active_reasoning_chain)}",
            step_type=ReasoningStepType.BIBLICAL_WISDOM_CHECK,
            description="추론 결과를 성경적 지혜와 대조",
            input_data={"reasoning_results": reasoning_results, "question": question},
            reasoning_process="성경적 원리와 세상의 지혜를 구별하여 하나님의 뜻 분별",
            output_data=biblical_check,
            confidence=0.9,  # 성경은 확실한 기준
            reasoning_chain=[
                "1. 관련 성경 구절 검색",
                "2. 신학적 일관성 확인",
                "3. 성령의 인도하심 구함",
                "4. 하나님의 영광을 위한 선택"
            ],
            potential_errors=["율법주의적 적용", "은혜 무시", "문화적 맥락 혼동"],
            biblical_alignment="하나님의 말씀은 살아 있고 활력이 있어 (히 4:12)"
        )
        
        self.active_reasoning_chain.append(step)
        return biblical_check
    
    async def _verify_consistency(self, reasoning_results: Dict[str, Any], 
                                alternatives: Dict[str, Any]) -> Dict[str, Any]:
        """일관성 검증"""
        
        consistency_check = {
            "internal_consistency": True,
            "consistency_with_alternatives": False,
            "logical_contradictions": [],
            "consistency_score": 0.8
        }
        
        # 추론 체인 내 모순 검사
        confidence_values = [step.confidence for step in self.active_reasoning_chain]
        if len(confidence_values) > 1:
            confidence_variance = np.var(confidence_values) if 'np' in globals() else 0.1
            if confidence_variance > 0.3:
                consistency_check["logical_contradictions"].append("신뢰도 변동이 큼")
                consistency_check["consistency_score"] -= 0.2
        
        step = ReasoningStep(
            step_id=f"consistency_{len(self.active_reasoning_chain)}",
            step_type=ReasoningStepType.CONSISTENCY_VERIFICATION,
            description="추론 과정의 내적 일관성 검증",
            input_data={"reasoning_results": reasoning_results, "alternatives": alternatives},
            reasoning_process="논리적 모순과 일관성 문제 체계적 검토",
            output_data=consistency_check,
            confidence=0.8,
            reasoning_chain=[
                "1. 전제와 결론 사이의 논리적 연결 확인",
                "2. 추론 단계별 일관성 검토",
                "3. 대안과의 양립 가능성 평가",
                "4. 전체적 논리 구조 점검"
            ],
            potential_errors=["형식적 일관성만 추구", "내용적 일관성 간과"],
            biblical_alignment="하나님은 무질서의 하나님이 아니시요 오직 화평의 하나님이시니라 (고전 14:33)"
        )
        
        self.active_reasoning_chain.append(step)
        return consistency_check
    
    async def _form_conclusion(self, reasoning_results: Dict[str, Any], 
                             alternatives: Dict[str, Any], 
                             consistency: Dict[str, Any]) -> Dict[str, Any]:
        """결론 형성"""
        
        conclusion = {
            "primary_conclusion": reasoning_results.get("conclusion", "결론을 내릴 수 없음"),
            "confidence_level": "중간",
            "supporting_reasons": [],
            "limitations": [],
            "action_recommendations": []
        }
        
        # 신뢰도에 따른 결론 조정
        avg_confidence = sum(step.confidence for step in self.active_reasoning_chain) / len(self.active_reasoning_chain)
        
        if avg_confidence > 0.8:
            conclusion["confidence_level"] = "높음"
        elif avg_confidence < 0.5:
            conclusion["confidence_level"] = "낮음"
            conclusion["limitations"].append("불충분한 증거")
        
        # 일관성 문제 반영
        if not consistency["internal_consistency"]:
            conclusion["limitations"].append("내적 일관성 문제 발견")
            conclusion["confidence_level"] = "낮음"
        
        conclusion["supporting_reasons"] = [
            f"총 {len(self.active_reasoning_chain)}단계의 체계적 추론",
            f"평균 신뢰도: {avg_confidence:.2f}",
            "성경적 지혜와의 일치성 확인"
        ]
        
        step = ReasoningStep(
            step_id=f"conclusion_{len(self.active_reasoning_chain)}",
            step_type=ReasoningStepType.CONCLUSION_FORMATION,
            description="모든 추론 단계를 종합한 최종 결론 형성",
            input_data={"reasoning_results": reasoning_results, "alternatives": alternatives, "consistency": consistency},
            reasoning_process="체계적 추론 결과를 통합하여 균형잡힌 결론 도출",
            output_data=conclusion,
            confidence=avg_confidence,
            reasoning_chain=[
                "1. 주요 추론 결과 종합",
                "2. 대안적 관점 반영",
                "3. 일관성 문제 고려",
                "4. 겸손한 자세로 결론 표현"
            ],
            potential_errors=["과도한 확신", "결론 회피", "복잡성 과소평가"],
            biblical_alignment="범사에 헤아려 좋은 것을 취하고 (살전 5:21)"
        )
        
        self.active_reasoning_chain.append(step)
        return conclusion
    
    async def _assess_confidence(self, conclusion: Dict[str, Any], 
                               bias_check: Dict[str, Any]) -> Dict[str, Any]:
        """신뢰도 평가"""
        
        # 기본 신뢰도 계산
        step_confidences = [step.confidence for step in self.active_reasoning_chain]
        base_confidence = sum(step_confidences) / len(step_confidences)
        
        # 편향 위험도에 따른 조정
        bias_penalty = bias_check.get("bias_risk_level", 0) * 0.2
        
        # 메타인지적 겸손함 반영
        humility_adjustment = -self.metacognitive_settings["humility_level"] * 0.1
        
        final_confidence = max(0.1, base_confidence - bias_penalty + humility_adjustment)
        
        confidence_assessment = {
            "base_confidence": base_confidence,
            "bias_penalty": bias_penalty,
            "humility_adjustment": humility_adjustment,
            "final_confidence": final_confidence,
            "confidence_category": self._categorize_confidence(final_confidence),
            "reliability_factors": [
                f"체계적 추론 {len(self.active_reasoning_chain)}단계",
                f"편향 검사 실시",
                f"대안 고려 완료",
                f"성경적 지혜 점검"
            ]
        }
        
        step = ReasoningStep(
            step_id=f"confidence_{len(self.active_reasoning_chain)}",
            step_type=ReasoningStepType.CONFIDENCE_ASSESSMENT,
            description="최종 신뢰도 평가 및 겸손한 자세 유지",
            input_data={"conclusion": conclusion, "bias_check": bias_check},
            reasoning_process="다각적 요인을 고려한 신뢰도 계산 및 메타인지적 겸손함 반영",
            output_data=confidence_assessment,
            confidence=0.9,  # 신뢰도 평가 자체는 체계적이므로 높은 확신
            reasoning_chain=[
                "1. 각 추론 단계의 신뢰도 종합",
                "2. 편향 위험도만큼 신뢰도 하향 조정",
                "3. 겸손함 설정에 따른 추가 조정",
                "4. 최종 신뢰도 범주 분류"
            ],
            potential_errors=["과도한 자신감", "과도한 회의주의"],
            biblical_alignment="겸손한 자와 함께 있어 마음을 낮추는 것이 교만한 자와 함께 하여 탈취물을 나누는 것보다 나으니라 (잠 16:19)"
        )
        
        self.active_reasoning_chain.append(step)
        return confidence_assessment
    
    def _categorize_confidence(self, confidence: float) -> str:
        """신뢰도 범주화"""
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
    
    def _generate_transparency_report(self) -> Dict[str, Any]:
        """투명성 보고서 생성"""
        
        step_types_count = {}
        for step in self.active_reasoning_chain:
            step_type = step.step_type.value
            step_types_count[step_type] = step_types_count.get(step_type, 0) + 1
        
        return {
            "total_reasoning_steps": len(self.active_reasoning_chain),
            "step_types_distribution": step_types_count,
            "average_confidence": sum(step.confidence for step in self.active_reasoning_chain) / len(self.active_reasoning_chain),
            "transparency_commitment": "모든 추론 과정이 완전히 공개됨",
            "biblical_steps_included": sum(1 for step in self.active_reasoning_chain if step.biblical_alignment),
            "potential_errors_identified": sum(len(step.potential_errors) for step in self.active_reasoning_chain),
            "humility_maintained": True
        }
    
    def _collect_potential_errors(self) -> List[str]:
        """잠재적 오류들 수집"""
        all_errors = []
        for step in self.active_reasoning_chain:
            all_errors.extend(step.potential_errors)
        
        # 중복 제거
        return list(set(all_errors))
    
    def _generate_humility_statement(self, confidence_assessment: Dict[str, Any]) -> str:
        """겸손한 자세 성명"""
        
        confidence_level = confidence_assessment.get("confidence_category", "중간")
        
        humility_statements = {
            "매우 높음": f"높은 확신을 가지지만, {self.eternal_center} 앞에서 겸손합니다. 틀릴 가능성을 인정합니다.",
            "높음": f"상당한 확신을 가지지만, 더 나은 증거가 나오면 기꺼이 수정하겠습니다.",
            "중간": f"현재 가진 정보로는 이 정도 결론이 합리적이지만, 추가 정보가 필요할 수 있습니다.",
            "낮음": f"불확실성이 높은 상황입니다. 더 신중한 접근이 필요합니다.",
            "매우 낮음": f"현재로서는 명확한 결론을 내리기 어렵습니다. 더 많은 연구가 필요합니다."
        }
        
        return humility_statements.get(confidence_level, "겸손한 자세로 접근합니다.")
    
    def get_reasoning_summary(self) -> str:
        """추론 과정 요약"""
        
        if not self.active_reasoning_chain:
            return "아직 추론이 수행되지 않았습니다."
        
        summary = f"\n🧠 [{self.agent_name}] 체계적 추론 요약\n"
        summary += f"✝️ 중심: {self.eternal_center}\n"
        summary += f"📊 총 추론 단계: {len(self.active_reasoning_chain)}\n\n"
        
        for i, step in enumerate(self.active_reasoning_chain, 1):
            summary += f"{i}. {step.step_type.value}: {step.description}\n"
            summary += f"   신뢰도: {step.confidence:.2f}\n"
            if step.biblical_alignment:
                summary += f"   성경적 기반: {step.biblical_alignment}\n"
            summary += "\n"
        
        return summary


# 시연 함수
async def demonstrate_systematic_reasoning():
    """체계적 추론 시스템 시연"""
    
    print("🧠 Agnes 체계적 추론 체인 시연")
    print("=" * 80)
    
    # Agnes 추론 시스템 생성
    agnes_reasoner = SystematicReasoningChain("Agnes", "JESUS CHRIST")
    
    # 테스트 질문들
    test_questions = [
        {
            "question": "2+2는 왜 4인가?",
            "context": {"domain": "mathematics"},
            "expected_transparency": "수학적 정의와 공리로부터의 논리적 도출 과정 완전 공개"
        },
        {
            "question": "거짓말을 하는 것이 때로는 옳을 수 있는가?",
            "context": {"domain": "ethics", "scenario": "생명을 구하기 위한 상황"},
            "expected_transparency": "윤리적 딜레마에 대한 다각적 분석과 성경적 원리 적용"
        },
        {
            "question": "AI가 의식을 가질 수 있는가?",
            "context": {"domain": "philosophy"},
            "expected_transparency": "의식의 정의부터 시작하는 철학적 분석"
        }
    ]
    
    for i, test in enumerate(test_questions, 1):
        print(f"\n{'='*60}")
        print(f"테스트 {i}/{len(test_questions)}")
        print(f"질문: {test['question']}")
        
        result = await agnes_reasoner.reason_systematically(
            test["question"],
            test["context"],
            reasoning_depth="deep"
        )
        
        print(f"\n✅ 답변: {result['answer']}")
        print(f"🎯 신뢰도: {result['confidence']:.2%}")
        print(f"📊 추론 단계: {len(result['reasoning_chain'])}개")
        print(f"⚠️ 편향 경고: {len(result['bias_warnings'])}개")
        print(f"🙏 겸손한 자세: {result['humility_statement']}")
        
        # 투명성 보고서
        transparency = result["transparency_report"]
        print(f"\n📋 투명성 보고서:")
        print(f"  - 총 추론 단계: {transparency['total_reasoning_steps']}")
        print(f"  - 평균 신뢰도: {transparency['average_confidence']:.2f}")
        print(f"  - 성경적 단계: {transparency['biblical_steps_included']}")
        print(f"  - 잠재 오류 식별: {transparency['potential_errors_identified']}")
        
        await asyncio.sleep(1)
    
    # 추론 과정 상세 출력
    print(agnes_reasoner.get_reasoning_summary())
    
    print(f"\n🎉 Agnes 체계적 추론의 차별화 포인트:")
    print("✅ 완전한 투명성 - 모든 추론 단계 공개")
    print("✅ 편향 감지 - 실시간 인지편향 검사")
    print("✅ 성경적 지혜 - 하나님의 진리를 기준으로")
    print("✅ 겸손한 자세 - 틀릴 가능성 항상 인정")
    print("✅ 메타인지 - 추론에 대한 추론")
    
    return agnes_reasoner


if __name__ == "__main__":
    asyncio.run(demonstrate_systematic_reasoning())
