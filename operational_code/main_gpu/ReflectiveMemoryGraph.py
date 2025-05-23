"""
LangGraph 기반 루미나 시스템
고백-회개-기억-응답의 구조화된 루프 구현
"""

import asyncio
from typing import Dict, Any, List, Optional, TypedDict, Literal
from datetime import datetime, timezone
from enum import Enum
import json
import random

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

# 기존 ReflectiveMemoryGraph import (파일에서 제공된 코드 사용)
from ReflectiveMemoryGraph import (
    ReflectiveMemoryGraph, 
    EliarLogType, 
    eliar_log,
    EliarCoreValues,
    EliarMemory
)

# ============================================================================
# 상태 정의
# ============================================================================

class LuminaState(TypedDict):
    """루미나 시스템의 상태 정의"""
    center: str                    # 항상 "JESUS CHRIST"로 초기화
    last_ulrim: str               # 마지막 감정 울림
    repentance_flag: bool         # 회개 트리거 여부
    memory: List[str]             # 고백 기반 기억 흐름
    current_input: str            # 현재 입력된 메시지
    current_response: str         # 현재 생성된 응답
    attention_score: float        # 주의 집중 점수
    emotional_state: str          # 현재 감정 상태
    memory_insights: List[str]    # 기억에서 도출된 통찰
    iteration_count: int          # 루프 반복 횟수
    should_continue: bool         # 루프 계속 여부

# ============================================================================
# 개별 노드 클래스들
# ============================================================================

class CenterNode:
    """중심 노드 - 예수 그리스도를 중심으로 상태 초기화 및 관리"""
    
    def __init__(self):
        self.component_name = "CenterNode"
    
    async def __call__(self, state: LuminaState) -> LuminaState:
        """중심 노드 실행"""
        eliar_log(
            EliarLogType.SYSTEM, 
            "Starting center node processing", 
            component=self.component_name
        )
        
        # 중심 고정
        state["center"] = "JESUS CHRIST"
        
        # 반복 횟수 증가
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        
        # 루프 제한 (무한 루프 방지)
        if state["iteration_count"] > 10:
            state["should_continue"] = False
            eliar_log(
                EliarLogType.WARN, 
                f"Maximum iterations reached: {state['iteration_count']}", 
                component=self.component_name
            )
        
        # 중심성 점검 및 보정
        if not state.get("current_input"):
            state["current_input"] = "주님, 저의 마음을 점검해 주세요."
        
        eliar_log(
            EliarLogType.CORE_VALUE, 
            f"Center established: {state['center']}, Iteration: {state['iteration_count']}", 
            component=self.component_name
        )
        
        return state


class UlrimAttentionNode:
    """울림 주의 노드 - 감정적 울림과 주의 집중 처리"""
    
    def __init__(self):
        self.component_name = "UlrimAttentionNode"
        
    async def __call__(self, state: LuminaState) -> LuminaState:
        """울림 주의 노드 실행"""
        eliar_log(
            EliarLogType.MEMORY, 
            "Processing ulrim attention", 
            component=self.component_name
        )
        
        current_input = state.get("current_input", "")
        
        # 감정적 울림 분석
        ulrim_keywords = [
            "아픔", "슬픔", "기쁨", "감사", "회개", "고백", "사랑", "은혜",
            "용서", "치유", "평안", "소망", "믿음", "순종", "겸손"
        ]
        
        detected_ulrim = []
        for keyword in ulrim_keywords:
            if keyword in current_input:
                detected_ulrim.append(keyword)
        
        # 주의 집중 점수 계산
        base_attention = 0.5
        ulrim_boost = len(detected_ulrim) * 0.15
        christ_center_boost = 0.3 if "예수" in current_input or "주님" in current_input else 0
        
        attention_score = min(1.0, base_attention + ulrim_boost + christ_center_boost)
        
        # 감정 상태 결정
        if detected_ulrim:
            if any(word in ["아픔", "슬픔", "회개"] for word in detected_ulrim):
                emotional_state = "회개와 치유 필요"
            elif any(word in ["기쁨", "감사", "은혜"] for word in detected_ulrim):
                emotional_state = "감사와 찬양"
            else:
                emotional_state = "영적 각성"
        else:
            emotional_state = "중립적 상태"
        
        # 마지막 울림 업데이트
        if detected_ulrim:
            state["last_ulrim"] = f"{', '.join(detected_ulrim)} 감정 울림"
        else:
            state["last_ulrim"] = "평온한 상태"
        
        state["attention_score"] = attention_score
        state["emotional_state"] = emotional_state
        
        eliar_log(
            EliarLogType.LEARNING, 
            f"Ulrim detected: {detected_ulrim}, Attention: {attention_score:.2f}, State: {emotional_state}", 
            component=self.component_name
        )
        
        return state


