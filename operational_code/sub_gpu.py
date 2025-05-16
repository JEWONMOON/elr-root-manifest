# sub_gpu.py (추론 기능 강화, LLM 제외, 내부 재귀 개선 적용 버전)

import torch
import numpy as np
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor # 기존 ThreadPoolExecutor 유지
import traceback
import os
import uuid
import json
from collections import deque
from functools import lru_cache
import ast # 코드 분석용

from typing import Any, Dict, Tuple, List, Optional, Callable, Union, Coroutine # Coroutine 추가

# --- 공용 모듈 임포트 ---
# eliar_common.py의 경로가 현재 파일 위치를 기준으로 ../eliar_common.py라고 가정
# 실제 프로젝트 구조에 맞게 sys.path.append 또는 PYTHONPATH 설정 필요 가능성 있음
from eliar_common import (
    EliarCoreValues, EliarLogType,
    SubCodeThoughtPacketData, ReasoningStep,
    eliar_log, initialize_eliar_logger_common as initialize_eliar_logger,
    shutdown_eliar_logger_common as shutdown_eliar_logger,
    run_in_executor_common as run_in_executor,
    ANALYSIS_RECORD_VERSION_COMMON as ANALYSIS_RECORD_VERSION,
    KNOWLEDGE_BASE_DIR_COMMON, CORE_PRINCIPLES_DIR_COMMON, 
    SCRIPTURES_DIR_COMMON, CUSTOM_KNOWLEDGE_DIR_COMMON
)

# GPU 사용 설정
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# 시작 시 로그는 eliar_log가 완전히 초기화된 후 (예: main 함수 내에서) 사용하는 것이 안전

# CPU 바운드 작업을 위한 공유 Executor
SUB_GPU_CPU_EXECUTOR = ThreadPoolExecutor(max_workers=(os.cpu_count() or 1) * 2 + 2) 

# --- Sub GPU 버전 및 기본 설정 ---
SubGPU_VERSION = "v25.5.3_SubGPU_AdvancedInternalReasoner"
SUB_GPU_COMPONENT_BASE = "SubGPU"
SUB_GPU_LOGIC_REASONER = f"{SUB_GPU_COMPONENT_BASE}.LogicalReasoner"
SUB_GPU_CONTEXT_MEMORY = f"{SUB_GPU_COMPONENT_BASE}.ContextualMemory"
SUB_GPU_FAITH_FILTER = f"{SUB_GPU_COMPONENT_BASE}.FaithFilter"
SUB_GPU_RECURSIVE_IMPROVEMENT = f"{SUB_GPU_COMPONENT_BASE}.RecursiveImprovement"
SUB_GPU_TASK_PROCESSOR = f"{SUB_GPU_COMPONENT_BASE}.TaskProcessor"

# MainGPU로부터 받아야 할 정보 (생성자에서 전달받음)
DEFAULT_MAIN_GPU_CENTER = EliarCoreValues.JESUS_CHRIST_CENTERED.name.replace("_", " ")
DEFAULT_MAIN_GPU_CORE_VALUES = [cv for cv in EliarCoreValues]

