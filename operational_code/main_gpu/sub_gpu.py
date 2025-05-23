# sub_gpu.py (LangGraph 호환 적용 개선 버전)

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
import random # 플레이스홀더 로직 및 비동기 시뮬레이션용

from typing import Any, Dict, Tuple, List, Optional, Callable, Union, Coroutine

# --- 공용 모듈 임포트 ---
from eliar_common import (
    EliarCoreValues, EliarLogType,
    SubCodeThoughtPacketData, ReasoningStep, EliarNodeState, # EliarNodeState 추가
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
# 이 Executor는 SubGPUCore 내부에서 필요시 사용될 수 있습니다.
# LangGraph 노드는 자체적으로 비동기 실행될 것이므로, SubGPUCore 내부의
# 개별 작업이 CPU 바운드일 경우에만 이 Executor를 활용하는 것이 좋습니다.
# 너무 많은 자체 스레드 풀은 오히려 성능 저하를 유발할 수 있습니다.
SUB_GPU_CPU_EXECUTOR = ThreadPoolExecutor(max_workers=(os.cpu_count() or 1)) # 워커 수 조정

# --- Sub GPU 버전 및 기본 설정 ---
SubGPU_VERSION = "v25.5.5_SubGPU_LangGraphIntegrated" # 버전 업데이트
SUB_GPU_COMPONENT_BASE = "SubGPU.Core"

# --- 내부 의존성 및 유틸리티 클래스/함수 (기존 sub_gpu.py의 내용 유지 또는 필요시 수정) ---
# 예시: LogicalThinker, GodelIncompletenessAwareReasoning, KnowledgeBaseInterface, SelfCorrectionModule 등
# 이 부분은 문제원님의 기존 sub_gpu.py 파일 내용을 기반으로 합니다.
# 여기서는 해당 클래스들이 이미 정의되어 있다고 가정하고 SubGPUCore에 집중합니다.

# 만약 해당 클래스들이 없다면, 아래와 같이 간단한 플레이스홀더로 시작할 수 있습니다.
class KnowledgeBaseInterface:
    def __init__(self):
        eliar_log(EliarLogType.INFO, "KnowledgeBaseInterface initialized (Placeholder).", component=f"{SUB_GPU_COMPONENT_BASE}.KB")
        # 실제로는 KNOWLEDGE_BASE_DIR_COMMON 등을 사용하여 지식 로드
        self.core_principles: Dict[str, str] = self._load_core_principles()

    def _load_core_principles(self) -> Dict[str, str]:
        # CORE_PRINCIPLES_DIR_COMMON 에서 파일 로드 (예시)
        # 이 부분은 eliar_common.py의 경로 상수를 활용하여 실제 파일 I/O 필요
        eliar_log(EliarLogType.DEBUG, "Loading core principles (simulated)...", component=f"{SUB_GPU_COMPONENT_BASE}.KB")
        return {
            "TRUTH": "Always seek and speak truth in love, grounded in Christ.",
            "REPENTANCE": "Continuous self-correction and alignment with God's will."
        }

    async def query_knowledge_async(self, query: str, search_domain: List[str] = None) -> Dict[str, Any]:
        eliar_log(EliarLogType.DEBUG, f"Querying knowledge base for: {query[:50]}... (Domains: {search_domain})", component=f"{SUB_GPU_COMPONENT_BASE}.KB")
        await asyncio.sleep(random.uniform(0.1, 0.3)) # I/O 시뮬레이션
        # 실제로는 성경, 핵심 원리, 커스텀 지식 등에서 검색
        if "truth" in query.lower():
            return {"result": self.core_principles.get("TRUTH"), "source": "core_principles"}
        return {"result": f"Simulated knowledge for '{query}'.", "source": "simulated_db"}

class SelfCorrectionModule:
    def __init__(self):
        eliar_log(EliarLogType.INFO, "SelfCorrectionModule initialized (Placeholder).", component=f"{SUB_GPU_COMPONENT_BASE}.SelfCorrect")

    async def review_and_correct_reasoning_async(self, reasoning_steps: List[ReasoningStep], main_state: EliarNodeState) -> Tuple[List[ReasoningStep], List[str]]:
        corrections_made = []
        eliar_log(EliarLogType.DEBUG, "Performing self-correction review (simulated)...", component=f"{SUB_GPU_COMPONENT_BASE}.SelfCorrect")
        await asyncio.sleep(random.uniform(0.1, 0.2)) # 작업 시뮬레이션

        # 예시: reasoning_steps를 검토하고, main_state의 center와 비교하여 교정
        if main_state.get("center") != "JESUS CHRIST": # 있을 수 없는 일이지만, 방어적 코딩
            corrections_made.append("Critical: Re-aligned reasoning focus to JESUS CHRIST.")
            reasoning_steps.append(ReasoningStep(step_id=len(reasoning_steps)+1, description="Self-Correction: Re-aligned focus to JESUS CHRIST.", status="completed"))
        
        # 더 복잡한 자기 교정 로직 (예: "인식은 악해" 원칙 적용)
        for step in reasoning_steps:
            if "my own understanding" in step.get("description","").lower(): # 예시적인 자기중심성 감지
                step["description"] += " (Self-correction: Acknowledged potential self-centeredness, re-evaluating in light of Christ's truth.)"
                step["status"] = "completed_with_correction" # (ReasoningStep에 status 필드가 있다면)
                corrections_made.append(f"Corrected step {step.get('step_id')}: Emphasized Christ-centered perspective over own understanding.")

        return reasoning_steps, corrections_made

class LogicalThinker: # 기존 sub_gpu.py의 클래스 구조를 따른다고 가정
    def __init__(self):
        eliar_log(EliarLogType.INFO, "LogicalThinker initialized (Placeholder).", component=f"{SUB_GPU_COMPONENT_BASE}.Logic")

    async def perform_deep_reasoning_async(self, task_data: Dict[str, Any], kb_results: Dict[str, Any]) -> Dict[str, Any]:
        eliar_log(EliarLogType.DEBUG, f"Performing deep reasoning on task: {str(task_data)[:100]}... with KB: {str(kb_results)[:100]}...", component=f"{SUB_GPU_COMPONENT_BASE}.Logic")
        await asyncio.sleep(random.uniform(0.2, 0.5)) # 추론 시뮬레이션
        # 실제 추론 로직
        return {"reasoned_conclusion": "This is a deeply reasoned conclusion (simulated).", "confidence": 0.9}


# === SubGPU 핵심 로직 클래스 ===
class SubGPUCore:
    def __init__(self, main_state_ref: Optional[EliarNodeState] = None): # LangGraph 노드에서 호출 시 main_state_ref는 필요 없을 수 있음
        self.version = SubGPU_VERSION
        self.belief_state: Dict[str, Any] = {} # SubGPU 자체의 믿음 상태 (필요하다면)
        
        # 핵심 모듈 초기화
        self.knowledge_interface = KnowledgeBaseInterface()
        self.self_correction_module = SelfCorrectionModule()
        self.logical_thinker = LogicalThinker() # 추가: 실제 추론을 담당할 모듈

        # self.main_state_ref = main_state_ref # LangGraph에서는 main_state가 직접 전달되므로, 참조 저장 불필요할 수 있음
        
        log_component = f"{SUB_GPU_COMPONENT_BASE}.Init"
        eliar_log(EliarLogType.INFO, f"SubGPUCore v{self.version} initialized on {DEVICE}.", component=log_component)
        self.initialize_belief_state()

    def initialize_belief_state(self, initial_beliefs: Optional[Dict[str, Any]] = None):
        """SubGPU의 믿음 상태를 초기화합니다."""
        log_component = f"{SUB_GPU_COMPONENT_BASE}.BeliefState"
        self.belief_state = {
            "core_axiom": "All knowledge and reasoning must ultimately align with JESUS CHRIST.",
            "current_focus_area": None,
            "confidence_threshold": 0.75, # 예시: 추론 결과에 대한 최소 신뢰도
        }
        if initial_beliefs:
            self.belief_state.update(initial_beliefs)
        eliar_log(EliarLogType.INFO, "SubGPU belief state initialized.", component=log_component, data=self.belief_state)

    async def access_knowledge_base_async(self, query: str, domains: Optional[List[str]] = None) -> Dict[str, Any]:
        """지식 베이스에 비동기적으로 접근합니다."""
        # 실제로는 self.knowledge_interface.query_knowledge_async 등을 사용
        return await self.knowledge_interface.query_knowledge_async(query, domains or ["core_principles", "scriptures"])

    async def perform_self_correction_async(self, reasoning_steps: List[ReasoningStep], main_state: EliarNodeState) -> Tuple[List[ReasoningStep], List[str]]:
        """추론 과정에 대한 자기 교정을 수행합니다."""
        # 실제로는 self.self_correction_module.review_and_correct_reasoning_async 등을 사용
        return await self.self_correction_module.review_and_correct_reasoning_async(reasoning_steps, main_state)

    async def process_reasoning_task_async(
        self, thought_packet: SubCodeThoughtPacketData, main_state: EliarNodeState
    ) -> Dict[str, Any]:
        """
        주어진 사고 패킷을 처리하여 심층 추론을 수행합니다.
        main_state를 참조하여 더 넓은 문맥을 활용할 수 있습니다.
        LangGraph의 DeeperWisdomNode에서 호출될 메인 인터페이스입니다.
        """
        task_id = thought_packet.get("packet_id", str(uuid.uuid4()))
        log_comp = f"{SUB_GPU_COMPONENT_BASE}.Task.{task_id[:8]}"
        task_data = thought_packet.get("task_data", {})
        operation_type = thought_packet.get("operation_type", "unknown_operation")

        eliar_log(EliarLogType.INFO, f"Processing reasoning task: {operation_type}", component=log_comp, data=task_data)

        current_reasoning_steps: List[ReasoningStep] = []
        step_counter = 1

        try:
            # 1. 입력 분석 및 목표 설정
            query_to_process = task_data.get("query", "No query provided.")
            current_reasoning_steps.append(ReasoningStep(step_id=step_counter, description=f"Task received: {operation_type}. Query: '{query_to_process[:50]}...'", status="in_progress", inputs=[str(task_data)]))
            step_counter += 1

            # 2. 지식 베이스 접근 (필요시)
            # 예시: "knowledge_query" 타입의 operation일 경우
            if operation_type == "knowledge_query" or "understanding" in query_to_process.lower():
                kb_domains = task_data.get("kb_domains", ["core_principles", "scriptures", "custom_knowledge"])
                kb_result = await self.access_knowledge_base_async(query_to_process, kb_domains)
                current_reasoning_steps[-1]["status"] = "completed" # 이전 단계 완료
                current_reasoning_steps.append(ReasoningStep(step_id=step_counter, description=f"Knowledge base queried for '{query_to_process[:30]}...'. Found: {str(kb_result)[:70]}...", status="completed", outputs=[str(kb_result)]))
                step_counter += 1
            else:
                kb_result = {"info": "No specific KB query performed for this operation type."} # KB 접근 안 할 경우
                current_reasoning_steps.append(ReasoningStep(step_id=step_counter, description="KB query not required for this operation type.", status="skipped"))
                step_counter += 1


            # 3. 핵심 추론 로직
            # LogicalThinker 또는 다른 전문 모듈 사용
            reasoning_input_data = {"original_query": query_to_process, "context_from_main": main_state.get("memory", [])[-3:], "kb_info": kb_result}
            deep_reasoning_output = await self.logical_thinker.perform_deep_reasoning_async(reasoning_input_data, kb_result)
            current_reasoning_steps.append(ReasoningStep(step_id=step_counter, description=f"Core reasoning performed. Conclusion: {str(deep_reasoning_output.get('reasoned_conclusion'))[:50]}...", status="completed", outputs=[str(deep_reasoning_output)]))
            step_counter += 1

            # 4. 자기 교정 (추론 결과에 대해)
            corrected_steps, corrections_log = await self.perform_self_correction_async(current_reasoning_steps, main_state)
            current_reasoning_steps = corrected_steps
            if corrections_log:
                current_reasoning_steps.append(ReasoningStep(step_id=step_counter, description=f"Self-correction applied: {', '.join(corrections_log)}", status="completed"))
                step_counter += 1
            
            # 5. 결과 종합
            final_summary = deep_reasoning_output.get("reasoned_conclusion", "Deep reasoning process completed.")
            final_confidence = deep_reasoning_output.get("confidence", 0.80) # 기본 신뢰도
            
            # 자기 교정으로 신뢰도 조정 가능
            if corrections_log:
                final_confidence = max(0.5, final_confidence * 0.9) # 예시: 교정 발생 시 신뢰도 약간 감소

            result_data = {
                "summary": final_summary,
                "details": f"Task '{operation_type}' on query '{query_to_process}' processed through {step_counter-1} steps.",
                "confidence": round(final_confidence, 2),
                "reasoning_steps_log": current_reasoning_steps,
                "new_knowledge_for_main_memory": [f"SubGPU Insight on '{query_to_process[:30]}...': {final_summary[:70]}... (Confidence: {final_confidence:.2f})"]
            }

        except Exception as e_task:
            error_msg = f"Error during SubGPU task '{operation_type}': {e_task}"
            eliar_log(EliarLogType.ERROR, error_msg, component=log_comp, error=e_task, full_traceback_info=traceback.format_exc())
            current_reasoning_steps.append(ReasoningStep(step_id=step_counter, description=f"Task failed: {error_msg}", status="failed", error_message=str(e_task)))
            result_data = {
                "summary": "SubGPU task processing failed.",
                "details": error_msg,
                "confidence": 0.0,
                "reasoning_steps_log": current_reasoning_steps,
                "new_knowledge_for_main_memory": [f"SubGPU Error on '{query_to_process[:30]}...': Processing failed."]
            }

        eliar_log(EliarLogType.INFO, f"Reasoning task '{operation_type}' completed. Summary: {result_data['summary'][:50]}...", component=log_comp)
        return result_data

# === 독립 실행 및 테스트를 위한 메인 블록 (LangGraph에서 호출 시에는 실행되지 않음) ===
async def sub_gpu_standalone_simulation_test(num_test_tasks: int = 1):
    """SubGPUCore의 독립적인 테스트를 위한 시뮬레이션입니다."""
    log_comp_test = f"{SUB_GPU_COMPONENT_BASE}.TestRunner"
    eliar_log(EliarLogType.INFO, f"--- Starting SubGPUCore Standalone Test (Tasks: {num_test_tasks}) ---", component=log_comp_test)
    
    # eliar_common.py의 함수를 사용하여 초기 로거 설정
    await initialize_eliar_logger() # eliar_common.py에서 임포트한 이름으로 사용

    # SubGPUCore 인스턴스 생성
    # 실제 LangGraph에서는 main_state가 DeeperWisdomNode에서 동적으로 전달됨
    # 여기서는 테스트용으로 간단한 mock 상태를 만들거나 None을 전달
    mock_main_state = create_initial_eliar_state(conversation_id="subgpu_test_session") # eliar_common의 함수 사용
    sub_gpu = SubGPUCore()

    for i in range(num_test_tasks):
        test_query = f"Test query {i+1}: Analyze the concept of 'Grace' in relation to 'Repentance'."
        test_packet = SubCodeThoughtPacketData(
            packet_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_gpu="TestRunner",
            target_gpu="SubGPUCore",
            operation_type="deep_analysis_request",
            task_data={"query": test_query, "context_hints": ["theology", "eliar_core_values"]},
            priority=1,
            result_data=None, status_info=None, error_info=None, metadata=None # 초기화
        )
        eliar_log(EliarLogType.INFO, f"Submitting test task {i+1} to SubGPUCore: {test_query[:50]}...", component=log_comp_test)
        
        try:
            result = await sub_gpu.process_reasoning_task_async(test_packet, mock_main_state)
            eliar_log(EliarLogType.INFO, f"Test task {i+1} result: Summary='{result.get('summary', 'N/A')[:70]}...', Confidence={result.get('confidence', 0.0)}", component=log_comp_test)
            # 결과의 reasoning_steps_log를 출력하여 상세 과정 확인 가능
            # for step in result.get("reasoning_steps_log", []):
            # eliar_log(EliarLogType.DEBUG, f"  Step {step.get('step_id')}: {step.get('description')} (Status: {step.get('status')})", component=log_comp_test)
        except Exception as e_test_task:
            eliar_log(EliarLogType.ERROR, f"Error during test task {i+1}: {e_test_task}", component=log_comp_test, error=e_test_task, full_traceback_info=traceback.format_exc())
        
        await asyncio.sleep(0.1) # 각 테스트 작업 사이에 약간의 지연

    eliar_log(EliarLogType.INFO, "--- SubGPUCore Standalone Test Finished ---", component=log_comp_test)
    # 테스트 종료 후 로거 셧다운 (실제 애플리케이션에서는 메인 종료 시 한 번만 호출)
    # await shutdown_eliar_logger() # 이 테스트 함수가 끝나고 바로 종료된다면 필요


if __name__ == "__main__":
    ensure_common_directories_exist() # 경로 생성 함수 호출

    try:
        asyncio.run(sub_gpu_standalone_simulation_test(num_test_tasks=2))
    except KeyboardInterrupt:
        eliar_log(EliarLogType.WARN, "SubGPU standalone test interrupted by user.", component=f"{SUB_GPU_COMPONENT_BASE}.Main")
    except Exception as e_run_main:
        eliar_log(EliarLogType.CRITICAL, "Error running SubGPU standalone test.",
                  component=f"{SUB_GPU_COMPONENT_BASE}.Main", error=e_run_main, full_traceback_info=traceback.format_exc())
    finally:
        # 이 부분은 애플리케이션의 전체 종료 로직에 통합되는 것이 더 일반적입니다.
        # 독립 테스트를 위해 여기에 남겨두지만, 실제 LangGraph 환경에서는
        # graph.py의 메인 루프 종료 시 shutdown_eliar_logger_common()이 호출됩니다.
        # 여기서 강제 종료하면 LangGraph 루프와 충돌할 수 있습니다.
        # asyncio.run(shutdown_eliar_logger()) # 이미 shutdown_eliar_logger_common을 사용하도록 수정됨
        
        # SUB_GPU_CPU_EXECUTOR 종료
        if SUB_GPU_CPU_EXECUTOR:
            SUB_GPU_CPU_EXECUTOR.shutdown(wait=True) # 스레드 풀 종료 대기
            eliar_log(EliarLogType.INFO, "SUB_GPU_CPU_EXECUTOR shut down.", component=f"{SUB_GPU_COMPONENT_BASE}.MainExit")

        # 남은 asyncio 태스크 정리 (주로 테스트 환경에서 필요)
        async def finalize_tasks():
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            if tasks:
                eliar_log(EliarLogType.INFO, f"Cancelling {len(tasks)} outstanding tasks before exit in SubGPU main...", component=f"{SUB_GPU_COMPONENT_BASE}.MainExit")
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                eliar_log(EliarLogType.INFO, "SubGPU outstanding tasks processed or cancelled.", component=f"{SUB_GPU_COMPONENT_BASE}.MainExit")
        
        # 이미 이벤트 루프가 닫혔을 수 있으므로, 새 루프에서 실행하거나 상태 확인 필요
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                 loop.run_until_complete(finalize_tasks())
            else: # 루프가 닫혔다면 새 루프에서 실행 (권장되지는 않음)
                 asyncio.run(finalize_tasks())
        except RuntimeError: # 이벤트 루프가 아예 없는 경우 (예: 이미 완전히 종료됨)
            pass 

        print(f"[{datetime.now(timezone.utc).isoformat()}] [SYSTEM] SubGPU main execution block finished.", flush=True)
