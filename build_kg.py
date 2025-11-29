"""
LangGraph Agent with Zep Knowledge Graph and Gemini API
========================================================
This module implements a conversational agent that:
- Uses Google Gemini API for language generation
- Builds and maintains a knowledge graph in Zep during conversations
- Retrieves relevant facts and entities from the graph
- Persists chat sessions with full context
- Uses LangGraph for agent orchestration (NO LangSmith)
"""

import asyncio
import logging
import os
import sys
import uuid
from contextlib import suppress
from typing import Annotated, Literal

from dotenv import load_dotenv
from typing_extensions import TypedDict

# LangChain and LangGraph imports
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, trim_messages
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.prebuilt import ToolNode

# Zep imports
from zep_cloud import Message
from zep_cloud.client import AsyncZep

# Load environment variables
load_dotenv(dotenv_path="backend/.env")


def setup_logging():
    """Configure logging for the application"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


logger = setup_logging()


# ============================================================================
# Configuration
# ============================================================================

# Disable LangSmith tracing as requested
os.environ["LANGCHAIN_TRACING_V2"] = "false"

# Get API keys
ZEP_API_KEY = os.getenv("ZEP_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not ZEP_API_KEY:
    raise ValueError("ZEP_API_KEY not found in environment variables")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Initialize Zep client
zep = AsyncZep(api_key=ZEP_API_KEY)


# ============================================================================
# Agent State Definition
# ============================================================================

class State(TypedDict):
    """Agent state containing messages and user context"""
    messages: Annotated[list, add_messages]
    first_name: str
    last_name: str
    session_id: str
    user_id: str


# ============================================================================
# Tools for Knowledge Graph Search
# ============================================================================

@tool
async def search_facts(query: str, user_id: str, limit: int = 5) -> list[str]:
    """
    Search for facts (edges) in the user's knowledge graph.
    
    Args:
        query: The search query to find relevant facts
        user_id: The user ID to search facts for
        limit: Maximum number of facts to return (default: 5)
    
    Returns:
        List of relevant facts as strings
    """
    try:
        edges = await zep.graph.search(
            user_id=user_id,
            text=query,
            limit=limit,
            search_scope="edges"
        )
        facts = [edge.fact for edge in edges if hasattr(edge, 'fact')]
        logger.info(f"Found {len(facts)} facts for query: {query}")
        return facts
    except Exception as e:
        logger.error(f"Error searching facts: {e}")
        return []


@tool
async def search_entities(query: str, user_id: str, limit: int = 5) -> list[str]:
    """
    Search for entities (nodes) in the user's knowledge graph.
    
    Args:
        query: The search query to find relevant entities
        user_id: The user ID to search entities for
        limit: Maximum number of entities to return (default: 5)
    
    Returns:
        List of entity summaries as strings
    """
    try:
        nodes = await zep.graph.search(
            user_id=user_id,
            text=query,
            limit=limit,
            search_scope="nodes"
        )
        entities = [node.summary for node in nodes if hasattr(node, 'summary')]
        logger.info(f"Found {len(entities)} entities for query: {query}")
        return entities
    except Exception as e:
        logger.error(f"Error searching entities: {e}")
        return []


# Define tools list
tools = [search_facts, search_entities]
tool_node = ToolNode(tools)


# ============================================================================
# Initialize Gemini LLM
# ============================================================================

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key=GEMINI_API_KEY,
    temperature=0.7,
    convert_system_message_to_human=True  # Gemini requires this
).bind_tools(tools)


# ============================================================================
# Agent Logic
# ============================================================================

async def chatbot(state: State):
    """
    Main chatbot function that:
    1. Retrieves relevant context from Zep memory
    2. Constructs a system message with facts and entities
    3. Generates a response using Gemini
    4. Persists the conversation to Zep (which builds the KG)
    5. Trims message history to prevent unbounded growth
    """
    
    # Get memory context from Zep
    try:
        memory = await zep.memory.get(state["session_id"])
        context = memory.context if hasattr(memory, 'context') else ""
    except Exception as e:
        logger.warning(f"Could not retrieve memory context: {e}")
        context = ""
    
    # Construct system message with context
    system_message = SystemMessage(
        content=f"""You are a helpful, empathetic AI assistant. 
        
Review the following information about the user and their conversation history, 
then respond accordingly. Be conversational, supportive, and remember details 
from previous interactions.

{context}

Keep responses concise but thoughtful. If you need to search for specific 
information, use the available tools."""
    )
    
    # Prepare messages for LLM
    messages = [system_message] + state["messages"]
    
    # Generate response
    response = await llm.ainvoke(messages)
    
    # Persist conversation to Zep (this builds the knowledge graph)
    messages_to_save = [
        Message(
            role_type="user",
            role=f"{state['first_name']} {state['last_name']}",
            content=state["messages"][-1].content,
        ),
        Message(
            role_type="assistant",
            content=response.content,
        ),
    ]
    
    try:
        await zep.memory.add(
            session_id=state["session_id"],
            messages=messages_to_save,
        )
        logger.info(f"Added messages to Zep session: {state['session_id']}")
    except Exception as e:
        logger.error(f"Error adding messages to Zep: {e}")
    
    # Trim message history to prevent unbounded growth
    # Keep only the last 6 messages (3 exchanges) in state
    state["messages"] = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=len,
        max_tokens=6,
        start_on="human",
        end_on=("human", "tool"),
        include_system=False,
    )
    
    logger.info(f"Messages in state after trim: {len(state['messages'])}")
    
    return {"messages": [response]}


# ============================================================================
# Graph Construction
# ============================================================================

def should_continue(state: State) -> Literal["continue", "end"]:
    """
    Determine whether to continue to tools or end the conversation.
    
    Args:
        state: Current agent state
        
    Returns:
        "continue" if tools should be called, "end" otherwise
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    # If the last message has tool calls, continue to tools
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "continue"
    else:
        return "end"