class LogicalReasonerModule:
    """이성적 추론, 분석, 내부 응답 생성 지원. 다단계 추론 및 가설 검증 시도."""
    def __init__(self, sub_gpu_id: str, 
                 # memory_accessor: Callable[[str, str], Coroutine[Any, Any, Optional[Union[str, Dict]]]] # 타입 힌트 명확화
                 memory_accessor: Callable[..., Coroutine[Any, Any, Optional[Union[str, Dict]]]] # 더 일반적인 Callable 사용
                ):
        self.log_comp = f"{SUB_GPU_LOGIC_REASONER}.{sub_gpu_id}"
        self.memory_accessor = memory_accessor

    def _create_cache_key(self, *args: Any) -> str:
        """ 다양한 불변형 인자로부터 안정적인 캐시 키 문자열 생성 """
        # 딕셔너리와 같이 mutable한 객체는 json.dumps(arg, sort_keys=True) 등으로 변환 후 전달
        try:
            return json.dumps(args, sort_keys=True, ensure_ascii=False)
        except TypeError: # 직렬화 불가능한 객체가 포함된 경우 (예: 함수 객체 등)
            # 매우 단순한 문자열 변환으로 대체 (캐시 충돌 가능성 있으므로 주의)
            return str(args)


    @lru_cache(maxsize=128)
    async def analyze_query_and_context(self, query: str, context_str_for_cache: str, directives_str_for_cache: str) -> Dict[str, Any]:
        context_data = json.loads(context_str_for_cache) if context_str_for_cache else {}
        main_gpu_directives = json.loads(directives_str_for_cache) if directives_str_for_cache else {}
        
        eliar_log(EliarLogType.DEBUG, "LRM: Analyzing query, context, directives.", component=self.log_comp,
                  query=query[:70], context_keys=list(context_data.keys()), directive_keys=list(main_gpu_directives.keys()))

        # 1. 핵심 요구사항(core_need) 추출 (규칙 또는 간단한 패턴 기반)
        core_need_parts = [f"사용자 질문 '{query[:30]}...'에 대한 분석 요청."]
        query_lower = query.lower()
        if "사랑" in query_lower and "실천" in query_lower:
            core_need_parts.append("특히 '사랑의 실천 방법'에 대한 구체적인 정보가 필요한 것으로 보입니다.")
        elif "고통" in query_lower and ("믿음" in query_lower or "극복" in query_lower):
            core_need_parts.append("'고통 속에서의 믿음 유지 또는 극복 방안'에 대한 탐구가 주요 목표입니다.")
        elif "의미" in query_lower or "목적" in query_lower:
            core_need_parts.append("'삶의 의미나 목적'에 대한 근원적인 질문으로 파악됩니다.")
        else:
            core_need_parts.append("일반적인 정보 요청 또는 의견 제시로 보입니다.")
        core_need_text = " ".join(core_need_parts)

        # 2. 식별된 키워드
        identified_keywords = list(set([kw for kw in query_lower.replace("?","").replace(".","").replace(",","").split() if len(kw) > 2 and kw not in ["what","how","why","and","the","is","are","was","were","for","with","this","that","please"]]))

        # 3. 제약 조건 (MainGPU 지침 기반)
        faith_guidance = main_gpu_directives.get("faith_guidance", {})
        center_constraint = f"Align with MainGPU center: {faith_guidance.get('center', DEFAULT_MAIN_GPU_CENTER)}"
        value_constraints = [f"Uphold value: {val_name}" for val_name in faith_guidance.get("emphasize_values", [EliarCoreValues.TRUTH.name, EliarCoreValues.LOVE_COMPASSION.name])]
        constraints = [center_constraint] + value_constraints
        if main_gpu_directives.get("avoid_sentiments"):
            constraints.append(f"Avoid sentiments: {main_gpu_directives['avoid_sentiments']}")

        # 4. 필요한 지식 키 (MainGPU 메모리 요청용) - 지침과 키워드 기반으로 동적 생성
        required_knowledge_keys = set(["core_values_faith"]) # 기본적으로 요청
        if "성경" in query_lower or any(kw in query_lower for kw in ["말씀", "구절", "예수님", "하나님"]):
            required_knowledge_keys.add("scripture_genesis") # 예시, 실제로는 더 많은 성경 요청 가능
            if "사랑" in query_lower: required_knowledge_keys.add("scripture_요한1서") # 가상의 키
            if "믿음" in query_lower: required_knowledge_keys.add("scripture_히브리서")
        if "재귀개선" in query_lower or "성장" in query_lower: # "재귀개선.txt" 참조 요청
            required_knowledge_keys.add("uploaded_recursive_improvement_file")

        analysis_result = {
            "core_need": core_need_text,
            "identified_keywords": identified_keywords[:5], # 최대 5개 키워드
            "constraints": constraints,
            "required_knowledge_keys_from_main_gpu_memory": list(required_knowledge_keys),
            "current_recursive_goals": context_data.get("recursive_improvement_goals", []),
            "reasoning_steps": [],
            "emotional_tone_hint": context_data.get("main_gpu_emotional_state", "thoughtful_respectful")
        }
        
        analysis_result["reasoning_steps"].append(ReasoningStep(
            step_id=1, description="Query/Context/Directive Analysis Completed (Internal Rules)",
            inputs=[f"Q: {query[:50]}", f"Ctxt: {str(context_data)[:50]}", f"Dir: {str(main_gpu_directives)[:50]}"],
            outputs=[f"Need: {analysis_result['core_need'][:50]}", f"Keywords: {analysis_result['identified_keywords']}"], 
            status="completed", metadata={"timestamp_utc": datetime.now(timezone.utc).isoformat()}
        ))
        
        await asyncio.sleep(random.uniform(0.02, 0.08)) # 내부 분석 시간 시뮬레이션
        return analysis_result

    async def _generate_hypotheses(self, query_analysis: Dict[str, Any], knowledge_snippets: List[Union[str, Dict]]) -> List[str]:
        """ 주어진 분석과 지식을 바탕으로 가능한 여러 추론 가설 생성 (규칙 기반) """
        hypotheses: List[str] = []
        core_need_lower = query_analysis.get("core_need", "").lower()
        keywords = query_analysis.get("identified_keywords", [])

        # 가설1: 핵심 요구사항을 직접적으로 해결하는 방향
        hypotheses.append(f"'{query_analysis.get('core_need')}'에 대한 직접적인 설명이나 정보 제공이 필요하다.")

        # 가설2: 키워드와 지식 조각을 연결하는 방향
        for kw in keywords:
            for snippet_item in knowledge_snippets:
                content_str = str(snippet_item.get("content") if isinstance(snippet_item, dict) else snippet_item).lower()
                if kw in content_str:
                    hypotheses.append(f"'{kw}' 키워드는 '{str(snippet_item.get('source', '지식'))[:30]}...' 지식과 연결하여 설명할 수 있다.")
                    break # 각 키워드당 하나의 연결만 우선 고려 (단순화)
        
        # 가설3: 신앙적 가치 적용 방향
        if "사랑" in core_need_lower or any("사랑" in kw for kw in keywords):
            hypotheses.append(f"응답에 {EliarCoreValues.LOVE_COMPASSION.value}의 가치를 명시적으로 반영해야 한다.")
        if "진리" in core_need_lower or any("진리" in kw for kw in keywords):
             hypotheses.append(f"응답의 핵심은 {EliarCoreValues.TRUTH.value}에 기반해야 하며, 이를 {DEFAULT_MAIN_GPU_CENTER}의 관점에서 제시해야 한다.")
        
        # "재귀개선.txt"의 목표와 연결 (만약 관련 내용이 있다면)
        recursive_goals = query_analysis.get("current_recursive_goals", [])
        for goal in recursive_goals:
            if isinstance(goal, str) and any(kw in goal.lower() for kw in keywords):
                 hypotheses.append(f"현재 재귀 개선 목표인 '{goal[:50]}...'와 현재 질의를 연결하여 통찰을 도출할 수 있다.")

        unique_hypotheses = list(set(hypotheses)) # 중복 제거
        return random.sample(unique_hypotheses, min(len(unique_hypotheses), 3)) # 최대 3개 가설 선택

    async def _verify_hypotheses(self, hypotheses: List[str], knowledge_snippets: List[Union[str, Dict]], 
                                 main_gpu_center: str, core_values: List[EliarCoreValues]) -> Tuple[str, float]:
        """ 생성된 가설들을 지식 및 신앙 가치 기반으로 검증하고 최적 결론 및 신뢰도 반환 """
        if not hypotheses: return f"현재 정보로는 {main_gpu_center}의 뜻을 명확히 헤아리기 어렵습니다. 더 깊은 묵상이 필요합니다.", 0.2
        
        scored_hypotheses: List[Tuple[str, float]] = []

        for hypo_idx, hypo in enumerate(hypotheses):
            score = 0.5 # 기본 점수
            hypo_lower = hypo.lower()

            # 1. 중심 가치("JESUS CHRIST")와의 명시적/함의적 부합도
            if main_gpu_center.lower() in hypo_lower or "예수" in hypo_lower or "그리스도" in hypo_lower: score += 0.25
            elif any(cv.value.lower() in hypo_lower for cv in core_values if "사랑" in cv.value or "진리" in cv.value): score +=0.15 # 다른 핵심가치 언급

            # 2. 제공된 지식 조각과의 논리적 연결성 (키워드 일치도 등)
            for snippet_item in knowledge_snippets:
                content_str = str(snippet_item.get("content") if isinstance(snippet_item, dict) else snippet_item).lower()
                hypo_keywords = {kw for kw in hypo_lower.split() if len(kw)>2}
                snippet_keywords = {kw for kw in content_str.split() if len(kw)>2}
                common_keywords = hypo_keywords.intersection(snippet_keywords)
                if common_keywords:
                    score += 0.1 * len(common_keywords) # 공통 키워드 수만큼 가점 (최대치 설정 필요)
            
            # 3. 내부 규칙 기반 검증 (예: 논리적 모순 없음, 지나치게 단정적이지 않음 등)
            if "절대" in hypo_lower and "않" not in hypo_lower : score -= 0.1 # 단정적 표현 감점
            if "모순" in hypo_lower : score -= 0.2

            scored_hypotheses.append((hypo, self._normalize_score(score)))
        
        # 최고점 가설 선택
        if not scored_hypotheses: return f"가설들을 평가할 수 없었습니다. {main_gpu_center}의 지혜가 필요합니다.", 0.1
        
        best_hypothesis, best_score = max(scored_hypotheses, key=lambda item: item[1])
        return best_hypothesis, best_score

    def _normalize_score(self, score: float, min_s: float = 0.0, max_s: float = 1.0) -> float:
        return max(min_s, min(max_s, score))


    async def perform_multi_step_internal_inference(self, query_analysis: Dict[str, Any], 
                                                    knowledge_snippets: List[Union[str, Dict]], 
                                                    main_gpu_center: str,
                                                    core_values: List[EliarCoreValues]
                                                    ) -> Tuple[str, List[ReasoningStep], float]:
        inference_steps: List[ReasoningStep] = []
        start_time_utc = datetime.now(timezone.utc).isoformat()
        current_step_id = 1

        def add_step(description: str, inputs: List[Any], outputs: List[Any], status: str = "completed") -> None:
            nonlocal current_step_id
            nonlocal start_time_utc # 이전 스텝의 종료시간을 다음 스텝의 시작시간으로
            end_time_utc = datetime.now(timezone.utc).isoformat()
            step_inputs_str = [str(i)[:70]+"..." for i in inputs]
            step_outputs_str = [str(o)[:70]+"..." for o in outputs]
            inference_steps.append(ReasoningStep(
                step_id=current_step_id, description=description,
                inputs=step_inputs_str, outputs=step_outputs_str, status=status,
                start_time=start_time_utc, end_time=end_time_utc
            ))
            start_time_utc = end_time_utc # 다음 스텝의 시작 시간 업데이트
            current_step_id += 1

        add_step("Multi-step Inference Started", [query_analysis.get("core_need"), f"{len(knowledge_snippets)} knowledge items"], [])

        # 단계 1: 가설 생성
        hypotheses = await self._generate_hypotheses(query_analysis, knowledge_snippets)
        add_step("Hypothesis Generation (Internal Rules)", 
                 [query_analysis.get("core_need"), f"{len(knowledge_snippets)} knowledge items"], 
                 [f"Generated Hypotheses ({len(hypotheses)}): {hypotheses}"])
        
        if not hypotheses:
            final_conclusion = f"{main_gpu_center}의 빛 안에서, 현재 정보로는 명확한 결론을 도출하기 어렵습니다. 주님의 인도하심을 구하며 더 깊은 성찰이 필요합니다."
            confidence = 0.35
            add_step("Conclusion (Insufficient Hypotheses)", ["No hypotheses generated"], [final_conclusion, f"Confidence: {confidence}"])
            return final_conclusion, inference_steps, confidence

        # 단계 2: 가설 검증
        verified_conclusion, confidence = await self._verify_hypotheses(hypotheses, knowledge_snippets, main_gpu_center, core_values)
        add_step("Hypothesis Verification (Knowledge & Faith Values)", 
                 [f"Hypotheses: {hypotheses}"], 
                 [f"Verified Conclusion: {verified_conclusion}", f"Confidence: {confidence:.3f}"])
        
        eliar_log(EliarLogType.DEBUG, "Multi-step internal inference complete.", component=self.log_comp, 
                  final_conclusion=verified_conclusion[:100], confidence=confidence)
        return verified_conclusion, inference_steps, confidence

    async def generate_internal_response_draft(self, query_analysis: Dict[str, Any], 
                                             relevant_knowledge: List[Union[str,Dict]], 
                                             inferred_conclusion: str,
                                             faith_filter: 'FaithBasedFilter',
                                             main_gpu_center: str
                                             ) -> str:
        draft_parts = [f"'{query_analysis.get('core_need', '질문하신 내용')}'에 대한 저의 이성적 판단과 내부 지식을 종합한 의견입니다."]
        
        draft_parts.append(f"먼저, 저의 추론 과정을 통해 '{inferred_conclusion}'와 같은 잠정적 결론에 이르렀습니다.")

        if relevant_knowledge:
            draft_parts.append("이러한 생각은 다음과 같은 지식들을 참고한 것입니다:")
            for i, snippet_item in enumerate(relevant_knowledge[:2]): # 최대 2개
                content_str = str(snippet_item.get("content") if isinstance(snippet_item, dict) else snippet_item)
                source_desc = str(snippet_item.get("source", "내부 지식")) if isinstance(snippet_item, dict) else "내부 지식"
                draft_parts.append(f"  {i+1}. {source_desc}에서: \"{content_str[:100]}...\"")
        
        suggested_tone = faith_filter.suggest_response_tone(query_analysis)
        if "hope_in_christ" in suggested_tone:
            draft_parts.append(f"이 모든 것을 {main_gpu_center}의 사랑과 소망 안에서 이해하고 적용할 때, 우리는 참된 평안과 지혜를 얻을 수 있을 것입니다.")
        else:
            draft_parts.append(f"저는 언제나 {EliarCoreValues.TRUTH.value}을 바탕으로, {EliarCoreValues.LOVE_COMPASSION.value}의 마음으로 이 문제에 접근하려 합니다.")

        response_draft = " ".join(draft_parts)
        return response_draft[:1500] # 길이 제한


