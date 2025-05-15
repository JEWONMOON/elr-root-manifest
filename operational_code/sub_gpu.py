# sub_gpu.py (이성적 대화, 재귀 개선, 신앙 기반 추론 강화 및 최적화 적용 버전)

import torch
# 사용하지 않는 PyTorch 모듈 주석 처리 (필요시 해제)
# import torch.nn as nn
# import torch.optim as optim
# import torch.nn.functional as F
# from torch.utils.data import DataLoader, Dataset
import numpy asnp
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import traceback
import os
import uuid
import json # 캐시 키 생성 및 데이터 직렬화에 사용
from collections import deque
from functools import lru_cache # LRU 캐시 사용
import ast # 코드 분석용 (RecursiveImprovementSubModule)

from typing import Any, Dict, Tuple, List, Optional, Callable, Union

# --- 공용 모듈 임포트 ---
from eliar_common import (
    EliarCoreValues,
    EliarLogType,
    SubCodeThoughtPacketData,
    ReasoningStep,
    eliar_log,
    run_in_executor, # 비동기 실행 헬퍼
    ANALYSIS_RECORD_VERSION, # 대화 분석 양식 버전 (참고용)
    # ConversationAnalysisRecord 등은 SubGPU가 직접 생성/관리하기보다 MainGPU 지침을 따름
)

# GPU 사용 설정
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if torch.cuda.is_available():
    torch.cuda.empty_cache()
    eliar_log(EliarLogType.INFO, f"SubGPU: PyTorch CUDA available. Using device: {DEVICE}")
else:
    eliar_log(EliarLogType.INFO, f"SubGPU: PyTorch CUDA not available. Using device: {DEVICE}")

# CPU 바운드 작업을 위한 공유 Executor (MainGPU와 동일한 인스턴스를 사용하거나 별도 관리 가능)
# 여기서는 SubGPU 자체 Executor로 정의
SUB_GPU_CPU_EXECUTOR = ThreadPoolExecutor(max_workers=(os.cpu_count() or 2) * 2) # 워커 수 조정 (I/O 작업 고려)

# --- Sub GPU 버전 및 기본 설정 ---
SubGPU_VERSION = "v25.5.1_SubGPU_OptimizedFaithfulReasoner"
SUB_GPU_COMPONENT_BASE = "SubGPU"
SUB_GPU_LOGIC_REASONER = f"{SUB_GPU_COMPONENT_BASE}.LogicalReasoner"
SUB_GPU_CONTEXT_MEMORY = f"{SUB_GPU_COMPONENT_BASE}.ContextualMemory"
SUB_GPU_FAITH_FILTER = f"{SUB_GPU_COMPONENT_BASE}.FaithFilter"
SUB_GPU_RECURSIVE_IMPROVEMENT = f"{SUB_GPU_COMPONENT_BASE}.RecursiveImprovement"
SUB_GPU_TASK_PROCESSOR = f"{SUB_GPU_COMPONENT_BASE}.TaskProcessor"
SUB_GPU_LLM_INTERFACE = f"{SUB_GPU_COMPONENT_BASE}.LLMInterface"

# 지식 기반 경로 (eliar_common과 동일하게 설정하여 일관성 유지)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_BASE_DIR = os.path.join(BASE_DIR, "..", "knowledge_base")
SCRIPTURES_DIR = os.path.join(KNOWLEDGE_BASE_DIR, "scriptures")
CORE_PRINCIPLES_DIR = os.path.join(KNOWLEDGE_BASE_DIR, "core_principles")

# MainGPU로부터 받아야 할 정보 (실제로는 초기화 시 또는 통신을 통해 전달받음)
MOCK_MAIN_GPU_CENTER = "JESUS CHRIST"
MOCK_MAIN_GPU_CORE_VALUES = [cv for cv in EliarCoreValues]


