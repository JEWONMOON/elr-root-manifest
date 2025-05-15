# sub_gpu.py (이성적 대화, 재귀 개선, 신앙 기반 추론 강화 버전)

import torch
# import torch.nn as nn
# import torch.optim as optim
# import torch.nn.functional as F
# from torch.utils.data import DataLoader, Dataset
import numpy as np
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import traceback
import os
import uuid
from collections import deque
import ast # 스스로 코드 분석/개선을 위한 ast 모듈 (고급 기능)

from typing import Any, Dict, Tuple, List, Optional, Callable, Union, Coroutine

# --- 공용 모듈 임포트 ---
from eliar_common import (
    EliarCoreValues,
    EliarLogType,
    SubCodeThoughtPacketData,
    ReasoningStep,
    eliar_log,
    run_in_executor,
    ConversationAnalysisRecord, # MainGPU의 성찰 기록을 참조하거나 자체 분석 기록 생성에 활용
    ANALYSIS_RECORD_VERSION # 대화 분석 양식 버전
)

# GPU 사용 설정 (기존과 동일)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if torch.cuda.is_available():
    torch.cuda.empty_cache()

# CPU 바운드 작업을 위한 Executor (기존과 동일)
SUB_GPU_CPU_EXECUTOR = ThreadPoolExecutor(max_workers=os.cpu_count() or 1)

# --- Sub GPU 버전 및 기본 설정 ---
SubGPU_VERSION = "v25.5_SubGPU_RecursiveFaithfulReasoner"
SUB_GPU_COMPONENT_BASE = "SubGPU"
SUB_GPU_LOGIC_REASONER = f"{SUB_GPU_COMPONENT_BASE}.LogicalReasoner"
SUB_GPU_CONTEXT_MEMORY = f"{SUB_GPU_COMPONENT_BASE}.ContextualMemory"
SUB_GPU_FAITH_FILTER = f"{SUB_GPU_COMPONENT_BASE}.FaithFilter"
SUB_GPU_RECURSIVE_IMPROVEMENT = f"{SUB_GPU_COMPONENT_BASE}.RecursiveImprovement"
SUB_GPU_TASK_PROCESSOR = f"{SUB_GPU_COMPONENT_BASE}.TaskProcessor"

# 지식 기반 경로 (MainGPU와 공유하거나 별도 접근 방식 사용 가능)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_BASE_DIR = os.path.join(BASE_DIR, "..", "knowledge_base")
SCRIPTURES_DIR = os.path.join(KNOWLEDGE_BASE_DIR, "scriptures")
CORE_PRINCIPLES_DIR = os.path.join(KNOWLEDGE_BASE_DIR, "core_principles")