# Build the graph
graph_builder = StateGraph(State)
memory = MemorySaver()

# Add nodes
graph_builder.add_node("agent", chatbot)
graph_builder.add_node("tools", tool_node)

# Add edges
graph_builder.add_edge(START, "agent")
graph_builder.add_conditional_edges(
    "agent",
    should_continue,
    {"continue": "tools", "end": END}
)
graph_builder.add_edge("tools", "agent")

# Compile the graph
graph = graph_builder.compile(checkpointer=memory)


# ============================================================================
# User and Session Management
# ============================================================================

async def create_user_and_session(first_name: str, last_name: str) -> tuple[str, str]:
    """
    Create a new user and session in Zep.
    
    Args:
        first_name: User's first name
        last_name: User's last name
        
    Returns:
        Tuple of (user_id, session_id)
    """
    user_id = first_name.lower() + uuid.uuid4().hex[:6]
    session_id = uuid.uuid4().hex
    
    try:
        # Create user
        await zep.user.add(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name
        )
        logger.info(f"Created user: {user_id}")
        
        # Create session
        await zep.memory.add_session(
            session_id=session_id,
            user_id=user_id
        )
        logger.info(f"Created session: {session_id}")
        
    except Exception as e:
        logger.error(f"Error creating user/session: {e}")
        raise
    
    return user_id, session_id


# ============================================================================
# Chat Interface
# ============================================================================

async def chat(
    message: str,
    first_name: str,
    last_name: str,
    user_id: str,
    session_id: str,
    ai_response_only: bool = True
) -> str:
    """
    Send a message to the agent and get a response.
    
    Args:
        message: User's message
        first_name: User's first name
        last_name: User's last name
        user_id: User ID
        session_id: Session ID
        ai_response_only: If True, return only AI response; if False, return full conversation
        
    Returns:
        AI response or full conversation string
    """
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=message)],
            "first_name": first_name,
            "last_name": last_name,
            "user_id": user_id,
            "session_id": session_id,
        },
        config={"configurable": {"thread_id": session_id}},
    )
    
    if ai_response_only:
        return result["messages"][-1].content
    else:
        # Extract full conversation
        output = ""
        for msg in result["messages"]:
            if isinstance(msg, AIMessage):
                role = "Assistant"
            else:
                role = f"{first_name} {last_name}"
            output += f"{role}: {msg.content}\n"
        return output.strip()


async def get_memory_context(session_id: str) -> str:
    """
    Retrieve the current memory context for a session.
    
    Args:
        session_id: Session ID to get context for
        
    Returns:
        Formatted context string with facts and entities
    """
    try:
        memory = await zep.memory.get(session_id=session_id)
        return memory.context if hasattr(memory, 'context') else "No context available"
    except Exception as e:
        logger.error(f"Error getting memory context: {e}")
        return f"Error retrieving context: {e}"


# ============================================================================
# Interactive CLI
# ============================================================================

async def run_interactive_chat():
    """Run an interactive chat session in the terminal"""
    print("\n" + "="*60)
    print("🤖 Zep Knowledge Graph Agent with Gemini")
    print("="*60)
    print("\nThis agent builds a knowledge graph as you chat!")
    print("Type 'exit' to quit, 'context' to view memory context\n")
    
    # Get user information
    first_name = input("Enter your first name: ").strip() or "User"
    last_name = input("Enter your last name: ").strip() or "Guest"
    
    # Create user and session
    print("\n🔧 Setting up your session...")
    user_id, session_id = await create_user_and_session(first_name, last_name)
    print(f"✅ Session created!")
    print(f"   User ID: {user_id}")
    print(f"   Session ID: {session_id}")
    print("\n" + "-"*60 + "\n")
    
    # Chat loop
    while True:
        user_input = input(f"{first_name}: ").strip()
        
        if not user_input:
            continue
            
        if user_input.lower() in ['exit', 'quit', 'bye']:
            print("\n👋 Goodbye! Your conversation has been saved to the knowledge graph.")
            break
            
        if user_input.lower() == 'context':
            print("\n📊 Current Memory Context:")
            print("-"*60)
            context = await get_memory_context(session_id)
            print(context)
            print("-"*60 + "\n")
            continue
        
        # Get response
        try:
            response = await chat(
                message=user_input,
                first_name=first_name,
                last_name=last_name,
                user_id=user_id,
                session_id=session_id,
                ai_response_only=True
            )
            print(f"\n🤖 Assistant: {response}\n")
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            print(f"\n❌ Error: {e}\n")


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    """Main entry point for the application"""
    await run_interactive_chat()


if __name__ == "__main__":
    asyncio.run(main())
