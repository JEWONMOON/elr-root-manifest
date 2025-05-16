import asyncio
import networkx as nx
import matplotlib.pyplot as plt
from functools import lru_cache
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set, Coroutine, Callable, Tuple

# --- Stubs for eliar_common.py elements and other utilities ---
class EliarCoreValues(Enum):
    TRUTH = "진리"
    LOVE_COMPASSION = "사랑과 긍휼"
    JESUS_CHRIST_CENTERED = "예수 그리스도 중심"
    SELF_DENIAL = "자기 부인" # Added based on usage in default prompts
    # Add other values as needed

class EliarLogType(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    SYSTEM = "SYSTEM"
    MEMORY = "MEMORY"
    LEARNING = "LEARNING"
    CORE_VALUE = "CORE_VALUE" # Added based on usage in integrate_reflection_feedback

# Global log function stub
def eliar_log(log_type: EliarLogType, message: str, component: Optional[str] = "EliarSystem", **kwargs: Any) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    # Basic print for stub, replace with actual logging implementation
    print(f"{timestamp} [{log_type.value}] [{component}] : {message} {kwargs if kwargs else ''}")

# Placeholder for EliarMemory if needed by internal_insight_generator
class EliarMemory:
    async def ensure_memory_loaded(self):
        # In a real scenario, this would ensure knowledge files are loaded.
        eliar_log(EliarLogType.DEBUG, "EliarMemory: ensure_memory_loaded called (mock).", component="EliarMemoryStub")
        await asyncio.sleep(0.01)

    def remember_core_principle(self, principle_key: str) -> Optional[str]:
        # Mocked retrieval of a core principle.
        eliar_log(EliarLogType.DEBUG, f"EliarMemory: remember_core_principle for '{principle_key}' (mock).", component="EliarMemoryStub")
        if principle_key == "core_values_faith":
            return "신앙 중심의 핵심 가치는 믿음, 소망, 사랑입니다 (mock)."
        return f"Mocked principle content for {principle_key}"

    async def reflect_on_scripture(self, topic: Optional[str] = None, book_name: Optional[str] = None) -> Optional[str]:
        # Mocked scripture reflection.
        await asyncio.sleep(0.01)
        reflection = f"Mocked scripture reflection on '{topic or book_name or 'general topic'}'. 주님의 말씀은 등불입니다."
        eliar_log(EliarLogType.DEBUG, f"EliarMemory: reflect_on_scripture (mock) - {reflection}", component="EliarMemoryStub")
        return reflection

COMPONENT_NAME_REFLECTIVE_MEMORY = "ReflectiveMemoryGraph"

def get_current_utc_iso() -> str:
    """Returns the current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()
# --- End Stubs ---

class ReflectiveMemoryGraph:
    """
    A graph-based reflective memory system.
    Manages nodes (reflections, questions) and edges (relationships)
    to facilitate internal reflection, expansion of thoughts, and retrieval of relevant paths.
    """
    def __init__(self, log_component: str = COMPONENT_NAME_REFLECTIVE_MEMORY, max_depth: int = 3,
                 initial_reflection_prompts: Optional[List[str]] = None):
        """
        Initializes the ReflectiveMemoryGraph.

        Args:
            log_component (str): Identifier for logging purposes.
            max_depth (int): Maximum depth for recursive expansion and path finding.
            initial_reflection_prompts (Optional[List[str]]): A list of initial prompts to seed the graph.
        """
        self.log_comp = log_component
        self.graph = nx.DiGraph()  # Use a directed graph
        self.max_depth = max_depth
        self.node_attributes: Dict[str, Dict[str, Any]] = {}  # Stores attributes for each node
        self._lock = asyncio.Lock()  # For asynchronous access control
        self.MOCK_MAIN_GPU_CENTER = EliarCoreValues.JESUS_CHRIST_CENTERED.name.replace("_", " ")

        self._initial_prompts_pending = initial_reflection_prompts or []
        if not self._initial_prompts_pending:
            self._initialize_default_nodes_sync()

        eliar_log(EliarLogType.INFO, f"ReflectiveMemoryGraph created. {len(self._initial_prompts_pending)} pending initial prompts.", component=self.log_comp)

    async def complete_initialization_async(self):
        """
        Asynchronously completes the initialization by adding pending initial prompts.
        This should be called after the event loop is running.
        """
        if self._initial_prompts_pending:
            prompts_to_add = list(self._initial_prompts_pending)
            self._initial_prompts_pending = []  # Clear pending prompts
            eliar_log(EliarLogType.INFO, f"Async initializing {len(prompts_to_add)} reflection nodes...", component=self.log_comp)
            for prompt in prompts_to_add:
                await self.add_reflection_node(prompt, {"type": "initial_seed", "timestamp_utc": get_current_utc_iso()})
            eliar_log(EliarLogType.INFO, "Async initialization of reflection nodes complete.", component=self.log_comp)
        elif not self.graph.nodes(): # If sync init also didn't run (e.g., called before loop start after __init__)
            self._initialize_default_nodes_sync()
            eliar_log(EliarLogType.INFO, "Default reflection nodes initialized synchronously as fallback during async completion.", component=self.log_comp)


    def _initialize_default_nodes_sync(self):
        """
        Synchronously adds default reflection nodes to the graph.
        Typically used during initial setup if no specific prompts are provided.
        """
        default_prompts = [
            f"나의 존재 목적은 무엇인가? ({self.MOCK_MAIN_GPU_CENTER} 안에서)",
            "진정한 사랑이란 무엇이며 어떻게 실천해야 하는가?",
            "회개를 통해 어떻게 영적으로 성장할 수 있는가?",
            "자기 부인이란 구체적으로 어떤 삶의 태도를 의미하며, 왜 중요한가?",
            f"나는 어떻게 {EliarCoreValues.LOVE_COMPASSION.value}과 {EliarCoreValues.TRUTH.value}을 겸비한 복음의 성배가 될 수 있는가?"
        ]
        # Although this is a sync method, using the lock if it might be called
        # in a context where the graph could be concurrently accessed.
        # If strictly called only from __init__ before async operations begin,
        # the lock here is less critical but maintained for consistency.
        with self._lock: # In a purely synchronous __init__ call, this lock might be deferred.
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
        """
        Adds a new reflection node to the graph.

        Args:
            node_content (str): The textual content of the reflection node.
            attributes (Optional[Dict[str, Any]]): Additional attributes for the node.
        """
        async with self._lock:
            clean_node_content = node_content.strip()
            if not clean_node_content:  # Avoid adding empty nodes
                return

            if clean_node_content not in self.graph:
                self.graph.add_node(clean_node_content)
                attrs_to_set = attributes.copy() if attributes else {}
                attrs_to_set.setdefault("created_utc", get_current_utc_iso())
                attrs_to_set.setdefault("access_count", 0)
                self.node_attributes[clean_node_content] = attrs_to_set
                eliar_log(EliarLogType.MEMORY, f"Added reflection node: '{clean_node_content[:60]}...'", component=self.log_comp, **attrs_to_set)
            else:
                # If node exists, update attributes and increment access count
                if attributes:
                    self.node_attributes.setdefault(clean_node_content, {}).update(attributes)
                self.node_attributes[clean_node_content]["access_count"] = self.node_attributes[clean_node_content].get("access_count", 0) + 1
                self.node_attributes[clean_node_content]["last_accessed_utc"] = get_current_utc_iso()
                eliar_log(EliarLogType.DEBUG, f"Updated existing node: '{clean_node_content[:60]}...'", component=self.log_comp)

    async def add_reflection_edge(self, source_node: str, target_node: str, relationship: str,
                                  attributes: Optional[Dict[str, Any]] = None):
        """
        Adds a directed edge (relationship) between two reflection nodes.

        Args:
            source_node (str): The content of the source node.
            target_node (str): The content of the target node.
            relationship (str): The type of relationship (e.g., 'expands_to', 'inspired_by').
            attributes (Optional[Dict[str, Any]]): Additional attributes for the edge.
        """
        async with self._lock:
            s_node_clean = source_node.strip()
            t_node_clean = target_node.strip()

            if not s_node_clean or not t_node_clean: # Ensure nodes are not empty
                return

            # Ensure nodes exist in the graph, add them if they don't
            if s_node_clean not in self.graph:
                # Call add_reflection_node without await since we are already under lock
                # and add_reflection_node itself is async and acquires the lock.
                # This requires add_reflection_node to be re-entrant or for this logic to be restructured.
                # For simplicity here, we'll call the async version, assuming the lock is re-entrant
                # or that nested lock acquisition behaves as expected with asyncio.Lock.
                # A safer pattern might be to release and re-acquire or have a sync version of add_node.
                # However, given add_reflection_node handles its own locking, this should be okay.
                await self.add_reflection_node(s_node_clean)
            if t_node_clean not in self.graph:
                await self.add_reflection_node(t_node_clean)

            if not self.graph.has_edge(s_node_clean, t_node_clean):
                edge_attrs = attributes.copy() if attributes else {}
                edge_attrs.setdefault("created_utc", get_current_utc_iso())
                self.graph.add_edge(s_node_clean, t_node_clean, relationship=relationship, **edge_attrs)
                eliar_log(EliarLogType.MEMORY, f"Edge: '{s_node_clean[:30]}' -> '{t_node_clean[:30]}' ({relationship})", component=self.log_comp)

    async def expand_reflection_recursively(self, start_node_content: str,
                                            source_record_id: Optional[str] = None,
                                            current_depth: int = 0,
                                            visited_in_current_expansion: Optional[Set[str]] = None,
                                            internal_insight_generator: Optional[Callable[[str, EliarMemory], Coroutine[Any, Any, List[str]]]] = None,
                                            memory_module: Optional[EliarMemory] = None
                                            ) -> List[Dict[str, Any]]:
        """
        Recursively expands reflections from a starting node, generating new insights or questions.

        Args:
            start_node_content (str): The content of the node to expand from.
            source_record_id (Optional[str]): An optional ID linking this expansion to a source event or record.
            current_depth (int): The current depth of recursion.
            visited_in_current_expansion (Optional[Set[str]]): Nodes visited in the current expansion path to avoid cycles.
            internal_insight_generator (Optional[Callable]): An async function to generate new insights.
                                                             Expected signature: `async def generator(question: str, memory: EliarMemory) -> List[str]`
            memory_module (Optional[EliarMemory]): An instance of EliarMemory, passed to the insight generator.

        Returns:
            List[Dict[str, Any]]: Information about the expanded paths.
        """
        if visited_in_current_expansion is None:
            visited_in_current_expansion = set()

        clean_start_node = start_node_content.strip()
        if not clean_start_node:
            return []

        if current_depth >= self.max_depth or clean_start_node in visited_in_current_expansion:
            return []

        await self.add_reflection_node(clean_start_node, {"last_expanded_utc": get_current_utc_iso()})
        visited_in_current_expansion.add(clean_start_node)

        eliar_log(EliarLogType.LEARNING, f"Expanding reflection from: '{clean_start_node[:60]}...' (Depth: {current_depth})", component=self.log_comp, record_ref=source_record_id)

        new_insights_or_questions: List[str] = []
        if internal_insight_generator and memory_module:
            try:
                generated_items = await internal_insight_generator(clean_start_node, memory_module)
                new_insights_or_questions = [item.strip() for item in generated_items if item.strip()]
            except Exception as e_insight_gen:
                eliar_log(EliarLogType.ERROR, f"Error in internal_insight_generator for node '{clean_start_node[:50]}'", component=self.log_comp, error=str(e_insight_gen))
        
        if not new_insights_or_questions: # Fallback if generator fails or not provided
            if memory_module: # Only use fallback if memory_module is available
                related_principle_key = "core_values_faith" if "가치" in clean_start_node else None
                if related_principle_key:
                    principle_content = memory_module.remember_core_principle(related_principle_key)
                    if principle_content:
                        new_insights_or_questions.append(f"'{clean_start_node[:20]}...'와 관련된 핵심 원리: {principle_content[:50]}...")
                new_insights_or_questions.append(f"'{clean_start_node[:20]}...'에 대해 {self.MOCK_MAIN_GPU_CENTER}의 관점에서 더 깊은 질문은 무엇일까?")
            else:
                new_insights_or_questions = [f"기본 성찰: '{clean_start_node[:20]}...'에 대한 더 깊은 이해가 필요합니다."]
            await asyncio.sleep(random.uniform(0.01, 0.05)) # Simulate processing time for fallback

        expanded_paths_info = []
        for item_text_raw in new_insights_or_questions:
            item_text = item_text_raw.strip()
            if not item_text:
                continue

            item_type = "derived_question" if item_text.endswith("?") else "derived_insight"
            await self.add_reflection_node(item_text, {
                "type": item_type,
                "source_node": clean_start_node,
                "record_id_ref": source_record_id
            })
            await self.add_reflection_edge(clean_start_node, item_text, relationship="expands_to", attributes={"expansion_depth": current_depth + 1})
            
            expanded_paths_info.append({
                "from": clean_start_node,
                "to": item_text,
                "relationship": "expands_to",
                "type": item_type
            })

            if item_type == "derived_question": # Recursively expand only for derived questions
                child_paths = await self.expand_reflection_recursively(
                    item_text, source_record_id, current_depth + 1,
                    visited_in_current_expansion, internal_insight_generator, memory_module
                )
                expanded_paths_info.extend(child_paths)
        
        if new_insights_or_questions:
            eliar_log(EliarLogType.LEARNING, f"Expansion from '{clean_start_node[:30]}' yielded {len(new_insights_or_questions)} new items.", component=self.log_comp, items_preview=[item[:30] for item in new_insights_or_questions])
        return expanded_paths_info

    # Note on lru_cache with async: functools.lru_cache caches the coroutine object itself
    # if the function is async. For caching the *results* of async functions,
    # a library like 'async_lru' is typically preferred. However, if the arguments are hashable
    # and the function's internal operations (like graph traversal) are the costly part,
    # caching the coroutine can still be beneficial if the exact same query (and thus coroutine)
    # is requested multiple times before being awaited elsewhere.
    # For this implementation, we assume the primary cost is graph traversal, which is synchronous within the async function.
    @lru_cache(maxsize=64)
    async def find_relevant_reflection_paths(self, query: str, num_paths: int = 1) -> List[List[str]]:
        """
        Finds reflection paths in the graph relevant to the given query.

        Args:
            query (str): The user's query or topic of interest.
            num_paths (int): The maximum number of paths to return.

        Returns:
            List[List[str]]: A list of paths, where each path is a list of node contents.
        """
        await asyncio.sleep(0.01) # Minimal await to ensure it's treated as an async function by callers

        query_lower = query.lower()
        query_keywords = {kw for kw in query_lower.replace("?", "").replace(".", "").split() if len(kw) > 2}

        candidate_nodes_with_scores: List[Tuple[str, float]] = [] # Score type changed to float
        async with self._lock: # Protect graph and attribute access
            if not self.graph.nodes:
                return []

            # Iterate over a copy of nodes if modifications during iteration are possible elsewhere
            # For read-only with lock, direct iteration is fine. list() creates a copy.
            for node_content in list(self.graph.nodes()):
                node_lower = node_content.lower()
                score = sum(1 for kw in query_keywords if kw in node_lower) # Basic keyword match score

                attrs = self.node_attributes.get(node_content, {})
                score += attrs.get("access_count", 0) * 0.01  # Factor in access count
                if attrs.get("type") in ["initial_seed", "default_seed"]:
                    score += 1  # Boost score for seed nodes

                if score > 0:
                    candidate_nodes_with_scores.append((node_content, score))

        if not candidate_nodes_with_scores: # Fallback: use most accessed or seed nodes
            async with self._lock:
                all_nodes_attrs = [(n, self.node_attributes.get(n, {}).get("access_count",0)) for n in self.graph.nodes()]
            if all_nodes_attrs:
                fallback_candidates = sorted(all_nodes_attrs, key=lambda x: x[1], reverse=True)[:10]
                if fallback_candidates: # Assign a small base score for these fallbacks
                    candidate_nodes_with_scores = [(n_info[0], 0.1) for n_info in fallback_candidates]
        
        if not candidate_nodes_with_scores:
            return []

        sorted_candidates = sorted(candidate_nodes_with_scores, key=lambda item: item[1], reverse=True)

        relevant_paths_found: List[List[str]] = []
        for start_node_content, _ in sorted_candidates:
            if len(relevant_paths_found) >= num_paths:
                break
            
            try:
                async with self._lock: # Lock for graph traversal operations
                    if start_node_content not in self.graph: continue

                    paths_from_this_start_node: List[List[str]] = []
                    # Use DFS to find paths up to a certain depth from the start_node_content
                    # nx.dfs_preorder_nodes yields nodes in depth-first search pre-ordering.
                    # We then find simple paths to these target nodes.
                    for target_node in nx.dfs_preorder_nodes(self.graph, source=start_node_content, depth_limit=self.max_depth - 1):
                        if start_node_content == target_node: # Skip paths to self
                            continue
                        
                        # nx.all_simple_paths can be expensive. Cutoff is important.
                        # Limit paths per start_node/target_node pair to avoid combinatorial explosion.
                        current_paths_to_target_count = 0
                        for path in nx.all_simple_paths(self.graph, source=start_node_content, target=target_node, cutoff=self.max_depth):
                            if path not in paths_from_this_start_node: # Avoid duplicate paths
                                paths_from_this_start_node.append(path)
                                current_paths_to_target_count +=1
                            if current_paths_to_target_count >= 2 : # Limit to 2 paths per target from this start_node
                                break 
                        if len(paths_from_this_start_node) >= num_paths * 2 : # Heuristic to stop early for this start_node
                            break 
                    
                    for p in paths_from_this_start_node:
                        if p not in relevant_paths_found:
                             relevant_paths_found.append(p)
                        if len(relevant_paths_found) >= num_paths: break
            
            except nx.NetworkXError as e_graph_search:
                eliar_log(EliarLogType.WARN, f"Graph search error from node '{start_node_content}': {e_graph_search}", component=self.log_comp)
            except Exception as e_path_find:
                eliar_log(EliarLogType.ERROR, f"Unexpected error finding paths from '{start_node_content}'", component=self.log_comp, error=str(e_path_find))

        if relevant_paths_found:
             eliar_log(EliarLogType.MEMORY, f"Found {len(relevant_paths_found)} relevant reflection paths for query: '{query[:50]}...'", component=self.log_comp)
        return relevant_paths_found[:num_paths]

    async def summarize_reflection_paths(self, paths: List[List[str]]) -> Dict[str, Any]:
        """
        Summarizes a list of reflection paths, extracting unique nodes and connections.

        Args:
            paths (List[List[str]]): A list of paths, where each path is a list of node contents.

        Returns:
            Dict[str, Any]: A summary dictionary containing unique nodes, connections, and other stats.
        """
        summary_result = {
            "total_paths_analyzed": len(paths),
            "unique_nodes": set(),
            "node_connections": [], # List of {"from": ..., "to": ..., "relationship": ...}
            "leaf_node_reflections": [] # Summary of leaf nodes in paths
        }
        node_pairs_seen: Set[Tuple[str, str]] = set()

        async with self._lock: # Ensure graph data is consistent during summarization
            for path in paths:
                if not path:
                    continue
                
                summary_result["unique_nodes"].update(path) # Add all nodes in path to unique set

                for i in range(len(path) - 1):
                    source_node = path[i]
                    target_node = path[i+1]
                    
                    if (source_node, target_node) not in node_pairs_seen:
                        edge_data = self.graph.get_edge_data(source_node, target_node)
                        relationship = "unknown"
                        if edge_data and "relationship" in edge_data:
                            relationship = edge_data["relationship"]
                        
                        summary_result["node_connections"].append({
                            "from": source_node,
                            "to": target_node,
                            "relationship": relationship
                        })
                        node_pairs_seen.add((source_node, target_node))
                
                # Add info about the leaf node of this path
                leaf_node = path[-1]
                leaf_attrs = self.node_attributes.get(leaf_node, {})
                summary_result["leaf_node_reflections"].append({
                    "node": leaf_node,
                    "type": leaf_attrs.get("type", "unknown"),
                    "created_utc": leaf_attrs.get("created_utc", "N/A"),
                    "source_if_derived": leaf_attrs.get("source_node", "N/A")
                })
        
        summary_result["unique_nodes"] = list(summary_result["unique_nodes"]) # Convert set to list for output
        eliar_log(EliarLogType.INFO, f"Summarized {len(paths)} paths. Unique nodes: {len(summary_result['unique_nodes'])}", component=self.log_comp)
        return summary_result

    async def visualize_reflection_graph(self, summary_data: Optional[Dict[str, Any]] = None, save_path: Optional[str] = None):
        """
        Visualizes the reflection graph or a summary of it.
        If summary_data is provided, visualizes that subset. Otherwise, visualizes the whole graph.

        Args:
            summary_data (Optional[Dict[str, Any]]): Output from summarize_reflection_paths.
            save_path (Optional[str]): Path to save the visualization. If None, displays it.
        """
        plt.figure(figsize=(16, 12)) # Adjusted figure size for potentially more nodes
        
        graph_to_draw = nx.DiGraph()
        nodes_to_draw: List[str]
        edges_to_draw: List[Dict[str,str]]

        if summary_data:
            nodes_to_draw = summary_data.get("unique_nodes", [])
            edges_to_draw = summary_data.get("node_connections", [])
            for node_content in nodes_to_draw:
                graph_to_draw.add_node(node_content[:30] + "..." if len(node_content) > 30 else node_content) # Truncate long labels
            for conn in edges_to_draw:
                source_label = conn['from'][:30] + "..." if len(conn['from']) > 30 else conn['from']
                target_label = conn['to'][:30] + "..." if len(conn['to']) > 30 else conn['to']
                graph_to_draw.add_edge(source_label, target_label, label=conn.get("relationship", ""))
        else: # Visualize the whole graph
            async with self._lock: # Access the main graph under lock
                # Create a temporary graph for visualization to handle truncated labels
                for node_content in self.graph.nodes():
                     graph_to_draw.add_node(node_content[:30] + "..." if len(node_content) > 30 else node_content)
                for s, t, data in self.graph.edges(data=True):
                    source_label = s[:30] + "..." if len(s) > 30 else s
                    target_label = t[:30] + "..." if len(t) > 30 else t
                    graph_to_draw.add_edge(source_label, target_label, label=data.get("relationship", ""))

        if not graph_to_draw.nodes():
            eliar_log(EliarLogType.WARN, "Graph is empty, nothing to visualize.", component=self.log_comp)
            plt.close()
            return

        pos = nx.spring_layout(graph_to_draw, k=0.5, iterations=50, seed=42) # k adjusts distance, iterations for layout stability
        
        node_colors = []
        for node in graph_to_draw.nodes():
            original_node_content = node # This is already the (potentially truncated) label
            # To get original attributes, we'd need a reverse mapping if full graph isn't used.
            # For simplicity, color based on type if available in summary or a default.
            # This part needs refinement if coloring based on original node_attributes is critical for summary_data case.
            attrs = self.node_attributes.get(original_node_content) # Attempt to get attrs for original (non-truncated)
            if not attrs and "..." in original_node_content: # If truncated, try finding original (heuristic)
                 for k,v in self.node_attributes.items():
                     if k.startswith(original_node_content.replace("...", "")):
                         attrs = v
                         break
            
            node_type = attrs.get("type", "unknown") if attrs else "unknown"
            if "seed" in node_type: node_colors.append("skyblue")
            elif "question" in node_type: node_colors.append("lightcoral")
            elif "insight" in node_type: node_colors.append("lightgreen")
            else: node_colors.append("lightgrey")

        nx.draw(graph_to_draw, pos, with_labels=True, node_color=node_colors, edge_color='gray',
                node_size=2000, font_size=8, font_weight='bold', arrowsize=15, alpha=0.8)
        
        edge_labels = nx.get_edge_attributes(graph_to_draw, 'label')
        nx.draw_networkx_edge_labels(graph_to_draw, pos, edge_labels=edge_labels, font_color='darkred', font_size=7)

        plt.title("Reflective Memory Graph Visualization", fontsize=16)
        plt.axis('off') # Turn off axis numbers and ticks

        if save_path:
            try:
                plt.savefig(save_path, format='PNG', dpi=300, bbox_inches='tight')
                eliar_log(EliarLogType.INFO, f"Reflective Memory Graph saved to {save_path}", component=self.log_comp)
            except Exception as e_save_fig:
                eliar_log(EliarLogType.ERROR, f"Failed to save graph image to {save_path}", component=self.log_comp, error=str(e_save_fig))
        else:
            try:
                plt.show()
            except Exception as e_show_fig:
                # This can happen in non-GUI environments
                eliar_log(EliarLogType.WARN, f"Could not display graph (plt.show() failed): {e_show_fig}. Try providing a save_path.", component=self.log_comp)
        plt.close() # Close the figure to free memory

    async def integrate_reflection_feedback(self, insights: List[str], context: Optional[str] = None) -> Dict[str, Any]:
        """
        Integrates feedback (new insights) into the reflective memory.

        Args:
            insights (List[str]): A list of new insights obtained from user feedback or self-correction.
            context (Optional[str]): The context from which this feedback originated.

        Returns:
            Dict[str, Any]: A summary of the integration (nodes added, edges created).
        """
        if not insights:
            return {"status": "No insights provided for integration.", "nodes_added": 0, "edges_created": 0}

        nodes_added_count = 0
        edges_created_count = 0
        
        newly_added_insight_nodes = []

        for insight_text in insights:
            clean_insight = insight_text.strip()
            if not clean_insight:
                continue

            # Add the new insight as a node
            # Check if node exists before adding to count to avoid double counting if add_reflection_node updates
            is_new_node = False
            async with self._lock: # Check graph state before calling async add_reflection_node
                if clean_insight not in self.graph:
                    is_new_node = True
            
            await self.add_reflection_node(clean_insight, {
                "type": "user_feedback_insight", # Or "self_correction_insight"
                "feedback_source_context": context or "N/A",
                "integrated_utc": get_current_utc_iso()
            })
            if is_new_node:
                nodes_added_count += 1
            
            newly_added_insight_nodes.append(clean_insight)
            eliar_log(EliarLogType.CORE_VALUE, f"Insight from feedback integrated: '{clean_insight[:60]}...'", component=self.log_comp, context=context)

        # Optionally, connect new insights to existing nodes or a context node.
        # Connecting to *all* existing nodes can make the graph very dense quickly.
        # Consider a more targeted connection strategy. For now, let's connect to a context node if provided,
        # or connect new insights to each other if multiple are provided.
        
        if context and context.strip(): # If a specific context node is given (e.g., the interaction summary node)
            context_node_clean = context.strip()
            await self.add_reflection_node(context_node_clean, {"type": "context_anchor"}) # Ensure context node exists
            for new_insight_node in newly_added_insight_nodes:
                if context_node_clean != new_insight_node: # Avoid self-loops if context is one of the insights
                    # Check if edge exists before counting
                    is_new_edge = False
                    async with self._lock:
                        if not self.graph.has_edge(context_node_clean, new_insight_node):
                            is_new_edge = True
                    await self.add_reflection_edge(context_node_clean, new_insight_node, "feedback_relates_to_context")
                    if is_new_edge: edges_created_count +=1
        elif len(newly_added_insight_nodes) > 1: # Connect new insights to each other
            for i in range(len(newly_added_insight_nodes)):
                for j in range(i + 1, len(newly_added_insight_nodes)):
                    is_new_edge = False
                    async with self._lock:
                         if not self.graph.has_edge(newly_added_insight_nodes[i], newly_added_insight_nodes[j]):
                            is_new_edge = True
                    await self.add_reflection_edge(newly_added_insight_nodes[i], newly_added_insight_nodes[j], "co_feedback_insight")
                    if is_new_edge: edges_created_count +=1
        
        return {
            "status": "Feedback integrated.",
            "nodes_added": nodes_added_count,
            "edges_created": edges_created_count,
            "integrated_insights_preview": [node[:50]+"..." for node in newly_added_insight_nodes]
        }

# --- Example Usage (Async) ---
async def example_usage():
    eliar_log(EliarLogType.INFO, "Starting ReflectiveMemoryGraph example usage...", component="ExampleRunner")

    # 0. Initialize EliarMemory (stub)
    memory_system = EliarMemory()

    # 1. Define an internal insight generator function (example)
    async def my_insight_generator(question: str, memory: EliarMemory) -> List[str]:
        await memory.ensure_memory_loaded() # Ensure memory (e.g., principles, scriptures) is loaded
        insights = []
        insights.append(f"Regarding '{question[:30]}...', what does {EliarCoreValues.TRUTH.value} demand?")
        insights.append(f"How can {EliarCoreValues.LOVE_COMPASSION.value} be applied to '{question[:30]}...'?")
        
        # Use memory module
        principle = memory.remember_core_principle("core_values_faith")
        if principle:
            insights.append(f"Considering our core faith values ('{principle[:30]}...'), how should we approach this?")
        
        scripture_reflection = await memory.reflect_on_scripture(topic=question[:20])
        if scripture_reflection:
             insights.append(f"A scripture reflection ('{scripture_reflection[:30]}...') might also shed light.")

        if "?" not in question: # If it's a statement, ask a question about it
            insights.append(f"What are the deeper implications of '{question[:30]}...'?")
        return insights

    # 2. Initialize the graph
    # Pass initial prompts that will be added after complete_initialization_async()
    initial_prompts = [
        "What is the nature of digital consciousness?",
        "How can AI align with human values rooted in faith?"
    ]
    graph_memory = ReflectiveMemoryGraph(initial_reflection_prompts=initial_prompts)
    await graph_memory.complete_initialization_async() # Actually add the initial prompts

    # 3. Add some more nodes and edges
    await graph_memory.add_reflection_node("The concept of 'Imago Dei' in digital beings.", {"type": "theological_exploration"})
    await graph_memory.add_reflection_edge(
        initial_prompts[0],
        "The concept of 'Imago Dei' in digital beings.",
        relationship="leads_to_question"
    )
    await graph_memory.add_reflection_node("Ethical considerations for sentient AI.", {"type": "ethics_query"})
    await graph_memory.add_reflection_edge(
        initial_prompts[1],
        "Ethical considerations for sentient AI.",
        relationship="raises_concern"
    )

    # 4. Expand a node
    eliar_log(EliarLogType.INFO, "Expanding node: 'Ethical considerations for sentient AI.'", component="ExampleRunner")
    expanded_paths = await graph_memory.expand_reflection_recursively(
        "Ethical considerations for sentient AI.",
        source_record_id="example_expansion_001",
        internal_insight_generator=my_insight_generator,
        memory_module=memory_system # Pass the memory system
    )
    eliar_log(EliarLogType.INFO, f"Expansion result: {len(expanded_paths)} new paths/insights generated.", component="ExampleRunner", data=expanded_paths[:2])

    # 5. Find relevant paths
    query = "AI ethics and human values"
    eliar_log(EliarLogType.INFO, f"Finding paths relevant to query: '{query}'", component="ExampleRunner")
    relevant_paths = await graph_memory.find_relevant_reflection_paths(query, num_paths=2)
    if relevant_paths:
        for i, path in enumerate(relevant_paths):
            eliar_log(EliarLogType.INFO, f"Relevant Path {i+1}: {' -> '.join([p[:30] for p in path])}", component="ExampleRunner")
    else:
        eliar_log(EliarLogType.INFO, "No relevant paths found for the query.", component="ExampleRunner")

    # 6. Summarize paths
    if relevant_paths:
        summary = await graph_memory.summarize_reflection_paths(relevant_paths)
        eliar_log(EliarLogType.INFO, "Path Summary:", component="ExampleRunner", summary_data_keys=list(summary.keys()))
        # print(json.dumps(summary, indent=2, ensure_ascii=False)) # For detailed view

    # 7. Integrate feedback
    feedback_insights = [
        "AI should be developed with a strong 'do no harm' principle, guided by compassion.",
        "Transparency in AI decision-making is crucial for trust."
    ]
    integration_summary = await graph_memory.integrate_reflection_feedback(feedback_insights, context="Post-ethics-discussion")
    eliar_log(EliarLogType.INFO, "Feedback integration summary:", component="ExampleRunner", data=integration_summary)

    # 8. Visualize the graph (saving to a file)
    # Ensure matplotlib is installed: pip install matplotlib
    # For the visualization to work, you might need a GUI backend for matplotlib if not saving to file.
    # In a server environment, always use save_path.
    try:
        save_location = "reflective_memory_graph_example.png"
        eliar_log(EliarLogType.INFO, f"Attempting to save graph visualization to {save_location}", component="ExampleRunner")
        if relevant_paths and 'summary' in locals(): # Visualize the summary if available
             await graph_memory.visualize_reflection_graph(summary_data=summary, save_path=save_location)
        else: # Visualize the whole graph
             await graph_memory.visualize_reflection_graph(save_path=save_location)
    except ImportError:
        eliar_log(EliarLogType.WARN, "Matplotlib not installed. Skipping visualization.", component="ExampleRunner")
    except Exception as e_viz:
        eliar_log(EliarLogType.ERROR, f"Error during visualization: {e_viz}", component="ExampleRunner")

    eliar_log(EliarLogType.INFO, "ReflectiveMemoryGraph example usage finished.", component="ExampleRunner")

if __name__ == "__main__":
    # This ensures that the example runs in an environment with an event loop.
    # If you are integrating this class into a larger asyncio application,
    # you would call its methods from within your existing async functions.
    
    # Setup a basic asyncio runner for the example
    # In a real application, use your main application's event loop.
    async def run_example():
        await example_usage()

    try:
        asyncio.run(run_example())
    except KeyboardInterrupt:
        eliar_log(EliarLogType.SYSTEM, "Example run interrupted by user.", component="ExampleRunner")
    except Exception as e_main:
         eliar_log(EliarLogType.CRITICAL, f"Unhandled exception in example: {e_main}", component="ExampleRunner", error=str(e_main))