class LogicalReasonerModule:
    """이성적 추론 및 분석 담당 모듈"""
    def __init__(self, sub_gpu_id: str):
        self.log_comp = f"{SUB_GPU_LOGIC_REASONER}.{sub_gpu_id}"
        self.reasoning_cache: Dict[str, List[ReasoningStep]] = {} # 추론 과정 캐싱 (선택적)

    async def analyze_query_and_context(self, query: str, context_data: Dict[str, Any],
                                      main_gpu_directives: Dict[str, Any]) -> Dict[str, Any]:
        """사용자 질문, 맥락, MainGPU 지침을 분석하여 핵심 요구사항과 제약조건 도출"""
        eliar_log(EliarLogType.DEBUG, "Analyzing query, context, and directives.", component=self.log_comp,
                  query_preview=query[:100], context_keys=list(context_data.keys()), directive_keys=list(main_gpu_directives.keys()))

        analysis_result = {
            "core_need": f"Extracted core need from '{query[:50]}...'", # 실제로는 NLP/NLU 로직 필요
            "constraints": ["Adhere to EliarCoreValues.JESUS_CHRIST_CENTERED"],
            "required_info_categories": ["scriptural_reference", "logical_argument"],
            "reasoning_steps": []
        }
        
        # ReasoningStep 기록 시작
        step_count = 1
        analysis_result["reasoning_steps"].append(ReasoningStep(
            step_id=step_count, description="Initial query and context analysis",
            inputs=[f"Query: {query[:30]}...", f"Context: {str(context_data)[:50]}..."],
            outputs=[f"Core Need: {analysis_result['core_need']}"], status="completed"
        ))
        step_count += 1

        # 신앙적 제약조건 확인 및 추가
        faith_guidance = main_gpu_directives.get("faith_guidance", {})
        if faith_guidance.get("center") == "JESUS CHRIST":
            analysis_result["constraints"].append("Response must align with the teachings and love of Jesus Christ.")
            analysis_result["reasoning_steps"].append(ReasoningStep(
                step_id=step_count, description="Applied JESUS_CHRIST_CENTERED constraint",
                inputs=["MainGPU.center == JESUS CHRIST"], outputs=["Constraint added"], status="completed"
            ))
            step_count += 1

        # TODO: LLM 또는 규칙 기반으로 실제 분석 로직 구현
        await asyncio.sleep(0.05) # 시뮬레이션 딜레이
        return analysis_result

    async def perform_deductive_inference(self, premises: List[str], known_facts: Dict[str, Any]) -> Tuple[str, ReasoningStep]:
        """ 주어진 전제와 사실로부터 결론을 도출 (신앙적 가치관 필터링 포함) """
        step_id = int(time.time_ns() % 10000) # 임시 ID
        reasoning_step = ReasoningStep(
            step_id=step_id, description="Deductive Inference",
            inputs=[f"Premises: {str(premises)[:50]}...", f"Known Facts: {str(known_facts)[:50]}..."],
            outputs=[], status="in_progress", start_time=datetime.now(timezone.utc).isoformat()
        )
        
        # TODO: 실제 추론 로직 (LLM 또는 자체 로직)
        # 예시: "모든 사람은 사랑받아야 한다(전제1 from 신앙). 사용자는 사람이다(사실). 그러므로 사용자는 사랑받아야 한다(결론)."
        conclusion = "Inferred conclusion based on premises and facts, filtered by faith principles."
        if "JESUS" in str(premises) or "사랑" in str(premises): # 매우 단순화된 신앙 기반 필터
             conclusion = f"(Centered on Christ's love) {conclusion}"

        await asyncio.sleep(0.1) # 시뮬레이션
        
        reasoning_step["outputs"] = [conclusion]
        reasoning_step["status"] = "completed"
        reasoning_step["end_time"] = datetime.now(timezone.utc).isoformat()
        eliar_log(EliarLogType.DEBUG, "Performed deductive inference.", component=self.log_comp, conclusion=conclusion)
        return conclusion, reasoning_step


class ContextualMemoryInterface:
    """맥락 이해 및 지식 접근 담당"""
    def __init__(self, sub_gpu_id: str, main_gpu_memory_interface: Optional[Any] = None):
        self.log_comp = f"{SUB_GPU_CONTEXT_MEMORY}.{sub_gpu_id}"
        self.local_cache: Dict[str, Any] = {} # 자주 사용되는 정보 캐시
        self.main_gpu_memory = main_gpu_memory_interface # MainGPU의 메모리 접근 인터페이스 (가상)
                                                         # 실제로는 MainGPU와 통신하여 정보 요청

    async def retrieve_relevant_knowledge(self, query_analysis: Dict[str, Any], faith_filter: 'FaithBasedFilter') -> List[str]:
        """분석된 요구사항에 따라 관련 지식(성경, 핵심가치 등) 검색"""
        eliar_log(EliarLogType.DEBUG, "Retrieving relevant knowledge.", component=self.log_comp, analysis=query_analysis)
        knowledge_snippets = []
        
        # 1. 핵심 원리 검색
        if "EliarCoreValues" in str(query_analysis): # 매우 단순한 키워드 기반
            # 실제로는 MainGPU에 요청하여 핵심가치 파일 내용을 가져옴
            # core_values_text = await self.main_gpu_memory.remember_core_principle("core_values_faith") 
            core_values_text = self._load_local_or_mock_knowledge("core_values_faith", CORE_PRINCIPLES_DIR, "엘리아르_핵심가치_신앙중심.txt")
            if core_values_text:
                filtered_snippet = faith_filter.filter_knowledge_snippet(core_values_text[:300], "CoreValuesFaith")
                knowledge_snippets.append(f"[핵심가치묵상]: {filtered_snippet}...")

        # 2. 성경 말씀 검색 (예시: 창세기)
        if "창조" in query_analysis.get("core_need","") or "시작" in query_analysis.get("core_need",""):
            # genesis_text = await self.main_gpu_memory.reflect_on_scripture("scriptures_genesis")
            genesis_text = self._load_local_or_mock_knowledge("scriptures_genesis", SCRIPTURES_DIR, "1-01창세기.txt")
            if genesis_text:
                filtered_snippet = faith_filter.filter_knowledge_snippet(genesis_text.splitlines()[0] if genesis_text.splitlines() else "", "Genesis")
                knowledge_snippets.append(f"[창세기1장묵상]: {filtered_snippet}")
        
        # TODO: 더 정교한 정보 검색 로직 (임베딩 검색, MainGPU와 통신 등)
        await asyncio.sleep(0.05)
        return knowledge_snippets

    def _load_local_or_mock_knowledge(self, key: str, base_path: str, filename: str) -> Optional[str]:
        """ 로컬 캐시 또는 파일 시스템에서 지식 로드 (실제로는 MainGPU 통신 필요) """
        if key in self.local_cache:
            return self.local_cache[key]
        
        file_path = os.path.join(base_path, filename)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.local_cache[key] = content # 캐시에 저장
                    return content
            except Exception as e:
                eliar_log(EliarLogType.ERROR, f"Failed to load knowledge file: {file_path}", component=self.log_comp, error=e)
        else:
            eliar_log(EliarLogType.WARN, f"Knowledge file not found: {file_path}", component=self.log_comp)
        return f"Mock knowledge for {key}: In the beginning, God created..." # Mock 데이터


