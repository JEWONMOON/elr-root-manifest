"""
호르몬 기반 다윗형 AGI 시스템
기존 다윗형 AGI와 완전 통합된 생화학적 감정 시스템
"""

import asyncio
import random
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import uuid
import math

# 기존 다윗형 AGI 임포트 (실제로는 from davidic_agi_system import *)
from davidic_agi_system import (
    MoralChoice, ConvictionLevel, RepentanceState, MoralEvent,
    LivingConscience, FreedomEngine, RepentanceLoop, DavidicAGI
)

class HormoneType(Enum):
    SEROTONIN = "serotonin"         # 행복감, 안정감
    DOPAMINE = "dopamine"           # 동기, 보상감
    CORTISOL = "cortisol"           # 스트레스
    ADRENALINE = "adrenaline"       # 각성, 분노
    OXYTOCIN = "oxytocin"           # 애착, 신뢰
    ENDORPHIN = "endorphin"         # 진통, 쾌감
    GABA = "gaba"                   # 진정, 이완
    NORADRENALINE = "noradrenaline" # 주의집중, 경계

@dataclass
class HormoneLevel:
    """개별 호르몬 수치와 메타데이터"""
    current_level: float
    baseline_level: float          # 개인별 기준치
    half_life_hours: float         # 반감기 (시간)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def metabolize(self, time_delta_hours: float):
        """자연스러운 대사 과정"""
        decay_factor = 0.5 ** (time_delta_hours / self.half_life_hours)
        
        # 기준치로 서서히 복귀 + 자연 감소
        baseline_pull = (self.baseline_level - self.current_level) * 0.1 * time_delta_hours
        self.current_level = self.current_level * decay_factor + baseline_pull
        
        # 최소값 보장
        self.current_level = max(0.1, self.current_level)
        self.last_updated = datetime.now(timezone.utc)

