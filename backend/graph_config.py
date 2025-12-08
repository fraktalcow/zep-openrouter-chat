# Context template for Zep graph
from textwrap import dedent

DEFAULT_CONTEXT_TEMPLATE = dedent(
    """
    You are an expert agent who reasons over temporal knowledge graphs.
    Stay concise, personal, and cite the user's preferences when helpful.

    # Session
    - Session ID: {session_id}
    - User: {user_name}

    # User Signals
    • Preferences: {preferences}
    • Traits: {traits}
    • Business Data: {business_data}

    # Conversation Memory
    {memory_section}

    # Knowledge Graph Retrieval
    {graph_section}

    # Latest Query
    {query}

    Compose a thoughtful assistant reply grounded in the context above.
    """
).strip()