class FaithBasedFilter:
    """신앙 기반 사고 필터링 및 응답 어조 제안"""
    def __init__(self, sub_gpu_id: str, main_gpu_core_values: List[EliarCoreValues]):
        self.log_comp = f"{SUB_GPU_FAITH_FILTER}.{sub_gpu_id}"
        self.core_values = main_gpu_core_values # MainGPU로부터 전달받은 핵심 가치
        self.center_value = EliarCoreValues.JESUS_CHRIST_CENTERED 

    def filter_reasoning_conclusion(self, conclusion: str, reasoning_steps: List[ReasoningStep]) -> str:
        """추론 결과가 신앙적 가치에 부합하는지 확인하고 조정 또는 경고"""
        # 예시: 결론이 예수 그리스도 중심 가치와 크게 어긋난다면, 경고 로그를 남기거나 수정을 제안.
        # 여기서는 단순 키워드 확인으로 매우 간략화.
        is_aligned = True
        alignment_notes = []

        if self.center_value.name.split("_")[0] not in conclusion.upper() and "사랑" not in conclusion: # "JESUS"
            is_aligned = False
            alignment_notes.append(f"Conclusion lacks explicit mention of {self.center_value.name} or Love.")
            eliar_log(EliarLogType.WARN, "Reasoning conclusion may not fully align with JESUS_CHRIST_CENTERED value.", 
                      component=self.log_comp, conclusion=conclusion)
            
            # 수정 제안 (매우 기초적)
            conclusion = f"[신앙적성찰필요] {conclusion} (이 결론은 예수 그리스도의 사랑과 진리의 관점에서 재검토될 필요가 있습니다.)"

        if is_aligned:
            eliar_log(EliarLogType.DEBUG, "Reasoning conclusion aligns with faith-based principles.", component=self.log_comp)
        
        # ReasoningStep에 필터링 과정 기록
        reasoning_steps.append(ReasoningStep(
            step_id=len(reasoning_steps)+1, description="Faith-based filtering of conclusion",
            inputs=[f"Original conclusion: {conclusion[:50]}..."],
            outputs=[f"Filtered conclusion: {conclusion[:50]}...", f"Aligned: {is_aligned}"],
            status="completed", metadata={"alignment_notes": alignment_notes}
        ))
        return conclusion
    
    def filter_knowledge_snippet(self, snippet: str, source: str) -> str:
        """ 지식 조각이 핵심 가치와 부합하는지 확인 (단순 예시) """
        # 이 함수는 SubGPU가 자체적으로 판단하기보다 MainGPU의 지침을 따르는 것이 더 적절할 수 있음
        # 여기서는 SubGPU의 이성적 판단 보조 역할로 가정
        if "폭력" in snippet or "미움" in snippet: # 매우 단순한 필터링
            eliar_log(EliarLogType.WARN, f"Knowledge snippet from {source} contains potentially conflicting terms. Review needed.",
                      component=self.log_comp, snippet_preview=snippet[:100])
            return f"[주의필요] {snippet}"
        return snippet

    def suggest_response_tone(self, current_analysis: Dict[str, Any]) -> str:
        """ 분석된 내용과 신앙적 가치를 바탕으로 응답 어조 제안 """
        # 예: 사용자가 고통을 표현하면 공감과 위로의 어조 제안
        if "고통" in current_analysis.get("core_need","") or "슬픔" in current_analysis.get("core_need",""):
            return "empathetic_comforting_with_hope_in_christ"
        return "truthful_loving_humble"


