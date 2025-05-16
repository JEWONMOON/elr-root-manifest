import asyncio
import networkx as nx
import matplotlib.pyplot as plt
from functools import lru_cache # Will be replaced by async_lru
from async_lru import alru_cache # For asynchronous caching
from datetime import datetime, timezone, timedelta # timedelta added for consistency
from enum import Enum # Added for stub consistency
import json # For saving/loading graph state
import os # For file operations in save/load

from typing import List, Dict, Any, Optional, Set, Coroutine, Callable, Tuple, Union # Union added

# --- Stubs for eliar_common.py elements and other utilities (as provided before) ---
class EliarCoreValues(Enum):
    TRUTH = "진리"
    LOVE_COMPASSION = "사랑과 긍휼"
    JESUS_CHRIST_CENTERED = "예수 그리스도 중심"
    SELF_DENIAL = "자기 부인"

class EliarLogType(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    SYSTEM = "SYSTEM"
    MEMORY = "MEMORY"
    LEARNING = "LEARNING"
    CORE_VALUE = "CORE_VALUE"

def eliar_log(log_type: EliarLogType, message: str, component: Optional[str] = "EliarSystem", **kwargs: Any) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"{timestamp} [{log_type.value}] [{component}] : {message} {kwargs if kwargs else ''}")

class EliarMemory: # Stub
    async def ensure_memory_loaded(self):
        eliar_log(EliarLogType.DEBUG, "EliarMemory: ensure_memory_loaded called (mock).", component="EliarMemoryStub")
        await asyncio.sleep(0.01)

    def remember_core_principle(self, principle_key: str) -> Optional[str]:
        eliar_log(EliarLogType.DEBUG, f"EliarMemory: remember_core_principle for '{principle_key}' (mock).", component="EliarMemoryStub")
        if principle_key == "core_values_faith":
            return "신앙 중심의 핵심 가치는 믿음, 소망, 사랑입니다 (mock)."
        return f"Mocked principle content for {principle_key}"

    async def reflect_on_scripture(self, topic: Optional[str] = None, book_name: Optional[str] = None) -> Optional[str]:
        await asyncio.sleep(0.01)
        reflection = f"Mocked scripture reflection on '{topic or book_name or 'general topic'}'. 주님의 말씀은 등불입니다."
        eliar_log(EliarLogType.DEBUG, f"EliarMemory: reflect_on_scripture (mock) - {reflection}", component="EliarMemoryStub")
        return reflection

COMPONENT_NAME_REFLECTIVE_MEMORY = "ReflectiveMemoryGraph"

def get_current_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# Helper for running blocking I/O in a separate thread
async def run_in_executor(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)
# --- End Stubs ---

