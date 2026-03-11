from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self):
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model
        self.embed_model = settings.ollama_embed_model
        self.timeout = settings.ollama_timeout

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self.base_url}/api/tags")
            r.raise_for_status()
            return r.json().get("models", [])

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> dict:
        """Send a chat completion request to Ollama."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 2048,
            },
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json()

    async def generate(
        self,
        prompt: str,
        system: str = "",
    ) -> str:
        """Fallback: use /api/generate for models that don't support /api/chat."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 2048,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json().get("response", "")

    async def generate_embeddings(self, text: str) -> list[float]:
        """Generate embeddings using Ollama's embedding model."""
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.embed_model, "prompt": text},
            )
            r.raise_for_status()
            return r.json().get("embedding", [])

    def set_model(self, model: str):
        self.model = model
        logger.info(f"Switched model to: {model}")