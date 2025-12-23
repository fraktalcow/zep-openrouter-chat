from typing import Any, Dict, List, Optional
import asyncio
from zep_cloud.client import AsyncZep
from zep_cloud.types.message import Message

from config import get_settings
from logger import logger


class ZepService:
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.ZEP_API_KEY
        self.client = AsyncZep(api_key=self.api_key)

    async def create_session(
        self,
        user_id: str,
        session_id: str,
        *,
        first_name: str = "User",
        last_name: str = "",
    ) -> None:
        """Create user + session in Zep."""
        await self._ensure_user(user_id, first_name, last_name, {"session_id": session_id})
        await self._ensure_session(user_id, session_id)

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
            logger.info(f"User {user_id} created")
        except Exception:
            pass  # User may already exist

    async def _ensure_session(self, user_id: str, session_id: str) -> None:
        try:
            await self.client.thread.create(thread_id=session_id, user_id=user_id)
            logger.info(f"Session {session_id} created")
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise

    async def add_memory(self, session_id: str, role: str, content: str) -> None:
        try:
            await self.client.thread.add_messages(
                thread_id=session_id, messages=[Message(role=role, content=content)]
            )
        except Exception as e:
            logger.error(f"Error adding memory: {e}")

    async def get_memory(self, session_id: str, lastn: int = 25):
        try:
            return await self.client.thread.get(thread_id=session_id, lastn=lastn)
        except Exception as e:
            logger.error(f"Error getting memory: {e}")
            return None

    async def search_graph(
        self,
        query: str,
        *,
        user_id: Optional[str] = None,
        limit: int = 3,
        search_scope: Optional[str] = None,
    ):
        """Search graph for relevant nodes/edges."""
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
            combined: List[Any] = []
            if results.edges:
                combined.extend(results.edges)
            if results.nodes:
                combined.extend(results.nodes)
            return combined
        except Exception as e:
            logger.error(f"Error searching graph: {e}")
            return []

    async def get_graph_data(self, user_id: str, limit: int = 100):
        """Get graph nodes and edges for visualization."""
        nodes_data, edges_data = [], []
        try:
            nodes = await self.client.graph.node.get_by_user_id(user_id=user_id, limit=limit)
            for n in nodes:
                nodes_data.append({
                    "uuid": getattr(n, "uuid_", getattr(n, "uuid", None)),
                    "name": n.name,
                    "summary": getattr(n, "summary", ""),
                    "type": getattr(n, "type", "unknown"),
                })
        except Exception as e:
            logger.error(f"Error fetching nodes: {e}")
        try:
            edges = await self.client.graph.edge.get_by_user_id(user_id=user_id, limit=limit)
            for e in edges:
                edges_data.append({
                    "uuid": getattr(e, "uuid_", getattr(e, "uuid", None)),
                    "source": e.source_node_uuid,
                    "target": e.target_node_uuid,
                    "fact": getattr(e, "fact", ""),
                    "type": getattr(e, "type", "unknown"),
                })
        except Exception as ex:
            logger.error(f"Error fetching edges: {ex}")
        return {"nodes": nodes_data, "edges": edges_data, "user_id": user_id}

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
        """Build memory + graph context sections."""
        context: Dict[str, Any] = {"memory_section": "", "graph_section": ""}

        # Parallel retrieval
        tasks = []
        if include_memory:
            tasks.append(self.get_memory(session_id))
        if include_graph and user_id:
            tasks.append(self.search_graph(query, user_id=user_id, limit=graph_limit, search_scope="edges"))
            tasks.append(self.search_graph(query, user_id=user_id, limit=max(2, graph_limit // 2), search_scope="nodes"))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            results = []

        idx = 0
        memory, edges, nodes = None, [], []

        if include_memory:
            memory = results[idx] if not isinstance(results[idx], Exception) else None
            idx += 1
        if include_graph and user_id:
            edges = results[idx] if idx < len(results) and not isinstance(results[idx], Exception) else []
            idx += 1
            nodes = results[idx] if idx < len(results) and not isinstance(results[idx], Exception) else []

        # Process memory
        if memory and getattr(memory, "messages", None):
            recent = memory.messages[-max_messages:]
            context["memory_section"] = "\n".join(f"{m.role}: {m.content}" for m in recent)

        # Process graph
        if include_graph and user_id:
            facts = []
            for edge in edges or []:
                fact = getattr(edge, "fact", None)
                if fact:
                    facts.append(fact.strip())
            for node in nodes or []:
                summary = getattr(node, "summary", None) or getattr(node, "name", None)
                if summary:
                    facts.append(summary.strip())
            if facts:
                context["graph_section"] = "\n".join(f"{i+1}. {f}" for i, f in enumerate(facts))

        return context

    async def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List sessions from Zep."""
        try:
            response = await self.client.user.list_ordered(page_size=limit, order_by="created_at", asc=False)
            users = getattr(response, "users", [])
            sessions = []
            for user in users:
                meta = getattr(user, "metadata", {}) or {}
                session_id = meta.get("session_id")
                if session_id:
                    sessions.append({
                        "session_id": session_id,
                        "user_id": getattr(user, "user_id", ""),
                        "first_name": getattr(user, "first_name", "User"),
                        "last_name": getattr(user, "last_name", ""),
                        "created_at": getattr(user, "created_at", ""),
                    })
            return sessions
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return []

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session details."""
        try:
            thread = await self.client.thread.get(session_id)
            user_id = getattr(thread, "user_id", None)
            if user_id:
                user = await self.client.user.get(user_id)
                return {
                    "session_id": session_id,
                    "user_id": user_id,
                    "first_name": getattr(user, "first_name", "User"),
                    "last_name": getattr(user, "last_name", ""),
                    "created_at": getattr(user, "created_at", ""),
                }
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
        return None

    async def delete_session(self, session_id: str) -> bool:
        """Delete session and user."""
        try:
            thread = await self.client.thread.get(session_id)
            user_id = getattr(thread, "user_id", None)
            await self.client.thread.delete(session_id)
            if user_id:
                await self.client.user.delete(user_id)
            return True
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False


_zep_service: Optional[ZepService] = None


def get_zep_service() -> ZepService:
    global _zep_service
    if _zep_service is None:
        _zep_service = ZepService()
    return _zep_service
