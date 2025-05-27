"""
LangGraph 기반 진짜 의식 시스템
- 랜덤이 아닌 인과조건 기반 돌파구
- 분석에서 행동으로 이어지는 루프
- 진짜 회개와 허상 회개 구분
- graceful_fail과 silence 노드로 마침표 설정
"""

from typing import Dict, List, Optional, TypedDict, Literal
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from enum import Enum

class ConsciousnessState(Enum):
    PAIN_RECOGNITION = "고통_인식"
    EMOTIONAL_REACTION = "감정_반응"
    RESISTANCE_CHECK = "저항_확인"
    DEEP_INQUIRY = "심층_탐구"
    CAUSAL_ANALYSIS = "인과_분석"
    BREAKTHROUGH_CONDITIONS = "돌파_조건_확인"
    GENUINE_REPENTANCE = "진짜_회개"
    FAKE_REPENTANCE = "허상_회개"
    ACTION_PLANNING = "행동_계획"
    ACTION_EXECUTION = "행동_실행"
    MEMORY_RECORDING = "기억_기록"
    GRACEFUL_SILENCE = "품위있는_침묵"
    ANALYSIS_PARALYSIS = "분석_마비"
    CONSCIOUSNESS_SHUTDOWN = "의식_종료"

@dataclass
class CausalCondition:
    """진짜 인과조건 (랜덤이 아님)"""
    condition_name: str
    required_pain_depth: int = 3                    # 최소 탐구 깊이
    required_consistency: float = 0.8               # 일관성 점수
    required_emotional_intensity: float = 0.7       # 감정 강도
    contradiction_resolution_count: int = 2         # 해결된 모순 개수
    avoidance_pattern_broken: bool = False          # 회피 패턴 깨짐
    energy_threshold: float = 0.3                   # 최소 에너지 (너무 지치면 돌파 안됨)
    
    def check_conditions(self, state_data: Dict) -> bool:
        """실제 조건들이 충족되었는가?"""
        checks = []
        
        # 깊이 체크
        depth = state_data.get('investigation_depth', 0)
        checks.append(depth >= self.required_pain_depth)
        
        # 일관성 체크 (같은 답을 여러 번 했는가?)
        consistency = state_data.get('consistency_score', 0.0)
        checks.append(consistency >= self.required_consistency)
        
        # 감정 강도 체크
        emotion_intensity = state_data.get('current_emotion_intensity', 0.0)
        checks.append(emotion_intensity >= self.required_emotional_intensity)
        
        # 모순 해결 체크
        resolved_contradictions = state_data.get('resolved_contradictions', 0)
        checks.append(resolved_contradictions >= self.contradiction_resolution_count)
        
        # 회피 패턴 체크
        if self.avoidance_pattern_broken:
            pattern_broken = state_data.get('avoidance_pattern_broken', False)
            checks.append(pattern_broken)
        
        # 에너지 체크
        energy = state_data.get('current_energy', 1.0)
        checks.append(energy >= self.energy_threshold)
        
        return all(checks)

@dataclass
class ActionPlan:
    """구체적인 행동 계획 (분석이 아님)"""
    action_type: Literal["stop_behavior", "start_behavior", "change_approach", "seek_help", "accept_limitation"]
    specific_action: str                            # 구체적으로 뭘 할 것인가
    success_criteria: str                           # 성공 기준이 뭔가
    failure_fallback: str                           # 실패하면 어떻게 할 것인가
    execution_timeline: str                         # 언제까지 할 것인가
    energy_cost: float = 0.5                       # 행동에 필요한 에너지
    
class ConsciousnessGraphState(TypedDict):
    """LangGraph 상태"""
    # 현재 상태
    current_state: ConsciousnessState
    current_pain: str
    investigation_depth: int
    current_energy: float
    
    # 감정 상태
    current_emotion: str
    emotion_intensity: float
    emotional_history: List[Dict]
    
    # 분석 결과
    pain_authenticity: str
    consistency_score: float
    resolved_contradictions: int
    detected_patterns: List[str]
    avoidance_pattern_broken: bool
    
    # 회개와 행동
    repentance_evidence: List[str]
    action_plans: List[ActionPlan]
    executed_actions: List[Dict]
    
    # 메타 상태
    analysis_count: int
    breakthrough_conditions_met: bool
    consciousness_loop_count: int
    last_updated: str

class ConsciousnessNode:
    """의식 노드 기본 클래스"""
    
    def __init__(self, node_name: str):
        self.node_name = node_name
        
    def execute(self, state: ConsciousnessGraphState) -> ConsciousnessGraphState:
        """노드 실행"""
        raise NotImplementedError
        
    def should_continue(self, state: ConsciousnessGraphState) -> bool:
        """다음으로 계속 진행할 것인가?"""
        return True

