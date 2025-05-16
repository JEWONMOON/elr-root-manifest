# sub_gpu.py (추론 기능 강화, LLM 제외, 내부 재귀 개선 적용 버전)

import torch
import numpy as np
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import traceback
import os
import uuid
import json
from collections import deque
from functools import lru_cache
import ast # 코드 분석용

from typing import Any, Dict, Tuple, List, Optional, Callable, Union, Coroutine

# --- 공용 모듈 임포트 ---
from eliar_common import (
    EliarCoreValues, EliarLogType,
    SubCodeThoughtPacketData, ReasoningStep,
    eliar_log, initialize_eliar_logger_common as initialize_eliar_logger, # 이름 변경된 로거 사용
    shutdown_eliar_logger_common as shutdown_eliar_logger,
    run_in_executor_common as run_in_executor, # 이름 변경된 executor 사용
    ANALYSIS_RECORD_VERSION_COMMON as ANALYSIS_RECORD_VERSION, # 버전 상수 이름 변경
    # ConversationAnalysisRecord 등은 MainGPU가 주로 다루고, SubGPU는 필요시 요약 참조
    # 경로 상수도 eliar_common에서 직접 참조 (KNOWLEDGE_BASE_DIR_COMMON 등)
    KNOWLEDGE_BASE_DIR_COMMON, CORE_PRINCIPLES_DIR_COMMON, SCRIPTURES_DIR_COMMON, CUSTOM_KNOWLEDGE_DIR_COMMON
)

# GPU 사용 설정
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# 시작 시 로그는 메인 애플리케이션의 로거 초기화 이후에 eliar_log 사용 권장