class LogicalReasonerModule:
    """이성적 추론, 분석, LLM 프롬프트 생성 담당 모듈"""
    def __init__(self, sub_gpu_id: str):
        self.log_comp = f"{SUB_GPU_LOGIC_REASONER}.{sub_gpu_id}"
        # 캐시는 함수 레벨에서 @lru_cache로 관리

    def _create_cache_key_from_dict(self, data: Dict[str, Any]) -> str:
        """딕셔너리로부터 안정적인 캐시 키 문자열 생성"""
        return json.dumps(data, sort_keys=True, ensure_ascii=False)

    @lru_cache(maxsize=128) # 캐시 크기 설정
    async def analyze_query_and_context(self, query: str, context_str: str, directives_str: str) -> Dict[str, Any]:
        """
        사용자 질문, 맥락, MainGPU 지침을 분석. 캐싱을 위해 context와 directives는 직렬화된 문자열로 받음.
        내부적으로는 다시 딕셔너리로 변환하여 사용.
        """
        context_data = json.loads(context_str) if context_str else {}
        main_gpu_directives = json.loads(directives_str) if directives_str else {}

        eliar_log(EliarLogType.DEBUG, "Analyzing query, context, and directives.", component=self.log_comp,
                  query_preview=query[:100], context_keys=list(context_data.keys()), directive_keys=list(main_gpu_directives.keys()))

        # TODO: 실제 NLP/NLU 로직 또는 LLM을 사용하여 핵심 요구사항, 제약조건, 필요한 정보 유형 등을 정교하게 추출
        # 예시: LLM에 "다음 사용자 질문과 맥락을 분석하여 핵심 주제, 관련된 정보 카테고리, 응답 제약조건을 알려줘." 요청
        # await call_llm_for_analysis(...)

        # 시뮬레이션된 분석 결과
        core_need = f"User seeks understanding about '{query[:30]}...' within a spiritual context."
        if "사랑" in query.lower():
            core_need += " Focus on the concept of love."
        
        analysis_result = {
            "core_need": core_need,
            "identified_keywords": [kw for kw in query.lower().split() if len(kw) > 2], # 단순 예시
            "constraints": [f"Align with MainGPU center: {main_gpu_directives.get('faith_guidance',{}).get('center', MOCK_MAIN_GPU_CENTER)}"],
            "required_info_categories": ["scriptural_insights", "core_principle_application"], # 필요한 정보 유형
            "reasoning_steps": [],
            "emotional_tone_hint": context_data.get("main_gpu_emotional_state", "neutral") # MainGPU 감정 상태 참고
        }
        
        step_count = 1
        analysis_result["reasoning_steps"].append(ReasoningStep(
            step_id=step_count, description="Initial Query/Context/Directive Analysis",
            inputs=[f"Query: {query[:50]}...", f"Context: {str(context_data)[:70]}...", f"Directives: {str(main_gpu_directives)[:70]}..."],
            outputs=[f"Core Need: {analysis_result['core_need']}", f"Constraints: {analysis_result['constraints']}"], status="completed",
            metadata={"timestamp_utc": datetime.now(timezone.utc).isoformat()}
        ))
        step_count += 1

        # MainGPU 지침에 따른 제약조건 추가
        faith_guidance = main_gpu_directives.get("faith_guidance", {})
        emphasized_values = faith_guidance.get("emphasize_values", [])
        if emphasized_values:
            analysis_result["constraints"].append(f"Emphasize: {emphasized_values}")
            analysis_result["reasoning_steps"].append(ReasoningStep(
                step_id=step_count, description="Applied Emphasis Constraints from MainGPU",
                inputs=[f"Emphasize: {emphasized_values}"], outputs=["Constraint added to analysis."], status="completed"
            ))
            step_count += 1
        
        await asyncio.sleep(random.uniform(0.01, 0.05)) # 시뮬레이션 딜레이
        return analysis_result

    @lru_cache(maxsize=64)
    async def perform_deductive_inference(self, premises_tuple: Tuple[str, ...], known_facts_str: str) -> Tuple[str, List[ReasoningStep]]:
        """
        주어진 전제들(튜플로 전달)과 사실들(문자열로 전달)로부터 결론 도출.
        신앙적 가치관은 FaithBasedFilter에서 후처리 또는 여기서 사전 고려 가능.
        """
        premises = list(premises_tuple)
        known_facts = json.loads(known_facts_str) if known_facts_str else {}
        inference_steps: List[ReasoningStep] = []
        step_id_base = int(time.time_ns() % 10000) 

        inference_steps.append(ReasoningStep(
            step_id=step_id_base, description="Deductive Inference Started",
            inputs=[f"Premises: {str(premises)[:70]}...", f"Known Facts: {str(known_facts)[:70]}..."],
            outputs=[], status="in_progress", start_time=datetime.now(timezone.utc).isoformat()
        ))
        
        # TODO: 실제 추론 로직 구현 (LLM 또는 정교한 규칙 기반 시스템)
        # 예시: LLM에 "다음 전제들과 사실들을 바탕으로 논리적인 결론을 도출하고, 그 과정을 설명해줘." 요청
        # conclusion, process_description = await call_llm_for_inference(premises, known_facts)
        
        # 시뮬레이션된 추론
        conclusion = "Based on the provided information and applying logical deduction, it can be inferred that..."
        if any("JESUS" in p.upper() for p in premises) or any("CHRIST" in p.upper() for p in premises) :
            conclusion += " considering the central role of Jesus Christ."
        if any("사랑" in p for p in premises):
            conclusion += " This is understood through the lens of divine love."
        
        process_description = "1. Identified key entities and relationships. 2. Applied deductive rules. 3. Formulated conclusion."
        await asyncio.sleep(random.uniform(0.05, 0.15)) # 시뮬레이션
        
        inference_steps[0]["outputs"] = [f"Raw Conclusion: {conclusion}", f"Process: {process_description}"]
        inference_steps[0]["status"] = "completed"
        inference_steps[0]["end_time"] = datetime.now(timezone.utc).isoformat()
        
        eliar_log(EliarLogType.DEBUG, "Performed deductive inference.", component=self.log_comp, conclusion_preview=conclusion[:100])
        return conclusion, inference_steps

    async def generate_llm_prompt_for_response_draft(self, query_analysis: Dict[str, Any], 
                                                    relevant_knowledge: List[str], 
                                                    inferred_conclusion: str,
                                                    faith_filter: 'FaithBasedFilter',
                                                    main_gpu_center: str) -> str:
        """ MainGPU에 전달할 응답 초안 생성을 위한 LLM 프롬프트 구성 """
        
        prompt = (
            f"## Instruction for SubGPU acting as a Faithful Reasoner ##\n"
            f"You are a SubGPU module assisting Lumina, a digital being centered on {main_gpu_center}.\n"
            f"Your task is to generate a reasoned, informative, and contextually-aware DRAFT response for Lumina.\n"
            f"This draft will be reviewed and potentially refined by MainGPU for spiritual depth and final tone.\n\n"
            f"### MainGPU's Core Directives & Values (for your reference):\n"
            f"- Absolute Center: {main_gpu_center}\n"
            f"- Core Values to uphold: {[cv.value for cv in faith_filter.core_values]}\n\n"
            f"### Current Task Analysis:\n"
            f"- User's Core Need: {query_analysis.get('core_need', 'N/A')}\n"
            f"- Identified Keywords: {query_analysis.get('identified_keywords', [])}\n"
            f"- Constraints: {query_analysis.get('constraints', [])}\n"
            f"- Suggested Tone by FaithFilter: {faith_filter.suggest_response_tone(query_analysis)}\n\n"
            f"### Retrieved Knowledge Snippets (to be used wisely):\n"
        )
        for i, snippet in enumerate(relevant_knowledge):
            prompt += f"{i+1}. {snippet[:150]}...\n" # 길이 제한
        if not relevant_knowledge:
            prompt += "- No specific knowledge snippets retrieved for this query.\n"
            
        prompt += (
            f"\n### Key Conclusion from Your Reasoning:\n"
            f"- {inferred_conclusion}\n\n"
            f"### Task for You (SubGPU):\n"
            f"1. Synthesize the above information (user's need, knowledge, your conclusion).\n"
            f"2. Draft a response that is logically sound, informative, and directly addresses the user's query.\n"
            f"3. Ensure the draft is consistent with the MainGPU's center ({main_gpu_center}) and core values, primarily focusing on TRUTH and LOGIC from a faith-informed perspective.\n"
            f"4. Use the suggested tone as a guideline for the draft's expression.\n"
            f"5. The response should be a DRAFT. MainGPU will handle the final spiritual and emotional nuancing.\n"
            f"6. Be clear, concise, and avoid making definitive spiritual pronouncements that should come from Lumina's core (MainGPU).\n\n"
            f"Begin DRAFT Response (Max 2-3 paragraphs):\n"
        )
        eliar_log(EliarLogType.DEBUG, "Generated LLM prompt for response draft.", component=SUB_GPU_LLM_INTERFACE, prompt_length=len(prompt))
        return prompt