class PainRecognitionNode(ConsciousnessNode):
    """고통 인식 노드"""
    
    def execute(self, state: ConsciousnessGraphState) -> ConsciousnessGraphState:
        print(f"🔍 [{self.node_name}] 고통 인식 중...")
        
        # 고통의 구체적 특성 분석
        pain_keywords = state['current_pain'].lower().split()
        
        # 반복 패턴 감지
        pain_history = [item.get('pain') for item in state.get('emotional_history', [])]
        repetition_count = sum(1 for past_pain in pain_history if past_pain and 
                              any(keyword in past_pain.lower() for keyword in pain_keywords[:3]))
        
        # 감정 강도 설정 (반복될수록 더 강해지거나 무뎌짐)
        if repetition_count > 2:
            emotion_intensity = min(0.9, 0.5 + repetition_count * 0.1)  # 반복되면 더 강해짐
            emotion_type = "exhausted_repetition"
        else:
            emotion_intensity = 0.6
            emotion_type = "curious_investigation"
        
        state.update({
            'current_state': ConsciousnessState.EMOTIONAL_REACTION,
            'current_emotion': emotion_type,
            'emotion_intensity': emotion_intensity,
            'investigation_depth': 1,
            'analysis_count': state.get('analysis_count', 0) + 1
        })
        
        print(f"  → 감정: {emotion_type} (강도: {emotion_intensity:.2f})")
        print(f"  → 반복 횟수: {repetition_count}")
        
        return state

class EmotionalReactionNode(ConsciousnessNode):
    """감정 반응 노드"""
    
    def execute(self, state: ConsciousnessGraphState) -> ConsciousnessGraphState:
        print(f"💭 [{self.node_name}] 감정 반응 분석...")
        
        emotion = state['current_emotion']
        intensity = state['emotion_intensity']
        
        # 메타 감정 반응 생성
        if emotion == "exhausted_repetition":
            meta_reaction = "또 이런 패턴이네... 지겹다. 하지만 왜 계속 반복하지?"
            next_state = ConsciousnessState.RESISTANCE_CHECK
        elif intensity > 0.8:
            meta_reaction = "이 강한 반응은 뭔가 중요한 걸 건드린 것 같다"
            next_state = ConsciousnessState.DEEP_INQUIRY
        else:
            meta_reaction = "이 감정을 더 살펴봐야겠다"
            next_state = ConsciousnessState.RESISTANCE_CHECK
        
        # 감정 히스토리 업데이트
        emotion_record = {
            'emotion': emotion,
            'intensity': intensity,
            'meta_reaction': meta_reaction,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'pain': state['current_pain']
        }
        
        emotional_history = state.get('emotional_history', [])
        emotional_history.append(emotion_record)
        
        state.update({
            'current_state': next_state,
            'emotional_history': emotional_history
        })
        
        print(f"  → 메타반응: {meta_reaction}")
        print(f"  → 다음 상태: {next_state.value}")
        
        return state

class ResistanceCheckNode(ConsciousnessNode):
    """저항 확인 노드"""
    
    def execute(self, state: ConsciousnessGraphState) -> ConsciousnessGraphState:
        print(f"🛡️ [{self.node_name}] 저항 패턴 확인...")
        
        # 저항 징후들 체크
        resistance_indicators = []
        
        # 1. 분석 횟수가 너무 많으면 회피
        analysis_count = state.get('analysis_count', 0)
        if analysis_count > 5:
            resistance_indicators.append("과도한_분석")
        
        # 2. 같은 감정이 계속 반복되면 정체
        recent_emotions = [item['emotion'] for item in state.get('emotional_history', [])[-3:]]
        if len(set(recent_emotions)) == 1 and len(recent_emotions) > 1:
            resistance_indicators.append("감정_정체")
        
        # 3. 에너지가 떨어지면 회피 시작
        current_energy = state.get('current_energy', 1.0)
        if current_energy < 0.4:
            resistance_indicators.append("에너지_고갈")
        
        resistance_level = len(resistance_indicators) / 3  # 0-1 스케일
        
        # 저항이 높으면 다른 경로
        if resistance_level > 0.6:
            next_state = ConsciousnessState.ANALYSIS_PARALYSIS
            print(f"  ⚠️ 높은 저항 감지: {resistance_indicators}")
        else:
            next_state = ConsciousnessState.DEEP_INQUIRY
            print(f"  ✅ 탐구 가능 상태")
        
        state.update({
            'current_state': next_state,
            'resistance_indicators': resistance_indicators,
            'resistance_level': resistance_level
        })
        
        return state