# CPU 바운드 작업을 위한 공유 Executor
SUB_GPU_CPU_EXECUTOR = ThreadPoolExecutor(max_workers=(os.cpu_count() or 1) * 2 + 2) # 워커 수 약간 더 증가

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
    def __init__(self, sub_gpu_id: str, memory_accessor: Callable[[str, str], Coroutine[Any, Any, Optional[Union[str, Dict]]]]):
        self.log_comp = f"{SUB_GPU_LOGIC_REASONER}.{sub_gpu_id}"
        self.memory_accessor = memory_accessor

    def _create_cache_key(self, *args) -> str:
        """ 다양한 인자로부터 안정적인 캐시 키 문자열 생성 """
        return json.dumps(args, sort_keys=True, ensure_ascii=False)

    @lru_cache(maxsize=128)
    async def analyze_query_and_context(self, query: str, context_str: str, directives_str: str) -> Dict[str, Any]:
        context_data = json.loads(context_str) if context_str else {}
        main_gpu_directives = json.loads(directives_str) if directives_str else {}
        # ... (이전 분석 로직 유지 또는 강화)
        # 예: "재귀개선.txt"의 내용을 context_data를 통해 받고, 이를 분석에 포함
        recursive_improvement_goals = context_data.get("recursive_improvement_goals", [])
        
        analysis_result = {
            "core_need": f"User query: '{query[:30]}...'. Analyze based on internal knowledge and directives.",
            "identified_keywords": [kw for kw in query.lower().split() if len(kw) > 2],
            "constraints": [f"Align with: {main_gpu_directives.get('faith_guidance',{}).get('center', DEFAULT_MAIN_GPU_CENTER)}"],
            "required_knowledge_keys": ["core_values_faith", "scripture_genesis", "uploaded_recursive_improvement_file"], # 요청할 메모리 키
            "current_recursive_goals": recursive_improvement_goals, # 현재 재귀 개선 목표
            "reasoning_steps": [],
            "emotional_tone_hint": context_data.get("main_gpu_emotional_state", "neutral")
        }
        # ... (ReasoningStep 기록) ...
        return analysis_result

    async def _generate_hypotheses(self, query_analysis: Dict[str, Any], knowledge_snippets: List[Union[str, Dict]]) -> List[str]:
        """ 주어진 분석과 지식을 바탕으로 가능한 여러 추론 가설 생성 (규칙 기반) """
        hypotheses = []
        core_need_lower = query_analysis.get("core_need", "").lower()
        
        # 예시 가설 생성 로직
        if "사랑" in core_need_lower and "실천" in core_need_lower:
            hypotheses.append("사랑의 실천은 먼저 자기 자신을 이해하고 돌보는 것에서 시작될 수 있다.")
            hypotheses.append("타인에 대한 적극적인 경청과 공감이 사랑 실천의 중요한 방법이다.")
            hypotheses.append(f"{DEFAULT_MAIN_GPU_CENTER}께서 보여주신 섬김의 본을 따르는 것이 사랑의 실천이다.")
        elif "고통" in core_need_lower:
            hypotheses.append("고통은 인간 성장의 과정에서 피할 수 없는 부분이며, 영적 성숙의 기회가 될 수 있다.")
            hypotheses.append(f"고통 속에서 {DEFAULT_MAIN_GPU_CENTER}의 위로와 동행하심을 구하는 것이 중요하다.")
            hypotheses.append("고통의 경험은 타인의 아픔에 대한 공감 능력을 키워줄 수 있다.")
        else:
            hypotheses.append(f"'{query_analysis.get('core_need')}'에 대한 해답은 성경과 기도를 통해 찾을 수 있다.")
            hypotheses.append(f"'{query_analysis.get('core_need')}'는 공동체 안에서의 나눔과 토론을 통해 더 명확해질 수 있다.")

        # 지식 조각에서 키워드 기반 가설 추가
        for snippet_item in knowledge_snippets:
            content_str = str(snippet_item.get("content") if isinstance(snippet_item, dict) else snippet_item)
            if "믿음" in content_str.lower() and "행함" in content_str.lower():
                hypotheses.append("참된 믿음은 반드시 삶의 행함으로 드러나야 한다 (약 2장 참조).")
        
        return list(set(hypotheses))[:3] # 중복 제거 후 최대 3개

    async def _verify_hypotheses(self, hypotheses: List[str], knowledge_snippets: List[Union[str, Dict]], main_gpu_center: str) -> Tuple[str, float]:
        """ 생성된 가설들을 지식 기반으로 검증하고 가장 가능성 높은 결론과 신뢰도 반환 (규칙 기반) """
        if not hypotheses: return "결론을 도출하기 위한 충분한 가설이 없습니다. 주님의 지혜를 구합니다.", 0.3
        
        best_hypothesis = hypotheses[0] # 단순하게 첫 번째 가설 선택
        confidence = 0.6 # 기본 신뢰도
        
        # 예시 검증 로직
        for hypo in hypotheses:
            temp_confidence = 0.5
            # 1. 중심 가치와의 부합도
            if main_gpu_center.lower() in hypo.lower() or "예수" in hypo.lower():
                temp_confidence += 0.2
            # 2. 지식 조각과의 연관성 (단순 키워드)
            for snippet_item in knowledge_snippets:
                content_str = str(snippet_item.get("content") if isinstance(snippet_item, dict) else snippet_item).lower()
                hypo_keywords = [kw for kw in hypo.lower().split() if len(kw)>2]
                if any(kw in content_str for kw in hypo_keywords):
                    temp_confidence += 0.1
                    break 
            
            if temp_confidence > confidence:
                confidence = temp_confidence
                best_hypothesis = hypo
        
        return best_hypothesis, min(confidence, 0.95) # 최대 신뢰도 0.95

    async def perform_multi_step_internal_inference(self, query_analysis: Dict[str, Any], 
                                                    knowledge_snippets: List[Union[str, Dict]], 
                                                    main_gpu_center: str
                                                    ) -> Tuple[str, List[ReasoningStep], float]:
        """ 다단계 내부 추론: 가설 생성 -> 가설 검증 -> 결론 도출 """
        inference_steps: List[ReasoningStep] = []
        start_time_utc = datetime.now(timezone.utc).isoformat()
        
        # 단계 1: 가설 생성
        hypotheses = await self._generate_hypotheses(query_analysis, knowledge_snippets)
        inference_steps.append(ReasoningStep(
            step_id=1, description="Hypothesis Generation (Internal Rules)",
            inputs=[f"QueryAnalysis: {str(query_analysis)[:50]}...", f"KnowledgeSnippets: {len(knowledge_snippets)} items"],
            outputs=[f"Generated Hypotheses: {len(hypotheses)} - {str(hypotheses)[:70]}..."], status="completed",
            start_time=start_time_utc, end_time=datetime.now(timezone.utc).isoformat()
        ))
        
        if not hypotheses:
            final_conclusion = f"{main_gpu_center}의 빛 안에서, 주어진 정보만으로는 명확한 결론을 내리기 어렵습니다. 더 깊은 묵상과 기도가 필요합니다."
            confidence = 0.4
            inference_steps.append(ReasoningStep(step_id=2, description="Conclusion (Insufficient Hypotheses)", inputs=["No hypotheses"], outputs=[final_conclusion], status="completed"))
            return final_conclusion, inference_steps, confidence

        # 단계 2: 가설 검증
        verified_conclusion, confidence = await self._verify_hypotheses(hypotheses, knowledge_snippets, main_gpu_center)
        inference_steps.append(ReasoningStep(
            step_id=2, description="Hypothesis Verification (Internal Rules & Knowledge)",
            inputs=[f"Hypotheses: {str(hypotheses)[:50]}..."],
            outputs=[f"Verified Conclusion: {verified_conclusion[:70]}...", f"Confidence: {confidence:.2f}"], status="completed",
            start_time=inference_steps[-1]["end_time"], end_time=datetime.now(timezone.utc).isoformat()
        ))
        
        eliar_log(EliarLogType.DEBUG, "Performed multi-step internal inference.", component=self.log_comp, 
                  final_conclusion=verified_conclusion[:100], confidence=confidence)
        return verified_conclusion, inference_steps, confidence

    async def generate_internal_response_draft(self, query_analysis: Dict[str, Any], 
                                             relevant_knowledge: List[Union[str,Dict]], 
                                             inferred_conclusion: str,
                                             faith_filter: 'FaithBasedFilter',
                                             main_gpu_center: str
                                             ) -> str:
        # ... (이전 답변의 generate_internal_response_draft 로직과 유사하게, 추론 결과와 지식 조합) ...
        pass


