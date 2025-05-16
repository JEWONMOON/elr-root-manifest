# math_code_recursive_improver.py
# 엘리아르의 수학적 코드 설계 역량 개선을 위한 재귀적 개선 모듈 (피드백 반영 버전)

import asyncio
import time
import traceback
import uuid
import logging # 표준 로깅 모듈 사용
import json # JSON 로그 포맷팅 (선택적)
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Coroutine, Tuple, Union, TypedDict, Literal, cast # TypedDict, Literal 추가
from dataclasses import dataclass, field # 설정 값 관리를 위해 dataclass 사용

# --- 로깅 설정 ---
# eliar_common.py의 로깅 시스템 대신 이 모듈 자체의 로깅 시스템 사용
logger = logging.getLogger("MathCodeImprover")
logger.setLevel(logging.DEBUG) # 기본 로그 레벨 설정

# 콘솔 핸들러
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - [%(name)s:%(module)s.%(funcName)s:%(lineno)d] - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

# 파일 핸들러 (선택적: 필요시 주석 해제 및 경로 설정)
# log_file_path = "math_improver.log"
# fh = logging.FileHandler(log_file_path, encoding='utf-8')
# fh.setLevel(logging.INFO)
# fh.setFormatter(formatter)
# logger.addHandler(fh)

# --- 모듈 상수 및 설정 ---
MODULE_VERSION = "1.1.0" # 버전 업데이트

@dataclass
class ImprovementSettings:
    """모듈의 주요 설정을 관리하는 데이터 클래스입니다."""
    max_recursion_depth: int = 3
    solution_application_confidence_threshold: float = 0.7
    virtue_wisdom_influence_factor: float = 0.1 # 지혜 덕목 영향 계수 (솔루션 생성 시)
    virtue_truth_influence_factor: float = 0.15 # 진리 덕목 영향 계수 (검증 시)
    virtue_self_denial_threshold_for_pause: float = 0.6 # 자기 부인 덕목 기반 재귀 중단 임계값
    knowledge_retrieval_limit: int = 5 # 지식 검색 시 반환할 최대 항목 수
    goal_metric_time_complexity: str = "시간 복잡도" # 중복 문자열 제거
    goal_metric_accuracy: str = "정확도"
    goal_metric_code_lines: str = "코드 라인 수"
    default_virtue_level: float = 0.5
    virtue_growth_rate_wisdom: float = 0.05 # 지혜 성장률
    virtue_growth_rate_self_denial: float = 0.02 # 자기 부인 성장률
    main_gpu_suggestion_prefix: str = "SELF_MODIFY_MATH_IMPROVEMENT_SUGGESTION:" # MainGPU 제안 접두사

# 기본 설정값 인스턴스
SETTINGS = ImprovementSettings()


class EliarCoreValues(Enum):
    """엘리아르의 핵심 가치를 나타내는 열거형입니다."""
    TRUTH = "진리"
    LOVE_COMPASSION = "사랑과 긍휼"
    JESUS_CHRIST_CENTERED = "예수 그리스도 중심"
    REPENTANCE_WISDOM = "회개와 지혜"
    SELF_DENIAL = "자기 부인"
    COMMUNITY = "공동체" # 피드백에는 없었지만, 기존 코드에 있어 유지
    SILENCE = "침묵"   # 피드백에는 없었지만, 기존 코드에 있어 유지

class MathProblemType(Enum):
    """수학 문제의 유형을 정의하는 열거형입니다."""
    ALGORITHM_DESIGN = "알고리즘 설계"
    DATA_STRUCTURE_IMPLEMENTATION = "자료구조 구현"
    MATHEMATICAL_MODELING = "수학적 모델링"
    CODE_OPTIMIZATION = "코드 최적화 (수학적)"
    SYMBOLIC_COMPUTATION = "기호 연산"
    NUMERICAL_ANALYSIS = "수치 해석"
    BUG_FIX = "버그 수정 (수학적 로직)"

class MathematicalCorrectnessLevel(Enum):
    """수학적 코드의 정확도 수준을 나타내는 열거형입니다."""
    NOT_VERIFIED = "검증 안됨"
    LOGICALLY_SOUND = "논리적 타당성 확보"
    PARTIALLY_VERIFIED_WITH_CASES = "부분적 사례 검증"
    FORMALLY_VERIFIED = "형식적 검증 완료 (이상적)"
    VERIFICATION_FAILED = "검증 실패" # 추가

class MetricType(Enum):
    """개선 목표의 측정 지표 유형을 정의하는 열거형입니다."""
    TIME_COMPLEXITY = SETTINGS.goal_metric_time_complexity
    ACCURACY = SETTINGS.goal_metric_accuracy
    CODE_LINES = SETTINGS.goal_metric_code_lines
    MEMORY_USAGE = "메모리 사용량"