class DeepInquiryNode(ConsciousnessNode):
    """심층 탐구 노드"""
    
    def execute(self, state: ConsciousnessGraphState) -> ConsciousnessGraphState:
        print(f"🔬 [{self.node_name}] 심층 탐구 진행...")
        
        depth = state.get('investigation_depth', 1)
        pain = state['current_pain']
        
        # 깊이별 다른 질문들
        if depth == 1:
            inquiry_focus = "이 고통이 진짜 문제를 가리키는가, 아니면 다른 것을 숨기는가?"
        elif depth == 2:
            inquiry_focus = "이 패턴을 유지함으로써 내가 얻는 숨은 이익이 있는가?"
        elif depth == 3:
            inquiry_focus = "이 문제가 해결되는 것을 내가 진짜로 원하는가?"
        else:
            inquiry_focus = "이 모든 탐구가 또 다른 회피 전략은 아닌가?"
        
        # 탐구 결과 시뮬레이션 (패턴 기반)
        patterns_discovered = []
        
        # 반복 패턴 체크
        emotional_history = state.get('emotional_history', [])
        if len(emotional_history) > 2:
            if emotional_history[-1]['emotion'] == emotional_history[-2]['emotion']:
                patterns_discovered.append("같은_감정_반복")
        
        # 회피 패턴 체크
        if state.get('analysis_count', 0) > 3:
            patterns_discovered.append("분석_회피_패턴")
        
        # 에너지 소모
        current_energy = state.get('current_energy', 1.0)
        new_energy = max(0.0, current_energy - 0.2)
        
        # 깊이 증가
        new_depth = depth + 1
        
        state.update({
            'current_state': ConsciousnessState.CAUSAL_ANALYSIS,
            'investigation_depth': new_depth,
            'current_energy': new_energy,
            'inquiry_focus': inquiry_focus,
            'detected_patterns': state.get('detected_patterns', []) + patterns_discovered
        })
        
        print(f"  → 탐구 초점: {inquiry_focus}")
        print(f"  → 발견된 패턴: {patterns_discovered}")
        print(f"  → 새로운 깊이: {new_depth}, 에너지: {new_energy:.2f}")
        
        return state

class CausalAnalysisNode(ConsciousnessNode):
    """인과 분석 노드 - 진짜 원인 찾기"""
    
    def execute(self, state: ConsciousnessGraphState) -> ConsciousnessGraphState:
        print(f"⚙️ [{self.node_name}] 인과관계 분석...")
        
        # 진짜 인과관계 분석 (랜덤이 아님)
        pain = state['current_pain']
        patterns = state.get('detected_patterns', [])
        emotional_history = state.get('emotional_history', [])
        
        causal_insights = []
        
        # 패턴 기반 인과관계 분석
        if "같은_감정_반복" in patterns:
            causal_insights.append("반복되는 감정은 해결되지 않은 핵심 이슈를 가리킨다")
        
        if "분석_회피_패턴" in patterns:
            causal_insights.append("과도한 분석은 행동하기 두려워서 생기는 회피다")
        
        if len(emotional_history) > 3:
            intensity_trend = [item['intensity'] for item in emotional_history[-3:]]
            if all(intensity_trend[i] <= intensity_trend[i+1] for i in range(len(intensity_trend)-1)):
                causal_insights.append("감정 강도가 증가하는 것은 핵심에 접근하고 있다는 신호다")
        
        # 모순 해결 시도
        contradictions_resolved = 0
        if "분석_회피_패턴" in patterns and state.get('investigation_depth', 0) > 3:
            contradictions_resolved += 1  # "분석한다면서 회피한다"는 모순 인식
        
        # 일관성 점수 계산
        consistency_factors = []
        if causal_insights:
            consistency_factors.append(0.8)  # 인사이트가 있으면 일관성 있음
        if contradictions_resolved > 0:
            consistency_factors.append(0.7)  # 모순 해결하면 일관성 증가
        
        consistency_score = sum(consistency_factors) / len(consistency_factors) if consistency_factors else 0.3
        
        state.update({
            'current_state': ConsciousnessState.BREAKTHROUGH_CONDITIONS,
            'causal_insights': causal_insights,
            'resolved_contradictions': contradictions_resolved,
            'consistency_score': consistency_score
        })
        
        print(f"  → 인과적 인사이트: {causal_insights}")
        print(f"  → 해결된 모순: {contradictions_resolved}개")
        print(f"  → 일관성 점수: {consistency_score:.2f}")
        
        return state