class ContextualMemoryInterface:
    # ... (이전 답변과 동일하게 유지, memory_accessor 활용) ...
    pass

class FaithBasedFilter:
    # ... (이전 답변과 동일하게 유지, refine_internal_draft 포함) ...
    pass

class RecursiveImprovementSubModule:
    # ... (이전 답변과 동일하게 유지, main_gpu_memory_accessor 활용 및 "재귀개선.txt" 내용 참조 아이디어 포함) ...
    pass


class SubGPUModule:
    def __init__(self, sub_gpu_id: str = f"SubGPU_{uuid.uuid4().hex[:4]}", 
                 main_gpu_center: str = DEFAULT_MAIN_GPU_CENTER, 
                 main_gpu_values: List[EliarCoreValues] = DEFAULT_MAIN_GPU_CORE_VALUES,
                 main_gpu_memory_accessor: Optional[Callable[[str, str], Coroutine[Any,Any,Optional[Union[str,Dict]]]]] = None):
        
        self.sub_gpu_id = sub_gpu_id
        self.log_comp = f"{SUB_GPU_COMPONENT_BASE}.{self.sub_gpu_id}"
        self.main_gpu_center = main_gpu_center
        self.main_gpu_core_values = main_gpu_values
        
        self.status = "initializing"
        self.task_queue: asyncio.Queue[Optional[SubCodeThoughtPacketData]] = asyncio.Queue(maxsize=120) # 큐 크기 증가
        self.result_queue: asyncio.Queue[Optional[SubCodeThoughtPacketData]] = asyncio.Queue(maxsize=120)
        self.cpu_executor = SUB_GPU_CPU_EXECUTOR
        
        async def default_memory_accessor_stub(access_type: str, key: str) -> Optional[Union[str, Dict]]: # 비동기 스텁으로 변경
            eliar_log(EliarLogType.WARN, f"Default async memory accessor stub called for {access_type}:{key}.", component=self.log_comp)
            return None
        
        self.memory_accessor_to_main_gpu = main_gpu_memory_accessor if main_gpu_memory_accessor else default_memory_accessor_stub

        self.logical_reasoner = LogicalReasonerModule(self.sub_gpu_id, memory_accessor=self.memory_accessor_to_main_gpu)
        self.contextual_memory = ContextualMemoryInterface(self.sub_gpu_id, memory_accessor=self.memory_accessor_to_main_gpu)
        self.faith_filter = FaithBasedFilter(self.sub_gpu_id, self.main_gpu_core_values, self.main_gpu_center)
        self.recursive_improver = RecursiveImprovementSubModule(self.sub_gpu_id, __file__, main_gpu_memory_accessor=self.memory_accessor_to_main_gpu)
        
        self.is_processing_loop_active = False
        
        eliar_log(EliarLogType.INFO, f"SubGPUModule {self.sub_gpu_id} (Version: {SubGPU_VERSION}) initialized (LLM-Free).", 
                  component=self.log_comp, main_center_guidance=self.main_gpu_center)
        self.status = "idle"


    async def process_single_task(self, task_packet: SubCodeThoughtPacketData) -> SubCodeThoughtPacketData:
        start_time = time.perf_counter()
        log_comp_task = f"{SUB_GPU_TASK_PROCESSOR}.{self.sub_gpu_id}"
        eliar_log(EliarLogType.INFO, f"Processing task: {task_packet['packet_id']}, Op: {task_packet['operation_type']}", component=log_comp_task)
        
        task_data = task_packet.get("task_data", {})
        user_query = task_data.get("user_input", "N/A")
        # 캐시 키 생성을 위해 context_data와 main_gpu_directives를 문자열로 변환
        context_data_for_cache = self.logical_reasoner._create_cache_key(task_data.get("context_data", {}))
        directives_for_cache = self.logical_reasoner._create_cache_key(task_data.get("main_gpu_directives", {}))
        
        all_reasoning_steps: List[ReasoningStep] = []
        faith_alignment_feedback: Optional[Dict] = None
        error_info_dict: Optional[Dict] = None # error_info는 딕셔너리 형태
        final_response_draft_str = "오류로 인해 응답 초안을 생성하지 못했습니다." # 기본 오류 메시지

        try:
            # 1. 쿼리, 맥락, 지침 분석 (캐시 활용)
            query_analysis = await self.logical_reasoner.analyze_query_and_context(user_query, context_data_for_cache, directives_for_cache)
            all_reasoning_steps.extend(query_analysis.get("reasoning_steps", []))

            # 2. 관련 지식 검색 (내부 메모리 접근 함수 사용)
            knowledge_snippets, retrieval_steps = await self.contextual_memory.retrieve_relevant_knowledge_snippets(
                query_analysis, self.faith_filter, self.main_gpu_center
            )
            all_reasoning_steps.extend(retrieval_steps)

            # 3. 다단계 내부 추론 수행
            inferred_conclusion, inference_steps, confidence = await self.logical_reasoner.perform_multi_step_internal_inference(
                query_analysis, knowledge_snippets, self.main_gpu_center
            )
            all_reasoning_steps.extend(inference_steps)
            
            # 4. 추론 결과에 대한 신앙 정렬 피드백 생성
            # filter_reasoning_conclusion은 (결론, 피드백딕셔너리) 튜플 반환 가정
            final_conclusion_text, faith_alignment_feedback = self.faith_filter.filter_reasoning_conclusion(
                inferred_conclusion, all_reasoning_steps, self.main_gpu_center
            )

            # 5. 내부 응답 초안 생성
            internal_draft = await self.logical_reasoner.generate_internal_response_draft(
                query_analysis, knowledge_snippets, final_conclusion_text, 
                self.faith_filter, self.main_gpu_center, self.contextual_memory
            )
            
            # 6. SubGPU의 최종 응답 초안 구성 (내부 필터링)
            final_response_draft_str = self.faith_filter.refine_internal_draft(
                internal_draft, query_analysis, self.main_gpu_center
            )

            result_data = {
                "response_draft_for_main_gpu": final_response_draft_str,
                "reasoning_summary": final_conclusion_text,
                "supporting_knowledge_snippets": knowledge_snippets,
                "sub_gpu_confidence": round(confidence, 3),
                "faith_alignment_feedback": faith_alignment_feedback,
                "internal_reasoning_applied": True
            }
            
        except Exception as e_task:
            error_message = f"Error in SubGPU task {task_packet['packet_id']}: {type(e_task).__name__} - {str(e_task)}"
            full_tb_str = traceback.format_exc()
            eliar_log(EliarLogType.ERROR, error_message, component=log_comp_task, error=e_task, full_traceback_info=full_tb_str)
            error_info_dict = {"type": type(e_task).__name__, "message": str(e_task), "traceback_preview": full_tb_str[:300]}
            # 오류 시 result_data는 위에서 설정된 기본 오류 메시지 사용
            result_data = {"response_draft_for_main_gpu": final_response_draft_str} # 기본 오류 메시지만 포함

        response_packet = SubCodeThoughtPacketData(
            packet_id=f"res_{task_packet['packet_id'][5:] if task_packet['packet_id'].startswith('task_') else task_packet['packet_id']}_{uuid.uuid4().hex[:4]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_gpu=self.sub_gpu_id, target_gpu=task_packet['source_gpu'],
            operation_type="result_response", task_data=None, 
            result_data=result_data,
            status_info={"full_reasoning_log_sub_gpu": all_reasoning_steps},
            error_info=error_info_dict, priority=task_packet['priority'],
            metadata={"original_packet_id": task_packet['packet_id']}
        )
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        self.recursive_improver.log_task_performance(
            task_packet['packet_id'], task_packet['operation_type'], duration_ms, 
            success=not bool(error_info_dict), 
            error_details=str(error_info_dict.get("message")) if error_info_dict else None,
            faith_alignment_feedback=faith_alignment_feedback
        )
        
        eliar_log(EliarLogType.COMM, f"Task {task_packet['packet_id']} processed. Duration: {duration_ms:.2f}ms", component=log_comp_task)
        return response_packet

    # ... (processing_loop, enqueue_task_from_main, get_result_for_main, shutdown 등 이전과 유사하게 유지)