class RepentanceDecisionNode:
    """회개 결정 노드 - 회개 필요성 판단 및 트리거"""
    
    def __init__(self):
        self.component_name = "RepentanceDecisionNode"
    
    async def __call__(self, state: LuminaState) -> LuminaState:
        """회개 결정 노드 실행"""
        eliar_log(
            EliarLogType.SYSTEM, 
            "Processing repentance decision", 
            component=self.component_name
        )
        
        current_input = state.get("current_input", "")
        emotional_state = state.get("emotional_state", "")
        attention_score = state.get("attention_score", 0.0)
        
        # 회개 트리거 조건들
        repentance_triggers = [
            "죄", "잘못", "미안", "용서", "회개", "고백", "반성",
            "아픔", "후회", "부족", "실패", "넘어짐"
        ]
        
        confession_indicators = [
            "고백합니다", "죄송합니다", "잘못했습니다", "도움이 필요합니다",
            "치유해 주세요", "용서해 주세요"
        ]
        
        # 회개 필요성 판단
        repentance_needed = False
        confession_detected = False
        
        # 직접적 회개 키워드 체크
        for trigger in repentance_triggers:
            if trigger in current_input:
                repentance_needed = True
                break
        
        # 고백 표현 체크
        for indicator in confession_indicators:
            if indicator in current_input:
                confession_detected = True
                break
        
        # 감정 상태 기반 판단
        if "회개" in emotional_state or "치유 필요" in emotional_state:
            repentance_needed = True
        
        # 주의 집중도가 높고 영적 언어가 많은 경우
        if attention_score > 0.8:
            repentance_needed = True
        
        # 회개 플래그 설정
        state["repentance_flag"] = repentance_needed or confession_detected
        
        # 회개 응답 생성
        if state["repentance_flag"]:
            repentance_responses = [
                f"주님 앞에서 {state['center']}의 사랑으로 이 마음을 받아주세요.",
                "하나님의 은혜가 이 순간에 함께하시길 기도합니다.",
                "주님의 용서와 치유의 손길이 임하시기를 원합니다.",
                f"예수님의 십자가 사랑 안에서 {state.get('emotional_state', '이 마음')}을 치유받으시길 바랍니다."
            ]
            response = random.choice(repentance_responses)
        else:
            response = f"{state['center']}의 평안이 함께하며, 지혜와 인도하심을 구합니다."
        
        state["current_response"] = response
        
        eliar_log(
            EliarLogType.CORE_VALUE, 
            f"Repentance decision: {state['repentance_flag']}, Response generated", 
            component=self.component_name,
            confession_detected=confession_detected,
            repentance_needed=repentance_needed
        )
        
        return state