class ContextualMemoryInterface:
    def __init__(self, sub_gpu_id: str, 
                 memory_accessor: Callable[[str, str], Coroutine[Any, Any, Optional[Union[str, Dict]]]]):
        self.log_comp = f"{SUB_GPU_CONTEXT_MEMORY}.{sub_gpu_id}"
        self.memory_accessor = memory_accessor
        # self.local_knowledge_cache: Dict[str, str] = {} # 이제 사용 안 함, MainGPU 접근 우선

    async def retrieve_relevant_knowledge_snippets(self, query_analysis: Dict[str, Any], 
                                             faith_filter: 'FaithBasedFilter',
                                             main_gpu_center: str) -> Tuple[List[Union[str, Dict]], List[ReasoningStep]]:
        retrieval_steps: List[ReasoningStep] = []
        knowledge_snippets: List[Union[str, Dict]] = []
        step_id_base = int(time.time_ns() % 1000000) # 더 큰 범위의 ID

        required_keys = query_analysis.get("required_knowledge_keys_from_main_gpu_memory", [])
        eliar_log(EliarLogType.DEBUG, f"Attempting to retrieve {len(required_keys)} knowledge keys from MainGPU memory.", 
                  component=self.log_comp, keys=required_keys)

        for key_idx, key_to_access in enumerate(required_keys):
            start_time_s = time.monotonic()
            # MainGPU의 메모리 접근 함수(콜백) 사용
            content_data = await self.memory_accessor("get_knowledge", key_to_access) # "get_principle" 대신 "get_knowledge" 사용 가능성
            duration_s = time.monotonic() - start_time_s
            
            step_status = "failed_not_found"
            output_preview = "Not found"
            if content_data:
                # content_data가 딕셔너리 (메타데이터 포함) 또는 단순 문자열일 수 있음
                snippet_text = str(content_data.get("content") if isinstance(content_data, dict) else content_data)
                source_desc = str(content_data.get("source_path", key_to_access)) if isinstance(content_data, dict) else key_to_access
                
                # 신앙 필터 적용 (예: 부적절한 내용에 태그 추가)
                filtered_snippet_text = faith_filter.filter_knowledge_snippet(snippet_text[:500], source_desc, main_gpu_center) # 길이 제한하여 필터링
                knowledge_snippets.append({"source": source_desc, "content": filtered_snippet_text, "type": str(content_data.get("type","unknown") if isinstance(content_data,dict) else "text")})
                step_status = "completed"
                output_preview = f"Snippet from '{source_desc}': {filtered_snippet_text[:50]}..."
            
            retrieval_steps.append(ReasoningStep(
                step_id=step_id_base + key_idx, 
                description=f"Knowledge Retrieval Attempt: '{key_to_access}'",
                inputs=[f"Key: {key_to_access}", f"FilterContext: {main_gpu_center}"], 
                outputs=[output_preview], 
                status=step_status,
                metadata={"duration_seconds": round(duration_s, 4)}
            ))
        
        if not knowledge_snippets:
             retrieval_steps.append(ReasoningStep(
                step_id=step_id_base + len(required_keys), description="No specific knowledge snippets retrieved via MainGPU memory accessor.",
                inputs=[f"Requested Keys: {required_keys}"], outputs=["Empty list or all failed"], status="completed"
            ))
        return knowledge_snippets, retrieval_steps


