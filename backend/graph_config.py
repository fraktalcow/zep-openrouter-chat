# Configuration for Custom Entity and Edge Types
# Refer to: https://help.getzep.com/cookbook/advanced-context-block-construction

from textwrap import dedent

# Domain specific metadata leveraged by the Zep graph.
CUSTOM_ENTITIES = [
    {"name": "Project", "description": "A software project or initiative"},
    {"name": "Technology", "description": "A language, framework, tool, or API"},
    {"name": "Preference", "description": "A persistent user preference or trait"},
]

CUSTOM_EDGES = [
    {"name": "USES", "description": "Project makes use of a technology"},
    {"name": "DEVELOPED_BY", "description": "Project created or owned by a person"},
    {"name": "LIKES", "description": "User preference or affinity"},
]

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