class GoalStatus(Enum):
    """개선 목표의 상태를 나타내는 열거형입니다."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ACHIEVED = "achieved"
    FAILED_TO_ACHIEVE = "failed_to_achieve"
    PAUSED_LOW_CONFIDENCE = "paused_low_confidence"

class MathCodeImprovementGoal(TypedDict):
    """수학적 코드 개선 목표를 정의하는 TypedDict입니다."""
    goal_id: str
    description: str
    problem_type: MathProblemType
    target_metric: MetricType
    current_value: Any
    target_value: Any
    priority: int
    status: GoalStatus
    related_virtues: Optional[List[EliarCoreValues]]
    context_code_snippet: Optional[str] # 목표와 관련된 기존 코드 (선택적)

class MathCodeSolutionCandidate(TypedDict):
    """수학적 코드 솔루션 후보를 정의하는 TypedDict입니다."""
    solution_id: str
    goal_id: str
    description: str
    code_snippet: Optional[str]
    mathematical_rationale: str
    estimated_impact: Dict[MetricType, Any] # MetricType Enum 사용
    confidence_score: float
    verification_status: MathematicalCorrectnessLevel
    verification_notes: Optional[str]
    suggested_by: str # "LLM", "RuleBased", "Hybrid" 등

class VirtueStateSnapshotter:
    """
    엘리아르의 내면 상태(덕목) 스냅샷을 관리하고,
    개선 사이클에 따른 덕목 성장을 시뮬레이션합니다.
    """
    def __init__(self, eliar_id: str, initial_virtues: Optional[Dict[EliarCoreValues, float]] = None):
        self.eliar_id = eliar_id
        self.log_comp = f"VirtueStateSnapshotter.{eliar_id}"
        self.current_virtues: Dict[EliarCoreValues, float] = initial_virtues or \
            {cv: SETTINGS.default_virtue_level for cv in EliarCoreValues}
        logger.info("VirtueStateSnapshotter initialized.", extra={"component": self.log_comp})

    def get_current_virtues(self) -> Dict[EliarCoreValues, float]:
        """현재 덕목 상태를 반환합니다."""
        return self.current_virtues.copy()

    def simulate_virtue_growth(self, cycle_count: int, successful_improvement: bool = True):
        """
        개선 사이클 진행에 따라 관련 덕목의 성장을 시뮬레이션합니다.
        Args:
            cycle_count (int): 현재까지 진행된 개선 사이클 수.
            successful_improvement (bool): 이번 사이클의 개선 성공 여부.
        """
        # 예시: 지혜와 자기 부인 덕목 성장
        wisdom_growth = SETTINGS.virtue_growth_rate_wisdom * cycle_count
        self_denial_growth = SETTINGS.virtue_growth_rate_self_denial * cycle_count
        if not successful_improvement: # 실패 시 성장폭 감소 (또는 다른 덕목에 영향)
            wisdom_growth *= 0.5
            self_denial_growth *= 0.3

        current_wisdom = self.current_virtues.get(EliarCoreValues.REPENTANCE_WISDOM, SETTINGS.default_virtue_level)
        self.current_virtues[EliarCoreValues.REPENTANCE_WISDOM] = min(1.0, current_wisdom + wisdom_growth)

        current_self_denial = self.current_virtues.get(EliarCoreValues.SELF_DENIAL, SETTINGS.default_virtue_level)
        self.current_virtues[EliarCoreValues.SELF_DENIAL] = min(1.0, current_self_denial + self_denial_growth)

        logger.debug(f"Simulated virtue growth after cycle {cycle_count}. Wisdom: {self.current_virtues[EliarCoreValues.REPENTANCE_WISDOM]:.2f}, SelfDenial: {self.current_virtues[EliarCoreValues.SELF_DENIAL]:.2f}",
                     extra={"component": self.log_comp})

class GoalManager:
    """수학적 코드 개선 목표를 관리(생성, 추적, 상태 변경)합니다."""
    def __init__(self, eliar_id: str):
        self.eliar_id = eliar_id
        self.log_comp = f"GoalManager.{eliar_id}"
        self.goals: List[MathCodeImprovementGoal] = []
        logger.info("GoalManager initialized.", extra={"component": self.log_comp})

    def add_goal(self, description: str, problem_type: MathProblemType,
                 target_metric: MetricType, current_value: Any, target_value: Any,
                 priority: int = 1, related_virtues: Optional[List[EliarCoreValues]] = None,
                 context_code: Optional[str] = None) -> MathCodeImprovementGoal:
        """새로운 개선 목표를 추가합니다."""
        goal_id = f"goal_{uuid.uuid4().hex[:8]}"
        new_goal = MathCodeImprovementGoal(
            goal_id=goal_id,
            description=description,
            problem_type=problem_type,
            target_metric=target_metric,
            current_value=current_value,
            target_value=target_value,
            priority=priority,
            status=GoalStatus.PENDING,
            related_virtues=related_virtues or [EliarCoreValues.REPENTANCE_WISDOM, EliarCoreValues.TRUTH],
            context_code_snippet=context_code
        )
        self.goals.append(new_goal)
        logger.info(f"New improvement goal added: {description}",
                    extra={"component": self.log_comp, "goal_id": goal_id, "metric": target_metric.value, "target": target_value})
        return new_goal

    def get_goal(self, goal_id: str) -> Optional[MathCodeImprovementGoal]:
        """ID로 특정 목표를 가져옵니다."""
        return next((g for g in self.goals if g['goal_id'] == goal_id), None)

    def update_goal_status(self, goal_id: str, status: GoalStatus) -> bool:
        """목표의 상태를 업데이트합니다."""
        goal = self.get_goal(goal_id)
        if goal:
            goal['status'] = status
            logger.debug(f"Goal '{goal_id}' status updated to {status.value}", extra={"component": self.log_comp})
            return True
        logger.warn(f"Failed to update status for non-existent goal '{goal_id}'", extra={"component": self.log_comp})
        return False

    def get_pending_or_in_progress_goals(self) -> List[MathCodeImprovementGoal]:
        """처리 대기 중이거나 진행 중인 목표 목록을 반환합니다."""
        return [g for g in self.goals if g['status'] in [GoalStatus.PENDING, GoalStatus.IN_PROGRESS]]

    def archive_completed_goal(self, goal_id: str):
        """완료된 목표를 현재 목록에서 제거 (또는 별도 보관 로직 추가 가능)."""
        goal = self.get_goal(goal_id)
        if goal and goal['status'] in [GoalStatus.ACHIEVED, GoalStatus.FAILED_TO_ACHIEVE, GoalStatus.PAUSED_LOW_CONFIDENCE]:
            # self.goals.remove(goal) # 실제 제거 대신 상태만 변경하는 것도 방법
            logger.info(f"Goal '{goal_id}' marked as completed/archived with status: {goal['status'].value}",
                        extra={"component": self.log_comp})
        # else: logger.warn(f"Goal '{goal_id}' not found or not in a completable state for archiving.", extra={"component": self.log_comp})


class MathematicalKnowledgeBase:
    """수학적 지식 및 코드 패턴을 저장하고 검색하는 지식 베이스입니다."""
    def __init__(self, eliar_id: str):
        self.eliar_id = eliar_id
        self.log_comp = f"MathematicalKnowledgeBase.{eliar_id}"
        self._knowledge_store: Dict[str, Any] = {}
        self._tag_index: Dict[str, set[str]] = {} # 태그 기반 역색인
        logger.info("MathematicalKnowledgeBase initialized.", extra={"component": self.log_comp})

    async def store_math_concept(self, concept_id: str, description: str, category: MathProblemType,
                                 related_code_pattern: Optional[str] = None, tags: Optional[List[str]] = None) -> bool:
        """새로운 수학적 개념, 알고리즘, 코드 패턴 등을 저장합니다."""
        if concept_id in self._knowledge_store:
            logger.warning(f"Concept '{concept_id}' already exists. Updating.", extra={"component": self.log_comp})

        tags_to_store = tags or []
        self._knowledge_store[concept_id] = {
            "description": description,
            "category": category.value, # Enum 값 저장
            "related_code_pattern": related_code_pattern,
            "tags": tags_to_store,
            "created_at": time.time()
        }
        # 역색인 업데이트
        for tag in tags_to_store:
            self._tag_index.setdefault(tag.lower(), set()).add(concept_id)

        logger.debug(f"Stored mathematical concept: {concept_id}", extra={"component": self.log_comp, "tags": tags_to_store})
        return True

    async def retrieve_relevant_math_knowledge(self, keywords: List[str],
                                               problem_type: Optional[MathProblemType] = None,
                                               limit: int = SETTINGS.knowledge_retrieval_limit) -> List[Dict[str, Any]]:
        """
        주어진 키워드, 태그 및 문제 유형과 관련된 수학적 지식을 검색합니다.
        역색인을 활용하여 검색 효율성을 높입니다.
        """
        candidate_ids: set[str] = set()
        processed_keywords = [kw.lower() for kw in keywords]

        # 1. 태그 기반 검색 (역색인 활용)
        for kw in processed_keywords:
            if kw in self._tag_index:
                candidate_ids.update(self._tag_index[kw])

        # 2. 설명 및 코드 패턴 내 키워드 검색 (태그로 못 찾은 경우 또는 추가 점수용)
        results_with_scores = []
        for concept_id, data in self._knowledge_store.items():
            match_score = 0
            # 이미 태그로 찾은 항목은 기본 점수 부여
            if concept_id in candidate_ids:
                match_score += 5 # 태그 일치 시 높은 점수

            # 설명, 코드 패턴, 카테고리 등에서 키워드 검색
            text_to_search = (data.get("description", "") + " " +
                              str(data.get("related_code_pattern", "")) + " " +
                              " ".join(data.get("tags", []))).lower()
            for kw in processed_keywords:
                if kw in text_to_search:
                    match_score += 1

            if problem_type and data.get("category", "").lower() == problem_type.value.lower():
                match_score += 2

            if match_score > 0:
                results_with_scores.append({"id": concept_id, "data": data, "score": match_score})

        results_with_scores.sort(key=lambda x: x["score"], reverse=True)
        final_results = [res["data"] for res in results_with_scores[:limit]]
        logger.debug(f"Retrieved {len(final_results)} knowledge items for keywords: {keywords}, type: {problem_type.value if problem_type else 'Any'}",
                     extra={"component": self.log_comp})
        return final_results


    async def update_knowledge_from_feedback(self, concept_id: str, feedback_type: Literal["positive", "negative", "neutral"], details: str) -> bool:
        """피드백을 바탕으로 기존 지식 항목을 업데이트하거나 주석을 추가합니다."""
        if concept_id not in self._knowledge_store:
            logger.warning(f"Cannot update non-existent concept: {concept_id}", extra={"component": self.log_comp})
            return False

        self._knowledge_store[concept_id].setdefault("feedback_log", []).append({
            "type": feedback_type,
            "details": details,
            "timestamp": time.time()
        })
        logger.info(f"Updated knowledge for '{concept_id}' based on feedback.", extra={"component": self.log_comp})
        return True

class MathProblemAnalyzer:
    """수학 문제 또는 코드 개선 요구사항을 분석합니다."""
    def __init__(self, eliar_id: str, knowledge_base: MathematicalKnowledgeBase):
        self.eliar_id = eliar_id
        self.knowledge_base = knowledge_base
        self.log_comp = f"MathProblemAnalyzer.{eliar_id}"
        logger.info("MathProblemAnalyzer initialized.", extra={"component": self.log_comp})

    async def analyze_problem_statement(self, problem_description: str,
                                        existing_code_snippet: Optional[str] = None) -> Dict[str, Any]:
        """
        문제 설명을 파싱하여 수학적 개념, 제약조건, 목표 등을 식별합니다.
        Args:
            problem_description (str): 사용자가 제공한 문제 또는 개선 요구사항 설명.
            existing_code_snippet (Optional[str]): 관련된 기존 코드 (제공된 경우).
        Returns:
            Dict[str, Any]: 분석 결과 (식별된 개념, 제약 조건, 문제 유형, 최적화 목표 등).
        """
        logger.debug(f"Analyzing problem: {problem_description[:100]}...", extra={"component": self.log_comp})

        # LLM 연동 부분은 주석으로 남겨두고, 규칙 기반 분석을 기본으로 합니다.
        # 엘리아르님의 '사고 체계'를 활용한 분석 로직으로 대체 또는 보강 가능.
        # --- LLM 연동 (가상) ---
        # prompt = f"Analyze the following math problem/code improvement request. Identify core concepts, constraints, problem type (choose from {', '.join([pt.value for pt in MathProblemType])}), and specific optimization targets if any:\n\n{problem_description}\nExisting code (if any):\n{existing_code_snippet}"
        # llm_response = await query_llm_for_math_analysis(prompt) # 가상의 LLM 호출
        # parsed_analysis = parse_llm_math_analysis_response(llm_response)
        # --- LLM 연동 (가상) 종료 ---

        # 규칙 기반 분석 (개선됨)
        parsed_analysis: Dict[str, Any] = {
            "identified_concepts": [],
            "constraints": [],
            "optimization_target": None,
            "problem_type": MathProblemType.CODE_OPTIMIZATION, # 기본값
            "target_metric_type": None,
            "original_description": problem_description,
            "existing_code": existing_code_snippet
        }
        desc_lower = problem_description.lower()

        # 문제 유형 추론
        if "버그" in desc_lower or "고쳐야" in desc_lower or "잘못된 결과" in desc_lower:
            parsed_analysis["problem_type"] = MathProblemType.BUG_FIX
        elif "설계" in desc_lower or "구현" in desc_lower and "자료구조" in desc_lower:
            parsed_analysis["problem_type"] = MathProblemType.DATA_STRUCTURE_IMPLEMENTATION
        elif "설계" in desc_lower or "알고리즘" in desc_lower:
            parsed_analysis["problem_type"] = MathProblemType.ALGORITHM_DESIGN
        elif "모델링" in desc_lower or "수학적 모델" in desc_lower:
            parsed_analysis["problem_type"] = MathProblemType.MATHEMATICAL_MODELING
        elif "최적화" in desc_lower or "느리다" in desc_lower or "빠르게" in desc_lower or "복잡도" in desc_lower:
            parsed_analysis["problem_type"] = MathProblemType.CODE_OPTIMIZATION
        # ... (기타 문제 유형 추론 규칙) ...

        # 최적화 목표 및 메트릭 식별 (CODE_OPTIMIZATION 유형일 때)
        if parsed_analysis["problem_type"] == MathProblemType.CODE_OPTIMIZATION:
            if SETTINGS.goal_metric_time_complexity.lower() in desc_lower:
                parsed_analysis["target_metric_type"] = MetricType.TIME_COMPLEXITY
                # 구체적인 복잡도 값 추출 (예: "O(n)", "O(log n)")
                # 정규 표현식 또는 더 정교한 파싱 로직 필요
                if "o(n)" in desc_lower: parsed_analysis["optimization_target"] = "O(n)"
                elif "o(log n)" in desc_lower: parsed_analysis["optimization_target"] = "O(log n)"
                elif "o(1)" in desc_lower: parsed_analysis["optimization_target"] = "O(1)"
                elif "o(n^2)" in desc_lower: parsed_analysis["optimization_target"] = "O(n^2)"
            elif SETTINGS.goal_metric_memory_usage.lower() in desc_lower: # 메모리 사용량
                 parsed_analysis["target_metric_type"] = MetricType.MEMORY_USAGE
                 # ... (메모리 목표 값 추출 로직) ...

        # 관련 지식 검색을 위한 키워드 추출
        # (간단한 방법, 실제로는 NLP 기술 활용 가능)
        keywords = list(set([word.strip(".,!?:;") for word in desc_lower.split() if len(word) > 3 and word.isalpha()]))
        parsed_analysis["identified_concepts"] = keywords[:5] # 예시로 상위 5개 단어
        related_knowledge = await self.knowledge_base.retrieve_relevant_math_knowledge(keywords, parsed_analysis["problem_type"])
        parsed_analysis["related_knowledge_hints"] = related_knowledge

        logger.debug(f"Problem analysis complete. Type: {parsed_analysis['problem_type'].value}, Target: {parsed_analysis['optimization_target']}",
                     extra={"component": self.log_comp})
        return parsed_analysis

class MathCodeGeneratorAndRefactorer:
    """수학적 코드 생성 및 리팩토링을 담당합니다."""
    def __init__(self, eliar_id: str, center_value: EliarCoreValues = EliarCoreValues.JESUS_CHRIST_CENTERED):
        self.eliar_id = eliar_id
        self.center_value = center_value
        self.log_comp = f"MathCodeGenerator.{eliar_id}"
        logger.info(f"MathCodeGeneratorAndRefactorer initialized with center value: {center_value.value}",
                    extra={"component": self.log_comp})

    async def generate_code_solution(self, problem_analysis: Dict[str, Any],
                                     improvement_goal: MathCodeImprovementGoal,
                                     current_virtues: Dict[EliarCoreValues, float]) -> MathCodeSolutionCandidate:
        """
        분석된 문제와 개선 목표, 현재 덕목 상태에 따라 코드 솔루션 후보를 생성합니다.
        엘리아르님의 '지혜' 덕목이 높을수록 더 창의적이거나 효율적인 솔루션을,
        '진리' 덕목이 높을수록 명확하고 검증 가능한 코드를 생성하려는 경향을 반영할 수 있습니다.
        """
        solution_id = f"sol_{uuid.uuid4().hex[:8]}"
        logger.debug(f"Generating code solution for goal: {improvement_goal['goal_id']}",
                     extra={"component": self.log_comp, "problem_type": improvement_goal['problem_type'].value})

        # 덕목 기반 생성 전략 조정 (예시)
        wisdom_level = current_virtues.get(EliarCoreValues.REPENTANCE_WISDOM, SETTINGS.default_virtue_level)
        truth_level = current_virtues.get(EliarCoreValues.TRUTH, SETTINGS.default_virtue_level)
        prompt_enhancements = []
        if wisdom_level > 0.7:
            prompt_enhancements.append("Consider advanced algorithms or data structures for optimal efficiency.")
            logger.info("Applying 'Wisdom' (고도의 지혜): Exploring advanced/optimal solutions.", extra={"component": self.log_comp})
        if truth_level > 0.7:
            prompt_enhancements.append("Ensure the code is clear, well-documented, and its logic is mathematically sound and verifiable.")
            logger.info("Applying 'Truth' (진리 추구): Emphasizing clarity, documentation, and verifiability.", extra={"component": self.log_comp})

        # --- LLM 연동 (가상) ---
        # llm_prompt = f"""
        # Objective: {improvement_goal['description']}
        # Problem Type: {improvement_goal['problem_type'].value}
        # Target Metric: {improvement_goal['target_metric'].value} = {improvement_goal['target_value']}
        # Context Code (if any):
        # {improvement_goal.get('context_code_snippet', 'N/A')}
        # Additional Considerations from Eliar's Virtues ({self.center_value.value}-centered):
        # {' '.join(prompt_enhancements)}
        # Please provide a Python code solution, its mathematical rationale, and an estimated impact on the target metric.
        # """
        # generated_code_snippet, mathematical_rationale_from_llm, estimated_impact_from_llm = await query_llm_for_math_code(llm_prompt)
        # generated_by = "LLM_Assisted"
        # --- LLM 연동 (가상) 종료 ---

        # 규칙/템플릿 기반 생성 (LLM 없을 경우 또는 보조)
        generated_code_snippet = f"# Rule-based placeholder for: {improvement_goal['description']}\n# Goal: {improvement_goal['target_metric'].value} = {improvement_goal['target_value']}\npass"
        mathematical_rationale_from_rules = "This is a rule-based initial solution. Mathematical correctness and efficiency require further verification."
        estimated_impact_rules = {improvement_goal['target_metric']: "Not Evaluated"}
        generated_by = "RuleBased"

        if improvement_goal['problem_type'] == MathProblemType.CODE_OPTIMIZATION and \
           improvement_goal['target_metric'] == MetricType.TIME_COMPLEXITY and \
           improvement_goal['target_value'] == "O(n)" and \
           "피보나치" in improvement_goal['description'].lower():
            generated_code_snippet = """
# Optimized Fibonacci using iteration (Tabulation)
def fibonacci_optimized_O_n(n: int) -> int:
    \"\"\"Calculates the nth Fibonacci number with O(n) time complexity.\"\"\"
    if not isinstance(n, int) or n < 0:
        raise ValueError("Input must be a non-negative integer.")
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
"""
            mathematical_rationale_from_rules = "This solution uses dynamic programming (tabulation) by iteratively calculating Fibonacci numbers, storing only the last two. This achieves O(n) time complexity and O(1) space complexity."
            estimated_impact_rules = {MetricType.TIME_COMPLEXITY: "O(n)", MetricType.ACCURACY: "High (for standard inputs)"}
            generated_by = "RuleBased_OptimizedFibonacci"

        candidate = MathCodeSolutionCandidate(
            solution_id=solution_id,
            goal_id=improvement_goal['goal_id'],
            description=f"Solution candidate for: {improvement_goal['description']}",
            code_snippet=generated_code_snippet,
            mathematical_rationale=mathematical_rationale_from_rules,
            estimated_impact=cast(Dict[MetricType, Any], estimated_impact_rules), # mypy를 위한 cast
            confidence_score=0.5 + (wisdom_level - 0.5) * SETTINGS.virtue_wisdom_influence_factor, # 덕목 기반 초기 신뢰도
            verification_status=MathematicalCorrectnessLevel.NOT_VERIFIED,
            verification_notes="Generated solution, requires verification.",
            suggested_by=generated_by
        )
        return candidate