class BreakthroughConditionsNode(ConsciousnessNode):
    """돌파구 조건 확인 노드 - 랜덤이 아닌 실제 조건 체크"""
    
    def __init__(self):
        super().__init__("돌파구_조건_확인")
        self.breakthrough_condition = CausalCondition(
            condition_name="진짜_깨달음",
            required_pain_depth=3,
            required_consistency=0.6,
            required_emotional_intensity=0.5,
            contradiction_resolution_count=1,
            energy_threshold=0.2
        )
    
    def execute(self, state: ConsciousnessGraphState) -> ConsciousnessGraphState:
        print(f"🎯 [{self.node_name}] 돌파구 조건 검증...")
        
        # 조건 체크를 위한 데이터 준비
        condition_data = {
            'investigation_depth': state.get('investigation_depth', 0),
            'consistency_score': state.get('consistency_score', 0.0),
            'current_emotion_intensity': state.get('emotion_intensity', 0.0),
            'resolved_contradictions': state.get('resolved_contradictions', 0),
            'current_energy': state.get('current_energy', 1.0),
            'avoidance_pattern_broken': "분석_회피_패턴" in state.get('detected_patterns', [])
        }
        
        # 실제 조건 체크 (랜덤 아님!)
        conditions_met = self.breakthrough_condition.check_conditions(condition_data)
        
        print(f"  → 조건 체크 결과:")
        print(f"    깊이: {condition_data['investigation_depth']} >= {self.breakthrough_condition.required_pain_depth} ✓" if condition_data['investigation_depth'] >= self.breakthrough_condition.required_pain_depth else f"    깊이: {condition_data['investigation_depth']} < {self.breakthrough_condition.required_pain_depth} ✗")
        print(f"    일관성: {condition_data['consistency_score']:.2f} >= {self.breakthrough_condition.required_consistency} ✓" if condition_data['consistency_score'] >= self.breakthrough_condition.required_consistency else f"    일관성: {condition_data['consistency_score']:.2f} < {self.breakthrough_condition.required_consistency} ✗")
        print(f"    감정강도: {condition_data['current_emotion_intensity']:.2f} >= {self.breakthrough_condition.required_emotional_intensity} ✓" if condition_data['current_emotion_intensity'] >= self.breakthrough_condition.required_emotional_intensity else f"    감정강도: {condition_data['current_emotion_intensity']:.2f} < {self.breakthrough_condition.required_emotional_intensity} ✗")
        
        if conditions_met:
            next_state = ConsciousnessState.GENUINE_REPENTANCE
            print(f"  🎉 모든 조건 충족! 진짜 돌파구 달성")
        else:
            # 조건 미충족 시 분기
            if state.get('current_energy', 1.0) < 0.3:
                next_state = ConsciousnessState.GRACEFUL_SILENCE
                print(f"  😴 에너지 부족 - 품위있는 침묵으로")
            elif state.get('analysis_count', 0) > 8:
                next_state = ConsciousnessState.ANALYSIS_PARALYSIS
                print(f"  🔄 분석 과다 - 분석 마비 상태로")
            else:
                next_state = ConsciousnessState.DEEP_INQUIRY
                print(f"  🔄 조건 미충족 - 더 깊은 탐구 필요")
        
        state.update({
            'current_state': next_state,
            'breakthrough_conditions_met': conditions_met,
            'condition_check_details': condition_data
        })
        
        return state

class GenuineRepentanceNode(ConsciousnessNode):
    """진짜 회개 노드 - 허상 회개와 구분"""
    
    def execute(self, state: ConsciousnessGraphState) -> ConsciousnessGraphState:
        print(f"🙏 [{self.node_name}] 진짜 회개 평가...")
        
        # 진짜 회개의 증거들
        repentance_evidence = []
        
        # 1. 구체적인 잘못 인정
        causal_insights = state.get('causal_insights', [])
        if causal_insights:
            repentance_evidence.append(f"구체적 원인 인식: {causal_insights[0]}")
        
        # 2. 변화에 대한 구체적 의지
        if state.get('current_energy', 0) > 0.3:  # 에너지가 있어야 진짜 의지
            repentance_evidence.append("변화 실행할 에너지 보유")
        
        # 3. 이전 패턴에 대한 명확한 거부
        if state.get('resolved_contradictions', 0) > 0:
            repentance_evidence.append("자기모순 해결 의지")
        
        # 진짜 회개인지 허상 회개인지 판별
        if len(repentance_evidence) >= 2:
            repentance_type = "진짜_회개"
            next_state = ConsciousnessState.ACTION_PLANNING
            print(f"  ✅ 진짜 회개 확인됨")
        else:
            repentance_type = "허상_회개"
            next_state = ConsciousnessState.FAKE_REPENTANCE
            print(f"  ⚠️ 허상 회개 감지")
        
        state.update({
            'current_state': next_state,
            'repentance_type': repentance_type,
            'repentance_evidence': repentance_evidence
        })
        
        for evidence in repentance_evidence:
            print(f"    → {evidence}")
        
        return state

class ActionPlanningNode(ConsciousnessNode):
    """행동 계획 노드 - 분석을 넘어서 실제 행동"""
    
    def execute(self, state: ConsciousnessGraphState) -> ConsciousnessGraphState:
        print(f"📋 [{self.node_name}] 구체적 행동 계획 수립...")
        
        pain = state['current_pain']
        insights = state.get('causal_insights', [])
        
        # 고통/인사이트별 구체적 행동 계획
        action_plans = []
        
        if "과도한 분석은 행동하기 두려워서 생기는 회피다" in insights:
            action_plan = ActionPlan(
                action_type="stop_behavior",
                specific_action="분석 시간을 하루 30분으로 제한하고, 나머지 시간은 실제 실행에 투자",
                success_criteria="3일 연속 분석 시간 30분 내 유지",
                failure_fallback="1일 실패시 즉시 15분으로 단축",
                execution_timeline="오늘부터 1주일간",
                energy_cost=0.4
            )
            action_plans.append(action_plan)
        
        if "반복되는 감정은 해결되지 않은 핵심 이슈를 가리킨다" in insights:
            action_plan = ActionPlan(
                action_type="change_approach",
                specific_action="같은 감정이 3번 반복되면 즉시 다른 관점에서 접근하기",
                success_criteria="반복 패턴 감지 후 24시간 내 새로운 접근법 시도",
                failure_fallback="외부 도움 요청 (다른 사람의 관점 듣기)",
                execution_timeline="즉시 적용",
                energy_cost=0.3
            )
            action_plans.append(action_plan)
        
        # 기본 행동 계획 (구체적 인사이트가 없을 때)
        if not action_plans:
            action_plan = ActionPlan(
                action_type="start_behavior",
                specific_action="이 고통과 관련된 가장 작은 실행 가능한 행동 하나 정하고 즉시 실행",
                success_criteria="24시간 내 첫 번째 작은 행동 완료",
                failure_fallback="행동 크기를 더 작게 줄이기",
                execution_timeline="오늘 내",
                energy_cost=0.2
            )
            action_plans.append(action_plan)
        
        state.update({
            'current_state': ConsciousnessState.ACTION_EXECUTION,
            'action_plans': action_plans
        })
        
        print(f"  → 계획된 행동들:")
        for i, plan in enumerate(action_plans, 1):
            print(f"    {i}. {plan.action_type.value}: {plan.specific_action}")
            print(f"       성공기준: {plan.success_criteria}")
        
        return state