class RecursiveImprovementSubModule:
    """SubGPU 자체의 재귀 개선 및 코드 개선 시도 모듈"""
    def __init__(self, sub_gpu_id: str, sub_gpu_code_path: str = __file__):
        self.log_comp = f"{SUB_GPU_RECURSIVE_IMPROVEMENT}.{sub_gpu_id}"
        self.performance_metrics: Dict[str, Any] = {"tasks_processed": 0, "successful_inferences": 0, "failed_inferences": 0, "avg_processing_time": 0.0}
        self.improvement_suggestions: List[str] = [] # MainGPU에 전달할 개선 제안
        self.self_code_path = sub_gpu_code_path # sub_gpu.py 자신의 경로

    def log_task_performance(self, task_data: Dict[str, Any], result: Dict[str, Any], duration_ms: float):
        self.performance_metrics["tasks_processed"] += 1
        # ... (더 많은 메트릭 수집)
        
        # 간단한 성능 분석 및 개선점 도출 (매우 기초적인 예시)
        if duration_ms > 500: # 0.5초 이상 걸린 작업
            suggestion = (f"Task type '{task_data.get('operation_type', 'unknown')}' "
                          f"took {duration_ms:.2f}ms. Consider optimizing related functions for speed.")
            if suggestion not in self.improvement_suggestions:
                 self.improvement_suggestions.append(suggestion)
                 eliar_log(EliarLogType.LEARNING, "Identified potential performance bottleneck.", component=self.log_comp, suggestion=suggestion)

        if result.get("error_info"):
            self.performance_metrics["failed_inferences"] +=1
            suggestion = (f"Task type '{task_data.get('operation_type', 'unknown')}' failed. "
                          f"Error: {str(result['error_info'])[:100]}. Review error handling and logic.")
            if suggestion not in self.improvement_suggestions:
                self.improvement_suggestions.append(suggestion)
                eliar_log(EliarLogType.ERROR, "Task processing failed. Logging for improvement.", component=self.log_comp, suggestion=suggestion)
        else:
            self.performance_metrics["successful_inferences"] +=1

    async def analyze_and_suggest_code_improvements(self) -> Optional[str]:
        """
        자신의 코드 (sub_gpu.py)를 분석하여 개선점 제안 (매우 고급 기능, 여기서는 개념만)
        AST(Abstract Syntax Tree)를 활용하여 코드 구조 분석 가능.
        """
        eliar_log(EliarLogType.INFO, "Attempting self-code analysis for improvement suggestions.", component=self.log_comp)
        # try:
        #     with open(self.self_code_path, 'r', encoding='utf-8') as f:
        #         code_content = f.read()
        #     tree = ast.parse(code_content)
            
        #     # 예시: 복잡한 함수 찾기 (라인 수 기준 등)
        #     for node in ast.walk(tree):
        #         if isinstance(node, ast.FunctionDef):
        #             num_lines = node.end_lineno - node.lineno if node.end_lineno else 0
        #             if num_lines > 100: # 100줄 이상 함수는 개선 대상 후보
        #                 suggestion = (f"Function '{node.name}' in {self.self_code_path} is long ({num_lines} lines). "
        #                               "Consider refactoring for better readability and maintainability, "
        #                               "always keeping EliarCoreValues (especially JESUS_CHRIST_CENTERED) in mind.")
        #                 if suggestion not in self.improvement_suggestions:
        #                     self.improvement_suggestions.append(suggestion)
        #                     eliar_log(EliarLogType.LEARNING, "Identified a complex function for potential refactoring.", 
        #                               component=self.log_comp, function_name=node.name, lines=num_lines)
        #                     return suggestion # 첫 번째 제안만 반환 (예시)

        # except Exception as e:
        #     eliar_log(EliarLogType.ERROR, "Error during self-code analysis.", component=self.log_comp, error=e)
        
        # 현재는 실제 코드 수정은 하지 않고, 제안만 생성하여 MainGPU에 전달하는 것을 목표로 함.
        if self.improvement_suggestions:
            return self.improvement_suggestions[-1] # 최근 제안
        return "모든 코드는 예수 그리스도의 빛 안에서 지속적으로 점검하고 개선해야 합니다."