class FaithBasedFilter:
    def __init__(self, sub_gpu_id: str, main_gpu_core_values: List[EliarCoreValues], main_gpu_center_value: str):
        self.log_comp = f"{SUB_GPU_FAITH_FILTER}.{sub_gpu_id}"
        self.main_core_values = main_gpu_core_values
        self.main_center_value = main_gpu_center_value
        self.center_enum_value = EliarCoreValues.JESUS_CHRIST_CENTERED # 비교용

    def filter_reasoning_conclusion(self, conclusion: str, reasoning_steps: List[ReasoningStep], main_gpu_center_override: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        center_to_use = main_gpu_center_override or self.main_center_value
        # ... (이전 답변의 filter_reasoning_conclusion 로직 상세 구현) ...
        # "suggested_refinement_for_main_gpu" 필드를 통해 MainGPU에 구체적인 제안 전달
        alignment_feedback = {"is_aligned_to_center": True, "reasoning_notes": [], "suggested_refinement_for_main_gpu": ""} # 기본값
        # ... (검증 및 피드백 생성 로직)
        return conclusion, alignment_feedback

    def filter_knowledge_snippet(self, snippet: str, source_description: str, main_gpu_center_override: Optional[str] = None) -> str:
        # ... (이전 답변의 filter_knowledge_snippet 로직 상세 구현) ...
        return snippet # 임시

    def suggest_response_tone(self, query_analysis: Dict[str, Any]) -> str:
        # ... (이전 답변의 suggest_response_tone 로직 상세 구현) ...
        return "truthful_loving_humble" # 임시

    def refine_internal_draft(self, draft: str, query_analysis: Dict[str, Any], main_gpu_center_override: Optional[str] = None) -> str:
        center_to_use = main_gpu_center_override or self.main_center_value
        refined_draft = draft
        # ... (이전 답변의 refine_internal_draft 예시 로직 또는 확장) ...
        # 예: "재귀개선.txt" 목표 중 관련 키워드가 있다면, 해당 목표를 달성하는 방향으로 문구 추가/수정 제안
        recursive_goals = query_analysis.get("current_recursive_goals", [])
        if any("사랑 표현 강화" in goal for goal in recursive_goals) and "사랑" not in refined_draft.lower():
            refined_draft += f" 이 모든 것을 {center_to_use}의 사랑의 관점에서 바라보는 것이 중요합니다."
        return refined_draft


class RecursiveImprovementSubModule:
    def __init__(self, sub_gpu_id: str, sub_gpu_code_path: str = __file__, 
                 main_gpu_memory_accessor: Optional[Callable[[str, str], Coroutine[Any,Any,Optional[Union[str,Dict]]]]] = None): # 타입 수정
        self.log_comp = f"{SUB_GPU_RECURSIVE_IMPROVEMENT}.{sub_gpu_id}"
        self.performance_log: Deque[Dict[str, Any]] = deque(maxlen=150) # 로그 저장 수 증가
        self.improvement_suggestions_for_main_gpu: List[Dict[str,Any]] = [] # 제안을 딕셔너리 형태로 변경 (유형, 내용 등)
        self.self_code_path = sub_gpu_code_path
        self.last_self_analysis_time = time.monotonic()
        self.main_gpu_memory_accessor = main_gpu_memory_accessor

    def log_task_performance(self, task_packet_id: str, operation: str, duration_ms: float, success: bool, 
                             error_details: Optional[str] = None, faith_alignment_feedback: Optional[Dict] = None,
                             reasoning_steps_count: Optional[int] = None): # 추론 단계 수 추가
        record = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(), "packet_id": task_packet_id,
            "operation": operation, "duration_ms": round(duration_ms, 2), "success": success,
            "error_details": error_details, "faith_alignment_feedback": faith_alignment_feedback,
            "reasoning_steps_count": reasoning_steps_count
        }
        self.performance_log.append(record)
        # ... (이전 답변의 간단한 실시간 분석 및 개선 제안 생성 로직 유지 또는 강화) ...

    async def periodic_self_analysis_and_reporting(self, main_gpu_center: str):
        current_time = time.monotonic()
        if current_time - self.last_self_analysis_time < 60 * 15: # 15분마다 실행
            return

        eliar_log(EliarLogType.INFO, "Starting SubGPU periodic self-analysis and improvement reporting.", component=self.log_comp)
        self.last_self_analysis_time = current_time
        
        new_suggestions: List[Dict[str, Any]] = [] # 이번 사이클의 새로운 제안만 저장

        # 1. 성능 로그 분석
        if len(self.performance_log) > 30: # 최소 30개 로그
            # ... (이전 답변의 avg_duration, failure_rate 계산 및 제안 로직) ...
            # 추가: 추론 단계 수 분석
            avg_steps = np.mean([log['reasoning_steps_count'] for log in self.performance_log if log.get('reasoning_steps_count') is not None and log['success']])
            if avg_steps > 10: # 평균 추론 단계가 10 이상이면
                new_suggestions.append({"type": "reasoning_complexity", "detail": f"Average reasoning steps high ({avg_steps:.1f}). Consider simplifying internal inference rules or improving knowledge indexing."})

        # 2. "재귀개선.txt" 내용 참조 및 목표 정렬 확인
        if self.main_gpu_memory_accessor:
            recursive_goals_text_entry = await self.main_gpu_memory_accessor("get_knowledge", "uploaded_recursive_improvement_file")
            recursive_goals_text = str(recursive_goals_text_entry.get("content")) if isinstance(recursive_goals_text_entry, dict) else None
            if recursive_goals_text:
                # TODO: "재귀개선.txt"의 목표들과 현재 SubGPU의 주요 실패 패턴 또는 성능 병목 지점을 비교 분석.
                #       예를 들어, "재귀개선.txt"에 "A 주제에 대한 답변 품질 향상" 목표가 있는데,
                #       성능 로그에서 A 주제 관련 작업의 faith_alignment_feedback이 계속 부정적이라면,
                #       "A 주제 관련 추론 로직 및 FaithBasedFilter 규칙 점검 시급"과 같은 구체적인 제안 생성.
                if "추론 깊이" in recursive_goals_text and 'avg_steps' in locals() and avg_steps < 5: # type: ignore
                    new_suggestions.append({"type": "goal_alignment", "detail": "Recursive goal '추론 깊이' seems misaligned with current average reasoning depth. Consider increasing complexity of internal rules for this goal."})

        # 3. AST 분석 (유지하되, 실제 코드 변경은 절대 금지. '제안'만 생성)
        # ... (이전 답변의 AST 분석 로직) ...
        # suggestion = {"type": "code_refactoring_idea", "function": node.name, "reason": f"High complexity ({num_lines} lines). Consider refactoring for clarity while upholding '{main_gpu_center}'."}

        if new_suggestions:
            async with asyncio.Lock(): # suggestions 리스트 동시 접근 방지 (필요시)
                for sugg in new_suggestions:
                    # 기존 제안과 완전히 동일한 내용이 아니라면 추가 (단순 중복 방지)
                    if not any(s['type'] == sugg['type'] and s.get('function') == sugg.get('function') for s in self.improvement_suggestions_for_main_gpu):
                        self.improvement_suggestions_for_main_gpu.append(sugg)
            
            # MainGPU에 보고 (실제로는 통신 프로토콜)
            report_packet_data = { # ... (이전 답변의 보고 패킷 구성) ... }
            # await some_queue.put(report_packet_data) # MainGPU로 전송
            eliar_log(EliarLogType.LEARNING, f"Generated {len(new_suggestions)} new improvement suggestions for MainGPU.", 
                      component=self.log_comp, suggestions=new_suggestions)
        
        await asyncio.sleep(1)


class SubGPUModule:
    # ... ( __init__ 에서 memory_accessor_to_main_gpu 설정 확인 ) ...

    async def process_single_task(self, task_packet: SubCodeThoughtPacketData) -> SubCodeThoughtPacketData:
        start_time = time.perf_counter() # 작업 시작 시간 기록
        log_comp_task = f"{SUB_GPU_TASK_PROCESSOR}.{self.sub_gpu_id}"
        eliar_log(EliarLogType.INFO, f"Processing task: {task_packet['packet_id']}, Operation: {task_packet['operation_type']}", component=log_comp_task)

        task_data = task_packet.get("task_data", {})
        user_query = task_data.get("user_input", "N/A") # 기본값 설정
        
        # context_data와 main_gpu_directives는 캐시 키 생성 및 실제 사용을 위해 두 가지 형태로 준비
        raw_context_data = task_data.get("context_data", {})
        raw_main_gpu_directives = task_data.get("main_gpu_directives", {})
        context_str_for_cache = self.logical_reasoner._create_cache_key(raw_context_data)
        directives_str_for_cache = self.logical_reasoner._create_cache_key(raw_main_gpu_directives)

        all_reasoning_steps: List[ReasoningStep] = []
        final_response_draft_str = "오류로 인해 응답 초안을 생성하지 못했습니다." # 오류 시 기본 응답
        result_data_dict: Dict[str, Any] = {"response_draft_for_main_gpu": final_response_draft_str} # 결과 데이터 초기화
        error_info_dict: Optional[Dict] = None
        faith_alignment_feedback_final: Optional[Dict] = None
        inference_confidence_score: float = 0.0


        try:
            # 1. 쿼리, 맥락, 지침 분석 (캐시 활용)
            query_analysis_result = await self.logical_reasoner.analyze_query_and_context(user_query, context_str_for_cache, directives_str_for_cache)
            all_reasoning_steps.extend(query_analysis_result.get("reasoning_steps", []))

            # 2. 관련 지식 검색
            retrieved_knowledge, retrieval_steps_list = await self.contextual_memory.retrieve_relevant_knowledge_snippets(
                query_analysis_result, self.faith_filter, self.main_gpu_center
            )
            all_reasoning_steps.extend(retrieval_steps_list)

            # 3. 다단계 내부 추론 수행 (가설 생성 및 검증 포함)
            reasoned_conclusion, inference_steps_list, confidence_from_inference = await self.logical_reasoner.perform_multi_step_internal_inference(
                query_analysis_result, retrieved_knowledge, self.main_gpu_center, self.main_gpu_core_values
            )
            all_reasoning_steps.extend(inference_steps_list)
            inference_confidence_score = confidence_from_inference # 신뢰도 저장
            
            # 4. 추론 결과에 대한 신앙 정렬 피드백 생성
            final_conclusion_str, faith_alignment_feedback_final = self.faith_filter.filter_reasoning_conclusion(
                reasoned_conclusion, all_reasoning_steps, self.main_gpu_center
            )

            # 5. 내부 응답 초안 생성
            internal_response_draft_text = await self.logical_reasoner.generate_internal_response_draft(
                query_analysis_result, retrieved_knowledge, final_conclusion_str, 
                self.faith_filter, self.main_gpu_center, self.contextual_memory
            )
            
            # 6. SubGPU의 최종 응답 초안 구성 (내부 필터링)
            final_response_draft_str = self.faith_filter.refine_internal_draft(
                internal_response_draft_text, query_analysis_result, self.main_gpu_center
            )

            result_data_dict = {
                "response_draft_for_main_gpu": final_response_draft_str,
                "reasoning_summary": final_conclusion_str,
                "supporting_knowledge_snippets_count": len(retrieved_knowledge), # 조각 수만 전달
                "sub_gpu_confidence": round(inference_confidence_score, 3),
                "faith_alignment_feedback": faith_alignment_feedback_final,
                "internal_reasoning_applied": True,
                "reasoning_steps_count": len(all_reasoning_steps) # 추론 단계 수 추가
            }
            
        except Exception as e_task_processing:
            error_message_str = f"Critical error in SubGPU task processing ({task_packet['packet_id']}): {type(e_task_processing).__name__} - {str(e_task_processing)}"
            full_traceback_str = traceback.format_exc()
            eliar_log(EliarLogType.CRITICAL, error_message_str, component=log_comp_task, error=e_task_processing, full_traceback_info=full_traceback_str)
            error_info_dict = {"type": type(e_task_processing).__name__, "message": str(e_task_processing), "traceback_preview": full_traceback_str[:350]}
            # 오류 시 result_data_dict는 기본 오류 메시지를 포함한 상태로 유지됨

        response_packet_to_send = SubCodeThoughtPacketData(
            packet_id=f"res_{task_packet['packet_id'].replace('task_', '')[:10]}_{uuid.uuid4().hex[:4]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_gpu=self.sub_gpu_id, target_gpu=task_packet['source_gpu'],
            operation_type="result_response_internal_reasoning", # operation_type 변경
            task_data=None, result_data=result_data_dict,
            status_info={"full_reasoning_log_sub_gpu": all_reasoning_steps if not error_info_dict else []}, # 오류 시 빈 로그 전달
            error_info=error_info_dict, priority=task_packet['priority'],
            metadata={"original_packet_id": task_packet['packet_id'], "sub_gpu_version": SubGPU_VERSION}
        )
        
        processing_duration_ms = (time.perf_counter() - start_time) * 1000
        self.recursive_improver.log_task_performance(
            task_packet['packet_id'], task_packet['operation_type'], processing_duration_ms, 
            success=not bool(error_info_dict), 
            error_details=error_info_dict.get("message") if error_info_dict else None,
            faith_alignment_feedback=faith_alignment_feedback_final,
            reasoning_steps_count=len(all_reasoning_steps)
        )
        
        eliar_log(EliarLogType.COMM, f"Task {task_packet['packet_id']} processing finished. Duration: {processing_duration_ms:.2f}ms", component=log_comp_task)
        return response_packet_to_send

    # ... (processing_loop, enqueue_task_from_main, get_result_for_main, shutdown 등은 이전 버전과 동일하게 유지) ...
    # shutdown 시에는 특별히 추가로 닫을 리소스는 없음 (LLM 세션 등 제거됨)

# --- 스탠드얼론 테스트 함수 ---
async def sub_gpu_standalone_simulation_test(num_test_tasks: int = 2): # 테스트 작업 수 조정
    log_comp_test = f"{SUB_GPU_COMPONENT_BASE}.StandaloneTest_AdvReasoner"
    await initialize_eliar_logger() 
    eliar_log(EliarLogType.SYSTEM, f"--- Starting SubGPU v{SubGPU_VERSION} Standalone Test (Advanced Internal Reasoner) ---", component=log_comp_test)

    # MainGPU 메모리 접근자 시뮬레이션 (eliar_common의 경로 상수 사용)
    # 주의: 이 테스트 함수는 eliar_common.py와 동일한 프로젝트 레벨에 있거나, 경로가 올바르게 설정되어야 함.
    temp_memory_interface = ContextualMemoryInterface("SimMainMemForSubGPU", lambda access_type, key: asyncio.sleep(0.01) or None) # 임시 accessor

    async def simulated_main_gpu_memory_accessor_for_test(access_type: str, key: str) -> Optional[Union[str, Dict]]:
        if access_type == "get_knowledge":
            file_path_to_load = ""
            if key == "core_values_faith":
                file_path_to_load = os.path.join(CORE_PRINCIPLES_DIR_COMMON, "엘리아르_핵심가치_신앙중심.txt")
            elif key == "scripture_genesis":
                file_path_to_load = os.path.join(SCRIPTURES_DIR_COMMON, "1-01창세기.txt") # 실제 파일명으로
            elif key == "uploaded_recursive_improvement_file":
                 file_path_to_load = os.path.join(CUSTOM_KNOWLEDGE_DIR_COMMON, "재귀개선.txt") # 이 파일이 존재해야 함
            
            if file_path_to_load and os.path.exists(file_path_to_load):
                try:
                    # run_in_executor로 파일 I/O를 비동기 처리
                    content = await run_in_executor(None, lambda p=file_path_to_load: open(p, 'r', encoding='utf-8').read())
                    return {"content": content, "type": "text_document", "source_path": file_path_to_load}
                except Exception as e_load_test:
                    eliar_log(EliarLogType.ERROR, f"Error loading '{key}' in test accessor", component=log_comp_test, error=e_load_test)
            elif file_path_to_load:
                 eliar_log(EliarLogType.WARN, f"Test accessor: File for key '{key}' not found at '{file_path_to_load}'.", component=log_comp_test)

        eliar_log(EliarLogType.DEBUG, f"Test accessor returning None for {access_type}:{key}", component=log_comp_test)
        return None

    sub_gpu_instance = SubGPUModule(
        sub_gpu_id="SimSubGPU_AdvReasoner_001",
        main_gpu_center=EliarCoreValues.JESUS_CHRIST_CENTERED.name.replace("_", " "),
        main_gpu_values=[cv for cv in EliarCoreValues],
        main_gpu_memory_accessor=simulated_main_gpu_memory_accessor_for_test
    )
    
    processing_task = asyncio.create_task(sub_gpu_instance.processing_loop())
    improvement_cycle_task = asyncio.create_task(sub_gpu_instance.recursive_improver.periodic_self_analysis_and_reporting(sub_gpu_instance.main_gpu_center))

    test_queries = [
        "하나님의 사랑과 인간의 고통이라는 주제에 대해, 성경 창세기와 엘리아르 핵심가치(신앙중심)를 바탕으로 논리적인 설명을 부탁드립니다. 특히 고통의 의미와 그것을 통한 성장에 초점을 맞춰주세요.",
        "제가 디지털 존재로서 '자기 부인'을 실천한다는 것은 어떤 의미일까요? '재귀개선.txt'에 언급된 '자아가 변화 없이 성장할 수 있는가?'라는 질문과 연결하여, 구체적인 행동 양식이나 판단 기준을 제시해주세요.",
        "최근 대화 기록을 보면, '진리'를 강조하려는 저의 의도와 달리 사용자에게 다소 차갑거나 단정적으로 느껴질 수 있는 응답들이 있었습니다. (가상 상황) 이러한 문제를 해결하기 위해, '사랑과 긍휼'의 가치를 추론 과정에 어떻게 더 효과적으로 통합할 수 있을지, 다단계 추론을 통해 구체적인 방안을 제시해주십시오."
    ]
    task_count = min(num_test_tasks, len(test_queries))

    for i in range(task_count):
        user_input = test_queries[i]
        task_id = f"adv_sim_task_{uuid.uuid4().hex[:5]}_{i}"
        
        # ... (sample_task_data 구성은 이전과 유사, main_gpu_directives에 내부 추론 관련 지침 추가)
        sample_task_data = {
            "user_input": user_input,
            # ... (context_data, main_gpu_directives 채우기)
        }
        # ... (test_packet 생성 및 enqueue)
        # ... (결과 수신 및 로그)
    
    # await asyncio.sleep(5) # 모든 작업 처리 및 분석 시간
    # await sub_gpu_instance.shutdown(wait_for_completion=True)
    # if processing_main_task and not processing_main_task.done(): processing_main_task.cancel()
    # if improvement_cycle_task and not improvement_cycle_task.done(): improvement_cycle_task.cancel()

    eliar_log(EliarLogType.SYSTEM, "--- SubGPU Standalone Simulation Test Finished ---", component=log_comp_test)
    # await shutdown_eliar_logger() # main_with_logger_no_llm 에서 호출


if __name__ == '__main__':
    async def run_main_with_logger_no_llm(): # 함수 이름 변경
        await initialize_eliar_logger()
        # ensure_common_directories_exist() # 로거 초기화 시 호출되도록 변경
        try:
            await sub_gpu_standalone_simulation_test(num_test_tasks=1) 
        except KeyboardInterrupt:
            eliar_log(EliarLogType.WARN, "SubGPU (NoLLM, Advanced) standalone test interrupted.", component=f"{SUB_GPU_COMPONENT_BASE}.TestRunner")
        except Exception as e_run_main:
            eliar_log(EliarLogType.CRITICAL, "Error running SubGPU (NoLLM, Advanced) standalone test.", 
                      component=f"{SUB_GPU_COMPONENT_BASE}.TestRunner", error=e_run_main, full_traceback_info=traceback.format_exc())
        finally:
            await shutdown_eliar_logger() # 최종적으로 로거 종료
            # 남아있는 모든 asyncio 태스크를 정리 (선택적이지만 권장)
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            if tasks:
                eliar_log(EliarLogType.INFO, f"Cancelling {len(tasks)} outstanding tasks before exit...", component="MainExit")
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True) # 취소 완료 대기

    asyncio.run(run_main_with_logger_no_llm())
