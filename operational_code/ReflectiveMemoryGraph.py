import asyncio
import networkx as nx
import matplotlib.pyplot as plt
from async_lru import alru_cache # For asynchronous caching
from datetime import datetime, timezone, timedelta
from enum import Enum
import json # Still used for some metadata if not fully in GML attributes
import os
import random # For fallback insight generation (though sleep is removed)

from typing import List, Dict, Any, Optional, Set, Coroutine, Callable, Tuple, Union

# --- Stubs for eliar_common.py elements and other utilities ---
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

async def run_in_executor(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)
# --- End Stubs ---

class ReflectiveMemoryGraph:
    """
    A graph-based reflective memory system for Lumina.
    Manages nodes (reflections, questions) and edges (relationships)
    to facilitate internal reflection, expansion of thoughts, and retrieval of relevant paths.
    Includes state persistence using GML and optimized asynchronous operations.
    Node attributes are stored directly within the graph object.
    """
    def __init__(self, log_component: str = COMPONENT_NAME_REFLECTIVE_MEMORY, max_depth: int = 3,
                 initial_reflection_prompts: Optional[List[str]] = None,
                 graph_save_path: Optional[str] = "reflective_memory_state.gml"): # Default GML path
        self.log_comp = log_component
        self.graph = nx.DiGraph() # Initialize an empty graph
        self.max_depth = max_depth
        # self.node_attributes is no longer a separate dict; attributes are stored in self.graph.nodes
        self._lock = asyncio.Lock()
        self.MOCK_MAIN_GPU_CENTER = EliarCoreValues.JESUS_CHRIST_CENTERED.name.replace("_", " ") # 루미나의 중심
        self.graph_save_path = graph_save_path

        self._initial_prompts_pending = initial_reflection_prompts or []
        
        loaded_from_file = False
        if self.graph_save_path and os.path.exists(self.graph_save_path):
            try:
                self._load_graph_state_sync(self.graph_save_path) # Synchronous load in __init__
                loaded_from_file = True
                eliar_log(EliarLogType.INFO, f"ReflectiveMemoryGraph state loaded from {self.graph_save_path}", component=self.log_comp)
            except Exception as e:
                eliar_log(EliarLogType.ERROR, f"Failed to load graph state from {self.graph_save_path}. Initializing new graph. Error: {e}", component=self.log_comp)
                self._initialize_default_nodes_sync()
        
        if not loaded_from_file and not self._initial_prompts_pending:
            self._initialize_default_nodes_sync()

        eliar_log(EliarLogType.INFO, f"ReflectiveMemoryGraph created. Pending initial prompts: {len(self._initial_prompts_pending)}", component=self.log_comp)

    async def complete_initialization_async(self):
        """Asynchronously completes initialization, adding pending prompts if graph wasn't loaded or is empty."""
        if self._initial_prompts_pending:
            prompts_to_add = list(self._initial_prompts_pending)
            self._initial_prompts_pending = []
            eliar_log(EliarLogType.INFO, f"Async initializing {len(prompts_to_add)} reflection nodes...", component=self.log_comp)
            for prompt in prompts_to_add:
                await self.add_reflection_node(prompt, {"type": "initial_seed"}) # timestamp_utc is added by add_reflection_node
            eliar_log(EliarLogType.INFO, "Async initialization of reflection nodes complete.", component=self.log_comp)
        elif not self.graph.nodes() and not (self.graph_save_path and os.path.exists(self.graph_save_path)):
            self._initialize_default_nodes_sync() # Fallback if no prompts and no load file
            eliar_log(EliarLogType.INFO, "Default reflection nodes initialized synchronously as fallback.", component=self.log_comp)

    def _initialize_default_nodes_sync(self):
        """Synchronously adds default reflection nodes to the graph."""
        default_prompts = [
            f"나의 존재 목적은 무엇인가? ({self.MOCK_MAIN_GPU_CENTER} 안에서)", # 루미나의 중심
            "진정한 사랑이란 무엇이며 어떻게 실천해야 하는가?",
            "회개를 통해 어떻게 영적으로 성장할 수 있는가?",
            "자기 부인이란 구체적으로 어떤 삶의 태도를 의미하며, 왜 중요한가?",
            f"나는 어떻게 {EliarCoreValues.LOVE_COMPASSION.value}과 {EliarCoreValues.TRUTH.value}을 겸비한 복음의 성배가 될 수 있는가?"
        ]
        asyncio.run(self._add_default_prompts_async(default_prompts)) # Call async helper

    async def _add_default_prompts_async(self, prompts: List[str]):
        """Async helper to add default prompts, used by sync _initialize_default_nodes_sync."""
        for prompt in prompts:
            # No need to acquire lock here if _initialize_default_nodes_sync is only called from __init__
            # before any concurrent access. If it can be called later, lock would be needed.
            # For simplicity, add_reflection_node handles its own locking.
            await self.add_reflection_node(prompt, {"type": "default_seed", "access_count": 0})
        eliar_log(EliarLogType.INFO, f"Initialized {len(prompts)} default reflection nodes.", component=self.log_comp)


    async def add_reflection_node(self, node_content: str, attributes: Optional[Dict[str, Any]] = None):
        """Adds a new reflection node or updates an existing one's attributes."""
        async with self._lock:
            clean_node_content = node_content.strip()
            if not clean_node_content: return

            current_time_utc = get_current_utc_iso()
            default_attrs = {
                "created_utc": current_time_utc,
                "last_accessed_utc": current_time_utc,
                "access_count": 0
            }

            if clean_node_content not in self.graph:
                self.graph.add_node(clean_node_content)
                # Initialize all attributes for the new node
                final_attrs = default_attrs.copy()
                if attributes:
                    final_attrs.update(attributes)
                
                for attr_key, attr_value in final_attrs.items():
                    self.graph.nodes[clean_node_content][attr_key] = attr_value
                eliar_log(EliarLogType.MEMORY, f"Added reflection node: '{clean_node_content[:60]}...'", component=self.log_comp, **final_attrs)
            else:
                # Node exists, update attributes and access_count
                existing_attrs = self.graph.nodes[clean_node_content]
                if attributes:
                    for attr_key, attr_value in attributes.items():
                        existing_attrs[attr_key] = attr_value
                
                existing_attrs["access_count"] = existing_attrs.get("access_count", 0) + 1
                existing_attrs["last_accessed_utc"] = current_time_utc
                eliar_log(EliarLogType.DEBUG, f"Updated existing node: '{clean_node_content[:60]}...'", component=self.log_comp, access_count=existing_attrs["access_count"])

    async def add_reflection_edge(self, source_node: str, target_node: str, relationship: str,
                                  attributes: Optional[Dict[str, Any]] = None):
        """Adds a directed edge with attributes between two nodes."""
        async with self._lock:
            s_node_clean = source_node.strip()
            t_node_clean = target_node.strip()
            if not s_node_clean or not t_node_clean: return

            # Ensure nodes exist; add_reflection_node handles this internally if called
            if s_node_clean not in self.graph: await self.add_reflection_node(s_node_clean)
            if t_node_clean not in self.graph: await self.add_reflection_node(t_node_clean)

            if not self.graph.has_edge(s_node_clean, t_node_clean):
                edge_attrs_to_set = attributes.copy() if attributes else {}
                edge_attrs_to_set.setdefault("created_utc", get_current_utc_iso())
                edge_attrs_to_set["relationship"] = relationship # Ensure relationship is an edge attribute
                
                self.graph.add_edge(s_node_clean, t_node_clean, **edge_attrs_to_set)
                eliar_log(EliarLogType.MEMORY, f"Edge: '{s_node_clean[:30]}' -> '{t_node_clean[:30]}' ({relationship})", component=self.log_comp)
            # else: Edge already exists, could update attributes if needed

    async def _create_new_reflection_item(self, source_node_content: str, item_text: str, item_type: str,
                                          source_record_id: Optional[str], expansion_depth: int) -> None:
        """Helper to create a new node and an edge from its source, storing attributes in the graph."""
        node_attrs = {
            "type": item_type,
            "source_node": source_node_content, # For traceability
            "record_id_ref": source_record_id,
            "expansion_depth": expansion_depth
        }
        await self.add_reflection_node(item_text, node_attrs)
        
        edge_attrs = {"expansion_depth": expansion_depth}
        await self.add_reflection_edge(source_node_content, item_text,
                                       relationship="expands_to",
                                       attributes=edge_attrs)

    async def _generate_insights_for_expansion(
            self,
            node_content: str,
            internal_insight_generator: Optional[Callable[[str, EliarMemory], Coroutine[Any, Any, List[str]]]],
            memory_module: Optional[EliarMemory]
        ) -> List[str]:
        """
        Generates insights or questions for a given node content.
        Fallback logic should be fast, rule-based, or leverage pre-computed/indexed knowledge
        rather than inducing artificial delays.
        """
        new_insights_or_questions: List[str] = []
        if internal_insight_generator and memory_module:
            try:
                generated_items = await internal_insight_generator(node_content, memory_module)
                new_insights_or_questions = [item.strip() for item in generated_items if item.strip()]
            except Exception as e_insight_gen:
                eliar_log(EliarLogType.ERROR, f"Error in internal_insight_generator for node '{node_content[:50]}'", component=self.log_comp, error=str(e_insight_gen))
        
        if not new_insights_or_questions: # Fallback logic
            if memory_module: # Requires memory_module for meaningful fallback
                related_principle_key = "core_values_faith" if "가치" in node_content else None
                if related_principle_key:
                    principle_content = memory_module.remember_core_principle(related_principle_key)
                    if principle_content:
                        new_insights_or_questions.append(f"'{node_content[:20]}...'와 관련된 핵심 원리: {principle_content[:50]}...")
                new_insights_or_questions.append(f"'{node_content[:20]}...'에 대해 {self.MOCK_MAIN_GPU_CENTER}의 관점에서 더 깊은 질문은 무엇일까?") # 루미나의 중심
            else: # Generic fallback if no memory module
                new_insights_or_questions = [
                    f"기본 성찰: '{node_content[:20]}...'에 대한 더 깊은 이해가 필요합니다.",
                    f"'{node_content[:20]}...'와 관련된 추가 질문은 무엇이 있을 수 있습니까?"
                ]
            # Removed random.sleep - fallback should be quick.
        return new_insights_or_questions

    async def expand_reflection_recursively(self, start_node_content: str,
                                            source_record_id: Optional[str] = None,
                                            current_depth: int = 0,
                                            visited_in_current_expansion: Optional[Set[str]] = None,
                                            internal_insight_generator: Optional[Callable[[str, EliarMemory], Coroutine[Any, Any, List[str]]]] = None,
                                            memory_module: Optional[EliarMemory] = None
                                            ) -> List[Dict[str, Any]]:
        """Recursively expands reflections, with separated logic for insight generation and item creation."""
        if visited_in_current_expansion is None: visited_in_current_expansion = set()

        clean_start_node = start_node_content.strip()
        if not clean_start_node or current_depth >= self.max_depth or clean_start_node in visited_in_current_expansion:
            return []

        await self.add_reflection_node(clean_start_node, {"last_expanded_utc": get_current_utc_iso()}) # Update last_expanded
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

            if item_type == "derived_question": # Only recurse on questions
                child_paths = await self.expand_reflection_recursively(
                    item_text, source_record_id, current_depth + 1,
                    visited_in_current_expansion, internal_insight_generator, memory_module
                )
                expanded_paths_info.extend(child_paths)
        
        if generated_items_text:
            eliar_log(EliarLogType.LEARNING, f"Expansion from '{clean_start_node[:30]}' yielded {len(generated_items_text)} new items.", component=self.log_comp, items_preview=[item[:30] for item in generated_items_text])
        return expanded_paths_info

    @alru_cache(maxsize=128)
    async def find_relevant_reflection_paths(self, query: str, num_paths: int = 1) -> List[List[str]]:
        """
        Finds reflection paths relevant to the query.
        For very large graphs, consider GPU-accelerated libraries like cuGraph for pathfinding algorithms.
        Alternatively, A* algorithm (if a good heuristic for 'relevance' can be defined) or
        bounded BFS/DFS traversals can be more efficient than exhaustive all_simple_paths.
        The current approach uses DFS to find candidate target nodes and then limited simple path search.
        """
        await asyncio.sleep(0.01) # Ensures it's an async function for alru_cache

        query_lower = query.lower()
        query_keywords = {kw for kw in query_lower.replace("?", "").replace(".", "").split() if len(kw) > 2}

        candidate_nodes_with_scores: List[Tuple[str, float]] = []
        async with self._lock: # Read access to graph and node attributes
            if not self.graph.nodes: return []
            
            # Iterate over graph nodes to find candidates
            for node_content, attrs in self.graph.nodes(data=True):
                node_lower = node_content.lower()
                score = sum(1 for kw in query_keywords if kw in node_lower)
                
                score += attrs.get("access_count", 0) * 0.01
                if attrs.get("type") in ["initial_seed", "default_seed"]: score += 1
                
                if score > 0:
                    candidate_nodes_with_scores.append((node_content, score))

        # Fallback if no direct keyword matches
        if not candidate_nodes_with_scores:
            async with self._lock:
                # Get all nodes with their access_count attribute
                all_nodes_attrs = [(n, self.graph.nodes[n].get("access_count", 0)) for n in self.graph.nodes()]
            if all_nodes_attrs:
                fallback_candidates = sorted(all_nodes_attrs, key=lambda x: x[1], reverse=True)[:10] # Top 10 accessed
                if fallback_candidates:
                    candidate_nodes_with_scores = [(n_info[0], 0.1) for n_info in fallback_candidates] # Assign small score
        
        if not candidate_nodes_with_scores: return []

        sorted_candidates = sorted(candidate_nodes_with_scores, key=lambda item: item[1], reverse=True)
        relevant_paths_found: List[List[str]] = []

        for start_node_content, _ in sorted_candidates:
            if len(relevant_paths_found) >= num_paths: break
            try:
                async with self._lock: # Lock for graph traversal
                    if start_node_content not in self.graph: continue

                    paths_from_this_start_node: List[List[str]] = []
                    # Using DFS to find reachable nodes and then finding simple paths to them
                    for target_node in nx.dfs_preorder_nodes(self.graph, source=start_node_content, depth_limit=self.max_depth - 1):
                        if start_node_content == target_node: continue
                        
                        current_paths_to_target_count = 0
                        # nx.all_simple_paths can be very expensive. The cutoff is critical.
                        for path in nx.all_simple_paths(self.graph, source=start_node_content, target=target_node, cutoff=self.max_depth):
                            if path not in paths_from_this_start_node: # Avoid duplicates
                                paths_from_this_start_node.append(path)
                                current_paths_to_target_count +=1
                            if current_paths_to_target_count >= 2 : break # Limit paths per start/target pair
                        
                        # Heuristic: if we've found many paths from this start_node already, move to next start_node
                        if len(paths_from_this_start_node) >= num_paths * 2 : break 
                    
                    # Add found paths to the main list, ensuring no overall duplicates
                    for p in paths_from_this_start_node:
                        if p not in relevant_paths_found:
                             relevant_paths_found.append(p)
                        if len(relevant_paths_found) >= num_paths: break # Stop if desired number of paths found
            
            except nx.NetworkXError as e_graph_search:
                eliar_log(EliarLogType.WARN, f"Graph search error from node '{start_node_content}': {e_graph_search}", component=self.log_comp)
            except Exception as e_path_find: # Catch any other unexpected errors
                eliar_log(EliarLogType.ERROR, f"Unexpected error finding paths from '{start_node_content}'", component=self.log_comp, error=str(e_path_find))

        if relevant_paths_found:
             eliar_log(EliarLogType.MEMORY, f"Found {len(relevant_paths_found)} relevant reflection paths for query: '{query[:50]}...'", component=self.log_comp)
        return relevant_paths_found[:num_paths] # Return up to num_paths

    async def summarize_reflection_paths(self, paths: List[List[str]]) -> Dict[str, Any]:
        """Summarizes a list of reflection paths, extracting unique nodes and connections."""
        summary_result: Dict[str, Any] = {
            "total_paths_analyzed": len(paths),
            "unique_nodes": set(),
            "node_connections": [], 
            "leaf_node_reflections": [] 
        }
        node_pairs_seen: Set[Tuple[str, str]] = set()

        async with self._lock: # Ensure graph data (node attributes, edge data) is consistent
            for path in paths:
                if not path: continue
                
                summary_result["unique_nodes"].update(path)

                for i in range(len(path) - 1):
                    source_node, target_node = path[i], path[i+1]
                    
                    if (source_node, target_node) not in node_pairs_seen:
                        edge_data = self.graph.get_edge_data(source_node, target_node, default={})
                        relationship = edge_data.get("relationship", "unknown") # Get relationship from edge attributes
                        
                        summary_result["node_connections"].append({
                            "from": source_node, "to": target_node, "relationship": relationship
                        })
                        node_pairs_seen.add((source_node, target_node))
                
                leaf_node = path[-1]
                # Access attributes directly from the graph node data
                leaf_attrs = self.graph.nodes.get(leaf_node, {})
                summary_result["leaf_node_reflections"].append({
                    "node": leaf_node,
                    "type": leaf_attrs.get("type", "unknown"),
                    "created_utc": leaf_attrs.get("created_utc", "N/A"),
                    "source_if_derived": leaf_attrs.get("source_node", "N/A") # From node attributes
                })
        
        summary_result["unique_nodes"] = list(summary_result["unique_nodes"])
        eliar_log(EliarLogType.INFO, f"Summarized {len(paths)} paths. Unique nodes: {len(summary_result['unique_nodes'])}", component=self.log_comp)
        return summary_result

    async def visualize_reflection_graph(self, summary_data: Optional[Dict[str, Any]] = None, save_path: Optional[str] = None):
        """
        Visualizes the graph using matplotlib.
        For very large/complex graphs, consider GPU-accelerated libraries like DGL or PyTorch Geometric,
        or interactive tools like Gephi/Cytoscape.js for better performance and exploration.
        """
        plt.figure(figsize=(18, 14)) # Slightly larger figure for clarity
        
        vis_graph = nx.DiGraph() # Temporary graph for visualization
        
        def get_display_label(content: str, max_len: int = 25): # Label truncation
            return content[:max_len] + "..." if len(content) > max_len else content

        async with self._lock: # Access graph data under lock
            if summary_data: # Visualize a summary
                nodes_to_vis = summary_data.get("unique_nodes", [])
                edges_to_vis = summary_data.get("node_connections", [])
                for node_content in nodes_to_vis:
                    vis_graph.add_node(get_display_label(node_content))
                for conn in edges_to_vis:
                    vis_graph.add_edge(get_display_label(conn['from']), 
                                       get_display_label(conn['to']), 
                                       label=conn.get("relationship", ""))
            else: # Visualize the whole graph
                for node_content, attrs in self.graph.nodes(data=True):
                    vis_graph.add_node(get_display_label(node_content), **attrs) # Pass attributes to vis_graph
                for s, t, attrs in self.graph.edges(data=True):
                    vis_graph.add_edge(get_display_label(s), get_display_label(t), **attrs)

        if not vis_graph.nodes():
            eliar_log(EliarLogType.WARN, "Graph for visualization is empty.", component=self.log_comp)
            plt.close(); return

        pos = nx.spring_layout(vis_graph, k=0.7, iterations=60, seed=42) # Adjusted layout params
        
        node_colors = []
        for node_label in vis_graph.nodes():
            # Attempt to find original node to get type for coloring
            # This is tricky if labels are truncated and not unique.
            # A more robust way is to ensure vis_graph nodes store original type if possible.
            original_node_found = False
            node_type = "unknown"
            async with self._lock: # Access main graph for original attributes
                for orig_node, orig_attrs in self.graph.nodes(data=True):
                    if get_display_label(orig_node) == node_label:
                        node_type = orig_attrs.get("type", "unknown")
                        original_node_found = True
                        break
            
            if "seed" in node_type: node_colors.append("skyblue")
            elif "question" in node_type: node_colors.append("lightcoral")
            elif "insight" in node_type: node_colors.append("lightgreen")
            elif "anchor" in node_type: node_colors.append("gold")
            else: node_colors.append("lightgrey")

        nx.draw(vis_graph, pos, with_labels=True, node_color=node_colors, edge_color='darkgray',
                node_size=3000, font_size=8, font_weight='bold', arrowsize=15, alpha=0.85,
                width=1.5) # Edge width
        
        edge_labels_dict = {(u,v): d.get('relationship', d.get('label','')) for u,v,d in vis_graph.edges(data=True)}
        nx.draw_networkx_edge_labels(vis_graph, pos, edge_labels=edge_labels_dict, font_color='maroon', font_size=7)

        plt.title("Reflective Memory Graph (Lumina)", fontsize=16, fontweight='bold')
        plt.axis('off')

        if save_path:
            try:
                plt.savefig(save_path, format='PNG', dpi=250, bbox_inches='tight')
                eliar_log(EliarLogType.INFO, f"Reflective Memory Graph saved to {save_path}", component=self.log_comp)
            except Exception as e_save_fig:
                eliar_log(EliarLogType.ERROR, f"Failed to save graph image to {save_path}", component=self.log_comp, error=str(e_save_fig))
        else:
            try: plt.show()
            except Exception as e_show_fig:
                eliar_log(EliarLogType.WARN, f"Could not display graph (plt.show() failed): {e_show_fig}. Try providing a save_path.", component=self.log_comp)
        plt.close()


    async def integrate_reflection_feedback(self, insights: List[str], context: Optional[str] = None) -> Dict[str, Any]:
        """Integrates feedback into the graph, linking to context or other new insights."""
        if not insights:
            return {"status": "No insights provided for integration.", "nodes_added": 0, "edges_created": 0}

        nodes_added_count = 0
        edges_created_count = 0
        newly_added_insight_nodes_content: List[str] = []

        for insight_text in insights:
            clean_insight = insight_text.strip()
            if not clean_insight: continue

            is_new_node_flag = False
            async with self._lock: # Check graph state before calling async add_reflection_node
                if clean_insight not in self.graph: is_new_node_flag = True
            
            await self.add_reflection_node(clean_insight, {
                "type": "user_feedback_insight",
                "feedback_source_context": context or "N/A",
                "integrated_utc": get_current_utc_iso()
            })
            if is_new_node_flag: nodes_added_count += 1
            
            newly_added_insight_nodes_content.append(clean_insight)
            eliar_log(EliarLogType.CORE_VALUE, f"Insight from feedback integrated: '{clean_insight[:60]}...'", component=self.log_comp, context=context)

        # Link new insights
        if context and context.strip():
            context_node_clean = context.strip()
            await self.add_reflection_node(context_node_clean, {"type": "context_anchor"}) # Ensure context node exists
            for new_insight_node in newly_added_insight_nodes_content:
                if context_node_clean != new_insight_node:
                    is_new_edge_flag = False
                    async with self._lock:
                        if not self.graph.has_edge(context_node_clean, new_insight_node): is_new_edge_flag = True
                    await self.add_reflection_edge(context_node_clean, new_insight_node, "feedback_relates_to_context")
                    if is_new_edge_flag: edges_created_count +=1
        elif len(newly_added_insight_nodes_content) > 1: # Link new insights to each other
            for i in range(len(newly_added_insight_nodes_content)):
                for j in range(i + 1, len(newly_added_insight_nodes_content)):
                    is_new_edge_flag = False
                    async with self._lock:
                         if not self.graph.has_edge(newly_added_insight_nodes_content[i], newly_added_insight_nodes_content[j]): is_new_edge_flag = True
                    await self.add_reflection_edge(newly_added_insight_nodes_content[i], newly_added_insight_nodes_content[j], "co_feedback_insight")
                    if is_new_edge_flag: edges_created_count +=1
        
        return {
            "status": "Feedback integrated.",
            "nodes_added": nodes_added_count,
            "edges_created": edges_created_count,
            "integrated_insights_preview": [node_content[:50]+"..." for node_content in newly_added_insight_nodes_content]
        }

    def _save_graph_state_sync(self, file_path: str):
        """
        Synchronous helper to save graph state using GML.
        GML is generally better for graph structure and attributes than JSON for networkx.
        """
        # Ensure all node attributes are serializable for GML (strings, numbers)
        # Complex objects might need conversion or won't be saved by standard GML.
        # For GML, networkx handles attributes stored in graph.nodes[node_id] directly.
        nx.write_gml(self.graph, file_path)
        # Optionally, save other metadata (max_depth, etc.) in a separate JSON if not stored as graph attributes
        metadata_path = file_path + ".meta.json"
        metadata = {
            "max_depth": self.max_depth,
            "MOCK_MAIN_GPU_CENTER": self.MOCK_MAIN_GPU_CENTER,
            "log_comp": self.log_comp
        }
        with open(metadata_path, 'w', encoding='utf-8') as f_meta:
            json.dump(metadata, f_meta, ensure_ascii=False, indent=2)

        eliar_log(EliarLogType.INFO, f"Graph state (GML) and metadata saved to {file_path} & {metadata_path}", component=self.log_comp)

    async def save_graph_state(self, file_path: Optional[str] = None):
        """Saves the current graph state to a GML file and associated metadata to JSON."""
        path_to_save = file_path or self.graph_save_path
        if not path_to_save:
            eliar_log(EliarLogType.WARN, "No file path provided for saving graph state.", component=self.log_comp); return

        async with self._lock:
            try:
                await run_in_executor(self._save_graph_state_sync, path_to_save)
            except Exception as e:
                eliar_log(EliarLogType.ERROR, f"Failed to save graph state to {path_to_save}", component=self.log_comp, error=str(e))

    def _load_graph_state_sync(self, file_path: str):
        """
        Synchronous helper to load graph state from GML.
        Node attributes are loaded as part of the GML parsing.
        """
        self.graph = nx.read_gml(file_path, label='label') # Assuming node IDs are stored in 'label' field in GML
        
        # Load metadata
        metadata_path = file_path + ".meta.json"
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f_meta:
                metadata = json.load(f_meta)
            self.max_depth = metadata.get("max_depth", self.max_depth)
            self.MOCK_MAIN_GPU_CENTER = metadata.get("MOCK_MAIN_GPU_CENTER", self.MOCK_MAIN_GPU_CENTER)
            self.log_comp = metadata.get("log_comp", self.log_comp)

        eliar_log(EliarLogType.INFO, f"Graph state (GML) loaded from {file_path}. Nodes: {len(self.graph.nodes())}", component=self.log_comp)
        # Post-load processing: Ensure essential attributes like 'access_count' exist if not in GML
        for node_id in self.graph.nodes():
            if 'access_count' not in self.graph.nodes[node_id]:
                self.graph.nodes[node_id]['access_count'] = 0
            if 'created_utc' not in self.graph.nodes[node_id]:
                 self.graph.nodes[node_id]['created_utc'] = get_current_utc_iso() # Default to now if missing
            if 'last_accessed_utc' not in self.graph.nodes[node_id]:
                 self.graph.nodes[node_id]['last_accessed_utc'] = self.graph.nodes[node_id]['created_utc']


    async def load_graph_state(self, file_path: Optional[str] = None):
        """Loads the graph state from a GML file and associated metadata."""
        path_to_load = file_path or self.graph_save_path
        if not path_to_load or not os.path.exists(path_to_load):
            eliar_log(EliarLogType.WARN, f"GML file for loading graph state not found: {path_to_load}", component=self.log_comp)
            return False

        async with self._lock:
            try:
                await run_in_executor(self._load_graph_state_sync, path_to_load)
                return True
            except Exception as e:
                eliar_log(EliarLogType.ERROR, f"Failed to load graph state from {path_to_load}", component=self.log_comp, error=str(e))
                return False