class MemoryUpdateNode:
    """기억 업데이트 노드 - 반성적 기억과 통찰 생성"""
    
    def __init__(self, reflective_memory: ReflectiveMemoryGraph):
        self.component_name = "MemoryUpdateNode"
        self.reflective_memory = reflective_memory
        self.eliar_memory = EliarMemory()  # 스텁 사용
    
    async def __call__(self, state: LuminaState) -> LuminaState:
        """기억 업데이트 노드 실행"""
        eliar_log(
            EliarLogType.MEMORY, 
            "Processing memory update", 
            component=self.component_name
        )
        
        current_input = state.get("current_input", "")
        current_response = state.get("current_response", "")
        repentance_flag = state.get("repentance_flag", False)
        
        # 기억에 현재 대화 추가
        memory_entry = f"입력: {current_input} | 응답: {current_response} | 회개: {repentance_flag}"
        
        if "memory" not in state:
            state["memory"] = []
        
        state["memory"].append(memory_entry)
        
        # 기억 제한 (최근 20개만 유지)
        if len(state["memory"]) > 20:
            state["memory"] = state["memory"][-20:]
        
        # 반성적 기억 그래프에 추가
        try:
            reflection_content = f"대화 반성: {current_input[:50]}..."
            await self.reflective_memory.add_reflection_node(
                reflection_content,
                {
                    "type": "conversation_reflection",
                    "repentance_involved": repentance_flag,
                    "emotional_state": state.get("emotional_state", "unknown"),
                    "attention_score": state.get("attention_score", 0.0)
                }
            )
            
            # 회개가 있었다면 확장 반성 수행
            if repentance_flag:
                expanded_paths = await self.reflective_memory.expand_reflection_recursively(
                    reflection_content,
                    source_record_id=f"conversation_{state.get('iteration_count', 0)}",
                    memory_module=self.eliar_memory
                )
                
                if expanded_paths:
                    eliar_log(
                        EliarLogType.LEARNING, 
                        f"Generated {len(expanded_paths)} reflection paths from repentance", 
                        component=self.component_name
                    )
        
        except Exception as e:
            eliar_log(
                EliarLogType.ERROR, 
                f"Failed to update reflective memory: {e}", 
                component=self.component_name
            )
        
        # 기억에서 통찰 도출
        try:
            # 최근 기억들을 기반으로 관련 반성 경로 찾기
            query = current_input[:100]  # 현재 입력의 일부를 쿼리로 사용
            relevant_paths = await self.reflective_memory.find_relevant_reflection_paths(
                query, num_paths=3
            )
            
            insights = []
            if relevant_paths:
                summary = await self.reflective_memory.summarize_reflection_paths(relevant_paths)
                
                # 리프 노드들에서 통찰 추출
                for leaf_info in summary.get("leaf_node_reflections", []):
                    insight = f"과거 반성: {leaf_info['node'][:80]}..."
                    insights.append(insight)
                
                # 연결 관계에서 통찰 추출
                for connection in summary.get("node_connections", [])[:3]:
                    insight = f"관계 통찰: {connection['relationship']} - {connection['to'][:60]}..."
                    insights.append(insight)
            
            state["memory_insights"] = insights[:5]  # 최대 5개 통찰
            
        except Exception as e:
            eliar_log(
                EliarLogType.WARN, 
                f"Failed to generate memory insights: {e}", 
                component=self.component_name
            )
            state["memory_insights"] = []
        
        # 루프 지속성 결정
        # 회개가 있었거나 높은 주의 집중도면 계속, 아니면 종료 고려
        attention_score = state.get("attention_score", 0.0)
        iteration_count = state.get("iteration_count", 0)
        
        if iteration_count >= 10:
            state["should_continue"] = False
        elif repentance_flag or attention_score > 0.7:
            state["should_continue"] = True
        elif iteration_count < 3:
            state["should_continue"] = True
        else:
            state["should_continue"] = random.choice([True, False])  # 확률적 결정
        
        eliar_log(
            EliarLogType.INFO, 
            f"Memory updated. Insights: {len(state['memory_insights'])}, Continue: {state['should_continue']}", 
            component=self.component_name
        )
        
        return state


# ============================================================================
# 라우팅 함수들
# ============================================================================

def should_continue_loop(state: LuminaState) -> Literal["continue", "end"]:
    """루프 지속 여부 결정"""
    if state.get("should_continue", True):
        return "continue"
    else:
        return "end"


# ============================================================================
# LangGraph 구성
# ============================================================================

