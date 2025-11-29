from typing import Any, Dict, List, Optional

from zep_cloud.client import AsyncZep
from zep_cloud.types.edge_type import EdgeType
from zep_cloud.types.entity_type import EntityType
from zep_cloud.types.message import Message

class ZepService:
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        # zep_cloud SDK doesn't use base_url for cloud instances
        self.client = AsyncZep(api_key=api_key)
        self._ontology_applied = False

    async def ensure_ontology(self, entities: List[Dict[str, str]], edges: List[Dict[str, str]]) -> None:
        """Apply a custom ontology once so the KG starts with useful types."""
        if self._ontology_applied or not entities:
            return

        valid_entities = [
            EntityType(name=item["name"], description=item["description"])
            for item in entities
            if item.get("name") and item.get("description")
        ]
        valid_edges = [
            EdgeType(name=item["name"], description=item["description"])
            for item in edges
            if item.get("name") and item.get("description")
        ]

        if not valid_entities and not valid_edges:
            self._ontology_applied = True
            return

        try:
            await self.client.graph.set_entity_types_internal(
                entity_types=valid_entities or None,
                edge_types=valid_edges or None,
            )
            self._ontology_applied = True
            print("Custom ontology applied to Zep graph")
        except Exception as exc:
            print(f"Error applying ontology: {exc}")
            self._ontology_applied = True

    async def create_session(
        self,
        user_id: str,
        session_id: str,
        *,
        first_name: str = "User",
        last_name: str = "Guest",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Create the backing Zep user + memory session."""
        await self._ensure_user(user_id, first_name, last_name, metadata)
        await self._ensure_session(user_id, session_id, metadata)

    async def _ensure_user(
        self,
        user_id: str,
        first_name: str,
        last_name: str,
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        try:
            await self.client.user.add(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                metadata=metadata or {},
            )
            print(f"User {user_id} created")
        except Exception:
            # User may already exist; swallow benign errors
            pass

    async def _ensure_session(
        self,
        user_id: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        try:
            await self.client.thread.create(
                thread_id=session_id,
                user_id=user_id,
            )
            print(f"Session {session_id} created for user {user_id}")
        except Exception as e:
            print(f"Error creating session: {e}")

    async def add_memory(self, session_id: str, role: str, content: str) -> None:
        message = Message(
            role=role,
            content=content,
        )
        try:
            await self.client.thread.add_messages(
                thread_id=session_id,
                messages=[message],
            )
            print(f"Memory added to session {session_id}")
        except Exception as e:
            print(f"Error adding memory: {e}")

    async def get_memory(self, session_id, lastn: int = 25):
        try:
            return await self.client.thread.get(thread_id=session_id, lastn=lastn)
        except Exception as e:
            print(f"Error getting memory: {e}")
            return None

    async def search_memory(self, session_id, query, limit=3):
        try:
            return await self.search_graph(
                query=query,
                user_id=None,
                limit=limit,
            )
        except Exception as e:
            print(f"Error searching memory: {e}")
            return []

    async def get_graph_data(self, user_id, limit=100):
        """
        Retrieve knowledge graph nodes and edges for visualization.
        """
        try:
            # Get nodes
            nodes_data = []
            try:
                nodes = await self.client.graph.node.get_by_user_id(user_id=user_id, limit=limit)
                for node in nodes:
                    node_id = getattr(node, "uuid_", getattr(node, "uuid", None))
                    nodes_data.append({
                        "uuid": node_id,
                        "name": node.name,
                        "summary": getattr(node, 'summary', ''),
                        "type": getattr(node, 'type', 'unknown')
                    })
            except Exception as e:
                print(f"Error fetching nodes: {e}")
            
            # Get edges
            edges_data = []
            try:
                edges = await self.client.graph.edge.get_by_user_id(user_id=user_id, limit=limit)
                for edge in edges:
                    edge_id = getattr(edge, "uuid_", getattr(edge, "uuid", None))
                    edges_data.append({
                        "uuid": edge_id,
                        "source": edge.source_node_uuid,
                        "target": edge.target_node_uuid,
                        "fact": getattr(edge, 'fact', ''),
                        "type": getattr(edge, 'type', 'unknown')
                    })
            except Exception as e:
                print(f"Error fetching edges: {e}")
            
            return {
                "nodes": nodes_data,
                "edges": edges_data,
                "user_id": user_id
            }
        except Exception as e:
            print(f"Error getting graph data: {e}")
            return {"nodes": [], "edges": [], "user_id": user_id}

    async def search_graph(
        self,
        query: str,
        *,
        user_id: Optional[str] = None,
        limit: int = 3,
        search_scope: Optional[str] = None,
    ):
        """
        Searches the graph for relevant nodes and edges.
        """
        if not query:
            return []
        params: Dict[str, Any] = {"query": query, "limit": limit}
        if user_id:
            params["user_id"] = user_id
        if search_scope:
            params["scope"] = search_scope
        try:
            results = await self.client.graph.search(**params)
            if search_scope == "edges":
                return results.edges or []
            if search_scope == "nodes":
                return results.nodes or []
            if search_scope == "episodes":
                return results.episodes or []
            combined: List[Any] = []
            if results.edges:
                combined.extend(results.edges)
            if results.nodes:
                combined.extend(results.nodes)
            if results.episodes:
                combined.extend(results.episodes)
            return combined
        except Exception as e:
            print(f"Error searching graph: {e}")
            return []

    async def check_status(self):
        try:
            # Simple health check
            await self.client.user.list_ordered(limit=1)
            return True
        except Exception as e:
            print(f"Status check failed: {e}")
            return False

    async def build_context_block(
        self,
        *,
        session_id: str,
        user_id: Optional[str],
        query: str,
        include_memory: bool = True,
        include_graph: bool = True,
        max_messages: int = 6,
        graph_limit: int = 5,
    ) -> Dict[str, Any]:
        """Return structured memory + graph context sections."""
        context: Dict[str, Any] = {
            "memory_section": "Memory disabled by user.",
            "graph_section": "Graph retrieval disabled by user.",
            "memory_messages": [],
            "graph_facts": [],
        }

        if include_memory:
            memory = await self.get_memory(session_id)
            if memory and getattr(memory, "messages", None):
                recent_messages = memory.messages[-max_messages:]
                formatted_history = "\n".join(
                    f"{msg.role}: {msg.content}".strip() for msg in recent_messages
                )
                context["memory_section"] = formatted_history or "No prior memory yet."
                context["memory_messages"] = [
                    {"role": msg.role, "content": msg.content} for msg in recent_messages
                ]
            else:
                context["memory_section"] = "No prior memory yet."

        if include_graph and user_id:
            facts: List[str] = []
            # Try edges first for fact triples
            edges = await self.search_graph(
                query,
                user_id=user_id,
                limit=graph_limit,
                search_scope="edges",
            )
            for edge in edges or []:
                fact = getattr(edge, "fact", None)
                if fact:
                    facts.append(fact.strip())
            # Supplement with nodes for summaries
            nodes = await self.search_graph(
                query,
                user_id=user_id,
                limit=max(2, graph_limit // 2),
                search_scope="nodes",
            )
            for node in nodes or []:
                summary = getattr(node, "summary", None) or getattr(node, "name", None)
                if summary:
                    facts.append(summary.strip())

            if facts:
                context["graph_section"] = "\n".join(
                    f"{idx + 1}. {fact}" for idx, fact in enumerate(facts)
                )
                context["graph_facts"] = facts
            else:
                context["graph_section"] = "No graph facts were retrieved for this query."

        return context
