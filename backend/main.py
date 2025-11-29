import asyncio
import os
import uuid

from dotenv import load_dotenv

from gemini_service import GeminiService
from graph_config import CUSTOM_ENTITIES, CUSTOM_EDGES, DEFAULT_CONTEXT_TEMPLATE
from zep_service import ZepService

# Load environment variables
load_dotenv()

ZEP_API_KEY = os.getenv("ZEP_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


async def main():
    if not ZEP_API_KEY or not GEMINI_API_KEY:
        raise RuntimeError("Set ZEP_API_KEY and GEMINI_API_KEY in backend/.env")

    zep_service = ZepService(ZEP_API_KEY)
    gemini_service = GeminiService(GEMINI_API_KEY)

    await zep_service.ensure_ontology(CUSTOM_ENTITIES, CUSTOM_EDGES)

    user_id = f"user_{uuid.uuid4().hex[:8]}"
    session_id = f"session_{uuid.uuid4().hex[:8]}"

    print(f"Starting chat session: {session_id} for user: {user_id}")
    await zep_service.create_session(
        user_id,
        session_id,
        first_name="CLI",
        last_name="User",
        metadata={"origin": "cli"},
    )

    print("Chat initialized. Type 'exit' to quit.")

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ["exit", "quit"]:
            break

        await zep_service.add_memory(session_id, "user", user_input)

        context = await zep_service.build_context_block(
            session_id=session_id,
            user_id=user_id,
            query=user_input,
        )

        prompt = DEFAULT_CONTEXT_TEMPLATE.format(
            session_id=session_id,
            user_name="CLI User",
            preferences="CLI run",
            traits="Exploratory",
            business_data="None",
            memory_section=context["memory_section"],
            graph_section=context["graph_section"],
            query=user_input,
        )

        response_text = await gemini_service.generate_response(prompt)
        print(f"Gemini: {response_text}")

        await zep_service.add_memory(session_id, "assistant", response_text)


if __name__ == "__main__":
    asyncio.run(main())