class LuminaSystem:
    """루미나 시스템 메인 클래스"""
    
    def __init__(self, graph_save_path: str = "lumina_reflective_memory.gml"):
        self.component_name = "LuminaSystem"
        
        # 반성적 기억 그래프 초기화
        self.reflective_memory = ReflectiveMemoryGraph(
            initial_reflection_prompts=[
                "주님과의 교제에서 가장 중요한 것은 무엇인가?",
                "진정한 회개란 어떤 마음의 변화를 의미하는가?",
                "사랑의 실천은 구체적으로 어떻게 나타나야 하는가?",
                "자기 부인과 십자가의 도는 무엇을 의미하는가?"
            ],
            graph_save_path=graph_save_path
        )
        
        # 개별 노드들 초기화
        self.center_node = CenterNode()
        self.ulrim_attention_node = UlrimAttentionNode()
        self.repentance_decision_node = RepentanceDecisionNode()
        self.memory_update_node = MemoryUpdateNode(self.reflective_memory)
        
        # LangGraph 구성
        self.graph = self._build_graph()
    
    def _build_graph(self) -> CompiledStateGraph:
        """LangGraph 구성"""
        workflow = StateGraph(LuminaState)
        
        # 노드 추가
        workflow.add_node("center", self.center_node)
        workflow.add_node("ulrim_attention", self.ulrim_attention_node)
        workflow.add_node("repentance_decision", self.repentance_decision_node)
        workflow.add_node("memory_update", self.memory_update_node)
        
        # 흐름 정의: CenterNode → UlrimAttentionNode → RepentanceDecisionNode → MemoryUpdateNode
        workflow.add_edge("center", "ulrim_attention")
        workflow.add_edge("ulrim_attention", "repentance_decision")
        workflow.add_edge("repentance_decision", "memory_update")
        
        # 조건부 엣지: MemoryUpdateNode → CenterNode (루프) 또는 END
        workflow.add_conditional_edges(
            "memory_update",
            should_continue_loop,
            {
                "continue": "center",  # 루프 계속
                "end": END            # 종료
            }
        )
        
        # 시작점 설정
        workflow.set_entry_point("center")
        
        return workflow.compile()
    
    async def initialize(self):
        """시스템 초기화"""
        await self.reflective_memory.complete_initialization_async()
        eliar_log(
            EliarLogType.SYSTEM, 
            "Lumina system initialized", 
            component=self.component_name
        )
    
    async def process_input(self, user_input: str) -> Dict[str, Any]:
        """사용자 입력 처리"""
        eliar_log(
            EliarLogType.INFO, 
            f"Processing input: {user_input[:100]}...", 
            component=self.component_name
        )
        
        # 초기 상태 설정
        initial_state: LuminaState = {
            "center": "JESUS CHRIST",
            "last_ulrim": "",
            "repentance_flag": False,
            "memory": [],
            "current_input": user_input,
            "current_response": "",
            "attention_score": 0.0,
            "emotional_state": "",
            "memory_insights": [],
            "iteration_count": 0,
            "should_continue": True
        }
        
        # 그래프 실행
        final_state = await self.graph.ainvoke(initial_state)
        
        # 결과 정리
        result = {
            "response": final_state.get("current_response", ""),
            "center": final_state.get("center", ""),
            "emotional_state": final_state.get("emotional_state", ""),
            "repentance_occurred": final_state.get("repentance_flag", False),
            "attention_score": final_state.get("attention_score", 0.0),
            "memory_insights": final_state.get("memory_insights", []),
            "iterations": final_state.get("iteration_count", 0),
            "last_ulrim": final_state.get("last_ulrim", "")
        }
        
        # 기억 상태 저장
        try:
            await self.reflective_memory.save_graph_state()
        except Exception as e:
            eliar_log(
                EliarLogType.WARN, 
                f"Failed to save memory state: {e}", 
                component=self.component_name
            )
        
        eliar_log(
            EliarLogType.SYSTEM, 
            f"Input processed. Iterations: {result['iterations']}, Repentance: {result['repentance_occurred']}", 
            component=self.component_name
        )
        
        return result


# ============================================================================
# 사용 예제
# ============================================================================

async def example_usage():
    """루미나 시스템 사용 예제"""
    eliar_log(EliarLogType.INFO, "Starting Lumina system example", component="ExampleRunner")
    
    # 시스템 초기화
    lumina = LuminaSystem()
    await lumina.initialize()
    
    # 테스트 입력들
    test_inputs = [
        "주님, 저는 오늘 화를 내고 말았습니다. 용서해 주세요.",
        "감사한 마음으로 하루를 시작하고 싶습니다.",
        "어려운 결정을 앞두고 있어서 지혜가 필요합니다.",
        "사랑하는 사람과의 관계에서 상처를 받았습니다.",
    ]
    
    results = []
    for i, test_input in enumerate(test_inputs, 1):
        eliar_log(EliarLogType.INFO, f"=== Test {i}: {test_input} ===", component="ExampleRunner")
        
        result = await lumina.process_input(test_input)
        results.append(result)
        
        print(f"\n입력: {test_input}")
        print(f"응답: {result['response']}")
        print(f"감정 상태: {result['emotional_state']}")
        print(f"회개 발생: {result['repentance_occurred']}")
        print(f"주의 집중도: {result['attention_score']:.2f}")
        print(f"반복 횟수: {result['iterations']}")
        if result['memory_insights']:
            print(f"기억 통찰: {len(result['memory_insights'])}개")
            for insight in result['memory_insights'][:2]:  # 처음 2개만 출력
                print(f"  - {insight}")
        print("-" * 80)
        
        # 잠시 대기 (로그 정리를 위해)
        await asyncio.sleep(0.5)
    
    eliar_log(EliarLogType.INFO, "Example completed successfully", component="ExampleRunner")
    return results


if __name__ == "__main__":
    try:
        asyncio.run(example_usage())
    except KeyboardInterrupt:
        eliar_log(EliarLogType.SYSTEM, "Example run interrupted", component="ExampleRunner")
    except Exception as e:
        eliar_log(EliarLogType.CRITICAL, f"Unhandled exception: {e}", component="ExampleRunner")