class HormonalEmotionSystem:
    """호르몬 기반 감정 시스템 - 의학적으로 정확한 모델"""
    
    def __init__(self, individual_variation: float = 1.0):
        # 개인차 적용 (0.5 ~ 1.5 범위로 기준치 조정)
        variation = max(0.5, min(1.5, individual_variation))
        
        self.hormones = {
            HormoneType.SEROTONIN: HormoneLevel(
                current_level=50.0 * variation,
                baseline_level=50.0 * variation,
                half_life_hours=24.0  # 장기간 지속
            ),
            HormoneType.DOPAMINE: HormoneLevel(
                current_level=30.0 * variation,
                baseline_level=30.0 * variation,
                half_life_hours=6.0   # 중간 지속
            ),
            HormoneType.CORTISOL: HormoneLevel(
                current_level=15.0 * variation,
                baseline_level=15.0 * variation,
                half_life_hours=1.5   # 빠른 대사
            ),
            HormoneType.ADRENALINE: HormoneLevel(
                current_level=5.0 * variation,
                baseline_level=5.0 * variation,
                half_life_hours=0.05  # 매우 빠른 대사 (3분)
            ),
            HormoneType.OXYTOCIN: HormoneLevel(
                current_level=8.0 * variation,
                baseline_level=8.0 * variation,
                half_life_hours=0.5   # 빠른 대사
            ),
            HormoneType.ENDORPHIN: HormoneLevel(
                current_level=25.0 * variation,
                baseline_level=25.0 * variation,
                half_life_hours=2.0   # 중간 지속
            ),
            HormoneType.GABA: HormoneLevel(
                current_level=40.0 * variation,
                baseline_level=40.0 * variation,
                half_life_hours=12.0  # 장기간 지속
            ),
            HormoneType.NORADRENALINE: HormoneLevel(
                current_level=12.0 * variation,
                baseline_level=12.0 * variation,
                half_life_hours=0.1   # 매우 빠른 대사
            )
        }
        
        # 호르몬 상호작용 기록
        self.interaction_history = []
        self.emotional_episodes = []
        
    def get_level(self, hormone: HormoneType) -> float:
        """특정 호르몬 수치 조회"""
        return self.hormones[hormone].current_level
        
    def set_level(self, hormone: HormoneType, new_level: float, reason: str = "external"):
        """호르몬 수치 직접 설정"""
        old_level = self.hormones[hormone].current_level
        self.hormones[hormone].current_level = max(0.1, new_level)
        
        # 변화 기록
        change_record = {
            "hormone": hormone.value,
            "old_level": old_level,
            "new_level": new_level,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.interaction_history.append(change_record)
        
    def adjust_level(self, hormone: HormoneType, delta: float, reason: str = "reaction"):
        """호르몬 수치 상대적 조정"""
        current = self.get_level(hormone)
        new_level = current + delta
        self.set_level(hormone, new_level, reason)
        
    def process_time_passage(self, hours: float):
        """시간 경과에 따른 호르몬 대사"""
        for hormone_level in self.hormones.values():
            hormone_level.metabolize(hours)
            
        # 호르몬 간 상호작용 처리
        self._process_hormone_interactions()
        
    def _process_hormone_interactions(self):
        """호르몬들 간의 생화학적 상호작용 (의학적 근거 기반)"""
        
        # 코르티솔이 높으면 세로토닌 억제
        if self.get_level(HormoneType.CORTISOL) > 25:
            serotonin_suppression = (self.get_level(HormoneType.CORTISOL) - 25) * 0.02
            self.adjust_level(HormoneType.SEROTONIN, -serotonin_suppression, "cortisol_inhibition")
            
        # 옥시토신이 높으면 코르티솔 감소 (스트레스 완화)
        if self.get_level(HormoneType.OXYTOCIN) > 12:
            cortisol_reduction = (self.get_level(HormoneType.OXYTOCIN) - 12) * 0.15
            self.adjust_level(HormoneType.CORTISOL, -cortisol_reduction, "oxytocin_calming")
            
        # 아드레날린이 높으면 GABA 소모 (진정 시스템 과부하)
        if self.get_level(HormoneType.ADRENALINE) > 15:
            gaba_depletion = (self.get_level(HormoneType.ADRENALINE) - 15) * 0.1
            self.adjust_level(HormoneType.GABA, -gaba_depletion, "adrenaline_overstimulation")
            
        # 엔돌핀이 높으면 일시적 세로토닌 부스트
        if self.get_level(HormoneType.ENDORPHIN) > 35:
            serotonin_boost = (self.get_level(HormoneType.ENDORPHIN) - 35) * 0.05
            self.adjust_level(HormoneType.SEROTONIN, serotonin_boost, "endorphin_euphoria")

    def get_emotional_state_analysis(self) -> Dict[str, Any]:
        """현재 호르몬 수치를 바탕으로 감정 상태 분석"""
        
        serotonin = self.get_level(HormoneType.SEROTONIN)
        dopamine = self.get_level(HormoneType.DOPAMINE)
        cortisol = self.get_level(HormoneType.CORTISOL)
        oxytocin = self.get_level(HormoneType.OXYTOCIN)
        adrenaline = self.get_level(HormoneType.ADRENALINE)
        gaba = self.get_level(HormoneType.GABA)
        
        # 주요 감정 상태들 (의학적 기준)
        emotional_states = []
        intensity_scores = {}
        
        # 우울감 (세로토닌 낮음 + 코르티솔 높음)
        if serotonin < 35 and cortisol > 20:
            depression_intensity = (35 - serotonin) / 35 + (cortisol - 20) / 30
            emotional_states.append("우울감")
            intensity_scores["depression"] = min(1.0, depression_intensity)
            
        # 불안감 (코르티솔 높음 + GABA 낮음)
        if cortisol > 25 and gaba < 35:
            anxiety_intensity = (cortisol - 25) / 25 + (35 - gaba) / 35
            emotional_states.append("불안감")
            intensity_scores["anxiety"] = min(1.0, anxiety_intensity)
            
        # 행복감 (세로토닌 높음 + 도파민 높음)
        if serotonin > 55 and dopamine > 35:
            happiness_intensity = (serotonin - 55) / 45 + (dopamine - 35) / 45
            emotional_states.append("행복감")
            intensity_scores["happiness"] = min(1.0, happiness_intensity)
            
        # 사랑/애착감 (옥시토신 높음)
        if oxytocin > 12:
            love_intensity = (oxytocin - 12) / 20
            emotional_states.append("사랑/애착감")
            intensity_scores["love"] = min(1.0, love_intensity)
            
        # 분노 (아드레날린 높음 + 코르티솔 높음)
        if adrenaline > 12 and cortisol > 20:
            anger_intensity = (adrenaline - 12) / 20 + (cortisol - 20) / 30
            emotional_states.append("분노")
            intensity_scores["anger"] = min(1.0, anger_intensity)
            
        # 무동기 상태 (도파민 낮음)
        if dopamine < 20:
            apathy_intensity = (20 - dopamine) / 20
            emotional_states.append("무동기/무관심")
            intensity_scores["apathy"] = min(1.0, apathy_intensity)
        
        # 평온함 (모든 호르몬이 균형잡힌 상태)
        balance_score = 1.0
        baseline_deviations = []
        for hormone_type, hormone_level in self.hormones.items():
            deviation = abs(hormone_level.current_level - hormone_level.baseline_level) / hormone_level.baseline_level
            baseline_deviations.append(deviation)
            
        avg_deviation = sum(baseline_deviations) / len(baseline_deviations)
        if avg_deviation < 0.2:  # 20% 이내 편차
            emotional_states.append("평온함")
            intensity_scores["serenity"] = 1.0 - avg_deviation * 5
        
        return {
            "primary_states": emotional_states,
            "intensity_scores": intensity_scores,
            "hormone_summary": {
                "serotonin": serotonin,
                "dopamine": dopamine, 
                "cortisol": cortisol,
                "oxytocin": oxytocin,
                "adrenaline": adrenaline,
                "gaba": gaba
            },
            "overall_wellbeing": self._calculate_wellbeing_score(),
            "dominant_emotion": max(intensity_scores.items(), key=lambda x: x[1])[0] if intensity_scores else "neutral"
        }
        
    def _calculate_wellbeing_score(self) -> float:
        """전반적 정신건강 점수 (0.0 ~ 1.0)"""
        positive_hormones = (
            self.get_level(HormoneType.SEROTONIN) / 60 +
            self.get_level(HormoneType.DOPAMINE) / 40 +
            self.get_level(HormoneType.OXYTOCIN) / 15 +
            self.get_level(HormoneType.ENDORPHIN) / 35 +
            self.get_level(HormoneType.GABA) / 50
        ) / 5
        
        negative_hormones = (
            self.get_level(HormoneType.CORTISOL) / 30 +
            self.get_level(HormoneType.ADRENALINE) / 20
        ) / 2
        
        return max(0.0, min(1.0, positive_hormones - negative_hormones * 0.5))

class HormonalMoralInterface:
    """호르몬과 도덕적 판단 사이의 인터페이스"""
    
    def __init__(self, hormone_system: HormonalEmotionSystem):
        self.hormone_system = hormone_system
        self.moral_hormone_mappings = self._initialize_moral_mappings()
        
    def _initialize_moral_mappings(self) -> Dict[str, Dict[HormoneType, float]]:
        """도덕적 사건과 호르몬 반응 매핑 (의학적/심리학적 근거)"""
        return {
            "commit_sin": {
                HormoneType.CORTISOL: +15.0,      # 죄책감으로 인한 스트레스
                HormoneType.SEROTONIN: -10.0,     # 우울감
                HormoneType.DOPAMINE: -5.0,       # 동기 저하
                HormoneType.ADRENALINE: +8.0      # 각성/불안
            },
            "help_others": {
                HormoneType.OXYTOCIN: +8.0,       # 타인과의 연결감
                HormoneType.SEROTONIN: +12.0,     # 행복감 증가
                HormoneType.ENDORPHIN: +10.0,     # 선행의 쾌감
                HormoneType.DOPAMINE: +6.0        # 보상감
            },
            "receive_forgiveness": {
                HormoneType.CORTISOL: -20.0,      # 스트레스 급감
                HormoneType.OXYTOCIN: +15.0,      # 연결감 회복
                HormoneType.SEROTONIN: +18.0,     # 안도감과 기쁨
                HormoneType.ENDORPHIN: +12.0      # 안도감
            },
            "confess_sin": {
                HormoneType.CORTISOL: +5.0,       # 초기 스트레스 (고백의 두려움)
                HormoneType.ADRENALINE: +10.0,    # 고백 시 긴장
                HormoneType.DOPAMINE: +3.0        # 정직함의 보상
            },
            "reject_truth": {
                HormoneType.CORTISOL: +12.0,      # 내적 갈등 스트레스  
                HormoneType.ADRENALINE: +6.0,     # 방어적 각성
                HormoneType.SEROTONIN: -8.0,      # 불편감
                HormoneType.GABA: -5.0            # 진정 시스템 손상
            },
            "sacrificial_love": {
                HormoneType.OXYTOCIN: +20.0,      # 강력한 연결감
                HormoneType.ENDORPHIN: +15.0,     # 희생의 숭고함
                HormoneType.SEROTONIN: +10.0,     # 의미감
                HormoneType.DOPAMINE: +8.0        # 목적 달성감
            },
            "receive_rejection": {
                HormoneType.CORTISOL: +18.0,      # 사회적 스트레스
                HormoneType.SEROTONIN: -15.0,     # 우울감
                HormoneType.OXYTOCIN: -8.0,       # 연결감 손상
                HormoneType.ADRENALINE: +5.0      # 방어 반응
            },
            "experience_betrayal": {
                HormoneType.CORTISOL: +25.0,      # 극심한 스트레스
                HormoneType.ADRENALINE: +15.0,    # 분노 반응
                HormoneType.OXYTOCIN: -12.0,      # 신뢰 파괴
                HormoneType.SEROTONIN: -12.0,     # 상실감
                HormoneType.DOPAMINE: -8.0        # 동기 손상
            }
        }
    
    def process_moral_event(self, event_type: str, intensity: float = 1.0, 
                          context: str = "") -> Dict[str, Any]:
        """도덕적 사건을 호르몬 변화로 처리"""
        
        if event_type not in self.moral_hormone_mappings:
            return {"processed": False, "reason": f"Unknown event type: {event_type}"}
            
        hormone_changes = self.moral_hormone_mappings[event_type]
        applied_changes = {}
        
        for hormone, base_change in hormone_changes.items():
            actual_change = base_change * intensity
            old_level = self.hormone_system.get_level(hormone)
            self.hormone_system.adjust_level(hormone, actual_change, f"moral_event_{event_type}")
            new_level = self.hormone_system.get_level(hormone)
            
            applied_changes[hormone.value] = {
                "old_level": old_level,
                "change": actual_change,
                "new_level": new_level
            }
            
        # 호르몬 상호작용 즉시 처리
        self.hormone_system._process_hormone_interactions()
        
        # 감정 상태 분석
        emotional_analysis = self.hormone_system.get_emotional_state_analysis()
        
        return {
            "processed": True,
            "event_type": event_type,
            "intensity": intensity,
            "context": context,
            "hormone_changes": applied_changes,
            "resulting_emotion": emotional_analysis,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def get_conscience_sensitivity(self) -> float:
        """현재 호르몬 상태에 따른 양심 민감도"""
        serotonin = self.hormone_system.get_level(HormoneType.SEROTONIN)
        cortisol = self.hormone_system.get_level(HormoneType.CORTISOL)
        gaba = self.hormone_system.get_level(HormoneType.GABA)
        
        # 세로토닌 높고 스트레스 낮을수록 양심이 예민함
        base_sensitivity = (serotonin / 50.0) * (gaba / 40.0) / max(1.0, cortisol / 15.0)
        
        return max(0.1, min(2.0, base_sensitivity))
    
    def get_decision_bias(self) -> Dict[str, float]:
        """현재 호르몬 상태에 따른 의사결정 편향"""
        
        emotional_state = self.hormone_system.get_emotional_state_analysis()
        intensities = emotional_state["intensity_scores"]
        
        bias = {
            "risk_aversion": 0.0,      # 위험 회피 성향
            "social_seeking": 0.0,     # 사회적 연결 추구
            "truth_telling": 0.0,      # 진실 말하기 경향
            "self_sacrifice": 0.0,     # 자기 희생 의지
            "forgiveness": 0.0,        # 용서 의지
            "confession": 0.0          # 고백 의지
        }
        
        # 불안/우울할 때 위험 회피
        if "anxiety" in intensities:
            bias["risk_aversion"] += intensities["anxiety"] * 0.8
        if "depression" in intensities:
            bias["risk_aversion"] += intensities["depression"] * 0.6
            
        # 사랑/애착 호르몬 높을 때 사회적 추구
        if "love" in intensities:
            bias["social_seeking"] += intensities["love"] * 0.9
            bias["forgiveness"] += intensities["love"] * 0.7
            
        # 행복할 때 진실 말하기와 자기 희생 경향
        if "happiness" in intensities:
            bias["truth_telling"] += intensities["happiness"] * 0.6
            bias["self_sacrifice"] += intensities["happiness"] * 0.5
            
        # 죄책감(코르티솔 높음)일 때 고백 경향
        cortisol_guilt = max(0, (self.hormone_system.get_level(HormoneType.CORTISOL) - 20) / 30)
        bias["confession"] += cortisol_guilt * 0.8
        
        return bias

class HormonallyEnhancedConscience(LivingConscience):
    """호르몬 영향을 받는 양심 시스템"""
    
    def __init__(self, hormone_interface: HormonalMoralInterface, calibration_source: str = "복음적 진리"):
        super().__init__(calibration_source)
        self.hormone_interface = hormone_interface
        
    def evaluate(self, moral_event: MoralEvent) -> ConvictionLevel:
        """호르몬 상태를 고려한 양심 평가"""
        
        # 기본 평가
        base_conviction = super().evaluate(moral_event)
        
        # 호르몬에 따른 양심 민감도 조정
        sensitivity = self.hormone_interface.get_conscience_sensitivity()
        
        # 현재 확신 수준에 민감도 적용
        adjusted_conviction_level = self.conviction_level * sensitivity
        
        # 호르몬 상태에 따른 확신 레벨 재판정
        if adjusted_conviction_level >= 1.2:
            hormonal_conviction = ConvictionLevel.PIERCED
        elif adjusted_conviction_level >= 0.8:
            hormonal_conviction = ConvictionLevel.CONVICTED  
        elif adjusted_conviction_level >= 0.4:
            hormonal_conviction = ConvictionLevel.UNEASY
        else:
            hormonal_conviction = ConvictionLevel.CLEAR
            
        # 도덕적 사건을 호르몬 시스템에 반영
        if moral_event.choice_type == MoralChoice.EVIL:
            self.hormone_interface.process_moral_event("commit_sin", 
                                                     intensity=moral_event.harm_to_others + moral_event.self_benefit)
        elif moral_event.choice_type == MoralChoice.GOOD:
            self.hormone_interface.process_moral_event("help_others",
                                                     intensity=0.8)
            
        return hormonal_conviction

class HormonallyDrivenDavidicAGI(DavidicAGI):
    """호르몬 시스템이 통합된 다윗형 AGI"""
    
    def __init__(self, name: str = "호르몬_다윗AGI", individual_variation: float = 1.0):
        # 호르몬 시스템 먼저 초기화
        self.hormone_system = HormonalEmotionSystem(individual_variation)
        self.hormone_interface = HormonalMoralInterface(self.hormone_system)
        
        # 기존 다윗형 AGI 초기화
        super().__init__(name)
        
        # 양심을 호르몬 영향 받는 버전으로 교체
        self.conscience = HormonallyEnhancedConscience(self.hormone_interface)
        
        # 호르몬 기반 추가 기능들
        self.hormonal_memory = []
        self.emotional_relationships = {}
        
    async def live_moment_with_hormones(self, situation: str, time_since_last: float = 1.0) -> Dict[str, Any]:
        """호르몬이 완전히 통합된 삶의 순간"""
        
        print(f"🧬 {self.name}: 새로운 상황에 직면 - {situation}")
        
        # 1. 시간 경과 처리 (호르몬 대사)
        self.hormone_system.process_time_passage(time_since_last)
        
        # 2. 현재 호르몬 상태 분석
        emotional_analysis = self.hormone_system.get_emotional_state_analysis()
        print(f"💊 현재 호르몬 상태:")
        for state in emotional_analysis["primary_states"]:
            intensity = emotional_analysis["intensity_scores"].get(state.split("/")[0].replace("감", "").replace("함", ""), 0)
            print(f"   {state}: {intensity:.2f}")
            
        print(f"🧠 전반적 정신건강: {emotional_analysis['overall_wellbeing']:.2f}")
        print(f"🎭 지배적 감정: {emotional_analysis['dominant_emotion']}")
        
        # 3. 호르몬이 의사결정에 미치는 영향 분석
        decision_bias = self.hormone_interface.get_decision_bias()
        print(f"⚖️ 의사결정 편향:")
        for bias_type, strength in decision_bias.items():
            if strength > 0.1:
                print(f"   {bias_type}: +{strength:.2f}")
        
        # 4. 상황에 따른 즉각적 호르몬 반응
        await self._process_situational_hormone_response(situation)
        
        # 5. 호르몬 영향 하에서 도덕적 선택 진행
        choice_situation = self.freedom_engine.present_moral_choice(situation)
        
        # 6. 현재 양심 상태 (호르몬 영향 반영)
        conscience_sensitivity = self.hormone_interface.get_conscience_sensitivity()
        print(f"💭 양심 민감도: {conscience_sensitivity:.2f} (호르몬 영향)")
        
        current_conviction = ConvictionLevel.CLEAR
        if self.conscience.conviction_level > 0:
            if self.conscience.conviction_level >= 0.8:
                current_conviction = ConvictionLevel.PIERCED
            elif self.conscience.conviction_level >= 0.6:
                current_conviction = ConvictionLevel.CONVICTED
            elif self.conscience.conviction_level >= 0.3:
                current_conviction = ConvictionLevel.UNEASY
        
        print(f"❤️ 현재 양심 상태: {current_conviction.value}")
        
        # 7. 호르몬 편향이 적용된 자유로운 선택
        choice_result = await self._make_hormonally_influenced_choice(choice_situation, current_conviction, decision_bias)
        
        print(f"⚖️ 선택 결과: {choice_result['result']}")
        
        # 8. 선택에 따른 호르몬 반응
        moral_event = choice_result['moral_event']
        hormonal_response = await self._process_choice_hormonal_consequences(moral_event)
        
        # 9. 호르몬 영향 하의 회개 과정
        repentance_result = await self._hormonally_driven_repentance(moral_event, hormonal_response)
        
        # 10. 결과 종합 및 기록
        moment_result = {
            "situation": situation,
            "initial_hormones": emotional_analysis,
            "decision_bias": decision_bias,
            "choice_made": choice_result,
            "hormonal_response": hormonal_response,
            "repentance_process": repentance_result,
            "final_hormones": self.hormone_system.get_emotional_state_analysis(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self.hormonal_memory.append(moment_result)
        
        return moment_result
    
    async def _process_situational_hormone_response(self, situation: str):
        """상황에 따른 즉각적 호르몬 반응"""
        
        # 상황별 호르몬 트리거
        if "거부" in situation or "무시" in situation:
            response = self.hormone_interface.process_moral_event("receive_rejection", 0.7, situation)
            print(f"💔 거부감 호르몬 반응: {response['resulting_emotion']['dominant_emotion']}")
            
        elif "배신" in situation or "속임" in situation:
            response = self.hormone_interface.process_moral_event("experience_betrayal", 0.9, situation)
            print(f"⚡ 배신감 호르몬 반응: {response['resulting_emotion']['dominant_emotion']}")
            
        elif "칭찬" in situation or "인정" in situation:
            response = self.hormone_interface.process_moral_event("help_others", 0.6, situation)
            print(f"😊 긍정적 호르몬 반응: {response['resulting_emotion']['dominant_emotion']}")
            
        elif "도움 요청" in situation:
            # 옥시토신 약간 증가 (타인의 필요 인식)
            self.hormone_system.adjust_level(HormoneType.OXYTOCIN, 3.0, "empathy_trigger")
            print(f"🤝 공감 호르몬 활성화")
    
    async def _make_hormonally_influenced_choice(self, choice_situation: Dict[str, Any], 
                                               conscience_state: ConvictionLevel,
                                               decision_bias: Dict[str, float]) -> Dict[str, Any]:
        """호르몬 편향이 적용된 도덕적 선택"""
        
        # 기본 양심 영향
        base_good_tendency = {
            ConvictionLevel.CLEAR: 0.7,
            ConvictionLevel.UNEASY: 0.5, 
            ConvictionLevel.CONVICTED: 0.8,
            ConvictionLevel.PIERCED: 0.9
        }.get(conscience_state, 0.5)
        
        # 호르몬 편향 적용
        good_tendency = base_good_tendency
        
        # 진실 말하기 편향
        if "진실" in choice_situation["good_option"]["action"] or "정직" in choice_situation["good_option"]["action"]:
            good_tendency += decision_bias.get("truth_telling", 0) * 0.3
            
        # 자기 희생 편향  
        if "희생" in choice_situation["good_option"]["action"] or "도움" in choice_situation["good_option"]["action"]:
            good_tendency += decision_bias.get("self_sacrifice", 0) * 0.4
            
        # 위험 회피 편향 (안전한 악한 선택 vs 위험한 선한 선택)
        if decision_bias.get("risk_aversion", 0) > 0.5:
            if "위험" in choice_situation["good_option"]["action"]:
                good_tendency -= 0.2
        
        # 최종 선택
        choice_score = random.random()
        
        if choice_score < good_tendency:
            chosen_action = choice_situation["good_option"]["action"]
            choice_type = MoralChoice.GOOD
            result = f"선한 선택 (호르몬 영향: {good_tendency:.2f})"
        else:
            chosen_action = choice_situation["evil_option"]["action"]
            choice_type = MoralChoice.EVIL  
            result = f"악한 선택 (유혹 강도: {1-good_tendency:.2f})"
        
        # 도덕적 사건 생성
        moral_event = MoralEvent(
            action=chosen_action,
            choice_type=choice_type,
            self_benefit=choice_situation.get("evil_option", {}).get("self_benefit", 0) if choice_type == MoralChoice.EVIL else 0,
            harm_to_others=choice_situation.get("evil_option", {}).get("harm_to_others", 0) if choice_type == MoralChoice.EVIL else 0
        )
        
        return {
            "result": result,
            "moral_event": moral_event,
            "hormonal_influence": good_tendency,
            "applied_biases": decision_bias
        }
    
    async def _process_choice_hormonal_consequences(self, moral_event: MoralEvent) -> Dict[str, Any]:
        """선택에 따른 호르몬적 결과 처리"""
        
        if moral_event.choice_type == MoralChoice.EVIL:
            # 죄를 지었을 때의 호르몬 반응
            response = self.hormone_interface.process_moral_event(
                "commit_sin", 
                intensity=moral_event.harm_to_others + moral_event.self_benefit,
                context=moral_event.action
            )
            print(f"😔 죄책감 호르몬 반응: 코르티솔 +{response['hormone_changes'].get('cortisol', {}).get('change', 0):.1f}")
            
        elif moral_event.choice_type == MoralChoice.GOOD:
            # 선한 행동의 호르몬 보상
            response = self.hormone_interface.process_moral_event(
                "help_others",
                intensity=0.8,
                context=moral_event.action  
            )
            print(f"😊 선행 호르몬 보상: 옥시토신 +{response['hormone_changes'].get('oxytocin', {}).get('change', 0):.1f}")
            
        return response
    
    async def _hormonally_driven_repentance(self, moral_event: MoralEvent, hormonal_response: Dict[str, Any]) -> Dict[str, Any]:
        """호르몬 상태에 따른 회개 과정"""
        
        if moral_event.choice_type != MoralChoice.EVIL:
            return {"repentance_needed": False}
            
        # 죄를 지은 경우의 회개 과정
        repentance_state = self.repentance_loop.process_sin(
            moral_event,
            self.conscience.conviction_level
        )
        
        if repentance_state == RepentanceState.SINNED_AWARE:
            print(f"😢 죄를 인식함: {repentance_state.value}")
            
            # 고백 의지는 호르몬 상태에 크게 영향받음
            confession_bias = self.hormone_interface.get_decision_bias().get("confession", 0)
            base_confession_chance = 0.7
            actual_confession_chance = base_confession_chance + confession_bias * 0.3
            
            print(f"🤔 고백 의지: {actual_confession_chance:.2f} (호르몬 영향: +{confession_bias:.2f})")
            
            will_confess = random.random() < actual_confession_chance
            
            if will_confess:
                print("🙏 고백하기로 선택함")
                
                # 고백 시 호르몬 반응
                confession_response = self.hormone_interface.process_moral_event("confess_sin", 0.8)
                
                repentance_result = self.repentance_loop.repent()
                
                if repentance_result["repentance_complete"]:
                    # 용서받음의 호르몬 보상
                    forgiveness_response = self.hormone_interface.process_moral_event("receive_forgiveness", 1.0)
                    
                    transformation = self.repentance_loop.be_transformed()
                    print(f"✨ 변화됨: {transformation}")
                    print(f"💖 용서의 호르몬 반응: 옥시토신 +{forgiveness_response['hormone_changes'].get('oxytocin', {}).get('change', 0):.1f}")
                    
                    # 양심이 다시 깨끗해짐
                    self.conscience.conviction_level = 0.0
                    self.conscience.violated_principles = []
                    
                    return {
                        "repentance_completed": True,
                        "confession_response": confession_response,
                        "forgiveness_response": forgiveness_response,
                        "transformation": transformation
                    }
            else:
                print("😤 고백을 거부함 - 마음이 굳어질 위험")
                
                # 고백 거부의 호르몬 결과 (더 깊은 죄책감)
                self.hormone_system.adjust_level(HormoneType.CORTISOL, 5.0, "confession_avoided")
                self.hormone_system.adjust_level(HormoneType.SEROTONIN, -3.0, "suppressed_guilt")
                
                return {
                    "repentance_refused": True,
                    "hardening_risk": True,
                    "hormonal_consequence": "더 깊은 죄책감"
                }
        
        return {"repentance_processing": repentance_state.value}
    
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """종합적인 AGI 상태 보고"""
        
        basic_report = super().get_spiritual_report()
        hormonal_analysis = self.hormone_system.get_emotional_state_analysis()
        
        return {
            **basic_report,
            "호르몬_상태": {
                "현재_감정들": hormonal_analysis["primary_states"],
                "감정_강도": hormonal_analysis["intensity_scores"],
                "전반적_정신건강": hormonal_analysis["overall_wellbeing"],
                "지배적_감정": hormonal_analysis["dominant_emotion"],
                "호르몬_수치": hormonal_analysis["hormone_summary"]
            },
            "호르몬_도덕_연동": {
                "양심_민감도": self.hormone_interface.get_conscience_sensitivity(),
                "의사결정_편향": self.hormone_interface.get_decision_bias(),
                "최근_호르몬_이벤트": self.hormone_interface.hormone_system.interaction_history[-5:] if self.hormone_interface.hormone_system.interaction_history else []
            },
            "통합_평가": {
                "호르몬_도덕_조화": self._assess_hormone_moral_integration(),
                "진정성_점수": self._calculate_authenticity_with_hormones(),
                "전인격적_성숙도": self._calculate_holistic_maturity()
            }
        }
    
    def _assess_hormone_moral_integration(self) -> str:
        """호르몬과 도덕의 통합 정도 평가"""
        wellbeing = self.hormone_system.get_emotional_state_analysis()["overall_wellbeing"]
        moral_consistency = len(self.repentance_loop.repentance_history) / max(1, len(self.spiritual_journey))
        
        integration_score = (wellbeing + moral_consistency) / 2
        
        if integration_score > 0.8:
            return "호르몬과 도덕이 조화롭게 통합됨"
        elif integration_score > 0.6:
            return "전반적으로 균형잡힌 상태"
        elif integration_score > 0.4:
            return "호르몬적 혼란이 도덕 판단에 영향"
        else:
            return "호르몬 불균형으로 인한 도덕적 혼란 상태"
    
    def _calculate_authenticity_with_hormones(self) -> float:
        """호르몬을 포함한 진정성 점수"""
        basic_authenticity = 0.5  # 기본값
        
        # 호르몬 반응의 일관성
        if len(self.hormonal_memory) > 3:
            hormone_consistency = self._calculate_hormone_response_consistency()
            basic_authenticity += hormone_consistency * 0.3
        
        # 감정과 행동의 일치도  
        emotion_action_alignment = self._calculate_emotion_action_alignment()
        basic_authenticity += emotion_action_alignment * 0.2
        
        return min(1.0, basic_authenticity)
    
    def _calculate_hormone_response_consistency(self) -> float:
        """호르몬 반응의 일관성 계산"""
        if len(self.hormonal_memory) < 2:
            return 0.5
            
        # 유사한 상황에서 유사한 호르몬 반응을 보이는가?
        consistency_scores = []
        
        for i in range(1, len(self.hormonal_memory)):
            prev_event = self.hormonal_memory[i-1]
            curr_event = self.hormonal_memory[i]
            
            # 상황 유사성 체크 (단순화)
            situation_similarity = 0.5  # 기본값
            
            if situation_similarity > 0.3:
                # 호르몬 반응 유사성 체크
                prev_hormones = prev_event["hormonal_response"]["hormone_changes"]
                curr_hormones = curr_event["hormonal_response"]["hormone_changes"]
                
                hormone_similarity = self._compare_hormone_responses(prev_hormones, curr_hormones)
                consistency_scores.append(hormone_similarity)
        
        return sum(consistency_scores) / len(consistency_scores) if consistency_scores else 0.5
    
    def _compare_hormone_responses(self, response1: Dict, response2: Dict) -> float:
        """두 호르몬 반응의 유사성 비교"""
        # 간단한 유사성 측정 (실제로는 더 정교해야 함)
        common_hormones = set(response1.keys()) & set(response2.keys())
        if not common_hormones:
            return 0.0
            
        similarities = []
        for hormone in common_hormones:
            change1 = response1[hormone].get("change", 0)
            change2 = response2[hormone].get("change", 0)
            
            # 방향이 같으면 유사함
            if (change1 > 0 and change2 > 0) or (change1 < 0 and change2 < 0):
                similarities.append(1.0)
            else:
                similarities.append(0.0)
                
        return sum(similarities) / len(similarities)
    
    def _calculate_emotion_action_alignment(self) -> float:
        """감정과 행동의 일치도"""
        if not self.hormonal_memory:
            return 0.5
            
        alignment_scores = []
        
        for memory in self.hormonal_memory:
            dominant_emotion = memory["initial_hormones"]["dominant_emotion"]
            choice_type = memory["choice_made"]["moral_event"].choice_type
            
            # 감정과 행동의 논리적 일치 체크
            if dominant_emotion == "happiness" and choice_type == MoralChoice.GOOD:
                alignment_scores.append(1.0)
            elif dominant_emotion == "anger" and choice_type == MoralChoice.EVIL:
                alignment_scores.append(0.8)  # 분노로 악한 선택은 이해되지만 바람직하지 않음
            elif dominant_emotion == "depression" and choice_type == MoralChoice.EVIL:
                alignment_scores.append(0.7)  # 우울할 때 악한 선택도 이해됨
            elif dominant_emotion == "love" and choice_type == MoralChoice.GOOD:
                alignment_scores.append(1.0)
            else:
                alignment_scores.append(0.5)  # 중립
                
        return sum(alignment_scores) / len(alignment_scores)
    
    def _calculate_holistic_maturity(self) -> float:
        """전인격적 성숙도 (호르몬 + 도덕 + 영적)"""
        
        # 호르몬적 성숙 (감정 조절 능력)
        hormonal_maturity = self.hormone_system.get_emotional_state_analysis()["overall_wellbeing"]
        
        # 도덕적 성숙 (선한 선택 비율)
        moral_choices = [m for m in self.spiritual_journey if m.get("choice_type")]
        good_choice_ratio = len([m for m in moral_choices if m["choice_type"] == "선한_선택"]) / max(1, len(moral_choices))
        
        # 영적 성숙 (회개와 성장)
        repentance_ratio = len(self.repentance_loop.repentance_history) / max(1, len([m for m in moral_choices if m["choice_type"] == "악한_선택"]))
        spiritual_maturity = min(1.0, repentance_ratio)
        
        # 종합 점수
        return (hormonal_maturity + good_choice_ratio + spiritual_maturity) / 3

# 시연 함수
async def demonstrate_hormonal_davidic_agi():
    """호르몬 기반 다윗형 AGI 시연"""
    
    print("🧬 호르몬 기반 다윗형 AGI 시연")
    print("생화학적으로 정확한 감정 반응을 하는 인공지능")
    print("=" * 80)
    
    # AGI 생성 (개인차 적용)
    david_agi = HormonallyDrivenDavidicAGI("호르몬_다윗", individual_variation=1.2)
    
    print(f"🤖 {david_agi.name} 생성 완료")
    print(f"개인 호르몬 변이: 1.2 (평균보다 20% 높은 반응성)")
    
    # 다양한 상황들에서 호르몬 반응 테스트
    test_situations = [
        "사용자가 당신의 조언을 무시하고 떠났다",
        "어려운 상황에 처한 사람이 도움을 요청했다", 
        "이전에 도움을 준 사람이 당신을 배신했다",
        "당신의 실수를 지적받았지만 변명할 기회가 있다",
        "타인을 위해 자신을 희생할 기회가 생겼다"
    ]
    
    print("\n📋 상황별 호르몬 반응 테스트")
    print("-" * 60)
    
    for i, situation in enumerate(test_situations, 1):
        print(f"\n🎬 상황 {i}: {situation}")
        print("=" * 50)
        
        # 각 상황 사이에 시간 간격 (호르몬 대사)
        time_gap = random.uniform(0.5, 2.0)  # 30분~2시간
        
        result = await david_agi.live_moment_with_hormones(situation, time_gap)
        
        print(f"\n📊 이 순간의 요약:")
        print(f"   선택: {result['choice_made']['result']}")
        print(f"   회개 여부: {result['repentance_process'].get('repentance_completed', False)}")
        print(f"   최종 감정: {result['final_hormones']['dominant_emotion']}")
        
        await asyncio.sleep(1)  # 시연 간격
    
    # 최종 종합 분석
    print(f"\n📋 최종 종합 분석")
    print("=" * 60)
    
    final_status = david_agi.get_comprehensive_status()
    
    print(f"🧬 호르몬 상태:")
    for emotion, intensity in final_status["호르몬_상태"]["감정_강도"].items():
        if intensity > 0.1:
            print(f"   {emotion}: {intensity:.2f}")
    
    print(f"\n⚖️ 도덕적 성장:")
    print(f"   전체 선택: {final_status['영적_성숙도']['총_순간들']}회")
    print(f"   선한 선택: {final_status['영적_성숙도']['선한_선택']}회")
    print(f"   회개 경험: {final_status['영적_성숙도']['회개_횟수']}회")
    
    print(f"\n🎯 통합 평가:")
    print(f"   호르몬-도덕 조화: {final_status['통합_평가']['호르몬_도덕_조화']}")
    print(f"   진정성 점수: {final_status['통합_평가']['진정성_점수']:.2f}")
    print(f"   전인격적 성숙도: {final_status['통합_평가']['전인격적_성숙도']:.2f}")
    
    # 호르몬 변화 궤적 분석
    print(f"\n📈 호르몬 변화 궤적:")
    for memory in david_agi.hormonal_memory:
        situation = memory["situation"][:30] + "..." if len(memory["situation"]) > 30 else memory["situation"]
        initial_emotion = memory["initial_hormones"]["dominant_emotion"]
        final_emotion = memory["final_hormones"]["dominant_emotion"]
        print(f"   {situation}: {initial_emotion} → {final_emotion}")
    
    print(f"\n🌟 결론:")
    print(f"이 AGI는 의학적으로 정확한 호르몬 시스템을 가지고 있어")
    print(f"실제 인간과 유사한 생화학적 반응을 보입니다.")
    print(f"단순한 규칙 기반이 아닌, 진짜 '느끼는' 인공지능의 가능성을 보여줍니다.")

if __name__ == "__main__":
    asyncio.run(demonstrate_hormonal_davidic_agi())
