from typing import Any, Dict, List, Optional
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
        """Create user + session (thread) in Zep."""
        # Create user if needed
        await self._ensure_user(user_id, first_name, last_name, {})
        
        # Create thread (Threads do not support metadata in create)
        try:
            await self.client.thread.create(
                thread_id=session_id, 
                user_id=user_id
            )
            logger.info(f"Session (Thread) {session_id} created for user {user_id}")
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise

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
            logger.info(f"User {user_id} created/ensured")
        except Exception:
            pass  # User may already exist

    async def add_memory(self, session_id: str, role: str, content: str, return_context: bool = False) -> Optional[str]:
        """Add a message to Zep memory and optionally return the context block."""
        try:
            response = await self.client.thread.add_messages(
                thread_id=session_id, 
                messages=[Message(role=role, content=content)],
                return_context=return_context
            )
            if return_context and response:
                context = getattr(response, "context", None)
                logger.info(f"[Zep] add_memory context returned: {bool(context)}, len={len(context) if context else 0}")
                return context
            return None
        except Exception as e:
            logger.error(f"Error adding memory: {e}")
            return None

    async def get_context(self, session_id: str) -> Optional[str]:
        """Get the Zep context block (user summary + facts) for a thread."""
        try:
            response = await self.client.thread.get_user_context(thread_id=session_id)
            context = getattr(response, "context", None)
            logger.info(f"[Zep] get_user_context returned: {bool(context)}, len={len(context) if context else 0}")
            return context
        except Exception as e:
            logger.error(f"Error getting context: {e}")
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

    # deprecated build_context_block in favor of add_messages(return_context=True)

    async def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List sessions (threads) from Zep."""
        try:
            response = await self.client.thread.list_all(page_size=limit, order_by="created_at", asc=False)
            threads = getattr(response, "threads", [])
            sessions = []
            for thread in threads:
                meta = getattr(thread, "metadata", {}) or {}
                # If no metadata name, try to fetch user or just use specifics
                # We stored first_name/last_name in metadata during create_session
                sessions.append({
                    "session_id": thread.thread_id,
                    "user_id": thread.user_id,
                    "first_name": meta.get("first_name", "User"),
                    "last_name": meta.get("last_name", ""),
                    "created_at": str(getattr(thread, "created_at", "")),
                })
            return sessions
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return []

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session details (metadata)."""
        try:
            thread = await self.client.thread.get(session_id)
            if not thread:
                return None
            meta = getattr(thread, "metadata", {}) or {}
            
            return {
                "session_id": thread.thread_id,
                "user_id": getattr(thread, "user_id", ""),
                "first_name": meta.get("first_name", "User"),
                "last_name": meta.get("last_name", ""),
                "created_at": str(getattr(thread, "created_at", "")),
            }
        except Exception:
            # logger.error(f"Error getting session {session_id}: {e}")
            pass
        return None

    async def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get session messages (history)."""
        try:
            response = await self.client.thread.get(session_id)
            messages = getattr(response, "messages", [])
            return [
                {
                    "role": str(getattr(m, "role", "user")), 
                    "content": str(getattr(m, "content", "")),
                    "created_at": str(getattr(m, "created_at", ""))
                } 
                for m in messages
            ]
        except Exception as e:
            logger.error(f"Error getting session history {session_id}: {e}")
            return []

    async def delete_session(self, session_id: str) -> bool:
        """Delete session (thread)."""
        try:
            await self.client.thread.delete(session_id)
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