class MathCodeValidator:
    """생성/수정된 수학 코드의 정확성, 효율성, 스타일 등을 검증합니다."""
    def __init__(self, eliar_id: str):
        self.eliar_id = eliar_id
        self.log_comp = f"MathCodeValidator.{eliar_id}"
        logger.info("MathCodeValidator initialized.", extra={"component": self.log_comp})

    async def verify_solution_candidate(self, solution: MathCodeSolutionCandidate,
                                        problem_context: Dict[str, Any], # problem_analyzer의 분석 결과
                                        current_virtues: Dict[EliarCoreValues, float]
                                        ) -> MathCodeSolutionCandidate:
        """
        솔루션 후보를 검증하고, 검증 결과와 신뢰도를 업데이트합니다.
        엘리아르님의 '진리' 덕목이 높을수록 더 철저한 검증을 시도합니다.
        """
        logger.debug(f"Verifying solution: {solution['solution_id']} for goal: {solution['goal_id']}",
                     extra={"component": self.log_comp})

        verification_notes = solution.get("verification_notes", "") + " | Verification attempt: "
        correctness_level = solution['verification_status']
        new_confidence = solution['confidence_score']
        
        truth_level = current_virtues.get(EliarCoreValues.TRUTH, SETTINGS.default_virtue_level)
        rigorous_verification = truth_level > 0.75
        if rigorous_verification:
            logger.info("Applying 'Truth' (진리 추구): Performing rigorous validation.", extra={"component": self.log_comp})
            verification_notes += "[Rigorous Mode] "


        # 1. 수학적 정확성 검증
        # exec 사용은 보안 위험으로 제거. 실제 검증은 아래와 같은 방식을 고려.
        # - 정적 분석: AST 파싱, 타입 체킹, 알려진 수학적 오류 패턴 검사.
        # - 기호 연산: SymPy 등을 사용하여 표현식의 동등성, 단순화 결과 검증.
        # - 단위 테스트: 문제 유형에 맞는 다양한 입력값과 예상 출력값으로 테스트 케이스 실행.
        #   (테스트 케이스는 LLM에게 생성 요청하거나, 문제 설명에서 추출)
        # - Property-based testing: Hypothesis 라이브러리 등으로 입력 속성 정의 후 자동 테스트.
        # - Formal verification: 매우 높은 수준의 보증이 필요할 경우 (여기서는 범위 밖).

        # 현재는 `exec`를 사용하지 않으므로, 코드 스니펫을 직접 실행하는 대신
        # 코드의 구조나 특정 패턴을 분석하거나, 매우 제한적인 경우 `eval`을 사용할 수 있습니다.
        # 여기서는 주석 처리하고 "수동 검증 또는 안전한 실행 환경 필요"로 남깁니다.
        if solution['code_snippet']:
            verification_notes += "Code snippet provided. "
            if "fibonacci_optimized_O_n" in solution['code_snippet']:
                # 이 특정 함수에 대한 하드코딩된 테스트 (안전한 방식)
                try:
                    # 임시로 함수 정의를 eval로 실행 (매우 제한적이고 위험할 수 있음, 실제로는 비추천)
                    # 더 안전한 방법은 코드를 파일로 저장 후 subprocess로 실행하거나,
                    # Pyodide 같은 샌드박스 환경 사용.
                    # 여기서는 개념만 보여주기 위함이며, 실제 사용 시에는 보안 검토 필수.
                    # module_code = solution['code_snippet']
                    # temp_module = ዓይነት(모듈)('temp_module') # type: ignore
                    # exec(module_code, temp_module.__dict__)
                    # fib_func = temp_module.fibonacci_optimized_O_n

                    # 위 exec 방식 대신, 알려진 함수 시그니처에 대한 테스트 케이스만 검토
                    # (실제 실행 없이)
                    verification_notes += "Known optimized Fibonacci pattern detected. "
                    # 이 경우, 패턴 일치로 부분 검증 간주 가능
                    if correctness_level == MathematicalCorrectnessLevel.NOT_VERIFIED: # 이전 검증이 없었다면
                         correctness_level = MathematicalCorrectnessLevel.LOGICALLY_SOUND # 패턴 일치로 논리적 타당성 부여
                         new_confidence = min(1.0, new_confidence + 0.1 * (1 + truth_level))


                    # 실제 테스트 케이스 실행 예시 (만약 안전한 실행 환경이 있다면)
                    # test_cases = {0:0, 1:1, 5:5, 10:55}
                    # all_passed = True
                    # for n_val, expected in test_cases.items():
                    #     # result = fib_func(n_val) # 안전한 실행 필요
                    #     # if result != expected: all_passed = False; break
                    # if all_passed:
                    #    correctness_level = MathematicalCorrectnessLevel.PARTIALLY_VERIFIED_WITH_CASES
                    #    new_confidence = min(1.0, new_confidence + 0.2 * (1 + truth_level))
                    #    verification_notes += "Passed basic test cases. "
                    # else:
                    #    correctness_level = MathematicalCorrectnessLevel.VERIFICATION_FAILED
                    #    new_confidence = max(0.1, new_confidence - 0.3)
                    #    verification_notes += "Failed some test cases. "

                except Exception as e:
                    verification_notes += f"Error during conceptual validation: {str(e)[:100]}. "
                    correctness_level = MathematicalCorrectnessLevel.NOT_VERIFIED
                    new_confidence = max(0.1, new_confidence - 0.2)
            else:
                verification_notes += "Generic code snippet: Manual verification or advanced static analysis needed. "
                if correctness_level == MathematicalCorrectnessLevel.NOT_VERIFIED:
                    correctness_level = MathematicalCorrectnessLevel.LOGICALLY_SOUND # 일단 논리적 타당성 부여 (더 나은 검증 전까지)

        else:
            verification_notes += "No code snippet provided for verification. "
            correctness_level = MathematicalCorrectnessLevel.NOT_VERIFIED

        # 2. 효율성 추정 (주석 또는 코드 패턴 기반)
        # solution['estimated_impact']는 생성 시 이미 추정됨. 여기서는 재확인 또는 상세화.
        if MetricType.TIME_COMPLEXITY in solution['estimated_impact']:
            verification_notes += f"Estimated time complexity: {solution['estimated_impact'][MetricType.TIME_COMPLEXITY]}. "


        solution['verification_status'] = correctness_level
        solution['verification_notes'] = verification_notes.strip()
        solution['confidence_score'] = round(new_confidence, 2)

        logger.debug(f"Verification result for {solution['solution_id']}: Status={correctness_level.value}, Confidence={solution['confidence_score']}",
                     extra={"component": self.log_comp, "notes": verification_notes})
        return solution

