from typing import Optional, List, Dict, Any
import httpx
import math
from datetime import datetime, timedelta

import db


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


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
    
    async def fetch_embedding_models(self) -> List[Dict[str, Any]]:
        """
        Fetch models that support embeddings from OpenRouter.
        Filters models with 'embeddings' in their supported modalities.
        """
        all_models = await self.fetch_all_models()
        
        # Filter for embedding models
        embedding_models = []
        for model in all_models:
            arch = model.get("architecture", {})
            modality = arch.get("modality", "")
            # Check if model supports embeddings
            if "embedding" in model["id"].lower() or "embed" in modality.lower():
                embedding_models.append({
                    "id": model["id"],
                    "name": model["name"],
                    "description": model.get("description", ""),
                    "pricing": model.get("pricing", {}),
                })
        
        # Add known embedding models that might not be filtered
        known_embeddings = [
            "openai/text-embedding-3-small",
            "openai/text-embedding-3-large", 
            "openai/text-embedding-ada-002",
        ]
        existing_ids = {m["id"] for m in embedding_models}
        for known in known_embeddings:
            if known not in existing_ids:
                embedding_models.append({
                    "id": known,
                    "name": known.split("/")[-1],
                    "description": "OpenAI embedding model",
                    "pricing": {},
                })
        
        return embedding_models
    
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
            elif e.response.status_code == 404:
                return "⚠️ Error: No endpoints matching your data policy for this model. Try a different model."
            else:
                error_details = e.response.text
                return f"⚠️ HTTP Error {e.response.status_code}: {error_msg}\nDetails: {error_details}"
                
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
        
        Yields:
            str: Content chunks from the streaming response
        """
        import json
        
        try:
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
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_name or self.model_name,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": True,
                    }
                ) as response:
                    response.raise_for_status()
                    
                    # Read raw bytes to avoid any text decoding buffering
                    buffer = b""
                    async for chunk_bytes in response.aiter_bytes():
                        if not chunk_bytes:
                            continue
                        
                        buffer += chunk_bytes
                        
                        # Process complete SSE lines (ending with \n)
                        while b'\n' in buffer:
                            line_end = buffer.find(b'\n')
                            line_bytes = buffer[:line_end]
                            buffer = buffer[line_end + 1:]
                            
                            if not line_bytes.strip():
                                continue
                            
                            try:
                                line = line_bytes.decode('utf-8').strip()
                                
                                # Handle SSE format: "data: {...}" or "data: [DONE]"
                                if line.startswith('data: '):
                                    data_str = line[6:]  # Remove "data: " prefix
                                    
                                    if data_str == '[DONE]':
                                        return
                                    
                                    try:
                                        data_obj = json.loads(data_str)
                                        # Handle OpenAI-compatible streaming format
                                        if "choices" in data_obj and len(data_obj["choices"]) > 0:
                                            delta = data_obj["choices"][0].get("delta", {})
                                            content = delta.get("content")
                                            if content:
                                                # Yield immediately - this is real streaming data from OpenRouter
                                                yield content
                                    except (json.JSONDecodeError, KeyError, IndexError):
                                        # Skip malformed chunks, continue streaming
                                        continue
                            except UnicodeDecodeError:
                                # Skip invalid UTF-8, continue with next chunk
                                continue
                    
                    # Process any remaining buffer content
                    if buffer.strip():
                        try:
                            remaining = buffer.decode('utf-8').strip()
                            if remaining.startswith('data: '):
                                data_str = remaining[6:]
                                if data_str != '[DONE]':
                                    try:
                                        data_obj = json.loads(data_str)
                                        if "choices" in data_obj and len(data_obj["choices"]) > 0:
                                            delta = data_obj["choices"][0].get("delta", {})
                                            content = delta.get("content")
                                            if content:
                                                yield content
                                    except (json.JSONDecodeError, KeyError, IndexError):
                                        pass
                        except UnicodeDecodeError:
                            pass
                                    
        except httpx.HTTPStatusError as e:
            error_msg = str(e)
            print(f"HTTP Error from OpenRouter streaming: {error_msg}")
            
            if e.response.status_code == 429:
                error_msg = "⚠️ Error: Rate limit exceeded. Please try again in a moment."
            elif e.response.status_code == 402:
                error_msg = "⚠️ Error: Insufficient credits. Please check your OpenRouter account."
            elif e.response.status_code == 401:
                error_msg = "⚠️ Error: Invalid API key. Please check your OPENROUTER_API_KEY."
            elif e.response.status_code == 404:
                error_msg = "⚠️ Error: No endpoints matching your data policy for this model. Try a different model."
            else:
                error_msg = f"⚠️ HTTP Error {e.response.status_code}: {error_msg}"
            
            raise Exception(error_msg)
            
        except httpx.TimeoutException:
            error_msg = "⚠️ Error: Request timed out. Please try again."
            print(f"Timeout from OpenRouter streaming: {error_msg}")
            raise Exception(error_msg)
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error in OpenRouter streaming: {error_msg}")
            if not error_msg.startswith("⚠️"):
                error_msg = f"⚠️ Error generating response: {error_msg}"
            raise Exception(error_msg)

    # ==================== EMBEDDINGS API ====================
    
    async def generate_embeddings(
        self,
        texts: List[str],
        model: str = "openai/text-embedding-3-small"
    ) -> List[List[float]]:
        """
        Generate embeddings using OpenRouter's embeddings API.
        
        Args:
            texts: List of texts to embed
            model: Embedding model to use
            
        Returns:
            List of embedding vectors
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "HTTP-Referer": "https://github.com/zep-chat",
                        "X-Title": "Zep Knowledge Graph Chat",
                    },
                    json={
                        "model": model,
                        "input": texts,
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                # Extract embeddings in order
                embeddings = [None] * len(texts)
                for item in data.get("data", []):
                    idx = item.get("index", 0)
                    embeddings[idx] = item.get("embedding", [])
                
                return embeddings
                
        except httpx.HTTPStatusError as e:
            print(f"Embeddings API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            print(f"Embeddings error: {e}")
            raise

    # ==================== RAG STORE ====================
    # Uses SQLite for persistent storage
    
    async def add_documents(
        self,
        documents: List[Dict[str, Any]],
        embedding_model: str = "openai/text-embedding-3-small"
    ) -> Dict[str, Any]:
        """
        Add documents to the RAG store (SQLite).
        
        Args:
            documents: List of {"text": str, "metadata": dict} objects
            embedding_model: Model for generating embeddings
            
        Returns:
            Status with count of added documents
        """
        texts = [doc["text"] for doc in documents]
        embeddings = await self.generate_embeddings(texts, embedding_model)
        total = db.add_documents(documents, embeddings)
        return {"added": len(documents), "total": total}
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        embedding_model: str = "openai/text-embedding-3-small"
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant documents using semantic similarity.
        
        Args:
            query: Search query
            top_k: Number of results to return
            embedding_model: Model for generating query embedding
            
        Returns:
            List of documents with similarity scores
        """
        documents, embeddings = db.get_all_documents()
        if not documents:
            return []
        
        # Get query embedding
        query_emb = (await self.generate_embeddings([query], embedding_model))[0]
        
        # Calculate similarities
        results = []
        for doc, emb in zip(documents, embeddings):
            score = cosine_similarity(query_emb, emb)
            results.append({
                "text": doc["text"],
                "metadata": doc["metadata"],
                "score": score,
            })
        
        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def clear_documents(self) -> Dict[str, Any]:
        """Clear all documents from RAG store."""
        count = db.clear_documents()
        return {"cleared": count}
    
    def get_document_count(self) -> int:
        """Get number of documents in RAG store."""
        return db.get_document_count()