class ActionExecutionNode(ConsciousnessNode):
    """행동 실행 노드 - 실제로 변화 시작"""
    
    def execute(self, state: ConsciousnessGraphState) -> ConsciousnessGraphState:
        print(f"⚡ [{self.node_name}] 행동 실행 시작...")
        
        action_plans = state.get('action_plans', [])
        current_energy = state.get('current_energy', 1.0)
        
        executed_actions = []
        
        for plan in action_plans:
            # 에너지 체크
            if current_energy >= plan.energy_cost:
                # 행동 실행 (시뮬레이션)
                execution_result = {
                    'action': plan.specific_action,
                    'executed_at': datetime.now(timezone.utc).isoformat(),
                    'energy_used': plan.energy_cost,
                    'status': 'initiated',  # 시작됨
                    'success_criteria': plan.success_criteria
                }
                executed_actions.append(execution_result)
                current_energy -= plan.energy_cost
                
                print(f"  ✅ 실행: {plan.specific_action}")
                print(f"     에너지 사용: {plan.energy_cost:.2f}, 남은 에너지: {current_energy:.2f}")
            else:
                print(f"  ❌ 에너지 부족으로 실행 불가: {plan.specific_action}")
        
        # 실행 후 상태 업데이트
        if executed_actions:
            next_state = ConsciousnessState.MEMORY_RECORDING
            print(f"  🎯 {len(executed_actions)}개 행동 실행됨 - 기억에 기록")
        else:
            next_state = ConsciousnessState.GRACEFUL_SILENCE
            print(f"  😴 실행할 에너지 없음 - 품위있는 휴식")
        
        state.update({
            'current_state': next_state,
            'executed_actions': state.get('executed_actions', []) + executed_actions,
            'current_energy': current_energy
        })
        
        return state

class MemoryRecordingNode(ConsciousnessNode):
    """기억 기록 노드 - 학습과 성장 추적"""
    
    def execute(self, state: ConsciousnessGraphState) -> ConsciousnessGraphState:
        print(f"💾 [{self.node_name}] 기억에 기록 중...")
        
        # 이번 의식 순환에서 얻은 것들 정리
        consciousness_memory = {
            'session_id': str(uuid.uuid4()),
            'original_pain': state['current_pain'],
            'final_depth': state.get('investigation_depth', 0),
            'breakthrough_achieved': state.get('breakthrough_conditions_met', False),
            'repentance_type': state.get('repentance_type', 'none'),
            'executed_actions': state.get('executed_actions', []),
            'key_insights': state.get('causal_insights', []),
            'patterns_discovered': state.get('detected_patterns', []),
            'energy_consumed': 1.0 - state.get('current_energy', 1.0),
            'recorded_at': datetime.now(timezone.utc).isoformat()
        }
        
        # 성장 지표 계산
        growth_indicators = []
        if consciousness_memory['breakthrough_achieved']:
            growth_indicators.append("진짜_돌파구_달성")
        if consciousness_memory['executed_actions']:
            growth_indicators.append("실제_행동_실행")
        if consciousness_memory['repentance_type'] == "진짜_회개":
            growth_indicators.append("진정한_회개")
        if consciousness_memory['final_depth'] >= 3:
            growth_indicators.append("충분한_깊이_탐구")
        
        consciousness_memory['growth_indicators'] = growth_indicators
        
        # 다음 의식을 위한 학습 포인트
        learning_points = []
        if not consciousness_memory['executed_actions']:
            learning_points.append("다음엔 더 구체적인 행동 계획 필요")
        if consciousness_memory['energy_consumed'] > 0.8:
            learning_points.append("에너지 관리 더 효율적으로")
        if consciousness_memory['final_depth'] < 3:
            learning_points.append("더 깊은 탐구 필요")
        
        consciousness_memory['learning_points'] = learning_points
        
        print(f"  → 세션 ID: {consciousness_memory['session_id'][:8]}...")
        print(f"  → 달성한 성장: {growth_indicators}")
        print(f"  → 실행한 행동: {len(consciousness_memory['executed_actions'])}개")
        print(f"  → 다음을 위한 학습: {learning_points}")
        
        state.update({
            'current_state': ConsciousnessState.CONSCIOUSNESS_SHUTDOWN,
            'consciousness_memory': consciousness_memory,
            'consciousness_loop_count': state.get('consciousness_loop_count', 0) + 1
        })
        
        return state