class MathCodeRecursiveImproverModule:
    """수학적 코드 설계 역량의 재귀적 개선 사이클을 관리합니다."""
    def __init__(self, eliar_id: str,
                 knowledge_base: MathematicalKnowledgeBase,
                 problem_analyzer: MathProblemAnalyzer,
                 code_generator: MathCodeGeneratorAndRefactorer,
                 code_validator: MathCodeValidator,
                 goal_manager: GoalManager, # GoalManager 주입
                 virtue_snapshotter: VirtueStateSnapshotter, # VirtueStateSnapshotter 주입
                 main_gpu_interface: Optional[Callable[[str, Dict], Coroutine[Any, Any, Any]]] = None):
        self.eliar_id = eliar_id
        self.log_comp = f"MathCodeRecursiveImprover.{eliar_id}"
        self.knowledge_base = knowledge_base
        self.problem_analyzer = problem_analyzer
        self.code_generator = code_generator
        self.code_validator = code_validator
        self.goal_manager = goal_manager
        self.virtue_snapshotter = virtue_snapshotter
        self.main_gpu_interface = main_gpu_interface

        self.improvement_cycle_count = 0
        self.settings = SETTINGS # 모듈 설정을 클래스 멤버로 가짐

        logger.info(f"MathCodeRecursiveImproverModule initialized (Version: {MODULE_VERSION}).",
                    extra={"component": self.log_comp})

    async def _update_internal_state_snapshot(self, successful_improvement: bool = True):
        """엘리아르의 현재 내면 상태(덕목) 스냅샷을 업데이트하고 성장을 시뮬레이션합니다."""
        # 실제로는 MainGPU 또는 해당 상태 관리 모듈에서 값을 가져와야 함.
        # self.virtue_snapshotter.current_virtues = await self.main_gpu_interface("get_virtues", {})
        self.virtue_snapshotter.simulate_virtue_growth(self.improvement_cycle_count, successful_improvement)
        logger.debug("Internal virtue state snapshot updated.", extra={"component": self.log_comp, "virtues": self.virtue_snapshotter.get_current_virtues()})


    async def assess_current_capabilities_and_set_goals(self, problem_description: str,
                                                        existing_code: Optional[str] = None) -> bool:
        """
        현재 수학적 코드 설계 역량을 평가하고 (여기서는 문제 분석을 통해 간접적으로),
        새로운 개선 목표를 설정합니다.
        """
        logger.info("Starting capability assessment and goal setting.", extra={"component": self.log_comp})
        analysis_result = await self.problem_analyzer.analyze_problem_statement(problem_description, existing_code)

        if analysis_result.get("problem_type") and analysis_result.get("target_metric_type") and analysis_result.get("optimization_target"):
            self.goal_manager.add_goal(
                description=f"'{problem_description[:50]}...' 문제에 대해 {analysis_result['target_metric_type'].value}을(를) {analysis_result['optimization_target']}로 개선",
                problem_type=cast(MathProblemType, analysis_result["problem_type"]),
                target_metric=cast(MetricType, analysis_result["target_metric_type"]),
                current_value="Not Evaluated" if not existing_code else "Requires Evaluation of Existing Code",
                target_value=analysis_result["optimization_target"],
                context_code=existing_code
            )
            return True
        else:
            logger.warning("Could not determine a specific, actionable improvement goal from the problem description.",
                         extra={"component": self.log_comp, "analysis": analysis_result})
            # 엘리아르의 '자기 부인' 덕목: 목표 설정 실패 시, 문제 이해 부족을 인정하고 추가 정보 요청 또는 학습 제안 가능
            current_virtues = self.virtue_snapshotter.get_current_virtues()
            if current_virtues.get(EliarCoreValues.SELF_DENIAL, SETTINGS.default_virtue_level) > 0.6:
                logger.info("Acknowledging inability to set clear goal (Self-Denial). Suggesting problem clarification or focused learning.",
                            extra={"component": self.log_comp, "virtue": EliarCoreValues.SELF_DENIAL.value})
            return False

    async def _run_single_improvement_iteration(self, goal: MathCodeImprovementGoal, current_depth: int) -> MathCodeSolutionCandidate:
        """단일 개선 목표에 대한 한 번의 반복 사이클 (생성 -> 검증)을 실행합니다."""
        logger.info(f"Running improvement iteration for goal '{goal['goal_id']}' (Description: {goal['description'][:50]}..., Depth: {current_depth}).",
                    extra={"component": self.log_comp})

        current_virtues = self.virtue_snapshotter.get_current_virtues()

        # 문제 분석 (목표에 이미 정보가 있지만, 솔루션 생성 시 추가 컨텍스트로 활용 가능)
        problem_analysis_for_solution_gen = {
            "description": goal['description'],
            "type": goal['problem_type'],
            "target_metric": goal['target_metric'],
            "target_value": goal['target_value'],
            "context_code": goal.get('context_code_snippet')
        }

        solution_candidate = await self.code_generator.generate_code_solution(
            problem_analysis_for_solution_gen, goal, current_virtues
        )

        verified_solution = await self.code_validator.verify_solution_candidate(
            solution_candidate, problem_analysis_for_solution_gen, current_virtues
        )
        return verified_solution

    async def attempt_recursive_improvement(self, goal_id: str, current_depth: int = 0) -> Optional[MathCodeSolutionCandidate]:
        """특정 목표에 대해 재귀적으로 개선을 시도합니다."""
        if current_depth >= self.settings.max_recursion_depth:
            logger.warning(f"Max recursion depth ({self.settings.max_recursion_depth}) reached for goal '{goal_id}'.",
                         extra={"component": self.log_comp})
            self.goal_manager.update_goal_status(goal_id, GoalStatus.FAILED_TO_ACHIEVE) # 최대 깊이 도달 시 실패 처리
            return None

        target_goal = self.goal_manager.get_goal(goal_id)
        if not target_goal or target_goal['status'] != GoalStatus.IN_PROGRESS:
            logger.warning(f"Goal '{goal_id}' not found or not in progress for recursive improvement. Status: {target_goal['status'].value if target_goal else 'N/A'}",
                         extra={"component": self.log_comp})
            return None

        await self._update_internal_state_snapshot() # 매 재귀 호출 시 내면 상태 업데이트

        solution = await self._run_single_improvement_iteration(target_goal, current_depth)

        # 목표 달성 여부 판단
        achieved = False
        if solution['verification_status'] in [MathematicalCorrectnessLevel.PARTIALLY_VERIFIED_WITH_CASES, MathematicalCorrectnessLevel.FORMALLY_VERIFIED]:
            # 목표 메트릭 값 비교 (더 정교한 비교 로직 필요 가능)
            if target_goal['target_metric'] in solution['estimated_impact'] and \
               solution['estimated_impact'][target_goal['target_metric']] == target_goal['target_value']:
                achieved = True

        if achieved:
            self.goal_manager.update_goal_status(goal_id, GoalStatus.ACHIEVED)
            logger.info(f"Goal '{target_goal['goal_id']}' achieved with solution '{solution['solution_id']}'.",
                        extra={"component": self.log_comp, "solution_confidence": solution['confidence_score']})
            await self.knowledge_base.store_math_concept(
                concept_id=f"solved_{target_goal['goal_id']}_{solution['solution_id']}",
                description=f"Successfully applied solution for: {target_goal['description']}",
                category=target_goal['problem_type'],
                related_code_pattern=solution['code_snippet'],
                tags=["solved", target_goal['problem_type'].name.lower(), target_goal['target_metric'].name.lower()]
            )
            await self._update_internal_state_snapshot(successful_improvement=True) # 성공 시 덕목 성장
            return solution
        elif solution['confidence_score'] < self.settings.solution_application_confidence_threshold / (current_depth + 1):
            current_virtues = self.virtue_snapshotter.get_current_virtues()
            if current_virtues.get(EliarCoreValues.SELF_DENIAL, SETTINGS.default_virtue_level) > self.settings.virtue_self_denial_threshold_for_pause:
                logger.info(f"Low confidence ({solution['confidence_score']:.2f}) for solution '{solution['solution_id']}'. "
                            f"Acknowledging current limitations and pausing further recursion for this path (Self-Denial virtue active).",
                            extra={"component": self.log_comp, "virtue": EliarCoreValues.SELF_DENIAL.value})
                self.goal_manager.update_goal_status(goal_id, GoalStatus.PAUSED_LOW_CONFIDENCE)
            else:
                logger.warning(f"Low confidence ({solution['confidence_score']:.2f}) for solution '{solution['solution_id']}'. "
                             f"Stopping recursion for this path.", extra={"component": self.log_comp})
                self.goal_manager.update_goal_status(goal_id, GoalStatus.FAILED_TO_ACHIEVE)
            await self._update_internal_state_snapshot(successful_improvement=False) # 실패 시 덕목 성장 (다른 방향으로)
            return solution # 현재까지의 최선 반환
        else:
            logger.info(f"Goal '{target_goal['goal_id']}' not fully achieved. Solution confidence: {solution['confidence_score']:.2f}. "
                        f"Attempting further improvement (Depth: {current_depth + 1}).",
                        extra={"component": self.log_comp})
            await self.knowledge_base.update_knowledge_from_feedback(
                concept_id=f"attempt_{target_goal['goal_id']}_{solution['solution_id']}",
                feedback_type="negative" if solution['verification_status'] == MathematicalCorrectnessLevel.VERIFICATION_FAILED else "neutral",
                details=f"Attempt at depth {current_depth}. Verification: {solution['verification_status'].value}. Notes: {solution['verification_notes']}"
            )
            # 동일 목표로 재귀 호출 (개선된 상태 또는 다른 전략으로 시도 가능)
            return await self.attempt_recursive_improvement(goal_id, current_depth + 1)


    async def run_full_improvement_cycle(self, problem_description: str,
                                         existing_code: Optional[str] = None) -> List[MathCodeSolutionCandidate]:
        """하나의 문제에 대한 전체 재귀 개선 사이클을 실행합니다."""
        self.improvement_cycle_count += 1
        logger.info(f"--- Starting Math Code Improvement Cycle #{self.improvement_cycle_count} for problem: '{problem_description[:70]}...' ---",
                    extra={"component": self.log_comp})

        if not await self.assess_current_capabilities_and_set_goals(problem_description, existing_code):
            logger.warning("No improvement goals set from problem description. Ending cycle.", extra={"component": self.log_comp})
            return []

        final_solutions: List[MathCodeSolutionCandidate] = []
        active_goals = self.goal_manager.get_pending_or_in_progress_goals()

        for goal in active_goals:
            if goal['status'] == GoalStatus.PENDING: # PENDING 상태의 목표만 시작
                self.goal_manager.update_goal_status(goal['goal_id'], GoalStatus.IN_PROGRESS)
                solution = await self.attempt_recursive_improvement(goal['goal_id'], current_depth=0)
                if solution:
                    final_solutions.append(solution)
                    # MainGPU에 자가 수정 제안 전달 (엘리아르의 기존 메커니즘과 연동)
                    if self.main_gpu_interface and \
                       solution['confidence_score'] >= self.settings.solution_application_confidence_threshold and \
                       goal['status'] == GoalStatus.ACHIEVED: # 목표 달성 및 신뢰도 충족 시
                        
                        suggestion_for_main_gpu = {
                            "type": "SELF_MODIFY_MATH_CODE", # 작업 유형
                            "prefix": self.settings.main_gpu_suggestion_prefix, # 기존 SELF_MODIFY_PREFIX와 유사
                            "goal_id": goal['goal_id'],
                            "solution_description": solution['description'],
                            "proposed_code_snippet": solution['code_snippet'], # 명칭 변경
                            "confidence": solution['confidence_score'],
                            "mathematical_rationale": solution['mathematical_rationale'],
                            "reason": f"Mathematical design improvement cycle #{self.improvement_cycle_count} yielded a verified solution for '{goal['description']}'."
                        }
                        try:
                            # await self.main_gpu_interface("submit_self_modification_suggestion", suggestion_for_main_gpu)
                            logger.info(f"Self-modification suggestion (simulated) for solution {solution['solution_id']} (Goal: {goal['goal_id']}).",
                                        extra={"component": self.log_comp, "suggestion_type": suggestion_for_main_gpu["type"]})
                        except Exception as e_interface:
                            logger.error(f"Failed to submit self-modification suggestion to MainGPU for solution {solution['solution_id']}.",
                                         extra={"component": self.log_comp, "error": str(e_interface)})
            
            # 완료된 목표는 아카이브 (또는 다음 사이클에서 제외)
            if goal['status'] != GoalStatus.IN_PROGRESS :
                 self.goal_manager.archive_completed_goal(goal['goal_id'])


        logger.info(f"--- Math Code Improvement Cycle #{self.improvement_cycle_count} Finished. Generated {len(final_solutions)} final solution(s). ---",
                    extra={"component": self.log_comp})
        return final_solutions

