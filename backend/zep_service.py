from typing import Any, Dict, List, Optional
import asyncio
from zep_cloud.client import AsyncZep
from zep_cloud.types.edge_type import EdgeType
from zep_cloud.types.entity_type import EntityType
from zep_cloud.types.message import Message

from config import get_settings

class ZepService:
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.ZEP_API_KEY
        # Lazy initialization of client can happen here or on first use.
        # AsyncZep client init is usually just local config, so it's safe here 
        # as long as we don't make network calls.
        self.client = AsyncZep(api_key=self.api_key)
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
            raise e  # Re-raise so the caller knows it failed

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
            await self.client.user.list_ordered(page_size=1)
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

        if include_memory and include_graph and user_id:
            # Parallelize all 3 calls
            memory_task = self.get_memory(session_id)
            edges_task = self.search_graph(query, user_id=user_id, limit=graph_limit, search_scope="edges")
            nodes_task = self.search_graph(query, user_id=user_id, limit=max(2, graph_limit // 2), search_scope="nodes")
            
            memory, edges, nodes = await asyncio.gather(memory_task, edges_task, nodes_task)
        else:
            # Sequential fallback if not all enabled (or just simpler logic)
            memory = await self.get_memory(session_id) if include_memory else None
            edges = await self.search_graph(query, user_id=user_id, limit=graph_limit, search_scope="edges") if (include_graph and user_id) else []
            nodes = await self.search_graph(query, user_id=user_id, limit=max(2, graph_limit // 2), search_scope="nodes") if (include_graph and user_id) else []

        # Process Memory
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

        # Process Graph
        if include_graph and user_id:
            facts: List[str] = []
            for edge in edges or []:
                fact = getattr(edge, "fact", None)
                if fact:
                    facts.append(fact.strip())
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
    
    async def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List sessions (users) from Zep."""
        try:
            # We treat Users as Sessions in this app architecture
            response = await self.client.user.list_ordered(page_size=limit, order_by="created_at", asc=False)
            users = getattr(response, "users", [])
            
            sessions = []
            for user in users:
                # Need to find the associated session/thread ID. 
                # For this app, we usually map 1 user -> 1 session.
                # We'll rely on metadata if present, or just list the user info.
                user_id = getattr(user, "user_id", "")
                
                # Try to get session ID from metadata first
                # (We don't strictly have the session_id here unless we query threads for each user, 
                # which is expensive. But we saved it in metadata in create_session?)
                # Wait, create_session saved metadata to USER.
                
                meta = getattr(user, "metadata", {}) or {}
                
                # If we don't have session_id in metadata (legacy), we might skip or imply it.
                # However, for the UI to work, we need a session_id.
                # Let's assume we can use user_id if session_id is missing, or we fetch threads.
                
                sessions.append({
                    "session_id": meta.get("session_id", "unknown"), # We will update create_session to store this
                    "user_id": user_id,
                    "first_name": getattr(user, "first_name", "User"),
                    "last_name": getattr(user, "last_name", ""),
                    "created_at": getattr(user, "created_at", ""),
                    "metadata": meta
                })
            
            # Filter out sessions with unknown IDs if critical
            return [s for s in sessions if s["session_id"] != "unknown"]
            
        except Exception as e:
            print(f"Error listing sessions: {e}")
            return []


    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session details. 
        """
        try:
            print(f"Debug: Fetching thread {session_id}")
            thread = await self.client.thread.get(session_id)
            print(f"Debug: Thread found: {thread}")
            
            user_id = getattr(thread, "user_id", None)
            print(f"Debug: Thread user_id: {user_id}")
            
            if user_id:
                user = await self.client.user.get(user_id)
                meta = getattr(user, "metadata", {}) or {}
                return {
                    "session_id": session_id,
                    "user_id": user_id,
                    "first_name": getattr(user, "first_name", "User"),
                    "last_name": getattr(user, "last_name", ""),
                    "traits": meta.get("traits", ""),
                    "preferences": meta.get("preferences", ""),
                    "business_data": meta.get("business_data", ""),
                    "created_at": getattr(user, "created_at", ""),
                }
            else:
                 print("Debug: No user_id in thread")
        except Exception as e:
            print(f"Error getting session {session_id}: {e}")
            import traceback
            traceback.print_exc()
        return None
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session (thread) and associated user."""
        try:
            # Get user ID first
            thread = await self.client.thread.get(session_id)
            user_id = getattr(thread, "user_id", None)
            
            # Delete thread
            await self.client.thread.delete(session_id)
            
            # Delete user if found
            if user_id:
                await self.client.user.delete(user_id)
                
            return True
        except Exception as e:
            print(f"Error deleting session: {e}")
            return False

# Singleton instance
_zep_service: Optional[ZepService] = None

def get_zep_service() -> ZepService:
    """Get or create Zep service instance."""
    global _zep_service
    if _zep_service is None:
        _zep_service = ZepService()
    return _zep_service