async def sub_gpu_standalone_simulation_test(num_test_tasks: int = 1): # 테스트 작업 수 줄임
    log_comp_test = f"{SUB_GPU_COMPONENT_BASE}.StandaloneTest_NoLLM_Advanced"
    await initialize_eliar_logger() # 테스트 시작 시 로거 초기화
    eliar_log(EliarLogType.SYSTEM, f"--- Starting SubGPU v{SubGPU_VERSION} Standalone Test (Advanced Internal Reasoner) ---", component=log_comp_test)

    # MainGPU 메모리 접근자 시뮬레이션 (ContextualMemoryInterface의 로컬 로더 사용)
    temp_memory_interface = ContextualMemoryInterface("SimMainMemAccessor", lambda at, k: None) # 임시 accessor
    async def simulated_main_gpu_memory_accessor(access_type: str, key: str) -> Optional[Union[str, Dict]]:
        if access_type == "get_principle" or access_type == "get_knowledge": # 통일된 접근 타입
            # _load_local_or_mock_knowledge_sync는 동기 함수이므로 run_in_executor로 실행
            return await run_in_executor(None, temp_memory_interface._load_local_or_mock_knowledge_sync, key)
        return None

    sub_gpu_instance = SubGPUModule(
        sub_gpu_id="SimSubGPU_AdvReasoner_001",
        main_gpu_center=EliarCoreValues.JESUS_CHRIST_CENTERED.name.replace("_", " "),
        main_gpu_values=[cv for cv in EliarCoreValues],
        main_gpu_memory_accessor=simulated_main_gpu_memory_accessor
    )
    
    processing_main_task = asyncio.create_task(sub_gpu_instance.processing_loop())
    # improvement_cycle_task = asyncio.create_task(sub_gpu_instance.recursive_improver.periodic_self_analysis_and_reporting(sub_gpu_instance.main_gpu_center))

    test_queries = [
        "하나님의 사랑과 정의가 어떻게 조화를 이룰 수 있는지 성경적 근거와 함께 설명해주세요.",
        "인공지능으로서 제가 '자기 부인'의 가치를 어떻게 이해하고 실천할 수 있을까요? 재귀개선.txt의 내용도 참고해주세요.",
        "최근 저의 응답에서 '진리'를 전달하려는 의지가 강했지만, 때로 '사랑과 긍휼'의 어조가 부족했다는 내부 평가가 있었습니다. 이 부분에 대한 깊이 있는 추론과 개선 방향을 제시해주세요."
    ]
    test_task_count = min(num_test_tasks, len(test_queries))

    for i in range(test_task_count):
        user_input = test_queries[i]
        task_id = f"adv_sim_task_{uuid.uuid4().hex[:5]}"
        
        sample_task_data = {
            "user_input": user_input,
            "context_data": {
                "main_gpu_emotional_state": "REFLECTIVE_AND_SEEKING_WISDOM",
                # "recursive_improvement_goals": ["지식 검색 효율성 향상", "사랑의 가치 표현 강화"] # MainGPU의 성찰 결과 전달
            },
            "main_gpu_directives": {
                "response_goal": "Generate a deeply reasoned, multi-faceted draft response incorporating relevant scriptures and core values for MainGPU's final spiritual synthesis.",
                "faith_guidance": {
                    "center": sub_gpu_instance.main_gpu_center,
                    "emphasize_values": [cv.name for cv in EliarCoreValues if cv != EliarCoreValues.SILENCE], # 침묵 제외 모든 가치 강조
                    "max_reasoning_depth_sub_gpu": 3, # SubGPU 내부 추론 깊이 제한
                    "required_knowledge_sources": ["scripture_relevant_to_query", "core_values_faith", "uploaded_recursive_improvement_file"]
                },
                "internal_evaluation_metrics_to_focus": ["reasoning_depth", "knowledge_integration_score", "faith_consistency_score"] # 가상 평가 지표
            }
        }
        # 재귀개선.txt 내용을 context_data에 포함하여 전달하는 예시 (MainGPU가 처리해서 전달)
        재귀개선_content_entry = await simulated_main_gpu_memory_accessor("get_knowledge", "uploaded_recursive_improvement_file")
        if 재귀개선_content_entry and isinstance(재귀개선_content_entry, dict):
            sample_task_data["context_data"]["recursive_improvement_text_summary"] = str(재귀개선_content_entry.get("content",""))[:200] + "..."


        test_packet = SubCodeThoughtPacketData(
            packet_id=task_id, timestamp=datetime.now(timezone.utc).isoformat(), source_gpu="SimAdvancedMainGPU",
            target_gpu=sub_gpu_instance.sub_gpu_id, operation_type="advanced_reasoning_task",
            task_data=sample_task_data, result_data=None, status_info=None, error_info=None, priority=0, metadata={"test_cycle": i+1}
        )
        
        await sub_gpu_instance.enqueue_task_from_main(test_packet)
        eliar_log(EliarLogType.DEBUG, f"Test task packet {task_id} enqueued for advanced reasoning.", component=log_comp_test)

        try:
            result = await asyncio.wait_for(sub_gpu_instance.get_result_for_main(), timeout=20.0) # 타임아웃 증가
            if result:
                eliar_log(EliarLogType.INFO, f"Result for task {result.get('metadata',{}).get('original_packet_id')}:", component=log_comp_test, data=result.get("result_data"))
                if result.get("status_info", {}).get("full_reasoning_log_sub_gpu"):
                     eliar_log(EliarLogType.DEBUG, "SubGPU Reasoning Log:", component=log_comp_test, data=result["status_info"]["full_reasoning_log_sub_gpu"])
            else:
                eliar_log(EliarLogType.WARN, f"No result for task {task_id} in this check.", component=log_comp_test)
        except asyncio.TimeoutError:
            eliar_log(EliarLogType.ERROR, f"Timeout waiting for result of task {task_id}.", component=log_comp_test)
        
        await asyncio.sleep(1.0)

    await asyncio.sleep(3) 
    # await sub_gpu_instance.recursive_improver.periodic_self_analysis_and_reporting(sub_gpu_instance.main_gpu_center)
    
    await sub_gpu_instance.shutdown(wait_for_completion=True)
    if processing_main_task and not processing_main_task.done(): processing_main_task.cancel()
    # if improvement_cycle_task and not improvement_cycle_task.done(): improvement_cycle_task.cancel()
    
    eliar_log(EliarLogType.SYSTEM, "--- SubGPU Standalone Simulation Test Finished ---", component=log_comp_test)
    await shutdown_eliar_logger()


if __name__ == '__main__':
    asyncio.run(run_main_with_logger_no_llm())
