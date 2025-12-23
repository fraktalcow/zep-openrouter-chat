import json
from typing import Optional, List, Dict, Any, AsyncGenerator
import httpx
from datetime import datetime, timedelta

from logger import logger
from config import get_settings


class OpenRouterService:
    """Service for interacting with OpenRouter Chat Completions API."""
    
    BASE_URL = "https://openrouter.ai/api/v1"
    _models_cache: Optional[List[Dict[str, Any]]] = None
    _cache_timestamp: Optional[datetime] = None
    _cache_duration = timedelta(hours=1)
    
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.OPENROUTER_API_KEY
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY is missing")
        
        self.model_name = settings.DEFAULT_MODEL
        self.system_instruction = "You are a smart assistant."
        
        logger.info(f"[OpenRouter] Initialized | default_model={self.model_name}")

    
    def _get_headers(self) -> Dict[str, str]:
        """Standard headers for OpenRouter API."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/zep-chat",
            "X-Title": "Zep Knowledge Graph Chat",
        }
    
    def _build_messages(self, prompt: str) -> List[Dict[str, str]]:
        """Build messages array for Chat Completions API."""
        return [
            {"role": "system", "content": self.system_instruction},
            {"role": "user", "content": prompt}
        ]
    
    async def generate_response(
        self, 
        prompt: str, 
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> str:
        """Non-streaming response generation."""
        model = model_name or self.model_name
        url = f"{self.BASE_URL}/chat/completions"
        
        payload = {
            "model": model,
            "messages": self._build_messages(prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        
        logger.info(f"[OpenRouter] POST {url}")
        logger.debug(f"[OpenRouter] Payload: model={model}, temp={temperature}, max_tokens={max_tokens}")
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                
                logger.info(f"[OpenRouter] Status: {response.status_code}")
                logger.debug(f"[OpenRouter] Response: {response.text[:500]}...")
                
                response.raise_for_status()
                data = response.json()
                
                # Parse Chat Completions response format
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0].get("message", {}).get("content", "")
                    logger.info(f"[OpenRouter] Success | response_len={len(content)}")
                    return content
                
                logger.warning(f"[OpenRouter] Unexpected format: {list(data.keys())}")
                return "Error: Unexpected response format"
                
        except httpx.HTTPStatusError as e:
            logger.error(f"[OpenRouter] HTTP {e.response.status_code}: {e.response.text}")
            return self._format_http_error(e)
        except httpx.TimeoutException:
            logger.error("[OpenRouter] Timeout")
            return "⚠️ Request timed out. Please retry."
        except Exception as e:
            logger.exception(f"[OpenRouter] Exception: {e}")
            return f"⚠️ Error: {e}"
    
    async def generate_response_stream(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> AsyncGenerator[str, None]:
        """
        Stream response using Chat Completions API.
        Per OpenRouter docs: uses 'delta.content' for streaming chunks.
        """
        model = model_name or self.model_name
        url = f"{self.BASE_URL}/chat/completions"
        
        payload = {
            "model": model,
            "messages": self._build_messages(prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        
        logger.info(f"[OpenRouter] STREAM POST {url}")
        logger.info(f"[OpenRouter] model={model} | temp={temperature} | max_tokens={max_tokens}")
        logger.debug(f"[OpenRouter] Full payload: {json.dumps(payload, indent=2)}")
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, headers=self._get_headers(), json=payload) as response:
                    
                    logger.info(f"[OpenRouter] Stream status: {response.status_code}")
                    
                    if response.status_code != 200:
                        body = await response.aread()
                        error_text = body.decode()
                        logger.error(f"[OpenRouter] Stream error: {error_text}")
                        yield f"⚠️ API Error ({response.status_code}): {error_text}"
                        return
                    
                    chunk_count = 0
                    async for line in response.aiter_lines():
                        # Skip empty lines
                        if not line:
                            continue
                        
                        # SSE format: "data: {...}"
                        if not line.startswith("data:"):
                            logger.debug(f"[OpenRouter] Skipping non-data line: {line[:50]}")
                            continue
                        
                        data_str = line[5:].strip()  # Remove "data:" prefix
                        
                        # End of stream marker
                        if data_str == "[DONE]":
                            logger.info(f"[OpenRouter] Stream complete | chunks={chunk_count}")
                            return
                        
                        try:
                            event = json.loads(data_str)
                            
                            # Check for errors in event
                            if "error" in event:
                                err = event["error"]
                                err_msg = err.get("message", str(err))
                                logger.error(f"[OpenRouter] Event error: {err_msg}")
                                yield f"⚠️ {err_msg}"
                                return
                            
                            # Standard Chat Completions streaming format:
                            # choices[0].delta.content contains the text chunk
                            choices = event.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content")
                                
                                if content:
                                    chunk_count += 1
                                    logger.debug(f"[OpenRouter] Chunk {chunk_count}: {repr(content[:30])}")
                                    yield content
                                
                                # Check for finish reason
                                finish = choices[0].get("finish_reason")
                                if finish:
                                    logger.info(f"[OpenRouter] Finish reason: {finish}")
                                    
                        except json.JSONDecodeError as e:
                            logger.warning(f"[OpenRouter] JSON decode error: {e} | line: {data_str[:100]}")
                            continue
                            
        except httpx.TimeoutException:
            logger.error("[OpenRouter] Stream timeout")
            yield "⚠️ Request timed out"
        except Exception as e:
            logger.exception(f"[OpenRouter] Stream exception: {e}")
            yield f"⚠️ Error: {e}"
    
    def _format_http_error(self, e: httpx.HTTPStatusError) -> str:
        """Format HTTP errors with helpful messages."""
        status = e.response.status_code
        error_text = e.response.text
        
        # Check for specific Data Policy error
        if status == 404 and "data policy" in error_text:
             return (
                 "⚠️ OpenRouter Data Policy Error: Free models require enabling data training.\n"
                 "Please go to https://openrouter.ai/settings/privacy and enable 'Allow inputs to be used for model improvement'."
             )

        error_map = {
            401: "Invalid API key. Check OPENROUTER_API_KEY.",
            402: "Insufficient credits. Check your OpenRouter account.",
            429: "Rate limit exceeded. Please wait and retry.",
            404: "Model not found or not available.",
        }
        base_msg = error_map.get(status, f"HTTP {status}")
        return f"⚠️ {base_msg}\nDetails: {error_text[:200]}"
    
    # ─────────────────────────────────────────────────────────────────────────
    # Model Discovery Methods (unchanged)
    # ─────────────────────────────────────────────────────────────────────────
    
    async def fetch_all_models(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Fetch all available models from OpenRouter API (cached for 1 hour)."""
        if not force_refresh and self._models_cache and self._cache_timestamp:
            if datetime.now() - self._cache_timestamp < self._cache_duration:
                return self._models_cache
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()
                data = response.json()
                
                models = []
                for m in data.get("data", []):
                    models.append({
                        "id": m.get("id", ""),
                        "name": m.get("name", m.get("id", "")),
                        "description": m.get("description", ""),
                        "context_length": m.get("context_length", 0),
                        "pricing": m.get("pricing", {}),
                        "top_provider": m.get("top_provider", {}),
                        "architecture": m.get("architecture", {}),
                    })
                
                self._models_cache = models
                self._cache_timestamp = datetime.now()
                logger.info(f"[OpenRouter] Cached {len(models)} models")
                return models
                
        except Exception as e:
            logger.error(f"[OpenRouter] fetch_all_models error: {e}")
            return self._models_cache or []
    
    async def search_models(
        self, 
        query: str = "", 
        free_only: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search and filter models by name/description."""
        all_models = await self.fetch_all_models()
        
        filtered = all_models
        if query:
            q = query.lower()
            filtered = [m for m in filtered if q in m["id"].lower() or q in m["name"].lower()]
        
        if free_only:
            filtered = [m for m in filtered if m.get("pricing", {}).get("prompt") == "0" or ":free" in m["id"]]
        
        return filtered[:limit]
    


# Singleton instance
_openrouter_service: Optional[OpenRouterService] = None

def get_openrouter_service() -> OpenRouterService:
    """Get or create OpenRouter service instance."""
    global _openrouter_service
    if _openrouter_service is None:
        _openrouter_service = OpenRouterService()
    return _openrouter_service