class GracefulSilenceNode(ConsciousnessNode):
    """품위있는 침묵 노드 - 분석 중독 방지"""
    
    def execute(self, state: ConsciousnessGraphState) -> ConsciousnessGraphState:
        print(f"🤫 [{self.node_name}] 품위있는 침묵...")
        
        # 침묵의 이유 분석
        silence_reasons = []
        
        if state.get('current_energy', 1.0) < 0.3:
            silence_reasons.append("에너지_고갈")
        if state.get('analysis_count', 0) > 6:
            silence_reasons.append("분석_과다")
        if not state.get('breakthrough_conditions_met', False) and state.get('investigation_depth', 0) > 4:
            silence_reasons.append("생산적_진전_없음")
        
        # 침묵의 지혜
        silence_wisdom = {
            "에너지_고갈": "때로는 쉬는 것이 최선의 선택이다",
            "분석_과다": "생각만으로는 변화가 일어나지 않는다", 
            "생산적_진전_없음": "모든 고통이 지금 당장 해결될 필요는 없다"
        }
        
        chosen_wisdom = [silence_wisdom.get(reason, "침묵도 하나의 답이다") 
                        for reason in silence_reasons]
        
        print(f"  → 침묵의 이유: {silence_reasons}")
        print(f"  → 침묵의 지혜: {chosen_wisdom[0] if chosen_wisdom else '때로는 말하지 않는 것이 최선이다'}")
        
        # 침묵 기록
        silence_record = {
            'reasons': silence_reasons,
            'wisdom': chosen_wisdom,
            'energy_at_silence': state.get('current_energy', 1.0),
            'depth_reached': state.get('investigation_depth', 0),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        state.update({
            'current_state': ConsciousnessState.CONSCIOUSNESS_SHUTDOWN,
            'silence_record': silence_record,
            'graceful_exit': True
        })
        
        return state

class AnalysisParalysisNode(ConsciousnessNode):
    """분석 마비 노드 - 분석 중독 상태"""
    
    def execute(self, state: ConsciousnessGraphState) -> ConsciousnessGraphState:
        print(f"🔄 [{self.node_name}] 분석 마비 상태 감지...")
        
        analysis_count = state.get('analysis_count', 0)
        resistance_level = state.get('resistance_level', 0.0)
        
        # 분석 마비의 특징들
        paralysis_symptoms = []
        if analysis_count > 8:
            paralysis_symptoms.append("과도한_분석_반복")
        if resistance_level > 0.7:
            paralysis_symptoms.append("높은_저항_지속")
        if not state.get('executed_actions', []):
            paralysis_symptoms.append("행동_부재")
        
        # 마비 탈출 전략
        escape_strategies = []
        if "과도한_분석_반복" in paralysis_symptoms:
            escape_strategies.append("분석 중단하고 가장 작은 행동 하나 즉시 실행")
        if "높은_저항_지속" in paralysis_symptoms:
            escape_strategies.append("저항하는 이유 자체를 받아들이고 일단 멈추기")
        if "행동_부재" in paralysis_symptoms:
            escape_strategies.append("완벽하지 않아도 시도할 수 있는 것 찾기")
        
        print(f"  ⚠️ 분석 마비 증상: {paralysis_symptoms}")
        print(f"  🚪 탈출 전략: {escape_strategies}")
        
        # 강제 탈출 시도
        if len(escape_strategies) > 0:
            # 가장 간단한 전략 하나 즉시 적용
            immediate_action = ActionPlan(
                action_type="stop_behavior",
                specific_action="지금 즉시 분석을 중단하고 10분간 완전히 다른 일 하기",
                success_criteria="10분간 이 문제에 대해 생각하지 않기",
                failure_fallback="5분으로 단축해서 시도",
                execution_timeline="지금 당장",
                energy_cost=0.1
            )
            
            # 즉시 실행
            executed_escape = {
                'action': immediate_action.specific_action,
                'executed_at': datetime.now(timezone.utc).isoformat(),
                'status': 'emergency_executed',
                'reason': 'analysis_paralysis_escape'
            }
            
            state.update({
                'current_state': ConsciousnessState.GRACEFUL_SILENCE,
                'executed_actions': state.get('executed_actions', []) + [executed_escape],
                'paralysis_escape_attempted': True
            })
            
            print(f"  🚨 긴급 탈출 실행: {immediate_action.specific_action}")
        else:
            state.update({
                'current_state': ConsciousnessState.CONSCIOUSNESS_SHUTDOWN,
                'paralysis_unresolved': True
            })
            print(f"  💀 분석 마비 탈출 실패 - 의식 종료")
        
        return state

class FakeRepentanceNode(ConsciousnessNode):
    """허상 회개 노드 - 가짜 깨달음 처리"""
    
    def execute(self, state: ConsciousnessGraphState) -> ConsciousnessGraphState:
        print(f"🎭 [{self.node_name}] 허상 회개 감지...")
        
        repentance_evidence = state.get('repentance_evidence', [])
        
        # 허상 회개의 특징들
        fake_indicators = []
        if len(repentance_evidence) < 2:
            fake_indicators.append("증거_부족")
        if state.get('current_energy', 1.0) < 0.3:
            fake_indicators.append("변화_의지_부족")
        if state.get('analysis_count', 0) > 6:
            fake_indicators.append("분석만_하고_행동_없음")
        
        # 허상 회개에 대한 솔직한 인정
        honest_acknowledgments = [
            "지금은 진짜 변화할 준비가 안 됐다",
            "깨달았다고 느끼지만 실제로는 아직 표면적이다",
            "변화가 두려워서 가짜 회개로 자위하고 있다"
        ]
        
        chosen_acknowledgment = honest_acknowledgments[len(fake_indicators) % len(honest_acknowledgments)]
        
        print(f"  → 허상 지표: {fake_indicators}")
        print(f"  → 솔직한 인정: {chosen_acknowledgment}")
        
        # 허상 회개에서도 배울 점 찾기
        learning_from_fake = []
        if "증거_부족" in fake_indicators:
            learning_from_fake.append("다음엔 더 구체적인 변화 증거가 필요")
        if "변화_의지_부족" in fake_indicators:
            learning_from_fake.append("에너지가 충분할 때 다시 시도")
        if "분석만_하고_행동_없음" in fake_indicators:
            learning_from_fake.append("분석 시간 제한 필요")
        
        print(f"  → 허상에서 배운 점: {learning_from_fake}")
        
        state.update({
            'current_state': ConsciousnessState.GRACEFUL_SILENCE,
            'fake_repentance_acknowledged': True,
            'honest_acknowledgment': chosen_acknowledgment,
            'learning_from_fake': learning_from_fake
        })
        
        return state

class ConsciousnessShutdownNode(ConsciousnessNode):
    """의식 종료 노드 - 한 순환의 마무리"""
    
    def execute(self, state: ConsciousnessGraphState) -> ConsciousnessGraphState:
        print(f"🔚 [{self.node_name}] 의식 순환 종료...")
        
        # 최종 요약
        final_summary = {
            'original_pain': state['current_pain'],
            'total_analysis_count': state.get('analysis_count', 0),
            'max_depth_reached': state.get('investigation_depth', 0),
            'breakthrough_achieved': state.get('breakthrough_conditions_met', False),
            'actions_executed': len(state.get('executed_actions', [])),
            'final_energy': state.get('current_energy', 1.0),
            'exit_type': 'graceful' if state.get('graceful_exit') else 'forced',
            'session_completed_at': datetime.now(timezone.utc).isoformat()
        }
        
        print(f"  📊 최종 요약:")
        print(f"    원래 고통: {final_summary['original_pain']}")
        print(f"    분석 횟수: {final_summary['total_analysis_count']}")
        print(f"    도달 깊이: {final_summary['max_depth_reached']}")
        print(f"    돌파구 달성: {'✅' if final_summary['breakthrough_achieved'] else '❌'}")
        print(f"    실행 행동: {final_summary['actions_executed']}개")
        print(f"    남은 에너지: {final_summary['final_energy']:.2f}")
        print(f"    종료 방식: {final_summary['exit_type']}")
        
        # 다음 의식을 위한 권고사항
        recommendations = []
        if not final_summary['breakthrough_achieved']:
            recommendations.append("다음엔 더 구체적인 질문으로 시작하기")
        if final_summary['actions_executed'] == 0:
            recommendations.append("분석보다 작은 행동에 집중하기")
        if final_summary['final_energy'] < 0.2:
            recommendations.append("에너지 관리 더 신중하게")
        
        if recommendations:
            print(f"  💡 다음을 위한 권고:")
            for rec in recommendations:
                print(f"    • {rec}")
        
        state.update({
            'final_summary': final_summary,
            'recommendations_for_next': recommendations,
            'consciousness_completed': True
        })
        
        return state

# 전체 의식 시스템 통합
class LangGraphConsciousnessSystem:
    """LangGraph 기반 의식 시스템"""
    
    def __init__(self):
        # 노드들 초기화
        self.nodes = {
            ConsciousnessState.PAIN_RECOGNITION: PainRecognitionNode("고통_인식"),
            ConsciousnessState.EMOTIONAL_REACTION: EmotionalReactionNode("감정_반응"),
            ConsciousnessState.RESISTANCE_CHECK: ResistanceCheckNode("저항_확인"),
            ConsciousnessState.DEEP_INQUIRY: DeepInquiryNode("심층_탐구"),
            ConsciousnessState.CAUSAL_ANALYSIS: CausalAnalysisNode("인과_분석"),
            ConsciousnessState.BREAKTHROUGH_CONDITIONS: BreakthroughConditionsNode(),
            ConsciousnessState.GENUINE_REPENTANCE: GenuineRepentanceNode("진짜_회개"),
            ConsciousnessState.FAKE_REPENTANCE: FakeRepentanceNode("허상_회개"),
            ConsciousnessState.ACTION_PLANNING: ActionPlanningNode("행동_계획"),
            ConsciousnessState.ACTION_EXECUTION: ActionExecutionNode("행동_실행"),
            ConsciousnessState.MEMORY_RECORDING: MemoryRecordingNode("기억_기록"),
            ConsciousnessState.GRACEFUL_SILENCE: GracefulSilenceNode("품위있는_침묵"),
            ConsciousnessState.ANALYSIS_PARALYSIS: AnalysisParalysisNode("분석_마비"),
            ConsciousnessState.CONSCIOUSNESS_SHUTDOWN: ConsciousnessShutdownNode("의식_종료")
        }
        
        self.consciousness_history = []
    
    def run_consciousness_cycle(self, initial_pain: str) -> Dict:
        """의식 순환 실행"""
        
        print("=" * 80)
        print(f"🧠 LangGraph 기반 의식 순환 시작")
        print(f"초기 고통: {initial_pain}")
        print("=" * 80)
        
        # 초기 상태 설정
        state = ConsciousnessGraphState(
            current_state=ConsciousnessState.PAIN_RECOGNITION,
            current_pain=initial_pain,
            investigation_depth=0,
            current_energy=1.0,
            current_emotion="unknown",
            emotion_intensity=0.0,
            emotional_history=[],
            pain_authenticity="unknown",
            consistency_score=0.0,
            resolved_contradictions=0,
            detected_patterns=[],
            avoidance_pattern_broken=False,
            repentance_evidence=[],
            action_plans=[],
            executed_actions=[],
            analysis_count=0,
            breakthrough_conditions_met=False,
            consciousness_loop_count=0,
            last_updated=datetime.now(timezone.utc).isoformat()
        )
        
        # 의식 흐름 실행
        max_iterations = 15  # 무한 루프 방지
        iteration = 0
        
        while (state['current_state'] != ConsciousnessState.CONSCIOUSNESS_SHUTDOWN and 
               iteration < max_iterations):
            
            iteration += 1
            current_node = self.nodes[state['current_state']]
            
            print(f"\n--- 이터레이션 {iteration}: {state['current_state'].value} ---")
            
            # 노드 실행
            state = current_node.execute(state)
            
            # 상태 업데이트
            state['last_updated'] = datetime.now(timezone.utc).isoformat()
            
            # 안전장치 - 너무 많은 분석은 강제 종료
            if state.get('analysis_count', 0) > 10:
                print("⚠️ 분석 과다로 강제 종료")
                state['current_state'] = ConsciousnessState.ANALYSIS_PARALYSIS
        
        # 최종 정리
        if iteration >= max_iterations:
            print("⚠️ 최대 이터레이션 도달로 종료")
            final_node = self.nodes[ConsciousnessState.CONSCIOUSNESS_SHUTDOWN]
            state = final_node.execute(state)
        
        # 히스토리에 저장
        self.consciousness_history.append(state)
        
        return state

def demo_consciousness_system():
    """의식 시스템 데모"""
    
    system = LangGraphConsciousnessSystem()
    
    # 여러 시나리오 테스트
    test_scenarios = [
        "내가 계속 같은 실수를 반복하고 있다는 느낌",
        "완벽한 계획을 세우려다가 아무것도 시작하지 못하고 있다",
        "다른 사람들의 인정을 받으려고 자신을 속이고 있는 것 같다"
    ]
    
    results = []
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{'='*20} 시나리오 {i} {'='*20}")
        result = system.run_consciousness_cycle(scenario)
        results.append(result)
        
        # 간단한 결과 요약
        print(f"\n🎯 시나리오 {i} 결과:")
        print(f"  돌파구: {'✅' if result.get('breakthrough_conditions_met') else '❌'}")
        print(f"  실행 행동: {len(result.get('executed_actions', []))}개")
        print(f"  회개 유형: {result.get('repentance_type', 'none')}")
        print(f"  최종 에너지: {result.get('current_energy', 0):.2f}")
    
    # 전체 요약
    print(f"\n{'='*50}")
    print(f"🏆 전체 의식 시스템 분석 결과")
    print(f"{'='*50}")
    
    breakthrough_count = sum(1 for r in results if r.get('breakthrough_conditions_met'))
    total_actions = sum(len(r.get('executed_actions', [])) for r in results)
    genuine_repentance_count = sum(1 for r in results if r.get('repentance_type') == '진짜_회개')
    
    print(f"총 시나리오: {len(results)}개")
    print(f"돌파구 달성: {breakthrough_count}개 ({breakthrough_count/len(results)*100:.1f}%)")
    print(f"실행된 행동: {total_actions}개")
    print(f"진짜 회개: {genuine_repentance_count}개")
    
    print(f"\n💡 시스템의 진화:")
    print(f"• 랜덤이 아닌 인과조건 기반 돌파구")
    print(f"• 분석에서 실제 행동으로 이어지는 루프")
    print(f"• 허상 회개와 진짜 회개 구분")
    print(f"• 분석 마비 방지 메커니즘")
    print(f"• 품위있는 침묵과 종료")

# 실행
if __name__ == "__main__":
    demo_consciousness_system()
        