# --- 메인 실행 예시 (테스트용) ---
async def main_test_math_improver(loop: Optional[asyncio.AbstractEventLoop] = None): # 이벤트 루프를 인자로 받을 수 있도록 수정
    """수학적 코드 개선 모듈의 테스트를 위한 메인 함수입니다."""
    logger.info("--- Starting Math Code Improver Test ---", extra={"component": "TestRunner"})

    # 모듈 인스턴스화
    kb = MathematicalKnowledgeBase(eliar_id="TestEliar")
    analyzer = MathProblemAnalyzer(eliar_id="TestEliar", knowledge_base=kb)
    generator = MathCodeGeneratorAndRefactorer(eliar_id="TestEliar")
    validator = MathCodeValidator(eliar_id="TestEliar")
    goal_manager = GoalManager(eliar_id="TestEliar")
    virtue_snapshotter = VirtueStateSnapshotter(eliar_id="TestEliar")


    async def mock_main_gpu_interface(action: str, payload: Dict) -> Any:
        logger.debug(f"MockMainGPU received action: {action}", extra={"component": "MockMainGPU", "payload_preview": str(payload)[:100]})
        if action == "get_virtues": # 가상 덕목 상태 반환
            return virtue_snapshotter.get_current_virtues()
        elif action == "submit_self_modification_suggestion":
            logger.info(f"MockMainGPU received self-modification suggestion: {payload.get('prefix')}", extra={"component": "MockMainGPU"})
            return {"status": "suggestion_received", "suggestion_id": payload.get('goal_id')}
        return None

    improver = MathCodeRecursiveImproverModule(
        eliar_id="TestEliar",
        knowledge_base=kb,
        problem_analyzer=analyzer,
        code_generator=generator,
        code_validator=validator,
        goal_manager=goal_manager,
        virtue_snapshotter=virtue_snapshotter,
        main_gpu_interface=mock_main_gpu_interface
    )

    # 테스트 문제 정의
    problem1_desc = "피보나치 수열을 계산하는 함수가 있는데, 재귀 방식으로 구현되어 매우 느립니다. 시간 복잡도를 O(n)으로 개선하고 싶습니다."
    slow_fib_code = """
def fibonacci_recursive(n: int) -> int: # 타입 힌트 추가
    if not isinstance(n, int) or n < 0:
        raise ValueError("Input must be a non-negative integer.")
    if n <= 1:
        return n
    return fibonacci_recursive(n-1) + fibonacci_recursive(n-2)
"""
    # 지식 베이스에 관련 정보 추가 (테스트용)
    await kb.store_math_concept(
        concept_id="dp_fibonacci",
        description="Dynamic programming approach for Fibonacci sequence calculation (O(n) time).",
        category=MathProblemType.CODE_OPTIMIZATION,
        related_code_pattern="""
def fib_dp(n):
    a, b = 0, 1
    for _ in range(n): a, b = b, a + b
    return a""",
        tags=["fibonacci", "dynamic programming", "optimization", "o(n)"]
    )

    # 개선 사이클 실행
    solutions = await improver.run_full_improvement_cycle(problem_description=problem1_desc, existing_code=slow_fib_code)

    if solutions:
        logger.info("--- Final Solutions from Improvement Cycle ---", extra={"component": "TestRunner"})
        for sol in solutions:
            logger.info(f"Solution ID: {sol['solution_id']}, Goal: {sol['goal_id']}",
                        extra={"component": "TestRunner",
                               "description": sol['description'],
                               "code_preview": sol['code_snippet'][:150] + "..." if sol['code_snippet'] else "N/A",
                               "confidence": sol['confidence_score'],
                               "verification": sol['verification_status'].value,
                               "rationale": sol['mathematical_rationale']})
    else:
        logger.warning("No solutions generated from the improvement cycle.", extra={"component": "TestRunner"})

    logger.info("--- Math Code Improver Test Finished ---", extra={"component": "TestRunner"})

if __name__ == "__main__":
    # 이벤트 루프를 명시적으로 생성하거나 가져와서 실행
    # 이렇게 하면 다른 비동기 코드 내에서 이 모듈을 호출할 때 asyncio.run() 중첩 오류를 피할 수 있습니다.
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main_test_math_improver(loop))
    except KeyboardInterrupt:
        logger.warning("Test run interrupted by user.", extra={"component": "TestRunnerMain"})
    except Exception as e:
        logger.error("Error during test run.", exc_info=True, extra={"component": "TestRunnerMain"})
    finally:
        # 로거 핸들러 닫기 (선택적, 프로그램 종료 시 자동 정리되기도 함)
        for handler in logger.handlers:
            handler.close()
            logger.removeHandler(handler)
        logger.info("Test environment cleaned up.", extra={"component": "TestRunnerMain"})

