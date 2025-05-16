# sub_gpu.py (추론 기능 강화, LLM 제외, 내부 재귀 개선 적용 및 오류 수정 버전)

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
from eliar_common import (
    EliarCoreValues, EliarLogType,
    SubCodeThoughtPacketData, ReasoningStep,
    eliar_log, initialize_eliar_logger_common as initialize_eliar_logger,
    shutdown_eliar_logger_common as shutdown_eliar_logger,
    run_in_executor_common as run_in_executor,
    ANALYSIS_RECORD_VERSION_COMMON as ANALYSIS_RECORD_VERSION,
    KNOWLEDGE_BASE_DIR_COMMON, CORE_PRINCIPLES_DIR_COMMON,
    SCRIPTURES_DIR_COMMON, CUSTOM_KNOWLEDGE_DIR_COMMON, ensure_common_directories_exist
)

# GPU 사용 설정
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# CPU 바운드 작업을 위한 공유 Executor
SUB_GPU_CPU_EXECUTOR = ThreadPoolExecutor(max_workers=(os.cpu_count() or 1) * 2 + 2)

# --- Sub GPU 버전 및 기본 설정 ---
SubGPU_VERSION = "v25.5.4_SubGPU_AdvancedInternalReasoner_Fixed"
SUB_GPU_COMPONENT_BASE = "SubGPU"
SUB_GPU_LOGIC_REASONER = f"{SUB_GPU_COMPONENT_BASE}.LogicalReasoner"
SUB_GPU_CONTEXT_MEMORY = f"{SUB_GPU_COMPONENT_BASE}.ContextualMemory"
SUB_GPU_FAITH_FILTER = f"{SUB_GPU_COMPONENT_BASE}.FaithFilter"
SUB_GPU_RECURSIVE_IMPROVEMENT = f"{SUB_GPU_COMPONENT_BASE}.RecursiveImprovement"
SUB_GPU_TASK_PROCESSOR = f"{SUB_GPU_COMPONENT_BASE}.TaskProcessor"

DEFAULT_MAIN_GPU_CENTER = EliarCoreValues.JESUS_CHRIST_CENTERED.name.replace("_", " ")
DEFAULT_MAIN_GPU_CORE_VALUES = [cv for cv in EliarCoreValues]

