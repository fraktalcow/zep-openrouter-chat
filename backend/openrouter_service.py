from typing import Optional, List, Dict, Any
import httpx
from datetime import datetime, timedelta


class OpenRouterService:
    """Service for interacting with OpenRouter API to access multiple AI models."""
    
    # Cache for models list
    _models_cache: Optional[List[Dict[str, Any]]] = None
    _cache_timestamp: Optional[datetime] = None
    _cache_duration = timedelta(hours=1)  # Cache for 1 hour
    
    def __init__(
        self,
        api_key: str,
        model_name: str = "meta-llama/llama-3.2-3b-instruct:free",
        system_instruction: Optional[str] = None,
    ):
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is missing")
        
        self.api_key = api_key
        self.model_name = model_name
        self.system_instruction = system_instruction or "You are a helpful agent that fuses Zep memory with AI reasoning."
        self.base_url = "https://openrouter.ai/api/v1"
    
    async def fetch_all_models(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch all available models from OpenRouter API.
        Results are cached for 1 hour to avoid excessive API calls.
        
        Args:
            force_refresh: Force refresh the cache
            
        Returns:
            List of model dictionaries with id, name, pricing, context length, etc.
        """
        # Check cache
        if not force_refresh and self._models_cache and self._cache_timestamp:
            if datetime.now() - self._cache_timestamp < self._cache_duration:
                return self._models_cache
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                    }
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Extract and format models
                models = []
                if "data" in data:
                    for model in data["data"]:
                        models.append({
                            "id": model.get("id", ""),
                            "name": model.get("name", model.get("id", "")),
                            "description": model.get("description", ""),
                            "context_length": model.get("context_length", 0),
                            "pricing": model.get("pricing", {}),
                            "top_provider": model.get("top_provider", {}),
                            "architecture": model.get("architecture", {}),
                        })
                
                # Update cache
                self._models_cache = models
                self._cache_timestamp = datetime.now()
                
                return models
                
        except Exception as e:
            print(f"Error fetching models from OpenRouter: {str(e)}")
            # Return cached data if available, even if expired
            if self._models_cache:
                return self._models_cache
            return []
    
    async def search_models(
        self, 
        query: str = "", 
        free_only: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search and filter models by name/description.
        
        Args:
            query: Search query to filter models (case-insensitive)
            free_only: Only return free models (pricing.prompt = "0")
            limit: Maximum number of results to return
            
        Returns:
            Filtered list of models matching the search criteria
        """
        all_models = await self.fetch_all_models()
        
        # Filter by query
        if query:
            query_lower = query.lower()
            filtered = [
                model for model in all_models
                if query_lower in model["id"].lower() 
                or query_lower in model["name"].lower()
                or query_lower in model.get("description", "").lower()
            ]
        else:
            filtered = all_models
        
        # Filter by free models
        if free_only:
            filtered = [
                model for model in filtered
                if (
                    model.get("pricing", {}).get("prompt", "1") == "0"
                    or ":free" in model["id"]
                )
            ]
        
        # Sort by relevance (exact matches first, then partial matches)
        if query:
            query_lower = query.lower()
            filtered.sort(
                key=lambda m: (
                    0 if m["id"].lower() == query_lower else
                    1 if m["id"].lower().startswith(query_lower) else
                    2 if query_lower in m["name"].lower() else
                    3
                )
            )
        
        return filtered[:limit]
    
    async def generate_response(
        self, 
        prompt: str, 
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> str:
        """
        Generate a response using OpenRouter API.
        
        Args:
            prompt: The user's prompt/query
            model_name: Optional model override
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated response text
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Prepare messages
                messages = [
                    {"role": "system", "content": self.system_instruction},
                    {"role": "user", "content": prompt}
                ]
                
                # Make request to OpenRouter
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "HTTP-Referer": "https://github.com/zep-chat",
                        "X-Title": "Zep Knowledge Graph Chat",
                    },
                    json={
                        "model": model_name or self.model_name,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Extract response
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
                else:
                    return "I was unable to compose a response."
                    
        except httpx.HTTPStatusError as e:
            error_msg = str(e)
            print(f"HTTP Error from OpenRouter: {error_msg}")
            
            if e.response.status_code == 429:
                return "⚠️ Error: Rate limit exceeded. Please try again in a moment."
            elif e.response.status_code == 402:
                return "⚠️ Error: Insufficient credits. Please check your OpenRouter account."
            elif e.response.status_code == 401:
                return "⚠️ Error: Invalid API key. Please check your OPENROUTER_API_KEY."
            else:
                return f"⚠️ HTTP Error {e.response.status_code}: {error_msg}"
                
        except httpx.TimeoutException:
            return "⚠️ Error: Request timed out. Please try again."
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error generating response from OpenRouter: {error_msg}")
            return f"⚠️ Error generating response: {error_msg}"

    async def generate_response_stream(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024
    ):
        """
        Stream a response using OpenRouter API with SSE.
        Yields content chunks as they arrive.
        """
        import httpx
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            messages = [
                {"role": "system", "content": self.system_instruction},
                {"role": "user", "content": prompt}
            ]
            
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://github.com/zep-chat",
                    "X-Title": "Zep Knowledge Graph Chat",
                },
                json={
                    "model": model_name or self.model_name,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                }
            ) as response:
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    while True:
                        line_end = buffer.find('\n')
                        if line_end == -1:
                            break
                        
                        line = buffer[:line_end].strip()
                        buffer = buffer[line_end + 1:]
                        
                        if line.startswith('data: '):
                            data = line[6:]
                            if data == '[DONE]':
                                return
                            
                            try:
                                import json
                                data_obj = json.loads(data)
                                content = data_obj["choices"][0]["delta"].get("content")
                                if content:
                                    yield content
                            except (json.JSONDecodeError, KeyError, IndexError):
                                pass