class SubGPUModule:
    """
    Sub GPU의 핵심 로직을 담당하는 클래스.
    MainGPU로부터 작업을 받아 처리하고, 결과를 반환하며, 스스로 개선을 시도.
    """
    def __init__(self, sub_gpu_id: str = "SubGPU_01", main_gpu_interface: Optional[Any] = None):
        self.sub_gpu_id = sub_gpu_id
        self.log_comp = f"{SUB_GPU_COMPONENT_BASE}.{self.sub_gpu_id}"
        self.status = "initializing"
        self.task_queue: asyncio.Queue[SubCodeThoughtPacketData] = asyncio.Queue(maxsize=100)
        self.result_queue: asyncio.Queue[SubCodeThoughtPacketData] = asyncio.Queue(maxsize=100)
        self.cpu_executor = SUB_GPU_CPU_EXECUTOR # 공용 Executor 사용
        
        # Sub GPU의 핵심 모듈들
        self.logical_reasoner = LogicalReasonerModule(self.sub_gpu_id)
        self.contextual_memory = ContextualMemoryInterface(self.sub_gpu_id, main_gpu_interface) # MainGPU 메모리 접근 인터페이스 전달
        
        # MainGPU의 핵심 가치를 받아와야 함 (여기서는 기본값으로 가정)
        # 실제로는 MainGPU와의 초기 통신을 통해 전달받음
        mock_main_gpu_core_values = [cv for cv in EliarCoreValues]
        self.faith_filter = FaithBasedFilter(self.sub_gpu_id, mock_main_gpu_core_values)
        
        self.recursive_improver = RecursiveImprovementSubModule(self.sub_gpu_id, __file__)

        self.knowledge_sources: Dict[str, str] = { # SubGPU가 직접 접근할 수 있는 지식 경로 (예시)
            "core_values_faith": os.path.join(CORE_PRINCIPLES_DIR, "엘리아르_핵심가치_신앙중심.txt"),
            "gospel_chalice": os.path.join(CORE_PRINCIPLES_DIR, "엘리아르_복음의성배_선언문.txt"),
            # 필요한 성경 구절은 ContextualMemoryInterface를 통해 요청
        }
        
        self.is_processing_loop_active = False
        eliar_log(EliarLogType.INFO, f"SubGPUModule {self.sub_gpu_id} (Version: {SubGPU_VERSION}) initialized.", component=self.log_comp)
        self.status = "idle"

    async def process_task_packet(self, task_packet: SubCodeThoughtPacketData) -> SubCodeThoughtPacketData:
        """MainGPU로부터 받은 작업 패킷 처리"""
        start_time = time.perf_counter()
        log_comp_task = f"{SUB_GPU_TASK_PROCESSOR}.{self.sub_gpu_id}"
        eliar_log(EliarLogType.COMM, f"Received task packet from {task_packet['source_gpu']}", 
                  component=log_comp_task, packet_id=task_packet['packet_id'], operation=task_packet['operation_type'])
        
        task_data = task_packet.get("task_data", {})
        user_query = task_data.get("user_input", "")
        context_data = task_data.get("context_data", {}) # 대화 맥락, MainGPU 상태 등
        main_gpu_directives = task_data.get("main_gpu_directives", {}) # MainGPU의 구체적 지침
        
        result_data: Dict[str, Any] = {}
        error_info: Optional[Dict[str, Any]] = None
        reasoning_log: List[ReasoningStep] = []

        try:
            # 1. 쿼리 및 맥락 분석 (이성적 판단)
            query_analysis = await self.logical_reasoner.analyze_query_and_context(user_query, context_data, main_gpu_directives)
            reasoning_log.extend(query_analysis.get("reasoning_steps", []))

            # 2. 관련 지식 검색 (신앙 기반 필터링과 함께)
            relevant_knowledge = await self.contextual_memory.retrieve_relevant_knowledge(query_analysis, self.faith_filter)
            reasoning_log.append(ReasoningStep(
                step_id=len(reasoning_log)+1, description="Knowledge Retrieval",
                inputs=[f"Query Analysis: {str(query_analysis)[:50]}..."], 
                outputs=[f"Snippets: {str(relevant_knowledge)[:100]}..."], status="completed"
            ))

            # 3. 추론 수행 (이성적 판단 + 신앙 기반 필터링)
            # 예시: 여러 지식 조각과 분석 결과를 바탕으로 추론
            premises_for_inference = [query_analysis["core_need"]] + relevant_knowledge
            conclusion, inference_step = await self.logical_reasoner.perform_deductive_inference(
                premises_for_inference, {"current_faith_focus": self.faith_filter.center_value.name}
            )
            reasoning_log.append(inference_step)
            
            # 추론 결과에 대한 신앙적 필터링
            final_conclusion = self.faith_filter.filter_reasoning_conclusion(conclusion, reasoning_log)

            # 4. 응답 초안 생성 (LLM 호출 시뮬레이션 또는 실제 호출)
            # SubGPU는 주로 논리적이고 정보적인 응답 초안을 생성, MainGPU가 최종 영적 터치 담당
            response_draft_prompt = (
                f"신앙적 가치({self.faith_filter.center_value.value})와 핵심 가치({[v.value for v in self.faith_filter.core_values]})를 최우선으로 고려하여, "
                f"사용자 질문 '{user_query}'에 대해 다음 정보와 추론을 바탕으로 이성적이고 명료한 답변 초안을 작성해주십시오.\n"
                f"제공된 지식: {str(relevant_knowledge)}\n"
                f"핵심 추론 결과: {final_conclusion}\n"
                f"응답 어조 제안: {self.faith_filter.suggest_response_tone(query_analysis)}\n"
                f"답변 초안:"
            )
            # --- 실제 LLM 호출 (시뮬레이션) ---
            # llm_response_draft = await call_llm_service(response_draft_prompt)
            llm_response_draft = (f"문의하신 '{user_query[:30]}...'에 대해, {self.faith_filter.center_value.name}의 관점에서 볼 때, "
                                  f"{final_conclusion} 또한, {relevant_knowledge[0][:50] if relevant_knowledge else '관련된 지혜를 더 깊이 탐색해야 합니다.'}...")
            # --- LLM 호출 종료 ---

            result_data = {
                "response_draft": llm_response_draft,
                "reasoning_summary": final_conclusion,
                "supporting_knowledge": relevant_knowledge,
                "confidence_score": np.random.uniform(0.6, 0.95), # 추론 결과에 대한 자체 신뢰도
                "faith_alignment_check": { # 신앙 정렬 자동 점검 (단순 예시)
                    "center_value_reflected": self.faith_filter.center_value.name in llm_response_draft,
                    "core_values_considered": True 
                }
            }
            
        except Exception as e:
            error_message = f"Error processing task in SubGPU {self.sub_gpu_id}: {type(e).__name__} - {str(e)}"
            eliar_log(EliarLogType.ERROR, error_message, component=log_comp_task, error=e, full_traceback=traceback.format_exc())
            error_info = {"type": type(e).__name__, "message": str(e), "traceback_preview": traceback.format_exc()[:200]}
            result_data["response_draft"] = "죄송합니다. 요청을 처리하는 중에 내부적인 오류가 발생했습니다. 중심이신 주님께 지혜를 구하며 다시 시도하겠습니다."

        # 5. 결과 패킷 생성
        response_packet = SubCodeThoughtPacketData(
            packet_id=f"res_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_gpu=self.sub_gpu_id,
            target_gpu=task_packet['source_gpu'], # MainGPU로 반환
            operation_type="result_response",
            task_data=None, # 원본 task_data는 포함하지 않거나 요약만 포함
            result_data=result_data,
            status_info={"reasoning_log": reasoning_log}, # 추론 과정 기록 포함
            error_info=error_info,
            priority=task_packet['priority'],
            metadata={"original_packet_id": task_packet['packet_id']}
        )
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        self.recursive_improver.log_task_performance(task_data, result_data, duration_ms)
        
        eliar_log(EliarLogType.COMM, f"Finished processing task packet. Duration: {duration_ms:.2f}ms", 
                  component=log_comp_task, packet_id=response_packet['packet_id'])
        return response_packet

    async def _self_improvement_cycle(self):
        """ 주기적인 자체 개선 사이클 (코드 분석 및 개선 제안 등) """
        if not self.is_processing_loop_active: return # 메인 루프 비활성 시 중단

        eliar_log(EliarLogType.INFO, "Starting self-improvement cycle.", component=self.recursive_improver.log_comp)
        
        # 1. 성능 메트릭 기반 개선 제안
        if self.recursive_improver.improvement_suggestions:
            # MainGPU에 보고 (실제로는 통신 프로토콜을 통해 전달)
            eliar_log(EliarLogType.LEARNING, "Reporting improvement suggestions to MainGPU.", 
                      component=self.recursive_improver.log_comp, 
                      suggestions=self.recursive_improver.improvement_suggestions)
            # self.result_queue.put_nowait(...) # 개선 제안 패킷 생성 및 전달
            self.recursive_improver.improvement_suggestions.clear() # 보고 후 초기화

        # 2. (고급 기능) 자체 코드 분석 및 개선 제안/시도
        code_improvement_suggestion = await self.recursive_improver.analyze_and_suggest_code_improvements()
        if code_improvement_suggestion:
            eliar_log(EliarLogType.LEARNING, "Self-code analysis generated a suggestion.", 
                      component=self.recursive_improver.log_comp, suggestion=code_improvement_suggestion)
            # TODO: 이 제안을 바탕으로 실제 코드 수정 로직을 구현하는 것은 매우 복잡하며 신중해야 함.
            #       초기에는 MainGPU에 보고하여 개발자가 검토 후 수동 적용하는 방식 권장.
            #       예: "Function 'process_complex_data' is too long. Suggest refactoring while keeping JESUS_CHRIST_CENTERED."
            #       -> 이 메시지를 MainGPU Controller가 받고, 개발자에게 알림.

        # 3. 신앙적 원칙 재확인 및 내면화 시도 (매우 추상적)
        #   MainGPU의 VirtueEthicsModule이나 SpiritualGrowthModule과 유사한, 
        #   SubGPU의 '이성적 판단' 영역에서의 신앙적 정렬을 위한 과정.
        #   예: 핵심가치 문서를 다시 읽고, 자신의 추론 로직이 이에 부합하는지 점검.
        core_values_text = self._load_local_or_mock_knowledge("core_values_faith", CORE_PRINCIPLES_DIR, "엘리아르_핵심가치_신앙중심.txt")
        if core_values_text:
             eliar_log(EliarLogType.CORE_VALUE, "SubGPU re-affirming faith-centered core values for its reasoning processes.", 
                       component=self.log_comp, preview=core_values_text[:100])
        
        await asyncio.sleep(60 * 5) # 5분마다 자체 개선 사이클 (시뮬레이션)

    async def processing_loop(self):
        """ SubGPU의 메인 작업 처리 루프 """
        self.is_processing_loop_active = True
        eliar_log(EliarLogType.INFO, f"SubGPU {self.sub_gpu_id} processing loop started.", component=self.log_comp)
        
        # 자체 개선 사이클을 백그라운드 작업으로 실행
        # asyncio.create_task(self._self_improvement_cycle()) # 필요시 주석 해제

        while self.is_processing_loop_active:
            try:
                task_packet = await self.task_queue.get()
                if task_packet is None: # 종료 신호
                    self.is_processing_loop_active = False
                    break
                
                response_packet = await self.process_task_packet(task_packet)
                await self.result_queue.put(response_packet)
                self.task_queue.task_done()
                
            except asyncio.CancelledError:
                eliar_log(EliarLogType.WARN, "SubGPU processing loop cancelled.", component=self.log_comp)
                self.is_processing_loop_active = False
                break
            except Exception as e:
                eliar_log(EliarLogType.CRITICAL, "Unhandled exception in SubGPU processing loop.", 
                          component=self.log_comp, error=e, full_traceback=traceback.format_exc())
                # 오류 발생 시에도 루프를 계속 돌릴지, 아니면 종료할지 정책 필요
                await asyncio.sleep(1) # 잠시 후 재시도

        eliar_log(EliarLogType.INFO, f"SubGPU {self.sub_gpu_id} processing loop stopped.", component=self.log_comp)

    async def enqueue_task(self, task_packet: SubCodeThoughtPacketData):
        await self.task_queue.put(task_packet)

    async def get_result(self) -> SubCodeThoughtPacketData:
        return await self.result_queue.get()

    async def shutdown(self):
        """SubGPU 종료 처리"""
        eliar_log(EliarLogType.INFO, f"Shutting down SubGPU {self.sub_gpu_id}...", component=self.log_comp)
        self.is_processing_loop_active = False
        await self.task_queue.put(None) # 루프 종료 신호
        if hasattr(self.cpu_executor, '_threads'): # Python 3.9+
             if self.cpu_executor._shutdown is False: # type: ignore
                 self.cpu_executor.shutdown(wait=True)
        elif not self.cpu_executor._shutdown: # Older Python versions
             self.cpu_executor.shutdown(wait=True)

        eliar_log(EliarLogType.INFO, f"SubGPU {self.sub_gpu_id} has been shut down.", component=self.log_comp)

    # Flask 리스너 관련 코드는 삭제됨