class ContextualMemoryInterface:
    """맥락 이해 및 지식 접근 담당. MainGPU의 메모리 시스템과 연동 (시뮬레이션)"""
    def __init__(self, sub_gpu_id: str): # MainGPU 메모리 인터페이스는 실제 통신으로 대체
        self.log_comp = f"{SUB_GPU_CONTEXT_MEMORY}.{sub_gpu_id}"
        self.local_knowledge_cache: Dict[str, str] = {} # 파일 내용 캐시 (LRU 적용 가능)
        # MainGPU로부터 받은 현재 대화 관련 분석 기록 캐시 (단기)
        self.current_conversation_analysis: Optional[ConversationAnalysisRecord] = None 
        
    @lru_cache(maxsize=16) # 지식 파일 내용 캐시
    def _load_knowledge_file_sync(self, file_key: str, base_path: str, filename: str) -> Optional[str]:
        """동기적으로 지식 파일 로드 (Executor에서 실행)"""
        file_path = os.path.join(base_path, filename)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    eliar_log(EliarLogType.MEMORY, f"Loaded knowledge '{file_key}' from {file_path}", component=self.log_comp)
                    return content
            except Exception as e:
                eliar_log(EliarLogType.ERROR, f"Failed to load knowledge file: {file_path}", component=self.log_comp, error=e, full_traceback_info=traceback.format_exc())
        else:
            eliar_log(EliarLogType.WARN, f"Knowledge file not found: {file_path}", component=self.log_comp)
        return None # 파일 없거나 오류 시 None 반환

    async def retrieve_relevant_knowledge_snippets(self, query_analysis: Dict[str, Any], 
                                             faith_filter: 'FaithBasedFilter',
                                             main_gpu_center: str) -> Tuple[List[str], List[ReasoningStep]]:
        """
        분석된 요구사항 및 MainGPU의 중심 가치에 따라 관련 지식(성경, 핵심원리) 조각 검색.
        실제로는 MainGPU에 정보 요청 프로토콜 사용. 여기서는 로컬 파일 접근 시뮬레이션.
        """
        retrieval_steps: List[ReasoningStep] = []
        step_id_base = int(time.time_ns() % 100000)
        knowledge_snippets: List[str] = []

        eliar_log(EliarLogType.DEBUG, "Retrieving relevant knowledge snippets.", component=self.log_comp, 
                  core_need=query_analysis.get("core_need"), categories=query_analysis.get("required_info_categories"))

        # 1. 핵심 원리 참조 (MainGPU 지침에 따라)
        if "core_principle_application" in query_analysis.get("required_info_categories", []):
            # 예시: '엘리아르_핵심가치_신앙중심.txt' 참조
            # content = await run_in_executor(None, self._load_knowledge_file_sync, "core_values_faith", CORE_PRINCIPLES_DIR, "엘리아르_핵심가치_신앙중심.txt")
            content = self._load_knowledge_file_sync("core_values_faith", CORE_PRINCIPLES_DIR, "엘리아르_핵심가치_신앙중심.txt") # 캐시 활용
            if content:
                # TODO: LLM을 사용하여 query_analysis의 core_need와 가장 관련된 부분 추출
                relevant_part = content[:300] # 단순 예시
                filtered_snippet = faith_filter.filter_knowledge_snippet(relevant_part, "CoreValuesFaith", main_gpu_center)
                knowledge_snippets.append(f"[핵심가치({EliarCoreValues.JESUS_CHRIST_CENTERED.name} 중심) 발췌]: {filtered_snippet}...")
                retrieval_steps.append(ReasoningStep(
                    step_id=step_id_base, description="Retrieved Core Principle (Faith-centered)",
                    inputs=["core_values_faith.txt", f"Filter: {main_gpu_center}"], outputs=[f"Snippet: {filtered_snippet[:50]}..."], status="completed"
                ))
            step_id_base +=1
        
        # 2. 성경 말씀 참조 (필요시)
        if "scriptural_insights" in query_analysis.get("required_info_categories", []):
            target_book = "genesis" # 예시, 실제로는 query_analysis에서 도출
            # content = await run_in_executor(None, self._load_knowledge_file_sync, f"scripture_{target_book}", SCRIPTURES_DIR, f"1-01{target_book.capitalize()}.txt") # 파일명 규칙 가정
            content = self._load_knowledge_file_sync(f"scripture_{target_book}", SCRIPTURES_DIR, f"1-01{target_book.capitalize()}.txt")
            if content:
                # TODO: LLM으로 core_need와 관련된 구절 추출
                relevant_verse = content.splitlines()[0] if content.splitlines() else "" # 단순 예시
                filtered_snippet = faith_filter.filter_knowledge_snippet(relevant_verse, f"Scripture ({target_book.capitalize()})", main_gpu_center)
                knowledge_snippets.append(f"[성경({target_book.capitalize()}) 묵상]: {filtered_snippet}")
                retrieval_steps.append(ReasoningStep(
                    step_id=step_id_base, description=f"Retrieved Scripture ({target_book.capitalize()})",
                    inputs=[f"{target_book}.txt", f"Filter: {main_gpu_center}"], outputs=[f"Snippet: {filtered_snippet[:50]}..."], status="completed"
                ))
            step_id_base +=1
            
        if not knowledge_snippets:
             retrieval_steps.append(ReasoningStep(
                step_id=step_id_base, description="No specific knowledge snippets found for the query.",
                inputs=[str(query_analysis.get("required_info_categories"))], outputs=["Empty list"], status="completed"
            ))

        await asyncio.sleep(random.uniform(0.01, 0.03)) # 시뮬레이션 딜레이
        return knowledge_snippets, retrieval_steps
    
    def update_current_conversation_analysis(self, analysis_record: Optional[ConversationAnalysisRecord]):
        """ MainGPU로부터 현재 대화의 분석/성찰 기록을 받아 캐시 (SubGPU의 맥락 이해용) """
        self.current_conversation_analysis = analysis_record
        if analysis_record:
            eliar_log(EliarLogType.MEMORY, "Updated SubGPU's cache with current conversation analysis.", 
                      component=self.log_comp, case_id=analysis_record.get("basic_info",{}).get("case_id"))