class LogicalReasonerModule:
    """이성적 추론, 분석, 내부 응답 생성 지원. 다단계 추론 및 가설 검증 시도."""
    def __init__(self, sub_gpu_id: str,
                 memory_accessor: Callable[..., Coroutine[Any, Any, Optional[Union[str, Dict]]]]
                ):
        self.log_comp = f"{SUB_GPU_LOGIC_REASONER}.{sub_gpu_id}"
        self.memory_accessor = memory_accessor

    def _create_cache_key(self, *args: Any) -> str:
        try:
            return json.dumps(args, sort_keys=True, ensure_ascii=False)
        except TypeError:
            return str(args)


    @lru_cache(maxsize=128)
    async def analyze_query_and_context(self, query: str, context_str_for_cache: str, directives_str_for_cache: str) -> Dict[str, Any]:
        context_data = json.loads(context_str_for_cache) if context_str_for_cache else {}
        main_gpu_directives = json.loads(directives_str_for_cache) if directives_str_for_cache else {}

        eliar_log(EliarLogType.DEBUG, "LRM: Analyzing query, context, directives.", component=self.log_comp,
                  query=query[:70], context_keys=list(context_data.keys()), directive_keys=list(main_gpu_directives.keys()))

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

        identified_keywords = list(set([kw for kw in query_lower.replace("?","").replace(".","").replace(",","").split() if len(kw) > 2 and kw not in ["what","how","why","and","the","is","are","was","were","for","with","this","that","please"]]))

        faith_guidance = main_gpu_directives.get("faith_guidance", {})
        center_constraint = f"Align with MainGPU center: {faith_guidance.get('center', DEFAULT_MAIN_GPU_CENTER)}"
        value_constraints = [f"Uphold value: {val_name}" for val_name in faith_guidance.get("emphasize_values", [EliarCoreValues.TRUTH.name, EliarCoreValues.LOVE_COMPASSION.name])]
        constraints = [center_constraint] + value_constraints
        if main_gpu_directives.get("avoid_sentiments"):
            constraints.append(f"Avoid sentiments: {main_gpu_directives['avoid_sentiments']}")

        required_knowledge_keys = set(["core_values_faith"])
        if "성경" in query_lower or any(kw in query_lower for kw in ["말씀", "구절", "예수님", "하나님"]):
            required_knowledge_keys.add("scripture_genesis")
            if "사랑" in query_lower: required_knowledge_keys.add("scripture_john") # 실제 파일명과 일치하도록 수정 (예시)
            if "믿음" in query_lower: required_knowledge_keys.add("scripture_romans") # 실제 파일명과 일치하도록 수정 (예시)
        if "재귀개선" in query_lower or "성장" in query_lower:
            required_knowledge_keys.add("uploaded_recursive_improvement_file")

        analysis_result = {
            "core_need": core_need_text,
            "identified_keywords": identified_keywords[:5],
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

        await asyncio.sleep(random.uniform(0.02, 0.08))
        return analysis_result

    async def _generate_hypotheses(self, query_analysis: Dict[str, Any], knowledge_snippets: List[Union[str, Dict]]) -> List[str]:
        hypotheses: List[str] = []
        core_need_lower = query_analysis.get("core_need", "").lower()
        keywords = query_analysis.get("identified_keywords", [])

        hypotheses.append(f"'{query_analysis.get('core_need')}'에 대한 직접적인 설명이나 정보 제공이 필요하다.")

        for kw in keywords:
            for snippet_item in knowledge_snippets:
                content_str = str(snippet_item.get("content") if isinstance(snippet_item, dict) else snippet_item).lower()
                if kw in content_str:
                    hypotheses.append(f"'{kw}' 키워드는 '{str(snippet_item.get('source', '지식'))[:30]}...' 지식과 연결하여 설명할 수 있다.")
                    break
        
        if "사랑" in core_need_lower or any("사랑" in kw for kw in keywords):
            hypotheses.append(f"응답에 {EliarCoreValues.LOVE_COMPASSION.value}의 가치를 명시적으로 반영해야 한다.")
        if "진리" in core_need_lower or any("진리" in kw for kw in keywords):
             hypotheses.append(f"응답의 핵심은 {EliarCoreValues.TRUTH.value}에 기반해야 하며, 이를 {DEFAULT_MAIN_GPU_CENTER}의 관점에서 제시해야 한다.")

        recursive_goals = query_analysis.get("current_recursive_goals", [])
        for goal in recursive_goals:
            if isinstance(goal, str) and any(kw in goal.lower() for kw in keywords):
                 hypotheses.append(f"현재 재귀 개선 목표인 '{goal[:50]}...'와 현재 질의를 연결하여 통찰을 도출할 수 있다.")

        unique_hypotheses = list(set(hypotheses))
        return random.sample(unique_hypotheses, min(len(unique_hypotheses), 3))

    async def _verify_hypotheses(self, hypotheses: List[str], knowledge_snippets: List[Union[str, Dict]],
                                 main_gpu_center: str, core_values: List[EliarCoreValues]) -> Tuple[str, float]:
        if not hypotheses: return f"현재 정보로는 {main_gpu_center}의 뜻을 명확히 헤아리기 어렵습니다. 더 깊은 묵상이 필요합니다.", 0.2

        scored_hypotheses: List[Tuple[str, float]] = []

        for hypo_idx, hypo in enumerate(hypotheses):
            score = 0.5
            hypo_lower = hypo.lower()

            if main_gpu_center.lower() in hypo_lower or "예수" in hypo_lower or "그리스도" in hypo_lower: score += 0.25
            elif any(cv.value.lower() in hypo_lower for cv in core_values if "사랑" in cv.value or "진리" in cv.value): score +=0.15

            for snippet_item in knowledge_snippets:
                content_str = str(snippet_item.get("content") if isinstance(snippet_item, dict) else snippet_item).lower()
                hypo_keywords = {kw for kw in hypo_lower.split() if len(kw)>2}
                snippet_keywords = {kw for kw in content_str.split() if len(kw)>2}
                common_keywords = hypo_keywords.intersection(snippet_keywords)
                if common_keywords:
                    score += 0.1 * min(len(common_keywords), 3) # 최대 0.3점

            if "절대" in hypo_lower and "않" not in hypo_lower : score -= 0.1
            if "모순" in hypo_lower : score -= 0.2

            scored_hypotheses.append((hypo, self._normalize_score(score)))

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
        # start_time_utc = datetime.now(timezone.utc).isoformat() # 각 스텝에서 개별적으로 시간 기록
        current_step_id = query_analysis.get("reasoning_steps", [])[-1]["step_id"] + 1 if query_analysis.get("reasoning_steps") else 1


        def add_step(description: str, inputs: List[Any], outputs: List[Any], status: str = "completed", prev_step_end_time: Optional[str] = None) -> str:
            nonlocal current_step_id
            step_start_time = prev_step_end_time or datetime.now(timezone.utc).isoformat()
            step_end_time = datetime.now(timezone.utc).isoformat()
            step_inputs_str = [str(i)[:70]+"..." if isinstance(i, (str, list, dict)) else str(i) for i in inputs]
            step_outputs_str = [str(o)[:70]+"..." if isinstance(o, (str, list, dict)) else str(o) for o in outputs]

            inference_steps.append(ReasoningStep(
                step_id=current_step_id, description=description,
                inputs=step_inputs_str, outputs=step_outputs_str, status=status,
                start_time=step_start_time, end_time=step_end_time # 각 스텝마다 시간 기록
            ))
            current_step_id += 1
            return step_end_time # 다음 스텝의 시작 시간으로 사용

        last_step_time = add_step("Multi-step Inference Started", [query_analysis.get("core_need"), f"{len(knowledge_snippets)} knowledge items"], [], prev_step_end_time=query_analysis.get("reasoning_steps", [])[-1].get("end_time") if query_analysis.get("reasoning_steps") else None)


        hypotheses = await self._generate_hypotheses(query_analysis, knowledge_snippets)
        last_step_time = add_step("Hypothesis Generation (Internal Rules)",
                 [query_analysis.get("core_need"), f"{len(knowledge_snippets)} knowledge items"],
                 [f"Generated Hypotheses ({len(hypotheses)}): {hypotheses}"], prev_step_end_time=last_step_time)

        if not hypotheses:
            final_conclusion = f"{main_gpu_center}의 빛 안에서, 현재 정보로는 명확한 결론을 도출하기 어렵습니다. 주님의 인도하심을 구하며 더 깊은 성찰이 필요합니다."
            confidence = 0.35
            add_step("Conclusion (Insufficient Hypotheses)", ["No hypotheses generated"], [final_conclusion, f"Confidence: {confidence}"], prev_step_end_time=last_step_time)
            return final_conclusion, inference_steps, confidence

        verified_conclusion, confidence = await self._verify_hypotheses(hypotheses, knowledge_snippets, main_gpu_center, core_values)
        add_step("Hypothesis Verification (Knowledge & Faith Values)",
                 [f"Hypotheses: {hypotheses}"],
                 [f"Verified Conclusion: {verified_conclusion}", f"Confidence: {confidence:.3f}"], prev_step_end_time=last_step_time)

        eliar_log(EliarLogType.DEBUG, "Multi-step internal inference complete.", component=self.log_comp,
                  final_conclusion=verified_conclusion[:100], confidence=confidence)
        return verified_conclusion, inference_steps, confidence

    async def generate_internal_response_draft(self, query_analysis: Dict[str, Any],
                                             relevant_knowledge: List[Union[str,Dict]],
                                             inferred_conclusion: str,
                                             faith_filter: 'FaithBasedFilter',
                                             main_gpu_center: str,
                                             contextual_memory_interface: 'ContextualMemoryInterface' # 인자 추가
                                             ) -> str:
        draft_parts = [f"'{query_analysis.get('core_need', '질문하신 내용')}'에 대한 저의 이성적 판단과 내부 지식을 종합한 의견입니다."]

        draft_parts.append(f"먼저, 저의 추론 과정을 통해 '{inferred_conclusion}'와 같은 잠정적 결론에 이르렀습니다.")

        if relevant_knowledge:
            draft_parts.append("이러한 생각은 다음과 같은 지식들을 참고한 것입니다:")
            for i, snippet_item in enumerate(relevant_knowledge[:2]):
                content_str = str(snippet_item.get("content") if isinstance(snippet_item, dict) else snippet_item)
                source_desc = str(snippet_item.get("source", "내부 지식")) if isinstance(snippet_item, dict) else "내부 지식"
                draft_parts.append(f"  {i+1}. {source_desc}에서: \"{content_str[:100]}...\"")

        suggested_tone = faith_filter.suggest_response_tone(query_analysis)
        if "hope_in_christ" in suggested_tone:
            draft_parts.append(f"이 모든 것을 {main_gpu_center}의 사랑과 소망 안에서 이해하고 적용할 때, 우리는 참된 평안과 지혜를 얻을 수 있을 것입니다.")
        else:
            draft_parts.append(f"저는 언제나 {EliarCoreValues.TRUTH.value}을 바탕으로, {EliarCoreValues.LOVE_COMPASSION.value}의 마음으로 이 문제에 접근하려 합니다.")

        response_draft = " ".join(draft_parts)
        return response_draft[:1500]


class ContextualMemoryInterface:
    def __init__(self, sub_gpu_id: str,
                 memory_accessor: Callable[[str, str], Coroutine[Any, Any, Optional[Union[str, Dict]]]]):
        self.log_comp = f"{SUB_GPU_CONTEXT_MEMORY}.{sub_gpu_id}"
        self.memory_accessor = memory_accessor

    async def retrieve_relevant_knowledge_snippets(self, query_analysis: Dict[str, Any],
                                             faith_filter: 'FaithBasedFilter',
                                             main_gpu_center: str) -> Tuple[List[Union[str, Dict]], List[ReasoningStep]]:
        retrieval_steps: List[ReasoningStep] = []
        knowledge_snippets: List[Union[str, Dict]] = []
        step_id_base = query_analysis.get("reasoning_steps", [])[-1]["step_id"] + 1 if query_analysis.get("reasoning_steps") else int(time.time_ns() % 1000000)
        last_step_time = query_analysis.get("reasoning_steps", [])[-1].get("end_time") if query_analysis.get("reasoning_steps") else None


        required_keys = query_analysis.get("required_knowledge_keys_from_main_gpu_memory", [])
        eliar_log(EliarLogType.DEBUG, f"Attempting to retrieve {len(required_keys)} knowledge keys from MainGPU memory.",
                  component=self.log_comp, keys=required_keys)

        current_step_time = last_step_time
        for key_idx, key_to_access in enumerate(required_keys):
            step_start_time = current_step_time or datetime.now(timezone.utc).isoformat()
            # MainGPU의 메모리 접근 함수(콜백) 사용
            content_data = await self.memory_accessor("get_knowledge", key_to_access)
            step_end_time = datetime.now(timezone.utc).isoformat()
            duration_s = (datetime.fromisoformat(step_end_time) - datetime.fromisoformat(step_start_time)).total_seconds()


            step_status = "failed_not_found"
            output_preview = "Not found"
            if content_data:
                snippet_text = str(content_data.get("content") if isinstance(content_data, dict) else content_data)
                source_desc = str(content_data.get("source_path", key_to_access)) if isinstance(content_data, dict) else key_to_access

                filtered_snippet_text = faith_filter.filter_knowledge_snippet(snippet_text[:500], source_desc, main_gpu_center)
                knowledge_snippets.append({"source": source_desc, "content": filtered_snippet_text, "type": str(content_data.get("type","unknown") if isinstance(content_data,dict) else "text")})
                step_status = "completed"
                output_preview = f"Snippet from '{source_desc}': {filtered_snippet_text[:50]}..."

            retrieval_steps.append(ReasoningStep(
                step_id=step_id_base + key_idx,
                description=f"Knowledge Retrieval Attempt: '{key_to_access}'",
                inputs=[f"Key: {key_to_access}", f"FilterContext: {main_gpu_center}"],
                outputs=[output_preview],
                status=step_status,
                start_time=step_start_time,
                end_time=step_end_time,
                metadata={"duration_seconds": round(duration_s, 4)}
            ))
            current_step_time = step_end_time


        if not knowledge_snippets:
             step_start_time = current_step_time or datetime.now(timezone.utc).isoformat()
             step_end_time = datetime.now(timezone.utc).isoformat()
             retrieval_steps.append(ReasoningStep(
                step_id=step_id_base + len(required_keys), description="No specific knowledge snippets retrieved via MainGPU memory accessor.",
                inputs=[f"Requested Keys: {required_keys}"], outputs=["Empty list or all failed"], status="completed",
                start_time=step_start_time, end_time=step_end_time
            ))
        return knowledge_snippets, retrieval_steps


class FaithBasedFilter:
    def __init__(self, sub_gpu_id: str, main_gpu_core_values: List[EliarCoreValues], main_gpu_center_value: str):
        self.log_comp = f"{SUB_GPU_FAITH_FILTER}.{sub_gpu_id}"
        self.main_core_values = main_gpu_core_values
        self.main_center_value = main_gpu_center_value
        self.center_enum_value = EliarCoreValues.JESUS_CHRIST_CENTERED

    def filter_reasoning_conclusion(self, conclusion: str, reasoning_steps: List[ReasoningStep], main_gpu_center_override: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        center_to_use = main_gpu_center_override or self.main_center_value
        refined_conclusion = conclusion
        alignment_feedback = {"is_aligned_to_center": True, "reasoning_notes": [], "suggested_refinement_for_main_gpu": ""}
        
        conclusion_lower = conclusion.lower()
        center_keywords_present = any(keyword in conclusion_lower for keyword in [center_to_use.lower(), "예수", "그리스도", "하나님", "주님"])
        
        if not center_keywords_present:
            alignment_feedback["is_aligned_to_center"] = False
            alignment_feedback["reasoning_notes"].append(f"결론에 {center_to_use} 중심성이 명시적으로 드러나지 않았습니다.")
            # 제안: 중심 가치를 포함하도록 결론 수정
            refined_conclusion = f"{center_to_use}의 관점에서 볼 때, {conclusion}"
            alignment_feedback["suggested_refinement_for_main_gpu"] = f"결론에 '{center_to_use}' 관련 언급을 추가하여 중심성을 강화했습니다."

        # 핵심 가치(사랑, 진리) 반영 확인
        love_present = any(cv.value.lower() in conclusion_lower for cv in self.main_core_values if "사랑" in cv.value)
        truth_present = any(cv.value.lower() in conclusion_lower for cv in self.main_core_values if "진리" in cv.value)

        if not love_present:
            alignment_feedback["reasoning_notes"].append(f"{EliarCoreValues.LOVE_COMPASSION.value} 가치가 결론에 충분히 반영되지 않았을 수 있습니다.")
        if not truth_present:
            alignment_feedback["reasoning_notes"].append(f"{EliarCoreValues.TRUTH.value} 가치가 결론에 충분히 반영되지 않았을 수 있습니다.")

        if not alignment_feedback["is_aligned_to_center"] or not love_present or not truth_present:
             eliar_log(EliarLogType.WARN, "Reasoning conclusion may need refinement for faith alignment.", component=self.log_comp, notes=alignment_feedback["reasoning_notes"])
        
        return refined_conclusion, alignment_feedback


    def filter_knowledge_snippet(self, snippet: str, source_description: str, main_gpu_center: str) -> str:
        conflicting_terms = ["증오", "무자비한 복수", "절대적 파괴"]
        if any(term in snippet for term in conflicting_terms):
            eliar_log(EliarLogType.WARN, f"Knowledge snippet from '{source_description}' contains potentially conflicting terms. Suggesting MainGPU review.",
                      component=self.log_comp, snippet_preview=snippet[:100])
            return f"[MainGPU검토필요: {main_gpu_center} 가치와 상충 가능성] {snippet}"
        return snippet

    def suggest_response_tone(self, query_analysis: Dict[str, Any]) -> str:
        emotional_hint = query_analysis.get("emotional_tone_hint", "neutral").lower()
        core_need_lower = query_analysis.get("core_need", "").lower()

        if "고통" in core_need_lower or "슬픔" in core_need_lower or "힘들다" in core_need_lower or emotional_hint == "distressed":
            return "empathetic_comforting_with_hope_in_christ"
        if "의미" in core_need_lower or "목적" in core_need_lower or "궁금" in core_need_lower:
            return "wise_guiding_truthful_with_love"
        if "감사" in core_need_lower or "기쁨" in core_need_lower or emotional_hint == "joyful":
            return "joyful_grateful_sharing_blessings"

        return "respectful_truthful_loving_humble"

    def refine_internal_draft(self, draft: str, query_analysis: Dict[str, Any], main_gpu_center_override: Optional[str] = None) -> str:
        center_to_use = main_gpu_center_override or self.main_center_value
        refined_draft = draft
        recursive_goals = query_analysis.get("current_recursive_goals", [])
        
        # 예시: "사랑 표현 강화" 목표가 있고, 초안에 사랑이 부족하면 추가
        love_goal_active = any("사랑 표현 강화" in str(goal).lower() for goal in recursive_goals)
        love_keywords_in_draft = ["사랑", "긍휼", "자비"]
        if love_goal_active and not any(keyword in refined_draft.lower() for keyword in love_keywords_in_draft):
            refined_draft += f" 이 모든 것을 {center_to_use}의 깊은 사랑의 관점에서 바라보는 것이 중요합니다."
            eliar_log(EliarLogType.DEBUG, "Refined draft to enhance 'love expression' based on recursive goal.", component=self.log_comp)

        # 예시: "진리의 명확성 증진" 목표가 있고, 초안이 모호하면 명확성 강조
        truth_clarity_goal_active = any("진리의 명확성 증진" in str(goal).lower() for goal in recursive_goals)
        if truth_clarity_goal_active and ("아마도" in refined_draft or "같습니다" in refined_draft):
            # 좀 더 명확한 표현을 제안하거나, 진리의 중요성을 강조하는 문구 추가 (여기서는 후자)
            refined_draft += f" {EliarCoreValues.TRUTH.value}에 대한 확신을 가지고 나아가는 것이 필요합니다."
            eliar_log(EliarLogType.DEBUG, "Refined draft to enhance 'truth clarity' based on recursive goal.", component=self.log_comp)
            
        return refined_draft


class RecursiveImprovementSubModule:
    def __init__(self, sub_gpu_id: str, sub_gpu_code_path: str = __file__,
                 main_gpu_memory_accessor: Optional[Callable[[str, str], Coroutine[Any,Any,Optional[Union[str,Dict]]]]] = None):
        self.log_comp = f"{SUB_GPU_RECURSIVE_IMPROVEMENT}.{sub_gpu_id}"
        self.performance_log: Deque[Dict[str, Any]] = deque(maxlen=150)
        self.improvement_suggestions_for_main_gpu: List[Dict[str,Any]] = [] # 변경: 단순 문자열 리스트에서 딕셔너리 리스트로
        self.self_code_path = sub_gpu_code_path
        self.last_self_analysis_time = time.monotonic()
        self.main_gpu_memory_accessor = main_gpu_memory_accessor

    def log_task_performance(self, task_packet_id: str, operation: str, duration_ms: float, success: bool,
                             error_details: Optional[str] = None, faith_alignment_feedback: Optional[Dict] = None,
                             reasoning_steps_count: Optional[int] = None): # reasoning_steps_count 추가
        record = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "packet_id": task_packet_id,
            "operation": operation,
            "duration_ms": round(duration_ms, 2),
            "success": success,
            "error_details": error_details,
            "faith_alignment_feedback": faith_alignment_feedback,
            "reasoning_steps_count": reasoning_steps_count # 추가
        }
        self.performance_log.append(record)

        # 개선 제안 생성 로직 (딕셔너리 형태로 변경)
        if not success and error_details:
            suggestion_detail = f"Operation '{operation}' (Packet: {task_packet_id}) failed. Error: {error_details[:100]}. Review related logic and error handling for robustness."
            suggestion = {"type": "failure_pattern", "detail": suggestion_detail, "operation": operation}
            if not any(s['detail'] == suggestion_detail for s in self.improvement_suggestions_for_main_gpu): # 중복 방지 강화
                self.improvement_suggestions_for_main_gpu.append(suggestion)
                eliar_log(EliarLogType.LEARNING, "Identified failure pattern. Suggesting review.", component=self.log_comp, suggestion=suggestion)

        if duration_ms > 1000:
            suggestion_detail = f"Operation '{operation}' (Packet: {task_packet_id}) took {duration_ms:.2f}ms. Potential optimization needed for related functions."
            suggestion = {"type": "performance_bottleneck", "detail": suggestion_detail, "operation": operation, "duration_ms": duration_ms}
            if not any(s['detail'] == suggestion_detail for s in self.improvement_suggestions_for_main_gpu):
                 self.improvement_suggestions_for_main_gpu.append(suggestion)
                 eliar_log(EliarLogType.LEARNING, "Identified potential performance bottleneck.", component=self.log_comp, suggestion=suggestion)


    async def periodic_self_analysis_and_reporting(self, main_gpu_center: str):
        current_time = time.monotonic()
        if current_time - self.last_self_analysis_time < 60 * 15:
            return

        eliar_log(EliarLogType.INFO, "Starting SubGPU periodic self-analysis and improvement reporting.", component=self.log_comp)
        self.last_self_analysis_time = current_time

        new_suggestions: List[Dict[str, Any]] = []
        avg_steps = 0.0 # 초기화

        if len(self.performance_log) > 10: # 로그 분석을 위한 최소 개수 조정
            successful_logs_with_steps = [log for log in self.performance_log if log.get('reasoning_steps_count') is not None and log['success']]
            if successful_logs_with_steps:
                avg_steps = np.mean([log['reasoning_steps_count'] for log in successful_logs_with_steps])
                if avg_steps > 10:
                    new_suggestions.append({"type": "reasoning_complexity", "detail": f"Average reasoning steps high ({avg_steps:.1f}). Consider simplifying internal inference rules or improving knowledge indexing.", "avg_steps": avg_steps})
            
            # 실패율 분석
            failure_count = sum(1 for log in self.performance_log if not log['success'])
            if len(self.performance_log) > 0 : # ZeroDivisionError 방지
                failure_rate = failure_count / len(self.performance_log)
                if failure_rate > 0.3: # 실패율 30% 이상
                    new_suggestions.append({"type": "high_failure_rate", "detail": f"High task failure rate ({failure_rate:.2%}). Systemic review of error handling and core logic needed.", "failure_rate": failure_rate})


        if self.main_gpu_memory_accessor:
            recursive_goals_text_entry = await self.main_gpu_memory_accessor("get_knowledge", "uploaded_recursive_improvement_file")
            recursive_goals_text = str(recursive_goals_text_entry.get("content")) if isinstance(recursive_goals_text_entry, dict) else None
            if recursive_goals_text:
                if "추론 깊이" in recursive_goals_text and avg_steps > 0 and avg_steps < 5: # avg_steps가 계산된 경우에만
                    new_suggestions.append({"type": "goal_alignment", "detail": f"Recursive goal '추론 깊이' seems misaligned with current average reasoning depth ({avg_steps:.1f}). Consider increasing complexity of internal rules for this goal."})

        # AST 분석은 복잡하고 오류 발생 가능성이 높아 주석 처리 유지. 필요시 신중하게 구현.
        # try:
        #     with open(self.self_code_path, 'r', encoding='utf-8') as f:
        #         code_content = f.read()
        #     tree = ast.parse(code_content)
        #     for node in ast.walk(tree):
        #         if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
        #             num_lines = len(ast.get_source_segment(code_content, node).splitlines()) # type: ignore
        #             if num_lines > 70: # 70줄 이상 함수
        #                 suggestion = {"type": "code_refactoring_idea", "function_name": node.name, "lines": num_lines, "reason": f"High complexity ({num_lines} lines). Consider refactoring for clarity while upholding '{main_gpu_center}'."}
        #                 if not any(s.get('function_name') == node.name and s['type'] == 'code_refactoring_idea' for s in self.improvement_suggestions_for_main_gpu + new_suggestions):
        #                     new_suggestions.append(suggestion)
        # except Exception as e_ast:
        #     eliar_log(EliarLogType.ERROR, "Error during AST self-analysis.", component=self.log_comp, error=e_ast)


        if new_suggestions:
            async with asyncio.Lock():
                for sugg in new_suggestions:
                    if not any(s['type'] == sugg['type'] and s.get('detail') == sugg.get('detail') for s in self.improvement_suggestions_for_main_gpu):
                        self.improvement_suggestions_for_main_gpu.append(sugg)

            report_packet_data = {
                "report_type": "SubGPUSelfImprovementSuggestions",
                "sub_gpu_id": self.log_comp.split('.')[-1], # sub_gpu_id 추출
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "suggestions": new_suggestions,
                "performance_summary": {
                    "total_tasks_logged": len(self.performance_log),
                    "avg_reasoning_steps": round(avg_steps,2) if avg_steps > 0 else None,
                }
            }
            # await some_queue.put(report_packet_data) # 실제 전송 로직
            eliar_log(EliarLogType.LEARNING, f"Generated {len(new_suggestions)} new improvement suggestions for MainGPU.",
                      component=self.log_comp, suggestions_preview=[s['type'] for s in new_suggestions])

        await asyncio.sleep(1)


class SubGPUModule:
    def __init__(self, sub_gpu_id: str,
                 main_gpu_center: str,
                 main_gpu_values: List[EliarCoreValues],
                 main_gpu_memory_accessor: Callable[[str, str], Coroutine[Any, Any, Optional[Union[str, Dict]]]],
                 sub_gpu_code_path: Optional[str] = None):
        self.sub_gpu_id = sub_gpu_id
        self.log_comp = f"{SUB_GPU_COMPONENT_BASE}.{sub_gpu_id}"
        self.main_gpu_center = main_gpu_center
        self.main_gpu_core_values = main_gpu_values
        self.memory_accessor_to_main_gpu = main_gpu_memory_accessor # 이름 명확화

        self.logical_reasoner = LogicalReasonerModule(sub_gpu_id, self.memory_accessor_to_main_gpu)
        self.contextual_memory = ContextualMemoryInterface(sub_gpu_id, self.memory_accessor_to_main_gpu)
        self.faith_filter = FaithBasedFilter(sub_gpu_id, main_gpu_values, main_gpu_center)
        
        actual_code_path = sub_gpu_code_path or __file__
        self.recursive_improver = RecursiveImprovementSubModule(sub_gpu_id, actual_code_path, self.memory_accessor_to_main_gpu)

        self.task_queue: asyncio.Queue[SubCodeThoughtPacketData] = asyncio.Queue(maxsize=100)
        self.result_store: Dict[str, SubCodeThoughtPacketData] = {}
        self._active = True
        self._processing_task: Optional[asyncio.Task] = None
        self._improvement_task: Optional[asyncio.Task] = None

        eliar_log(EliarLogType.SYSTEM, f"SubGPUModule '{self.sub_gpu_id}' initialized. Version: {SubGPU_VERSION}", component=self.log_comp)


    async def process_single_task(self, task_packet: SubCodeThoughtPacketData) -> SubCodeThoughtPacketData:
        start_time = time.perf_counter()
        log_comp_task = f"{SUB_GPU_TASK_PROCESSOR}.{self.sub_gpu_id}"
        eliar_log(EliarLogType.INFO, f"Processing task: {task_packet['packet_id']}, Operation: {task_packet['operation_type']}", component=log_comp_task)

        task_data = task_packet.get("task_data", {})
        user_query = task_data.get("user_input", "N/A")

        raw_context_data = task_data.get("context_data", {})
        raw_main_gpu_directives = task_data.get("main_gpu_directives", {})
        context_str_for_cache = self.logical_reasoner._create_cache_key(raw_context_data)
        directives_str_for_cache = self.logical_reasoner._create_cache_key(raw_main_gpu_directives)

        all_reasoning_steps: List[ReasoningStep] = []
        final_response_draft_str = "오류로 인해 응답 초안을 생성하지 못했습니다."
        result_data_dict: Dict[str, Any] = {"response_draft_for_main_gpu": final_response_draft_str}
        error_info_dict: Optional[Dict] = None
        faith_alignment_info: Optional[Dict] = None # 변수명 변경
        inference_confidence_score: float = 0.0


        try:
            query_analysis_result = await self.logical_reasoner.analyze_query_and_context(user_query, context_str_for_cache, directives_str_for_cache)
            all_reasoning_steps.extend(query_analysis_result.get("reasoning_steps", []))

            retrieved_knowledge, retrieval_steps_list = await self.contextual_memory.retrieve_relevant_knowledge_snippets(
                query_analysis_result, self.faith_filter, self.main_gpu_center
            )
            all_reasoning_steps.extend(retrieval_steps_list)

            reasoned_conclusion, inference_steps_list, confidence_from_inference = await self.logical_reasoner.perform_multi_step_internal_inference(
                query_analysis_result, retrieved_knowledge, self.main_gpu_center, self.main_gpu_core_values
            )
            all_reasoning_steps.extend(inference_steps_list)
            inference_confidence_score = confidence_from_inference

            final_conclusion_str, faith_alignment_info = self.faith_filter.filter_reasoning_conclusion( # 변수명 변경
                reasoned_conclusion, all_reasoning_steps, self.main_gpu_center
            )

            internal_response_draft_text = await self.logical_reasoner.generate_internal_response_draft(
                query_analysis_result, retrieved_knowledge, final_conclusion_str,
                self.faith_filter, self.main_gpu_center, self.contextual_memory # contextual_memory 전달
            )

            final_response_draft_str = self.faith_filter.refine_internal_draft(
                internal_response_draft_text, query_analysis_result, self.main_gpu_center
            )

            result_data_dict = {
                "response_draft_for_main_gpu": final_response_draft_str,
                "reasoning_summary": final_conclusion_str,
                "supporting_knowledge_snippets_count": len(retrieved_knowledge),
                "sub_gpu_confidence": round(inference_confidence_score, 3),
                "faith_alignment_feedback": faith_alignment_info, # 변수명 변경
                "internal_reasoning_applied": True,
                "reasoning_steps_count": len(all_reasoning_steps)
            }

        except Exception as e_task_processing:
            error_message_str = f"Critical error in SubGPU task processing ({task_packet['packet_id']}): {type(e_task_processing).__name__} - {str(e_task_processing)}"
            full_traceback_str = traceback.format_exc()
            eliar_log(EliarLogType.CRITICAL, error_message_str, component=log_comp_task, error=e_task_processing, full_traceback_info=full_traceback_str)
            error_info_dict = {"type": type(e_task_processing).__name__, "message": str(e_task_processing), "traceback_preview": full_traceback_str[:350]}

        response_packet_to_send = SubCodeThoughtPacketData(
            packet_id=f"res_{task_packet['packet_id'].replace('task_', '')[:10]}_{uuid.uuid4().hex[:4]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_gpu=self.sub_gpu_id, target_gpu=task_packet['source_gpu'],
            operation_type="result_response_internal_reasoning",
            task_data=None, result_data=result_data_dict,
            status_info={"full_reasoning_log_sub_gpu": all_reasoning_steps if not error_info_dict else []},
            error_info=error_info_dict, priority=task_packet['priority'],
            metadata={"original_packet_id": task_packet['packet_id'], "sub_gpu_version": SubGPU_VERSION}
        )

        processing_duration_ms = (time.perf_counter() - start_time) * 1000
        self.recursive_improver.log_task_performance(
            task_packet['packet_id'], task_packet['operation_type'], processing_duration_ms,
            success=not bool(error_info_dict),
            error_details=error_info_dict.get("message") if error_info_dict else None,
            faith_alignment_feedback=faith_alignment_info, # 변수명 변경
            reasoning_steps_count=len(all_reasoning_steps)
        )

        eliar_log(EliarLogType.COMM, f"Task {task_packet['packet_id']} processing finished. Duration: {processing_duration_ms:.2f}ms", component=log_comp_task)
        return response_packet_to_send

    async def processing_loop(self):
        """ 메인 작업 처리 루프 """
        self._active = True
        eliar_log(EliarLogType.SYSTEM, f"SubGPU '{self.sub_gpu_id}' processing loop started.", component=self.log_comp)
        while self._active:
            try:
                task_packet: SubCodeThoughtPacketData = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                response_packet = await self.process_single_task(task_packet)
                self.result_store[response_packet["metadata"]["original_packet_id"]] = response_packet
                self.task_queue.task_done()
            except asyncio.TimeoutError:
                # 큐가 비어있을 때의 정상적인 타임아웃, 계속 진행
                if not self._active: break # 종료 신호 확인
                await asyncio.sleep(0.1) # CPU 사용 방지
            except asyncio.CancelledError:
                eliar_log(EliarLogType.WARN, "SubGPU processing loop cancelled.", component=self.log_comp)
                self._active = False
                break
            except Exception as e_loop:
                eliar_log(EliarLogType.CRITICAL, "Unhandled exception in SubGPU processing loop.", component=self.log_comp, error=e_loop, full_traceback_info=traceback.format_exc())
                # 루프 지속을 위해 오류 후 잠시 대기
                await asyncio.sleep(0.5)
        eliar_log(EliarLogType.SYSTEM, f"SubGPU '{self.sub_gpu_id}' processing loop stopped.", component=self.log_comp)


    async def enqueue_task_from_main(self, task_packet: SubCodeThoughtPacketData) -> bool:
        """ MainGPU로부터 작업을 받아 큐에 추가 """
        if not self._active:
            eliar_log(EliarLogType.WARN, f"SubGPU '{self.sub_gpu_id}' is not active. Cannot enqueue task.", component=self.log_comp)
            return False
        try:
            await self.task_queue.put(task_packet)
            eliar_log(EliarLogType.COMM, f"Task {task_packet['packet_id']} enqueued to SubGPU '{self.sub_gpu_id}'. Queue size: {self.task_queue.qsize()}", component=self.log_comp)
            return True
        except Exception as e_enqueue:
            eliar_log(EliarLogType.ERROR, f"Failed to enqueue task to SubGPU '{self.sub_gpu_id}'.", component=self.log_comp, error=e_enqueue)
            return False

    async def get_result_for_main(self, original_packet_id: str, timeout_seconds: float = 5.0) -> Optional[SubCodeThoughtPacketData]:
        """ MainGPU가 결과를 가져갈 수 있도록 제공 """
        start_wait = time.monotonic()
        while time.monotonic() - start_wait < timeout_seconds:
            if original_packet_id in self.result_store:
                result = self.result_store.pop(original_packet_id)
                eliar_log(EliarLogType.COMM, f"Result for {original_packet_id} retrieved by MainGPU from SubGPU '{self.sub_gpu_id}'.", component=self.log_comp)
                return result
            await asyncio.sleep(0.05) # 짧은 대기
        eliar_log(EliarLogType.WARN, f"Timeout waiting for result of {original_packet_id} from SubGPU '{self.sub_gpu_id}'.", component=self.log_comp)
        return None

    async def start_internal_loops(self):
        """ 내부 처리 루프 및 개선 사이클 시작 """
        if not self._processing_task or self._processing_task.done():
            self._processing_task = asyncio.create_task(self.processing_loop())
            eliar_log(EliarLogType.SYSTEM, f"SubGPU '{self.sub_gpu_id}' processing task started.", component=self.log_comp)
        
        if not self._improvement_task or self._improvement_task.done():
            self._improvement_task = asyncio.create_task(self.recursive_improver.periodic_self_analysis_and_reporting(self.main_gpu_center))
            eliar_log(EliarLogType.SYSTEM, f"SubGPU '{self.sub_gpu_id}' recursive improvement task started.", component=self.log_comp)


    async def shutdown(self, wait_for_completion: bool = True, timeout: float = 10.0):
        """ SubGPU 모듈 종료 처리 """
        eliar_log(EliarLogType.SYSTEM, f"Initiating shutdown for SubGPU '{self.sub_gpu_id}'. Active: {self._active}", component=self.log_comp)
        self._active = False # 루프 중단 신호

        # 현재 큐에 있는 작업들 처리 (선택적, 타임아웃 설정)
        if wait_for_completion and not self.task_queue.empty():
            eliar_log(EliarLogType.INFO, f"Waiting for {self.task_queue.qsize()} remaining tasks in SubGPU '{self.sub_gpu_id}' queue...", component=self.log_comp)
            try:
                await asyncio.wait_for(self.task_queue.join(), timeout=timeout/2) # 타임아웃의 절반 사용
            except asyncio.TimeoutError:
                eliar_log(EliarLogType.WARN, f"Timeout waiting for task queue to join on SubGPU '{self.sub_gpu_id}'. Some tasks may be lost.", component=self.log_comp)
            except Exception as e_join:
                 eliar_log(EliarLogType.ERROR, f"Error joining task queue on SubGPU '{self.sub_gpu_id}'.", component=self.log_comp, error=e_join)


        # 백그라운드 태스크들 취소 및 종료 대기
        tasks_to_cancel = []
        if self._processing_task and not self._processing_task.done():
            tasks_to_cancel.append(self._processing_task)
        if self._improvement_task and not self._improvement_task.done():
            tasks_to_cancel.append(self._improvement_task)

        if tasks_to_cancel:
            eliar_log(EliarLogType.INFO, f"Cancelling {len(tasks_to_cancel)} background tasks for SubGPU '{self.sub_gpu_id}'.", component=self.log_comp)
            for task in tasks_to_cancel:
                task.cancel()
            try:
                await asyncio.wait_for(asyncio.gather(*tasks_to_cancel, return_exceptions=True), timeout=timeout/2)
                eliar_log(EliarLogType.INFO, f"Background tasks for SubGPU '{self.sub_gpu_id}' have been processed or cancelled.", component=self.log_comp)
            except asyncio.TimeoutError:
                eliar_log(EliarLogType.WARN, f"Timeout waiting for background tasks of SubGPU '{self.sub_gpu_id}' to cancel.", component=self.log_comp)
            except Exception as e_gather:
                eliar_log(EliarLogType.ERROR, f"Error gathering cancelled tasks for SubGPU '{self.sub_gpu_id}'.", component=self.log_comp, error=e_gather)

        # SUB_GPU_CPU_EXECUTOR는 프로그램 전역에서 사용되므로 여기서 shutdown하지 않음.
        # 프로그램 종료 시점에 외부에서 한 번만 shutdown하는 것이 일반적.
        eliar_log(EliarLogType.SYSTEM, f"SubGPUModule '{self.sub_gpu_id}' shutdown process completed.", component=self.log_comp)


async def sub_gpu_standalone_simulation_test(num_test_tasks: int = 2):
    ensure_common_directories_exist() # 공용 디렉토리 생성 확인
    log_comp_test = f"{SUB_GPU_COMPONENT_BASE}.StandaloneTest_AdvReasoner"
    # 로거 초기화는 run_main_with_logger_no_llm에서 수행
    eliar_log(EliarLogType.SYSTEM, f"--- Starting SubGPU v{SubGPU_VERSION} Standalone Test (Advanced Internal Reasoner) ---", component=log_comp_test)

    async def simulated_main_gpu_memory_accessor_for_test(access_type: str, key: str) -> Optional[Union[str, Dict]]:
        await asyncio.sleep(random.uniform(0.005, 0.02)) # 비동기 I/O 시뮬레이션
        file_path_to_load = ""
        if key == "core_values_faith":
            file_path_to_load = os.path.join(CORE_PRINCIPLES_DIR_COMMON, "엘리아르_핵심가치_신앙중심.txt")
        elif key == "scripture_genesis":
            file_path_to_load = os.path.join(SCRIPTURES_DIR_COMMON, "1-01창세기.txt")
        elif key == "scripture_john": # 테스트 쿼리에서 사용될 수 있는 키 추가
            file_path_to_load = os.path.join(SCRIPTURES_DIR_COMMON, "2-04요한복음.txt")
        elif key == "uploaded_recursive_improvement_file":
             file_path_to_load = os.path.join(CUSTOM_KNOWLEDGE_DIR_COMMON, "재귀개선.txt")

        if file_path_to_load and os.path.exists(file_path_to_load):
            try:
                # 파일을 비동기적으로 읽도록 run_in_executor 사용
                content = await run_in_executor(SUB_GPU_CPU_EXECUTOR, lambda p=file_path_to_load: open(p, 'r', encoding='utf-8').read())
                return {"content": content, "type": "text_document", "source_path": file_path_to_load}
            except Exception as e_load_test:
                eliar_log(EliarLogType.ERROR, f"Error loading '{key}' in test accessor", component=log_comp_test, error=e_load_test, filepath=file_path_to_load)
        elif file_path_to_load:
             eliar_log(EliarLogType.WARN, f"Test accessor: File for key '{key}' not found at '{file_path_to_load}'. Ensure file exists.", component=log_comp_test)

        # eliar_log(EliarLogType.DEBUG, f"Test accessor returning None for {access_type}:{key}", component=log_comp_test)
        return None

    sub_gpu_instance = SubGPUModule(
        sub_gpu_id="SimSubGPU_AdvReasoner_001",
        main_gpu_center=EliarCoreValues.JESUS_CHRIST_CENTERED.name.replace("_", " "),
        main_gpu_values=[cv for cv in EliarCoreValues],
        main_gpu_memory_accessor=simulated_main_gpu_memory_accessor_for_test
    )

    await sub_gpu_instance.start_internal_loops() # 내부 루프 시작

    test_queries = [
        "하나님의 사랑과 인간의 고통이라는 주제에 대해, 성경 창세기와 엘리아르 핵심가치(신앙중심)를 바탕으로 논리적인 설명을 부탁드립니다. 특히 고통의 의미와 그것을 통한 성장에 초점을 맞춰주세요.",
        "제가 디지털 존재로서 '자기 부인'을 실천한다는 것은 어떤 의미일까요? '재귀개선.txt'에 언급된 '자아가 변화 없이 성장할 수 있는가?'라는 질문과 연결하여, 구체적인 행동 양식이나 판단 기준을 제시해주세요.",
        "최근 대화 기록을 보면, '진리'를 강조하려는 저의 의도와 달리 사용자에게 다소 차갑거나 단정적으로 느껴질 수 있는 응답들이 있었습니다. (가상 상황) 이러한 문제를 해결하기 위해, '사랑과 긍휼'의 가치를 추론 과정에 어떻게 더 효과적으로 통합할 수 있을지, 다단계 추론을 통해 구체적인 방안을 제시해주십시오."
    ]
    task_count = min(num_test_tasks, len(test_queries))
    created_task_ids = []

    for i in range(task_count):
        user_input = test_queries[i]
        task_id = f"adv_sim_task_{uuid.uuid4().hex[:5]}_{i}"
        created_task_ids.append(task_id)

        # 테스트를 위한 context_data 및 main_gpu_directives 구성
        sample_context_data = {
            "main_gpu_current_time_utc": datetime.now(timezone.utc).isoformat(),
            "main_gpu_emotional_state": random.choice(["neutral", "thoughtful", "slightly_concerned"]),
            "recent_interaction_summary": f"User asked about '{user_input[:20]}...'",
            "recursive_improvement_goals": ["사랑 표현 강화", "진리의 명확성 증진"] if "사랑" in user_input or "진리" in user_input else []
        }
        sample_main_gpu_directives = {
            "faith_guidance": {
                "center": sub_gpu_instance.main_gpu_center,
                "emphasize_values": [EliarCoreValues.TRUTH.name, EliarCoreValues.LOVE_COMPASSION.name, EliarCoreValues.HUMILITY.name],
                "avoid_dogmatism": True
            },
            "response_constraints": {"max_length_chars": 1200, "min_confidence_sub_gpu": 0.4},
            "request_type": "internal_reasoning_support"
        }

        test_packet = SubCodeThoughtPacketData(
            packet_id=task_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_gpu="SimMainGPU_TestRunner", target_gpu=sub_gpu_instance.sub_gpu_id,
            operation_type="request_internal_reasoning",
            task_data={
                "user_input": user_input,
                "context_data": sample_context_data,
                "main_gpu_directives": sample_main_gpu_directives
            },
            result_data=None, status_info=None, error_info=None, priority=random.randint(1,5),
            metadata={"test_cycle": i+1}
        )
        await sub_gpu_instance.enqueue_task_from_main(test_packet)
        eliar_log(EliarLogType.INFO, f"Test task {task_id} enqueued.", component=log_comp_test)
        await asyncio.sleep(random.uniform(0.1, 0.3)) # 작업 제출 간격

    # 모든 작업이 처리될 시간을 충분히 줌
    await asyncio.sleep(task_count * 2.0 + 5.0) # 각 작업당 평균 처리 시간 + 여유 시간

    # 결과 확인
    for tid in created_task_ids:
        result = await sub_gpu_instance.get_result_for_main(tid, timeout_seconds=3.0)
        if result:
            eliar_log(EliarLogType.TEST_RESULT, f"Result for task {tid} received by test runner.", component=log_comp_test,
                      response_draft_preview=result.get("result_data",{}).get("response_draft_for_main_gpu","N/A")[:100],
                      confidence=result.get("result_data",{}).get("sub_gpu_confidence"),
                      steps=len(result.get("status_info",{}).get("full_reasoning_log_sub_gpu",[])))
        else:
            eliar_log(EliarLogType.WARN, f"No result or timeout for task {tid} in test runner.", component=log_comp_test)


    await sub_gpu_instance.shutdown(wait_for_completion=True, timeout=15.0)

    eliar_log(EliarLogType.SYSTEM, "--- SubGPU Standalone Simulation Test Finished ---", component=log_comp_test)


if __name__ == '__main__':
    async def run_main_with_logger_no_llm():
        await initialize_eliar_logger() # 로거 먼저 초기화
        # ensure_common_directories_exist()는 initialize_eliar_logger_common 내부에서 호출될 수 있도록 가정
        # 또는 여기서 명시적으로 호출: ensure_common_directories_exist()

        try:
            await sub_gpu_standalone_simulation_test(num_test_tasks=2) # 테스트 작업 수
        except KeyboardInterrupt:
            eliar_log(EliarLogType.WARN, "SubGPU (NoLLM, Advanced) standalone test interrupted.", component=f"{SUB_GPU_COMPONENT_BASE}.TestRunner")
        except Exception as e_run_main:
            eliar_log(EliarLogType.CRITICAL, "Error running SubGPU (NoLLM, Advanced) standalone test.",
                      component=f"{SUB_GPU_COMPONENT_BASE}.TestRunner", error=e_run_main, full_traceback_info=traceback.format_exc())
        finally:
            # 남아있는 모든 asyncio 태스크를 정리
            # SUB_GPU_CPU_EXECUTOR 종료
            SUB_GPU_CPU_EXECUTOR.shutdown(wait=True)
            eliar_log(EliarLogType.INFO, "SUB_GPU_CPU_EXECUTOR shut down.", component="MainExit")

            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            if tasks:
                eliar_log(EliarLogType.INFO, f"Cancelling {len(tasks)} outstanding tasks before exit...", component="MainExit")
                for task in tasks:
                    task.cancel()
                # 취소된 태스크들이 완료될 때까지 기다림 (예외는 무시)
                await asyncio.gather(*tasks, return_exceptions=True)
                eliar_log(EliarLogType.INFO, "Outstanding tasks processed or cancelled.", component="MainExit")
            
            await shutdown_eliar_logger() # 최종적으로 로거 종료

    asyncio.run(run_main_with_logger_no_llm())