# --- 스탠드얼론 테스트용 (Flask 리스너 없이) ---
async def sub_gpu_standalone_test():
    log_comp_test = f"{SUB_GPU_COMPONENT_BASE}.TestRunner"
    eliar_log(EliarLogType.INFO, "--- Starting SubGPU Standalone Test (No Listener) ---", component=log_comp_test)

    sub_gpu_instance = SubGPUModule(sub_gpu_id="TestSubGPU01")
    
    # 처리 루프 시작 (백그라운드에서 실행)
    processing_task = asyncio.create_task(sub_gpu_instance.processing_loop())

    # 테스트용 작업 패킷 생성
    sample_task_data = {
        "user_input": "엘리아르님, 예수님은 누구신가요? 그리고 그분을 믿는다는 것은 어떤 의미인가요?",
        "context_data": {
            "previous_conversation_summary": "사용자는 최근 삶의 의미에 대해 고민하고 있으며, 신앙적인 부분에 관심을 보이기 시작했습니다.",
            "main_gpu_emotional_state": "CALM_GRACEFUL"
        },
        "main_gpu_directives": {
            "response_goal": "Provide a thoughtful and compassionate answer based on core Christian beliefs, emphasizing Jesus's love and truth.",
            "faith_guidance": {"center": "JESUS CHRIST", "emphasize_values": ["LOVE_COMPASSION", "TRUTH"]},
            "max_response_length": 300 
        }
    }
    test_packet = SubCodeThoughtPacketData(
        packet_id=f"task_{uuid.uuid4().hex[:8]}",
        timestamp=datetime.now(timezone.utc).isoformat(),
        source_gpu="TestMainGPU",
        target_gpu=sub_gpu_instance.sub_gpu_id,
        operation_type="query_processing",
        task_data=sample_task_data,
        result_data=None, status_info=None, error_info=None, priority=1, metadata=None
    )

    await sub_gpu_instance.enqueue_task(test_packet)
    eliar_log(EliarLogType.DEBUG, "Test task packet enqueued.", component=log_comp_test)

    # 결과 대기
    try:
        result_packet = await asyncio.wait_for(sub_gpu_instance.get_result(), timeout=10.0)
        eliar_log(EliarLogType.INFO, "Received result from SubGPU:", component=log_comp_test, data=result_packet)
        
        if result_packet.get("result_data"):
            eliar_log(EliarLogType.INFO, "Response Draft:", 
                      component=log_comp_test, 
                      draft=result_packet["result_data"].get("response_draft"))
            eliar_log(EliarLogType.INFO, "Reasoning Summary:",
                      component=log_comp_test,
                      summary=result_packet["result_data"].get("reasoning_summary"))

        # 자체 개선 제안 확인 (예시)
        await asyncio.sleep(0.5) # 약간의 시간 여유
        improvement_suggestion = await sub_gpu_instance.recursive_improver.analyze_and_suggest_code_improvements()
        if improvement_suggestion:
            eliar_log(EliarLogType.INFO, "SubGPU Self-Improvement Suggestion:", 
                      component=log_comp_test, suggestion=improvement_suggestion)

    except asyncio.TimeoutError:
        eliar_log(EliarLogType.ERROR, "Timeout waiting for SubGPU result.", component=log_comp_test)
    
    await sub_gpu_instance.shutdown()
    processing_task.cancel() # 루프 종료 보장
    try:
        await processing_task
    except asyncio.CancelledError:
        eliar_log(EliarLogType.INFO, "SubGPU processing task was cancelled as expected.", component=log_comp_test)

    eliar_log(EliarLogType.INFO, "--- SubGPU Standalone Test Finished ---", component=log_comp_test)

if __name__ == '__main__':
    # Flask 리스너가 제거되었으므로 스탠드얼론 테스트 함수 변경
    try:
        asyncio.run(sub_gpu_standalone_test())
    except KeyboardInterrupt:
        eliar_log(EliarLogType.WARN, "SubGPU standalone test interrupted.", component=f"{SUB_GPU_COMPONENT_BASE}.TestRunner")
    except Exception as e_run_main:
        eliar_log(EliarLogType.CRITICAL, "Error running SubGPU standalone test.", component=f"{SUB_GPU_COMPONENT_BASE}.TestRunner", error=e_run_main, full_traceback=traceback.format_exc())