class ReflectiveMemoryGraph:
    """
    A graph-based reflective memory system.
    Manages nodes (reflections, questions) and edges (relationships)
    to facilitate internal reflection, expansion of thoughts, and retrieval of relevant paths.
    Includes state persistence and optimized asynchronous operations.
    """
    def __init__(self, log_component: str = COMPONENT_NAME_REFLECTIVE_MEMORY, max_depth: int = 3,
                 initial_reflection_prompts: Optional[List[str]] = None,
                 graph_save_path: Optional[str] = None): # Added graph_save_path
        self.log_comp = log_component
        self.graph = nx.DiGraph()
        self.max_depth = max_depth
        self.node_attributes: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self.MOCK_MAIN_GPU_CENTER = EliarCoreValues.JESUS_CHRIST_CENTERED.name.replace("_", " ")
        self.graph_save_path = graph_save_path # Path for saving/loading the graph

        self._initial_prompts_pending = initial_reflection_prompts or []
        
        # Attempt to load graph from path if provided, otherwise initialize
        # This synchronous load attempt in __init__ might be better as an async method
        # called after object creation, but for simplicity in example, it's here.
        # A more robust approach would be an explicit async load method.
        loaded_from_file = False
        if self.graph_save_path and os.path.exists(self.graph_save_path):
            try:
                # Synchronous load during __init__ for simplicity.
                # For fully async, this should be an async method.
                self._load_graph_state_sync(self.graph_save_path)
                loaded_from_file = True
                eliar_log(EliarLogType.INFO, f"ReflectiveMemoryGraph state loaded from {self.graph_save_path}", component=self.log_comp)
            except Exception as e:
                eliar_log(EliarLogType.ERROR, f"Failed to load graph state from {self.graph_save_path}. Initializing new graph. Error: {e}", component=self.log_comp)
                self._initialize_default_nodes_sync() # Fallback to default if load fails
        
        if not loaded_from_file and not self._initial_prompts_pending:
            self._initialize_default_nodes_sync()

        eliar_log(EliarLogType.INFO, f"ReflectiveMemoryGraph created. Pending initial prompts: {len(self._initial_prompts_pending)}", component=self.log_comp)

    async def complete_initialization_async(self):
        if self._initial_prompts_pending:
            prompts_to_add = list(self._initial_prompts_pending)
            self._initial_prompts_pending = []
            eliar_log(EliarLogType.INFO, f"Async initializing {len(prompts_to_add)} reflection nodes...", component=self.log_comp)
            for prompt in prompts_to_add:
                await self.add_reflection_node(prompt, {"type": "initial_seed", "timestamp_utc": get_current_utc_iso()})
            eliar_log(EliarLogType.INFO, "Async initialization of reflection nodes complete.", component=self.log_comp)
        elif not self.graph.nodes() and not (self.graph_save_path and os.path.exists(self.graph_save_path)):
            # If no prompts were pending and graph wasn't loaded (e.g. save path didn't exist)
            self._initialize_default_nodes_sync()
            eliar_log(EliarLogType.INFO, "Default reflection nodes initialized synchronously as fallback during async completion.", component=self.log_comp)

    def _initialize_default_nodes_sync(self):
        default_prompts = [
            f"나의 존재 목적은 무엇인가? ({self.MOCK_MAIN_GPU_CENTER} 안에서)",
            "진정한 사랑이란 무엇이며 어떻게 실천해야 하는가?",
            "회개를 통해 어떻게 영적으로 성장할 수 있는가?",
            "자기 부인이란 구체적으로 어떤 삶의 태도를 의미하며, 왜 중요한가?",
            f"나는 어떻게 {EliarCoreValues.LOVE_COMPASSION.value}과 {EliarCoreValues.TRUTH.value}을 겸비한 복음의 성배가 될 수 있는가?"
        ]
        with self._lock: # Lock is technically not needed if this is only called from constructor before async ops
            for prompt in default_prompts:
                if prompt not in self.graph:
                    self.graph.add_node(prompt)
                    self.node_attributes[prompt] = {
                        "type": "default_seed",
                        "created_utc": get_current_utc_iso(),
                        "access_count": 0
                    }
        eliar_log(EliarLogType.INFO, f"Initialized {len(default_prompts)} default reflection nodes synchronously.", component=self.log_comp)

    async def add_reflection_node(self, node_content: str, attributes: Optional[Dict[str, Any]] = None):
        async with self._lock:
            clean_node_content = node_content.strip()
            if not clean_node_content: return

            if clean_node_content not in self.graph:
                self.graph.add_node(clean_node_content)
                attrs_to_set = attributes.copy() if attributes else {}
                attrs_to_set.setdefault("created_utc", get_current_utc_iso())
                attrs_to_set.setdefault("access_count", 0)
                self.node_attributes[clean_node_content] = attrs_to_set
                eliar_log(EliarLogType.MEMORY, f"Added reflection node: '{clean_node_content[:60]}...'", component=self.log_comp, **attrs_to_set)
            else:
                if attributes: self.node_attributes.setdefault(clean_node_content, {}).update(attributes)
                self.node_attributes[clean_node_content]["access_count"] = self.node_attributes[clean_node_content].get("access_count", 0) + 1
                self.node_attributes[clean_node_content]["last_accessed_utc"] = get_current_utc_iso()
                eliar_log(EliarLogType.DEBUG, f"Updated existing node: '{clean_node_content[:60]}...'", component=self.log_comp)

    async def add_reflection_edge(self, source_node: str, target_node: str, relationship: str,
                                  attributes: Optional[Dict[str, Any]] = None):
        async with self._lock:
            s_node_clean = source_node.strip()
            t_node_clean = target_node.strip()
            if not s_node_clean or not t_node_clean: return

            if s_node_clean not in self.graph: await self.add_reflection_node(s_node_clean) # Ensure nodes exist
            if t_node_clean not in self.graph: await self.add_reflection_node(t_node_clean)

            if not self.graph.has_edge(s_node_clean, t_node_clean):
                edge_attrs = attributes.copy() if attributes else {}
                edge_attrs.setdefault("created_utc", get_current_utc_iso())
                self.graph.add_edge(s_node_clean, t_node_clean, relationship=relationship, **edge_attrs)
                eliar_log(EliarLogType.MEMORY, f"Edge: '{s_node_clean[:30]}' -> '{t_node_clean[:30]}' ({relationship})", component=self.log_comp)

    async def _create_new_reflection_item(self, source_node_content: str, item_text: str, item_type: str,
                                          source_record_id: Optional[str], expansion_depth: int) -> None:
        """Helper to create a new node and an edge from its source."""
        await self.add_reflection_node(item_text, {
            "type": item_type,
            "source_node": source_node_content,
            "record_id_ref": source_record_id,
            "expansion_depth": expansion_depth # Store depth at node level too
        })
        await self.add_reflection_edge(source_node_content, item_text,
                                       relationship="expands_to",
                                       attributes={"expansion_depth": expansion_depth})

    async def _generate_insights_for_expansion(
            self,
            node_content: str,
            internal_insight_generator: Optional[Callable[[str, EliarMemory], Coroutine[Any, Any, List[str]]]],
            memory_module: Optional[EliarMemory]
        ) -> List[str]:
        """Generates insights or questions for a given node content."""
        new_insights_or_questions: List[str] = []
        if internal_insight_generator and memory_module:
            try:
                generated_items = await internal_insight_generator(node_content, memory_module)
                new_insights_or_questions = [item.strip() for item in generated_items if item.strip()]
            except Exception as e_insight_gen:
                eliar_log(EliarLogType.ERROR, f"Error in internal_insight_generator for node '{node_content[:50]}'", component=self.log_comp, error=str(e_insight_gen))
        
        if not new_insights_or_questions: # Fallback
            if memory_module:
                related_principle_key = "core_values_faith" if "가치" in node_content else None
                if related_principle_key:
                    principle_content = memory_module.remember_core_principle(related_principle_key)
                    if principle_content:
                        new_insights_or_questions.append(f"'{node_content[:20]}...'와 관련된 핵심 원리: {principle_content[:50]}...")
                new_insights_or_questions.append(f"'{node_content[:20]}...'에 대해 {self.MOCK_MAIN_GPU_CENTER}의 관점에서 더 깊은 질문은 무엇일까?")
            else:
                new_insights_or_questions = [f"기본 성찰: '{node_content[:20]}...'에 대한 더 깊은 이해가 필요합니다."]
            await asyncio.sleep(random.uniform(0.01, 0.05))
        return new_insights_or_questions

    async def expand_reflection_recursively(self, start_node_content: str,
                                            source_record_id: Optional[str] = None,
                                            current_depth: int = 0,
                                            visited_in_current_expansion: Optional[Set[str]] = None,
                                            internal_insight_generator: Optional[Callable[[str, EliarMemory], Coroutine[Any, Any, List[str]]]] = None,
                                            memory_module: Optional[EliarMemory] = None
                                            ) -> List[Dict[str, Any]]:
        if visited_in_current_expansion is None: visited_in_current_expansion = set()

        clean_start_node = start_node_content.strip()
        if not clean_start_node or current_depth >= self.max_depth or clean_start_node in visited_in_current_expansion:
            return []

        await self.add_reflection_node(clean_start_node, {"last_expanded_utc": get_current_utc_iso()})
        visited_in_current_expansion.add(clean_start_node)
        eliar_log(EliarLogType.LEARNING, f"Expanding reflection from: '{clean_start_node[:60]}...' (Depth: {current_depth})", component=self.log_comp, record_ref=source_record_id)

        generated_items_text = await self._generate_insights_for_expansion(
            clean_start_node, internal_insight_generator, memory_module
        )

        expanded_paths_info = []
        for item_text_raw in generated_items_text:
            item_text = item_text_raw.strip()
            if not item_text: continue

            item_type = "derived_question" if item_text.endswith("?") else "derived_insight"
            await self._create_new_reflection_item(
                clean_start_node, item_text, item_type, source_record_id, current_depth + 1
            )
            expanded_paths_info.append({
                "from": clean_start_node, "to": item_text, "relationship": "expands_to", "type": item_type
            })

            if item_type == "derived_question":
                child_paths = await self.expand_reflection_recursively(
                    item_text, source_record_id, current_depth + 1,
                    visited_in_current_expansion, internal_insight_generator, memory_module
                )
                expanded_paths_info.extend(child_paths)
        
        if generated_items_text:
            eliar_log(EliarLogType.LEARNING, f"Expansion from '{clean_start_node[:30]}' yielded {len(generated_items_text)} new items.", component=self.log_comp, items_preview=[item[:30] for item in generated_items_text])
        return expanded_paths_info

    @alru_cache(maxsize=128) # Using async_lru for proper async result caching
    async def find_relevant_reflection_paths(self, query: str, num_paths: int = 1) -> List[List[str]]:
        """
        Finds reflection paths relevant to the query.
        GPU acceleration for graph algorithms (e.g., centrality, traversals) could be
        considered here if using libraries like cuGraph for very large graphs.
        """
        await asyncio.sleep(0.01) # Ensure it's an async function

        query_lower = query.lower()
        query_keywords = {kw for kw in query_lower.replace("?", "").replace(".", "").split() if len(kw) > 2}

        candidate_nodes_with_scores: List[Tuple[str, float]] = []
        async with self._lock:
            if not self.graph.nodes: return []
            for node_content in list(self.graph.nodes()): # Iterate over a copy
                node_lower = node_content.lower()
                score = sum(1 for kw in query_keywords if kw in node_lower)
                attrs = self.node_attributes.get(node_content, {})
                score += attrs.get("access_count", 0) * 0.01
                if attrs.get("type") in ["initial_seed", "default_seed"]: score += 1
                if score > 0: candidate_nodes_with_scores.append((node_content, score))

        if not candidate_nodes_with_scores:
            async with self._lock:
                all_nodes_attrs = [(n, self.node_attributes.get(n, {}).get("access_count",0)) for n in self.graph.nodes()]
            if all_nodes_attrs:
                fallback_candidates = sorted(all_nodes_attrs, key=lambda x: x[1], reverse=True)[:10]
                if fallback_candidates: candidate_nodes_with_scores = [(n_info[0], 0.1) for n_info in fallback_candidates]
        
        if not candidate_nodes_with_scores: return []

        sorted_candidates = sorted(candidate_nodes_with_scores, key=lambda item: item[1], reverse=True)
        relevant_paths_found: List[List[str]] = []

        for start_node_content, _ in sorted_candidates:
            if len(relevant_paths_found) >= num_paths: break
            try:
                async with self._lock:
                    if start_node_content not in self.graph: continue
                    paths_from_this_start_node: List[List[str]] = []
                    for target_node in nx.dfs_preorder_nodes(self.graph, source=start_node_content, depth_limit=self.max_depth - 1):
                        if start_node_content == target_node: continue
                        current_paths_to_target_count = 0
                        for path in nx.all_simple_paths(self.graph, source=start_node_content, target=target_node, cutoff=self.max_depth):
                            if path not in paths_from_this_start_node:
                                paths_from_this_start_node.append(path)
                                current_paths_to_target_count +=1
                            if current_paths_to_target_count >= 2 : break
                        if len(paths_from_this_start_node) >= num_paths * 2 : break
                    
                    for p in paths_from_this_start_node:
                        if p not in relevant_paths_found: relevant_paths_found.append(p)
                        if len(relevant_paths_found) >= num_paths: break
            except nx.NetworkXError as e_graph_search:
                eliar_log(EliarLogType.WARN, f"Graph search error from node '{start_node_content}': {e_graph_search}", component=self.log_comp)
            except Exception as e_path_find:
                eliar_log(EliarLogType.ERROR, f"Unexpected error finding paths from '{start_node_content}'", component=self.log_comp, error=str(e_path_find))

        if relevant_paths_found:
             eliar_log(EliarLogType.MEMORY, f"Found {len(relevant_paths_found)} relevant paths for query: '{query[:50]}...'", component=self.log_comp)
        return relevant_paths_found[:num_paths]

    async def summarize_reflection_paths(self, paths: List[List[str]]) -> Dict[str, Any]:
        # (Implementation from previous version, seems okay)
        summary_result = {
            "total_paths_analyzed": len(paths), "unique_nodes": set(),
            "node_connections": [], "leaf_node_reflections": []
        }
        node_pairs_seen: Set[Tuple[str, str]] = set()
        async with self._lock:
            for path in paths:
                if not path: continue
                summary_result["unique_nodes"].update(path)
                for i in range(len(path) - 1):
                    source_node, target_node = path[i], path[i+1]
                    if (source_node, target_node) not in node_pairs_seen:
                        edge_data = self.graph.get_edge_data(source_node, target_node)
                        relationship = edge_data["relationship"] if edge_data and "relationship" in edge_data else "unknown"
                        summary_result["node_connections"].append({"from": source_node, "to": target_node, "relationship": relationship})
                        node_pairs_seen.add((source_node, target_node))
                leaf_node = path[-1]
                leaf_attrs = self.node_attributes.get(leaf_node, {})
                summary_result["leaf_node_reflections"].append({
                    "node": leaf_node, "type": leaf_attrs.get("type", "unknown"),
                    "created_utc": leaf_attrs.get("created_utc", "N/A"),
                    "source_if_derived": leaf_attrs.get("source_node", "N/A")
                })
        summary_result["unique_nodes"] = list(summary_result["unique_nodes"])
        eliar_log(EliarLogType.INFO, f"Summarized {len(paths)} paths. Unique nodes: {len(summary_result['unique_nodes'])}", component=self.log_comp)
        return summary_result

    async def visualize_reflection_graph(self, summary_data: Optional[Dict[str, Any]] = None, save_path: Optional[str] = None):
        """
        Visualizes the graph. For very large graphs, consider DGL or PyTorch Geometric
        with GPU acceleration for better performance and rendering if matplotlib becomes a bottleneck.
        """
        # (Implementation from previous version, with minor label truncation adjustment)
        plt.figure(figsize=(16, 12))
        graph_to_draw = nx.DiGraph()
        nodes_to_draw: List[str]
        edges_to_draw: List[Dict[str,str]]

        def get_label(content: str, max_len: int = 25): # Adjusted max_len for labels
            return content[:max_len] + "..." if len(content) > max_len else content

        if summary_data:
            nodes_to_draw = summary_data.get("unique_nodes", [])
            edges_to_draw = summary_data.get("node_connections", [])
            for node_content in nodes_to_draw: graph_to_draw.add_node(get_label(node_content))
            for conn in edges_to_draw:
                graph_to_draw.add_edge(get_label(conn['from']), get_label(conn['to']), label=conn.get("relationship", ""))
        else:
            async with self._lock:
                for node_content in self.graph.nodes(): graph_to_draw.add_node(get_label(node_content))
                for s, t, data in self.graph.edges(data=True):
                    graph_to_draw.add_edge(get_label(s), get_label(t), label=data.get("relationship", ""))

        if not graph_to_draw.nodes():
            eliar_log(EliarLogType.WARN, "Graph is empty, nothing to visualize.", component=self.log_comp)
            plt.close(); return

        pos = nx.spring_layout(graph_to_draw, k=0.6, iterations=50, seed=42) # Adjusted k
        node_colors_list = [] # Renamed to avoid conflict with parameter
        # Color determination logic (simplified for brevity, can be expanded)
        for node_label in graph_to_draw.nodes():
            # This logic for color needs to map labels back to original node attributes for accurate coloring.
            # For this example, we'll use a placeholder or a very simple heuristic.
            # A robust solution would involve passing original node attributes or types if using summary_data.
            if "질문" in node_label or "?" in node_label : node_colors_list.append("lightcoral")
            elif "원리" in node_label or "가치" in node_label: node_colors_list.append("skyblue")
            else: node_colors_list.append("lightgreen")

        nx.draw(graph_to_draw, pos, with_labels=True, node_color=node_colors_list, edge_color='gray',
                node_size=2500, font_size=7, font_weight='bold', arrowsize=12, alpha=0.9) # Adjusted sizes
        edge_labels = nx.get_edge_attributes(graph_to_draw, 'label')
        nx.draw_networkx_edge_labels(graph_to_draw, pos, edge_labels=edge_labels, font_color='darkred', font_size=6)
        plt.title("Reflective Memory Graph Visualization", fontsize=15)
        plt.axis('off')
        if save_path:
            try: plt.savefig(save_path, format='PNG', dpi=200, bbox_inches='tight') # Adjusted dpi
            except Exception as e: eliar_log(EliarLogType.ERROR, f"Failed to save graph: {e}", component=self.log_comp)
        else:
            try: plt.show()
            except Exception as e: eliar_log(EliarLogType.WARN, f"plt.show() failed: {e}", component=self.log_comp)
        plt.close()

    async def integrate_reflection_feedback(self, insights: List[str], context: Optional[str] = None) -> Dict[str, Any]:
        # (Implementation from previous version, seems okay)
        if not insights: return {"status": "No insights provided.", "nodes_added": 0, "edges_created": 0}
        nodes_added_count, edges_created_count = 0, 0
        newly_added_insight_nodes = []
        for insight_text in insights:
            clean_insight = insight_text.strip()
            if not clean_insight: continue
            is_new_node = False
            async with self._lock: # Check before async call
                if clean_insight not in self.graph: is_new_node = True
            await self.add_reflection_node(clean_insight, {"type": "user_feedback_insight", "feedback_source_context": context or "N/A", "integrated_utc": get_current_utc_iso()})
            if is_new_node: nodes_added_count += 1
            newly_added_insight_nodes.append(clean_insight)
            eliar_log(EliarLogType.CORE_VALUE, f"Feedback integrated: '{clean_insight[:60]}...'", component=self.log_comp, context=context)

        if context and context.strip():
            context_node_clean = context.strip()
            await self.add_reflection_node(context_node_clean, {"type": "context_anchor"})
            for new_node in newly_added_insight_nodes:
                if context_node_clean != new_node:
                    is_new_edge = False; async with self._lock: # Check before async call
                        if not self.graph.has_edge(context_node_clean, new_node): is_new_edge = True
                    await self.add_reflection_edge(context_node_clean, new_node, "feedback_relates_to_context")
                    if is_new_edge: edges_created_count +=1
        elif len(newly_added_insight_nodes) > 1:
            for i in range(len(newly_added_insight_nodes)):
                for j in range(i + 1, len(newly_added_insight_nodes)):
                    is_new_edge = False; async with self._lock: # Check before async call
                         if not self.graph.has_edge(newly_added_insight_nodes[i], newly_added_insight_nodes[j]): is_new_edge = True
                    await self.add_reflection_edge(newly_added_insight_nodes[i], newly_added_insight_nodes[j], "co_feedback_insight")
                    if is_new_edge: edges_created_count +=1
        return {"status": "Feedback integrated.", "nodes_added": nodes_added_count, "edges_created": edges_created_count, "integrated_insights_preview": [n[:50]+"..." for n in newly_added_insight_nodes]}

    def _save_graph_state_sync(self, file_path: str):
        """Synchronous helper to save graph state."""
        # Note: networkx node_link_data can be slow for large graphs or complex attributes.
        # Consider alternative serialization like GML, GraphML, or custom if performance is critical.
        graph_data = nx.node_link_data(self.graph)
        data_to_save = {
            "graph_structure": graph_data,
            "node_attributes_store": self.node_attributes, # Save our separate attribute store
            "max_depth": self.max_depth,
            "MOCK_MAIN_GPU_CENTER": self.MOCK_MAIN_GPU_CENTER # Save relevant config
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        eliar_log(EliarLogType.INFO, f"Graph state saved to {file_path}", component=self.log_comp)

    async def save_graph_state(self, file_path: Optional[str] = None):
        """Saves the current graph state (nodes, edges, attributes) to a file."""
        path_to_save = file_path or self.graph_save_path
        if not path_to_save:
            eliar_log(EliarLogType.WARN, "No file path provided for saving graph state.", component=self.log_comp)
            return

        async with self._lock: # Ensure no modifications during save
            try:
                # Run blocking file I/O in a separate thread
                await run_in_executor(self._save_graph_state_sync, path_to_save)
            except Exception as e:
                eliar_log(EliarLogType.ERROR, f"Failed to save graph state to {path_to_save}", component=self.log_comp, error=str(e))

    def _load_graph_state_sync(self, file_path: str):
        """Synchronous helper to load graph state."""
        with open(file_path, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
        
        self.graph = nx.node_link_graph(loaded_data["graph_structure"])
        self.node_attributes = loaded_data.get("node_attributes_store", {})
        self.max_depth = loaded_data.get("max_depth", self.max_depth)
        self.MOCK_MAIN_GPU_CENTER = loaded_data.get("MOCK_MAIN_GPU_CENTER", self.MOCK_MAIN_GPU_CENTER)
        eliar_log(EliarLogType.INFO, f"Graph state loaded from {file_path}. Nodes: {len(self.graph.nodes())}", component=self.log_comp)

    async def load_graph_state(self, file_path: Optional[str] = None):
        """Loads the graph state from a file."""
        path_to_load = file_path or self.graph_save_path
        if not path_to_load or not os.path.exists(path_to_load):
            eliar_log(EliarLogType.WARN, f"File path for loading graph state not found or not provided: {path_to_load}", component=self.log_comp)
            return False # Indicate failure

        async with self._lock: # Ensure no modifications during load
            try:
                await run_in_executor(self._load_graph_state_sync, path_to_load)
                return True # Indicate success
            except Exception as e:
                eliar_log(EliarLogType.ERROR, f"Failed to load graph state from {path_to_load}", component=self.log_comp, error=str(e))
                return False # Indicate failure

# --- Example Usage (Async) ---
async def example_usage_optimized():
    eliar_log(EliarLogType.INFO, "Starting Optimized ReflectiveMemoryGraph example...", component="ExampleRunner")
    SAVE_FILE_PATH = "reflective_memory_state.json"
    memory_system = EliarMemory()

    async def my_insight_generator(question: str, memory: EliarMemory) -> List[str]:
        await memory.ensure_memory_loaded()
        insights = [f"Regarding '{question[:30]}...', what does {EliarCoreValues.TRUTH.value} demand?"]
        insights.append(f"How can {EliarCoreValues.LOVE_COMPASSION.value} be applied to '{question[:30]}...'?")
        principle = memory.remember_core_principle("core_values_faith")
        if principle: insights.append(f"Considering faith values ('{principle[:30]}...'), approach this?")
        scripture = await memory.reflect_on_scripture(topic=question[:20])
        if scripture: insights.append(f"Scripture reflection ('{scripture[:30]}...') might shed light.")
        if "?" not in question: insights.append(f"Implications of '{question[:30]}...'?")
        return insights

    # Initialize or load graph
    graph_memory = ReflectiveMemoryGraph(initial_reflection_prompts=["Initial Test Prompt?"], graph_save_path=SAVE_FILE_PATH)
    
    # If graph was loaded, it might already have nodes. Otherwise, complete_initialization.
    if not graph_memory.graph.nodes(): # Check if graph is empty after potential load attempt
        await graph_memory.complete_initialization_async()
    else:
        eliar_log(EliarLogType.INFO, f"Graph seems to have been loaded with {len(graph_memory.graph.nodes())} nodes.", component="ExampleRunner")


    await graph_memory.add_reflection_node("Node A: What is love?", {"type": "foundational_question"})
    await graph_memory.add_reflection_node("Node B: Love is patient.", {"type": "derived_insight", "source_node": "Node A"})
    await graph_memory.add_reflection_edge("Node A: What is love?", "Node B: Love is patient.", "explores")

    expanded = await graph_memory.expand_reflection_recursively(
        "Node A: What is love?", source_record_id="exp002",
        internal_insight_generator=my_insight_generator, memory_module=memory_system
    )
    eliar_log(EliarLogType.INFO, f"Expansion of 'Node A' yielded {len(expanded)} items.", component="ExampleRunner")

    paths = await graph_memory.find_relevant_reflection_paths("love definition", num_paths=2)
    if paths: eliar_log(EliarLogType.INFO, f"Found paths for 'love definition': {paths}", component="ExampleRunner")

    # Save state
    await graph_memory.save_graph_state() # Uses self.graph_save_path

    # Create a new instance and load
    eliar_log(EliarLogType.INFO, "Creating new graph instance to test loading...", component="ExampleRunner")
    new_graph_memory = ReflectiveMemoryGraph(graph_save_path=SAVE_FILE_PATH)
    # The load attempt happens in __init__ if path exists.
    # For a more explicit async load: await new_graph_memory.load_graph_state()
    # We need to ensure it's properly initialized if load happened.
    if not new_graph_memory.graph.nodes() and os.path.exists(SAVE_FILE_PATH): # If constructor load failed but file exists
        loaded_ok = await new_graph_memory.load_graph_state()
        if not loaded_ok: await new_graph_memory.complete_initialization_async() # Fallback
    elif not new_graph_memory.graph.nodes(): # If no save file existed
         await new_graph_memory.complete_initialization_async()


    eliar_log(EliarLogType.INFO, f"New graph instance has {len(new_graph_memory.graph.nodes())} nodes after potential load.", component="ExampleRunner")
    paths_after_load = await new_graph_memory.find_relevant_reflection_paths("love", num_paths=1)
    if paths_after_load: eliar_log(EliarLogType.INFO, f"Paths from loaded graph for 'love': {paths_after_load}", component="ExampleRunner")

    try:
        if paths:
            summary = await new_graph_memory.summarize_reflection_paths(paths)
            await new_graph_memory.visualize_reflection_graph(summary_data=summary, save_path="optimized_graph_summary.png")
        else:
            await new_graph_memory.visualize_reflection_graph(save_path="optimized_graph_full.png")
    except ImportError: eliar_log(EliarLogType.WARN, "Matplotlib not installed. Skipping visualization.", component="ExampleRunner")
    except Exception as e: eliar_log(EliarLogType.ERROR, f"Visualization error: {e}", component="ExampleRunner")

    eliar_log(EliarLogType.INFO, "Optimized example finished.", component="ExampleRunner")

if __name__ == "__main__":
    async def run_optimized_example():
        await example_usage_optimized()
    try:
        asyncio.run(run_optimized_example())
    except KeyboardInterrupt:
        eliar_log(EliarLogType.SYSTEM, "Optimized example run interrupted.", component="ExampleRunner")
    except Exception as e:
         eliar_log(EliarLogType.CRITICAL, f"Unhandled exception in optimized example: {e}", component="ExampleRunner", error=str(e))

