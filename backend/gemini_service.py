from typing import Optional

from google import genai
from google.genai import types


class GeminiService:
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-1.5-flash",
        system_instruction: Optional[str] = None,
    ):
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is missing")
        
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.system_instruction = system_instruction or "You are a helpful agent that fuses Zep memory with Gemini reasoning."

    async def generate_response(self, prompt: str, model_name: Optional[str] = None) -> str:
        try:
            # Use the async client (aio)
            response = await self.client.aio.models.generate_content(
                model=model_name or self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    temperature=0.35,
                    top_p=0.9,
                    top_k=40,
                    max_output_tokens=1024,
                )
            )
            return response.text or "I was unable to compose a response."
        except Exception as e:
            error_msg = str(e)
            print(f"Error generating response from Gemini: {error_msg}")
            if "429" in error_msg:
                return "⚠️ Error: Gemini API quota exceeded. Please try again later or switch models."
            return f"⚠️ Error generating response: {error_msg}"