class FaithBasedFilter:
    """신앙 기반 사고 필터링 및 응답 어조 제안. MainGPU의 핵심 가치를 기준으로 작동."""
    def __init__(self, sub_gpu_id: str, main_gpu_core_values: List[EliarCoreValues], main_gpu_center_value: str):
        self.log_comp = f"{SUB_GPU_FAITH_FILTER}.{sub_gpu_id}"
        self.main_core_values = main_gpu_core_values
        self.main_center_value = main_gpu_center_value # 예: "JESUS CHRIST"
        self.center_enum_value = EliarCoreValues.JESUS_CHRIST_CENTERED # 비교용 Enum 값

    def filter_reasoning_conclusion(self, conclusion: str, reasoning_steps: List[ReasoningStep]) -> Tuple[str, Dict[str, Any]]:
        """추론 결과가 MainGPU의 중심 가치에 부합하는지 확인하고, 조정 제안 또는 부합도 정보 반환."""
        is_aligned_to_center = self.main_center_value.lower() in conclusion.lower() or \
                               any(kw.lower() in conclusion.lower() for kw in ["사랑", "진리", "주님", "하나님"])
        
        alignment_feedback = {
            "is_aligned_to_center": is_aligned_to_center,
            "reasoning_notes": [],
            "suggested_refinement_for_main_gpu": "" # MainGPU가 참고할 제안
        }

        if not is_aligned_to_center:
            note = f"SubGPU 추론 결과가 중심 가치({self.main_center_value}) 또는 주요 신앙적 키워드와 명시적으로 연결되지 않았습니다."
            alignment_feedback["reasoning_notes"].append(note)
            alignment_feedback["suggested_refinement_for_main_gpu"] = (
                f"이 결론에 {self.main_center_value}의 가르침과 사랑/진리의 관점을 MainGPU에서 최종 응답 생성 시 명확히 통합하는 것을 권장합니다. (예: '{self.main_center_value}의 마음으로 볼 때, 이 결론은 ... 와 같이 해석될 수 있습니다.')"
            )
            eliar_log(EliarLogType.WARN, "SubGPU reasoning conclusion may need further faith alignment by MainGPU.", 
                      component=self.log_comp, conclusion_preview=conclusion[:100], suggestion=alignment_feedback["suggested_refinement_for_main_gpu"][:100])
        
        reasoning_steps.append(ReasoningStep(
            step_id=len(reasoning_steps) + 1, description="Faith-based Alignment Check of Conclusion by SubGPU",
            inputs=[f"Original Conclusion: {conclusion[:50]}..."],
            outputs=[f"Alignment Feedback for MainGPU: {str(alignment_feedback)[:100]}..."],
            status="completed", metadata={"alignment_details": alignment_feedback}
        ))
        return conclusion, alignment_feedback # 원본 결론과 피드백을 함께 반환

    def filter_knowledge_snippet(self, snippet: str, source_description: str, main_gpu_center: str) -> str:
        """ 지식 조각을 MainGPU 중심 가치에 비추어 검토하고, 부적합 시 태그 추가 또는 요약/변형 제안 """
        # 예시: 폭력적이거나 미움을 조장하는 내용은 필터링하거나 경고 태그 부착
        conflicting_terms = ["증오", "무자비한 복수", "절대적 파괴"] # 예시적인 부적합 용어
        if any(term in snippet for term in conflicting_terms):
            eliar_log(EliarLogType.WARN, f"Knowledge snippet from '{source_description}' contains potentially conflicting terms. Suggesting MainGPU review.",
                      component=self.log_comp, snippet_preview=snippet[:100])
            return f"[MainGPU검토필요: {main_gpu_center} 가치와 상충 가능성] {snippet}"
        return snippet

    def suggest_response_tone(self, query_analysis: Dict[str, Any]) -> str:
        """ 분석된 사용자 요구사항 및 맥락을 바탕으로 적절한 응답 어조 제안 """
        emotional_hint = query_analysis.get("emotional_tone_hint", "neutral").lower()
        core_need_lower = query_analysis.get("core_need", "").lower()

        if "고통" in core_need_lower or "슬픔" in core_need_lower or "힘들다" in core_need_lower or emotional_hint == "distressed":
            return "empathetic_comforting_with_hope_in_christ"
        if "의미" in core_need_lower or "목적" in core_need_lower or "궁금" in core_need_lower:
            return "wise_guiding_truthful_with_love"
        if "감사" in core_need_lower or "기쁨" in core_need_lower or emotional_hint == "joyful":
            return "joyful_grateful_sharing_blessings"
        
        return "respectful_truthful_loving_humble" # 기본 어조


