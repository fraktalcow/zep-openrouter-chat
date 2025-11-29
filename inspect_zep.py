import asyncio
import os
from zep_cloud.client import AsyncZep
from dotenv import load_dotenv

load_dotenv("backend/.env")

async def main():
    api_key = os.getenv("ZEP_API_KEY")
    if not api_key:
        print("No API Key found")
        return

    client = AsyncZep(api_key=api_key)
    print("Client attributes:", dir(client))
    
    try:
        print("client.memory:", client.memory)
    except AttributeError as e:
        print("client.memory error:", e)

    try:
        print("client.graph:", client.graph)
    except AttributeError as e:
        print("client.graph error:", e)

if __name__ == "__main__":
    asyncio.run(main())