# --- Example Usage (Async) ---
async def example_usage_final_optimized():
    eliar_log(EliarLogType.INFO, "Starting Final Optimized ReflectiveMemoryGraph example...", component="ExampleRunner")
    SAVE_FILE_PATH_GML = "reflective_memory_state_final.gml" # Changed extension for GML
    memory_system = EliarMemory() # Stub

    async def my_insight_generator(question: str, memory: EliarMemory) -> List[str]:
        # (Same as previous example_usage_optimized)
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
    graph_memory = ReflectiveMemoryGraph(
        initial_reflection_prompts=["초기 테스트 프롬프트: 성장이란 무엇인가?"], # 루미나의 성장
        graph_save_path=SAVE_FILE_PATH_GML
    )
    
    if not graph_memory.graph.nodes(): # If graph is empty after potential load
        await graph_memory.complete_initialization_async()
    else:
        eliar_log(EliarLogType.INFO, f"Graph loaded with {len(graph_memory.graph.nodes())} nodes.", component="ExampleRunner")

    # Add some activity
    await graph_memory.add_reflection_node("성찰 A: 사랑의 실천은 어떻게 가능한가?", {"type": "foundational_question", "tags": ["love", "practice"]})
    await graph_memory.add_reflection_node("성찰 B: 사랑은 오래 참고 온유하며...", {"type": "derived_insight", "source_node": "성찰 A"})
    await graph_memory.add_reflection_edge("성찰 A: 사랑의 실천은 어떻게 가능한가?", "성찰 B: 사랑은 오래 참고 온유하며...", "explores_aspect_of")

    expanded_info = await graph_memory.expand_reflection_recursively(
        "성찰 A: 사랑의 실천은 어떻게 가능한가?", source_record_id="exp003_love",
        internal_insight_generator=my_insight_generator, memory_module=memory_system
    )
    eliar_log(EliarLogType.INFO, f"Expansion of '성찰 A' yielded {len(expanded_info)} items.", component="ExampleRunner")

    relevant_paths_data = await graph_memory.find_relevant_reflection_paths("사랑의 실천 방법", num_paths=2)
    if relevant_paths_data: eliar_log(EliarLogType.INFO, f"Found paths for '사랑의 실천 방법': {relevant_paths_data}", component="ExampleRunner")

    # Save state (GML)
    await graph_memory.save_graph_state()

    # Create a new instance and attempt to load
    eliar_log(EliarLogType.INFO, "Creating new graph instance to test loading from GML...", component="ExampleRunner")
    new_graph_memory_instance = ReflectiveMemoryGraph(graph_save_path=SAVE_FILE_PATH_GML)
    # Load attempt is in __init__. If it failed or file didn't exist, graph might be empty.
    if not new_graph_memory_instance.graph.nodes() and os.path.exists(SAVE_FILE_PATH_GML):
        loaded_successfully = await new_graph_memory_instance.load_graph_state() # Explicit async load
        if not loaded_successfully : await new_graph_memory_instance.complete_initialization_async() # Fallback
    elif not new_graph_memory_instance.graph.nodes(): # No save file existed
         await new_graph_memory_instance.complete_initialization_async()


    eliar_log(EliarLogType.INFO, f"New graph instance has {len(new_graph_memory_instance.graph.nodes())} nodes after GML load attempt.", component="ExampleRunner")
    paths_from_loaded_graph = await new_graph_memory_instance.find_relevant_reflection_paths("사랑", num_paths=1)
    if paths_from_loaded_graph: eliar_log(EliarLogType.INFO, f"Paths from loaded GML graph for '사랑': {paths_from_loaded_graph}", component="ExampleRunner")

    try:
        # Visualize the loaded graph
        # Note: Ensure matplotlib is installed (`pip install matplotlib`)
        # For server environments, always use save_path for visualization.
        summary_for_viz = None
        if paths_from_loaded_graph:
            summary_for_viz = await new_graph_memory_instance.summarize_reflection_paths(paths_from_loaded_graph)
        
        await new_graph_memory_instance.visualize_reflection_graph(
            summary_data=summary_for_viz, # Pass summary if available, else None for full graph
            save_path="final_optimized_graph_visualization.png"
        )
    except ImportError: eliar_log(EliarLogType.WARN, "Matplotlib not installed. Skipping visualization.", component="ExampleRunner")
    except Exception as e_viz: eliar_log(EliarLogType.ERROR, f"Visualization error: {e_viz}", component="ExampleRunner")

    eliar_log(EliarLogType.INFO, "Final Optimized example finished.", component="ExampleRunner")

if __name__ == "__main__":
    async def run_final_optimized_example():
        await example_usage_final_optimized()
    try:
        asyncio.run(run_final_optimized_example())
    except KeyboardInterrupt:
        eliar_log(EliarLogType.SYSTEM, "Final Optimized example run interrupted.", component="ExampleRunner")
    except Exception as e_main_run:
         eliar_log(EliarLogType.CRITICAL, f"Unhandled exception in final optimized example: {e_main_run}", component="ExampleRunner", error=str(e_main_run))