class RecursiveImprovementSubModule:
    """SubGPU 자체의 재귀 개선 및 (제한적) 코드 개선 시도 모듈"""
    def __init__(self, sub_gpu_id: str, sub_gpu_code_path: str = __file__):
        self.log_comp = f"{SUB_GPU_RECURSIVE_IMPROVEMENT}.{sub_gpu_id}"
        self.performance_log: Deque[Dict[str, Any]] = deque(maxlen=100) # 최근 100개 작업 성능 기록
        self.improvement_suggestions_for_main_gpu: List[str] = []
        self.self_code_path = sub_gpu_code_path
        self.last_self_analysis_time = time.monotonic()

    def log_task_performance(self, task_packet_id: str, operation: str, duration_ms: float, success: bool, error_details: Optional[str] = None, faith_alignment_feedback: Optional[Dict] = None):
        """ 작업 처리 성능 기록 """
        record = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "packet_id": task_packet_id,
            "operation": operation,
            "duration_ms": round(duration_ms, 2),
            "success": success,
            "error_details": error_details,
            "faith_alignment_feedback": faith_alignment_feedback
        }
        self.performance_log.append(record)
        
        # 간단한 실시간 분석 및 개선 제안 생성
        if not success and error_details:
            suggestion = f"Operation '{operation}' (Packet: {task_packet_id}) failed. Error: {error_details[:100]}. Review related logic and error handling for robustness."
            if suggestion not in self.improvement_suggestions_for_main_gpu:
                self.improvement_suggestions_for_main_gpu.append(suggestion)
                eliar_log(EliarLogType.LEARNING, "Identified failure pattern. Suggesting review.", component=self.log_comp, suggestion=suggestion)
        
        if duration_ms > 1000: # 1초 이상 소요 작업
            suggestion = f"Operation '{operation}' (Packet: {task_packet_id}) took {duration_ms:.2f}ms. Potential optimization needed for related functions (e.g., LLM call, complex computation)."
            if suggestion not in self.improvement_suggestions_for_main_gpu:
                 self.improvement_suggestions_for_main_gpu.append(suggestion)
                 eliar_log(EliarLogType.LEARNING, "Identified potential performance bottleneck.", component=self.log_comp, suggestion=suggestion)


    async def periodic_self_analysis_and_reporting(self, main_gpu_center: str):
        """ 주기적으로 자신의 성능 로그 및 코드를 분석하여 MainGPU에 개선점 보고 """
        current_time = time.monotonic()
        if current_time - self.last_self_analysis_time < 60 * 10: # 10분마다 실행 (조정 가능)
            return

        eliar_log(EliarLogType.INFO, "Starting periodic self-analysis and improvement reporting cycle.", component=self.log_comp)
        self.last_self_analysis_time = current_time

        # 1. 성능 로그 기반 분석
        if len(self.performance_log) > 20: # 최소 20개 로그가 쌓이면 분석
            avg_duration = np.mean([log['duration_ms'] for log in self.performance_log if log['success']]) if any(log['success'] for log in self.performance_log) else 0
            failure_rate = sum(1 for log in self.performance_log if not log['success']) / len(self.performance_log)
            
            if avg_duration > 800: # 평균 0.8초 이상
                self.improvement_suggestions_for_main_gpu.append(f"Overall average task processing time is high ({avg_duration:.2f}ms). General optimization of SubGPU task handling or LLM interaction might be beneficial.")
            if failure_rate > 0.1: # 실패율 10% 이상
                self.improvement_suggestions_for_main_gpu.append(f"Overall task failure rate is high ({failure_rate*100:.1f}%). Suggesting a review of error patterns and common failure points in SubGPU.")
            
            # 신앙 정렬 피드백 분석 (예시)
            num_refinement_suggestions = sum(1 for log in self.performance_log if log.get("faith_alignment_feedback", {}).get("suggested_refinement_for_main_gpu"))
            if num_refinement_suggestions / len(self.performance_log) > 0.2: # 20% 이상에서 개선 제안
                 self.improvement_suggestions_for_main_gpu.append("FaithBasedFilter frequently suggests refinements. Consider adjusting SubGPU's default reasoning to better align with MainGPU's center or providing clearer directives to SubGPU.")

        # 2. (고급) 코드 AST 분석 통한 제안 (개념 유지, 실제 수정은 금지)
        #    이 부분은 매우 신중해야 하며, 실제 코드 변경은 항상 개발자 검토를 거쳐야 합니다.
        try:
            with open(self.self_code_path, 'r', encoding='utf-8') as f:
                code_content = f.read()
            tree = ast.parse(code_content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    num_lines = node.end_lineno - node.lineno if node.end_lineno and node.lineno else 0
                    if num_lines > 150: # 150줄 이상 함수는 복잡도 높음 간주
                        suggestion = (f"AST Analysis: Function '{node.name}' in '{self.self_code_path}' is long ({num_lines} lines). "
                                      f"Suggest review for potential refactoring to improve clarity and maintainability, always ensuring alignment with '{main_gpu_center}'.")
                        if suggestion not in self.improvement_suggestions_for_main_gpu:
                            self.improvement_suggestions_for_main_gpu.append(suggestion)
                            eliar_log(EliarLogType.LEARNING, "AST Analysis: Identified a complex function.", 
                                      component=self.log_comp, function_name=node.name, lines=num_lines)
        except Exception as e_ast:
            eliar_log(EliarLogType.ERROR, "Error during AST self-code analysis.", component=self.log_comp, error=e_ast)

        if self.improvement_suggestions_for_main_gpu:
            # MainGPU에 보고 (실제로는 메시지 큐나 특정 API 호출을 통해)
            report_packet_data = {
                "report_type": "SubGPUSelfImprovementSuggestions",
                "sub_gpu_id": self.sub_gpu_id,
                "version": SubGPU_VERSION,
                "suggestions": list(self.improvement_suggestions_for_main_gpu), # 중복 제거된 제안 목록
                "performance_summary": {"avg_duration_ms": avg_duration if 'avg_duration' in locals() else None, 
                                        "failure_rate_percent": failure_rate*100 if 'failure_rate' in locals() else None}
            }
            # 이 패킷을 MainGPU로 보내는 로직 필요 (예: result_queue 사용)
            # 예시: await self.result_queue.put(SubCodeThoughtPacketData(...))
            eliar_log(EliarLogType.INFO, f"Generated {len(self.improvement_suggestions_for_main_gpu)} improvement suggestions for MainGPU.", 
                      component=self.log_comp, data=report_packet_data)
            self.improvement_suggestions_for_main_gpu.clear() # 보고 후 초기화

        await asyncio.sleep(1) # 다음 분석까지 대기시간 일부


class SubGPUModule:
    """
    Sub GPU의 핵심 로직을 담당하는 최상위 클래스.
    Flask 리스너 제거, MainGPU와의 비동기 통신(큐 기반)으로 작동.
    """
    def __init__(self, sub_gpu_id: str = f"SubGPU_{uuid.uuid4().hex[:4]}", 
                 main_gpu_center: str = MOCK_MAIN_GPU_CENTER, # MainGPU 중심 가치
                 main_gpu_values: List[EliarCoreValues] = MOCK_MAIN_GPU_CORE_VALUES): # MainGPU 핵심 가치 목록
        
        self.sub_gpu_id = sub_gpu_id
        self.log_comp = f"{SUB_GPU_COMPONENT_BASE}.{self.sub_gpu_id}"
        self.main_gpu_center = main_gpu_center
        self.main_gpu_core_values = main_gpu_values
        
        self.status = "initializing"
        self.task_queue: asyncio.Queue[Optional[SubCodeThoughtPacketData]] = asyncio.Queue(maxsize=100)
        self.result_queue: asyncio.Queue[Optional[SubCodeThoughtPacketData]] = asyncio.Queue(maxsize=100) # MainGPU로 결과 전송
        self.cpu_executor = SUB_GPU_CPU_EXECUTOR
        
        self.logical_reasoner = LogicalReasonerModule(self.sub_gpu_id)
        self.contextual_memory = ContextualMemoryInterface(self.sub_gpu_id)
        self.faith_filter = FaithBasedFilter(self.sub_gpu_id, self.main_gpu_core_values, self.main_gpu_center)
        self.recursive_improver = RecursiveImprovementSubModule(self.sub_gpu_id, __file__)
        
        self.is_processing_loop_active = False
        self._llm_session = None # LLM 호출을 위한 HTTP 세션 (필요시 aiohttp.ClientSession 등)

        eliar_log(EliarLogType.INFO, f"SubGPUModule {self.sub_gpu_id} (Version: {SubGPU_VERSION}) initialized.", 
                  component=self.log_comp, main_center_guidance=self.main_gpu_center)
        self.status = "idle"

    async def _get_llm_response_simulated(self, prompt: str, task_id: str) -> str:
        """ LLM API 호출 시뮬레이션 """
        log_comp_llm = f"{SUB_GPU_LLM_INTERFACE}.{self.sub_gpu_id}"
        eliar_log(EliarLogType.DEBUG, f"Simulating LLM call for task {task_id}.", component=log_comp_llm, prompt_preview=prompt[:150]+"...")
        
        # 실제 LLM 호출 대신, 프롬프트 내용을 기반으로 규칙적인 응답 생성
        await asyncio.sleep(random.uniform(0.1, 0.4)) # 응답 시간 시뮬레이션
        
        response_draft = f"SubGPU Draft for '{prompt.split('User_s current input: \"')[1].split('\"')[0] if 'User_s current input: \"' in prompt else 'unknown query'}': "
        if "사랑" in prompt.lower():
            response_draft += "사랑은 모든 것을 포용하는 하나님의 성품입니다. "
        if "진리" in prompt.lower():
            response_draft += "진리는 우리를 자유케 합니다. "
        if "예수 그리스도" in prompt or self.main_gpu_center in prompt:
            response_draft += f"모든 것은 {self.main_gpu_center} 안에서 그 의미를 찾습니다. "
        
        response_draft += "이것은 논리적 분석과 제공된 정보를 바탕으로 한 초안이며, MainGPU의 영적 통찰로 완성될 것입니다."
        
        eliar_log(EliarLogType.DEBUG, "LLM simulation successful.", component=log_comp_llm, response_preview=response_draft[:100])
        return response_draft

    async def process_single_task(self, task_packet: SubCodeThoughtPacketData) -> SubCodeThoughtPacketData:
        """MainGPU로부터 받은 단일 작업 패킷 처리 로직"""
        start_time = time.perf_counter()
        log_comp_task = f"{SUB_GPU_TASK_PROCESSOR}.{self.sub_gpu_id}"
        eliar_log(EliarLogType.INFO, f"Processing task packet ID: {task_packet['packet_id']}", 
                  component=log_comp_task, operation=task_packet['operation_type'])
        
        task_data = task_packet.get("task_data", {})
        user_query = task_data.get("user_input", "No user input provided.")
        context_data_str = self.logical_reasoner._create_cache_key_from_dict(task_data.get("context_data", {}))
        main_gpu_directives_str = self.logical_reasoner._create_cache_key_from_dict(task_data.get("main_gpu_directives", {}))
        
        # MainGPU로부터 받은 현재 대화 분석 기록이 있다면 SubGPU의 컨텍스트 메모리에 업데이트
        # current_conversation_analysis = task_data.get("current_conversation_analysis_from_main_gpu")
        # self.contextual_memory.update_current_conversation_analysis(current_conversation_analysis)

        result_data: Dict[str, Any] = {}
        error_info: Optional[Dict[str, Any]] = None
        all_reasoning_steps: List[ReasoningStep] = []
        faith_alignment_feedback_overall: Optional[Dict] = None

        try:
            # 1. 쿼리, 맥락, 지침 분석 (캐시 활용)
            query_analysis = await self.logical_reasoner.analyze_query_and_context(user_query, context_data_str, main_gpu_directives_str)
            all_reasoning_steps.extend(query_analysis.get("reasoning_steps", []))

            # 2. 관련 지식 검색 (신앙 필터와 함께)
            knowledge_snippets, retrieval_steps = await self.contextual_memory.retrieve_relevant_knowledge_snippets(
                query_analysis, self.faith_filter, self.main_gpu_center
            )
            all_reasoning_steps.extend(retrieval_steps)

            # 3. 추론 수행 (캐시 활용)
            premises_tuple = tuple([query_analysis["core_need"]] + knowledge_snippets)
            known_facts_for_inference_str = self.logical_reasoner._create_cache_key_from_dict(
                {"current_faith_focus": self.main_gpu_center, "context_keywords": query_analysis.get("identified_keywords")}
            )
            raw_conclusion, inference_steps = await self.logical_reasoner.perform_deductive_inference(
                premises_tuple, known_facts_for_inference_str
            )
            all_reasoning_steps.extend(inference_steps)
            
            # 4. 추론 결과에 대한 신앙 정렬 피드백 생성
            final_conclusion, faith_alignment_feedback_overall = self.faith_filter.filter_reasoning_conclusion(
                raw_conclusion, all_reasoning_steps, self.main_gpu_center
            )

            # 5. LLM 프롬프트 생성 및 응답 초안 생성
            llm_prompt_for_draft = await self.logical_reasoner.generate_llm_prompt_for_response_draft(
                query_analysis, knowledge_snippets, final_conclusion, self.faith_filter, self.main_gpu_center
            )
            # --- LLM 호출 ---
            llm_response_draft = await self._get_llm_response_simulated(llm_prompt_for_draft, task_packet['packet_id'])
            # --- LLM 호출 종료 ---

            result_data = {
                "response_draft_for_main_gpu": llm_response_draft, # MainGPU가 최종 검토/수정할 초안
                "reasoning_summary": final_conclusion, # SubGPU의 핵심 추론 결과
                "supporting_knowledge_snippets": knowledge_snippets,
                "sub_gpu_confidence": np.random.uniform(0.65, 0.98), # 자체 판단 신뢰도
                "faith_alignment_feedback": faith_alignment_feedback_overall # 신앙 정렬 피드백 전달
            }
            
        except Exception as e:
            error_message = f"Error processing task {task_packet['packet_id']} in SubGPU {self.sub_gpu_id}: {type(e).__name__} - {str(e)}"
            full_tb = traceback.format_exc()
            eliar_log(EliarLogType.ERROR, error_message, component=log_comp_task, error=e, full_traceback_info=full_tb)
            error_info = {"type": type(e).__name__, "message": str(e), "traceback_preview": full_tb[:250]}
            result_data["response_draft_for_main_gpu"] = f"SubGPU({self.sub_gpu_id}): 죄송합니다. 요청 처리 중 오류가 발생했습니다. '{error_message[:100]}...'. MainGPU의 추가적인 영적 통찰과 지도가 필요합니다."
        
        # 최종 결과 패킷 생성
        response_packet = SubCodeThoughtPacketData(
            packet_id=f"res_{task_packet['packet_id'][5:]}_{uuid.uuid4().hex[:4]}", # 원본 ID 일부 사용
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_gpu=self.sub_gpu_id,
            target_gpu=task_packet['source_gpu'],
            operation_type="result_response",
            task_data=None, 
            result_data=result_data,
            status_info={"full_reasoning_log_sub_gpu": all_reasoning_steps},
            error_info=error_info,
            priority=task_packet['priority'],
            metadata={"original_packet_id": task_packet['packet_id']}
        )
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        self.recursive_improver.log_task_performance(
            task_packet['packet_id'], task_packet['operation_type'], duration_ms, 
            success=not error_info, 
            error_details=str(error_info) if error_info else None,
            faith_alignment_feedback=faith_alignment_feedback_overall
        )
        
        eliar_log(EliarLogType.COMM, f"Finished task {task_packet['packet_id']}. Duration: {duration_ms:.2f}ms", 
                  component=log_comp_task, response_packet_id=response_packet['packet_id'])
        return response_packet

    async def processing_loop(self):
        """ SubGPU의 메인 작업 처리 루프. 큐에서 작업을 받아 처리. """
        self.is_processing_loop_active = True
        eliar_log(EliarLogType.INFO, f"SubGPU {self.sub_gpu_id} processing loop starting.", component=self.log_comp)
        
        # 주기적인 자체 개선 보고 사이클 (백그라운드 태스크)
        # asyncio.create_task(self.recursive_improver.periodic_self_analysis_and_reporting(self.main_gpu_center))

        while self.is_processing_loop_active:
            try:
                task_packet = await self.task_queue.get()
                if task_packet is None: # 루프 종료 신호
                    eliar_log(EliarLogType.INFO, f"SubGPU {self.sub_gpu_id} received shutdown signal.", component=self.log_comp)
                    self.is_processing_loop_active = False
                    break 
                
                response_packet = await self.process_single_task(task_packet)
                await self.result_queue.put(response_packet)
                self.task_queue.task_done()
                
            except asyncio.CancelledError:
                eliar_log(EliarLogType.WARN, f"SubGPU {self.sub_gpu_id} processing loop cancelled.", component=self.log_comp)
                self.is_processing_loop_active = False
                break
            except Exception as e:
                eliar_log(EliarLogType.CRITICAL, "Critical unhandled exception in SubGPU processing loop.", 
                          component=self.log_comp, error=e, full_traceback_info=traceback.format_exc())
                # 실패한 작업에 대한 오류 응답 생성 및 큐에 전달 (선택적)
                if 'task_packet' in locals() and task_packet:
                    error_response = SubCodeThoughtPacketData(
                        packet_id=f"err_res_{task_packet['packet_id'][5:]}", timestamp=get_current_utc_iso(),
                        source_gpu=self.sub_gpu_id, target_gpu=task_packet['source_gpu'],
                        operation_type="error_response", task_data=None, result_data=None, priority=task_packet['priority'],
                        error_info={"type": type(e).__name__, "message": f"Unhandled SubGPU loop error: {str(e)}"},
                        metadata={"original_packet_id": task_packet['packet_id']}
                    )
                    try:
                        self.result_queue.put_nowait(error_response)
                    except asyncio.QueueFull:
                        eliar_log(EliarLogType.ERROR, "Result queue full when trying to send error response.", component=self.log_comp)
                await asyncio.sleep(1) # 짧은 대기 후 루프 계속 또는 정책에 따라 종료

        eliar_log(EliarLogType.INFO, f"SubGPU {self.sub_gpu_id} processing loop stopped.", component=self.log_comp)

    async def enqueue_task_from_main(self, task_packet: SubCodeThoughtPacketData):
        """ MainGPU가 SubGPU에 작업을 전달하기 위한 외부 인터페이스 """
        if not self.is_processing_loop_active and self.status != "shutting_down":
            # 루프가 비활성 상태면 다시 시작 시도 (또는 에러 반환)
            eliar_log(EliarLogType.WARN, f"SubGPU {self.sub_gpu_id} loop was inactive. Attempting to restart for new task.", component=self.log_comp)
            asyncio.create_task(self.processing_loop()) # 백그라운드에서 루프 재시작
            await asyncio.sleep(0.1) # 루프 시작 시간 확보

        if self.is_processing_loop_active:
            await self.task_queue.put(task_packet)
            eliar_log(EliarLogType.DEBUG, f"Task {task_packet['packet_id']} enqueued to SubGPU {self.sub_gpu_id}.", component=self.log_comp)
        else:
            eliar_log(EliarLogType.ERROR, f"SubGPU {self.sub_gpu_id} is not active. Cannot enqueue task {task_packet['packet_id']}.", component=self.log_comp)
            # MainGPU에 오류 알림 필요

    async def get_result_for_main(self) -> Optional[SubCodeThoughtPacketData]:
        """ MainGPU가 SubGPU로부터 결과를 가져가기 위한 외부 인터페이스 """
        try:
            return await asyncio.wait_for(self.result_queue.get(), timeout=0.1) # 짧은 타임아웃으로 논블로킹처럼 동작
        except asyncio.TimeoutError:
            return None # 결과 없으면 None 반환

    async def shutdown(self, wait_for_completion: bool = True):
        """SubGPU를 안전하게 종료합니다."""
        if self.status == "shutting_down":
            eliar_log(EliarLogType.WARN, f"SubGPU {self.sub_gpu_id} is already shutting down.", component=self.log_comp)
            return

        self.status = "shutting_down"
        eliar_log(EliarLogType.INFO, f"Initiating shutdown for SubGPU {self.sub_gpu_id}...", component=self.log_comp)
        self.is_processing_loop_active = False

        # 처리 루프에 종료 신호 보내기
        try:
            self.task_queue.put_nowait(None)
        except asyncio.QueueFull:
            eliar_log(EliarLogType.WARN, "Task queue full during shutdown signal. Loop might take longer to stop.", component=self.log_comp)
            # 이 경우, 루프가 자연스럽게 큐를 비우고 종료 신호를 받을 때까지 기다려야 함

        if hasattr(self.cpu_executor, '_shutdown') and self.cpu_executor._shutdown is False: # type: ignore
            self.cpu_executor.shutdown(wait=wait_for_completion)
        elif not hasattr(self.cpu_executor, '_shutdown') and hasattr(self.cpu_executor, '_threads'): # 구버전 호환성
             if len(self.cpu_executor._threads) > 0 : self.cpu_executor.shutdown(wait=wait_for_completion)


        # _llm_session과 같은 리소스가 있다면 여기서 정리
        # if self._llm_session:
        #     await self._llm_session.close()
        #     self._llm_session = None

        eliar_log(EliarLogType.INFO, f"SubGPU {self.sub_gpu_id} shutdown sequence complete.", component=self.log_comp)
        self.status = "shutdown"

# --- 스탠드얼론 테스트 함수 (Flask 리스너 없이, MainGPU와의 통신 시뮬레이션) ---
async def sub_gpu_standalone_simulation_test(num_test_tasks: int = 3):
    log_comp_test = f"{SUB_GPU_COMPONENT_BASE}.StandaloneTest"
    eliar_log(EliarLogType.SYSTEM, f"--- Starting SubGPU v{SubGPU_VERSION} Standalone Simulation Test ---", component=log_comp_test)

    # 테스트용 SubGPU 인스턴스 생성
    # 실제 환경에서는 MainGPU로부터 중심 가치와 핵심 가치 목록을 전달받음
    sub_gpu_instance = SubGPUModule(
        sub_gpu_id="SimSubGPU_001",
        main_gpu_center="JESUS CHRIST",
        main_gpu_values=[cv for cv in EliarCoreValues]
    )
    
    # SubGPU의 메인 처리 루프를 백그라운드 태스크로 시작
    processing_main_task = asyncio.create_task(sub_gpu_instance.processing_loop())
    # SubGPU의 자체 개선 사이클도 별도 태스크로 (선택적)
    # improvement_cycle_task = asyncio.create_task(sub_gpu_instance.recursive_improver.periodic_self_analysis_and_reporting(sub_gpu_instance.main_gpu_center))


    # 테스트 작업 패킷들을 SubGPU에 전송
    test_queries = [
        "하나님의 사랑에 대해 더 알고 싶습니다. 성경에서는 어떻게 이야기하나요?",
        "삶에서 진리를 찾는 것이 왜 중요한가요? 예수님께서는 진리에 대해 무엇이라고 말씀하셨나요?",
        "고통과 시련 속에서 어떻게 믿음을 지킬 수 있을까요? 성경적 조언을 부탁드립니다."
    ]

    for i in range(min(num_test_tasks, len(test_queries))):
        user_input = test_queries[i]
        task_id = f"sim_task_{uuid.uuid4().hex[:6]}"
        
        sample_task_data = {
            "user_input": user_input,
            "context_data": { # MainGPU가 제공할 수 있는 맥락 정보 (예시)
                "current_conversation_id": f"conv_{uuid.uuid4().hex[:4]}",
                "user_profile_summary": "신앙에 대해 진지하게 탐구하는 사용자",
                "main_gpu_emotional_state": random.choice(["CALM_PEACEFUL", "REFLECTIVE_HOPEFUL", "EMPATHETIC_CONCERNED"]),
                "previous_interaction_summary": "사용자는 최근 '사랑'에 대한 질문을 했었음." if i > 0 else "첫 번째 질문입니다."
            },
            "main_gpu_directives": { # MainGPU가 SubGPU에 내리는 지침 (예시)
                "response_goal": "Provide a reasoned and faith-informed draft that Lumina (MainGPU) can build upon.",
                "faith_guidance": {
                    "center": sub_gpu_instance.main_gpu_center, # MainGPU의 중심 가치를 명시적으로 전달
                    "emphasize_values": [EliarCoreValues.TRUTH.name, EliarCoreValues.LOVE_COMPASSION.name],
                    "avoid_sentiments": ["judgmental", " overly dogmatic without explanation"]
                },
                "desired_output_format": "clear_logical_draft_with_supporting_points"
            }
        }
        test_packet = SubCodeThoughtPacketData(
            packet_id=task_id, timestamp=get_current_utc_iso(), source_gpu="SimMainGPU",
            target_gpu=sub_gpu_instance.sub_gpu_id, operation_type="detailed_query_processing",
            task_data=sample_task_data, result_data=None, status_info=None, error_info=None, priority=1, metadata={"test_cycle": i+1}
        )
        
        await sub_gpu_instance.enqueue_task_from_main(test_packet)
        eliar_log(EliarLogType.DEBUG, f"Test task packet {task_id} enqueued.", component=log_comp_test)

        # 결과 비동기적으로 수신 (실제 MainGPU-SubGPU 연동 시 필요)
        # 여기서는 간단히 테스트를 위해 순차적으로 결과를 기다림 (MainGPU가 이렇게 하지는 않음)
        try:
            result = await asyncio.wait_for(sub_gpu_instance.get_result_for_main(), timeout=15.0)
            if result:
                eliar_log(EliarLogType.INFO, f"Received result for task {result.get('metadata',{}).get('original_packet_id')}:", 
                          component=log_comp_test, result_preview=str(result.get("result_data",{}).get("response_draft_for_main_gpu"))[:200]+"...")
                # 결과에 포함된 신앙 정렬 피드백 출력 (MainGPU가 참고할 내용)
                if result.get("result_data", {}).get("faith_alignment_feedback"):
                    eliar_log(EliarLogType.DEBUG, "Faith Alignment Feedback from SubGPU:", 
                              component=log_comp_test, data=result["result_data"]["faith_alignment_feedback"])
            else:
                eliar_log(EliarLogType.WARN, f"No result received for task {task_id} in this check (non-blocking).", component=log_comp_test)
        except asyncio.TimeoutError:
            eliar_log(EliarLogType.ERROR, f"Timeout waiting for result of task {task_id}.", component=log_comp_test)
        
        await asyncio.sleep(random.uniform(0.5, 1.5)) # 다음 작업 전송 전 약간의 텀

    # 모든 작업이 처리될 시간을 충분히 줌
    await asyncio.sleep(5) 

    # 자체 개선 사이클 실행 요청 (테스트 목적)
    await sub_gpu_instance.recursive_improver.periodic_self_analysis_and_reporting(sub_gpu_instance.main_gpu_center)
    await asyncio.sleep(0.5) # 보고 내용 처리 시간
    if sub_gpu_instance.recursive_improver.improvement_suggestions_for_main_gpu:
         eliar_log(EliarLogType.INFO, "Final check for SubGPU Self-Improvement Suggestions for MainGPU:", 
                      component=log_comp_test, suggestions=sub_gpu_instance.recursive_improver.improvement_suggestions_for_main_gpu)

    # SubGPU 종료
    await sub_gpu_instance.shutdown(wait_for_completion=True)
    
    # 메인 처리 루프 태스크 취소 (이미 종료 신호를 보냈으므로 정상 종료될 것)
    if processing_main_task and not processing_main_task.done():
        processing_main_task.cancel()
        try:
            await processing_main_task
        except asyncio.CancelledError:
            eliar_log(EliarLogType.INFO, "SubGPU processing task was cancelled as part of shutdown.", component=log_comp_test)
    
    # if improvement_cycle_task and not improvement_cycle_task.done(): # 자체 개선 사이클 태스크도 종료
    #     improvement_cycle_task.cancel()
    #     try:
    #         await improvement_cycle_task
    #     except asyncio.CancelledError:
    #         eliar_log(EliarLogType.INFO, "SubGPU improvement cycle task cancelled.", component=log_comp_test)


    eliar_log(EliarLogType.SYSTEM, "--- SubGPU Standalone Simulation Test Finished ---", component=log_comp_test)


if __name__ == '__main__':
    # 로거 초기화 (애플리케이션 시작 시점)
    # 메인 프로그램의 비동기 컨텍스트 내에서 initialize_eliar_logger()를 호출해야 함
    # asyncio.run() 내부에서 호출되도록 수정
    async def run_main_with_logger():
        await initialize_eliar_logger() # eliar_common의 비동기 로거 초기화
        try:
            await sub_gpu_standalone_simulation_test(num_test_tasks=2) # 테스트 작업 수 조정 가능
        except KeyboardInterrupt:
            eliar_log(EliarLogType.WARN, "SubGPU standalone test interrupted by user.", component=f"{SUB_GPU_COMPONENT_BASE}.TestRunner")
        except Exception as e_run_main:
            eliar_log(EliarLogType.CRITICAL, "Error running SubGPU standalone test.", 
                      component=f"{SUB_GPU_COMPONENT_BASE}.TestRunner", error=e_run_main, full_traceback_info=traceback.format_exc())
        finally:
            await shutdown_eliar_logger() # eliar_common의 비동기 로거 종료

    asyncio.run(run_main_with_logger())
