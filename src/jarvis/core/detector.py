"""Local LLM Auto-Detection Subsystem.

Discovers and tests local inference servers (Ollama, LM Studio, llama.cpp,
and custom OpenAI-compatible endpoints) and retrieves their installed models.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field


class LocalLLMServerInfo(BaseModel):
    """Status and discovered model catalog for a local LLM engine."""
    engine_id: str
    display_name: str
    base_url: str
    is_running: bool = False
    models: List[str] = Field(default_factory=list)
    latency_ms: float = 0.0
    error_message: Optional[str] = None


KNOWN_ENGINES = [
    {
        "engine_id": "ollama",
        "display_name": "Ollama",
        "base_url": "http://127.0.0.1:11434/v1",
        "probe_urls": [
            "http://127.0.0.1:11434/api/tags",
            "http://localhost:11434/api/tags",
            "http://127.0.0.1:11434/v1/models",
            "http://localhost:11434/v1/models",
        ],
    },
    {
        "engine_id": "lm_studio",
        "display_name": "LM Studio",
        "base_url": "http://127.0.0.1:1234/v1",
        "probe_urls": [
            "http://127.0.0.1:1234/v1/models",
            "http://localhost:1234/v1/models",
        ],
    },
    {
        "engine_id": "llama_cpp",
        "display_name": "llama.cpp Server",
        "base_url": "http://127.0.0.1:8080/v1",
        "probe_urls": [
            "http://127.0.0.1:8080/v1/models",
            "http://localhost:8080/v1/models",
            "http://127.0.0.1:8080/health",
        ],
    },
]


class LocalLLMDetector:
    """Asynchronously scans localhost for active LLM backends."""

    def __init__(self, timeout_seconds: float = 1.5) -> None:
        self.timeout_seconds = timeout_seconds

    async def probe_engine(
        self,
        engine_id: str,
        display_name: str,
        base_url: str,
        probe_urls: List[str],
        client: Optional[httpx.AsyncClient] = None,
    ) -> LocalLLMServerInfo:
        """Probe a specific local engine."""
        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=self.timeout_seconds, trust_env=False)
            close_client = True

        models: List[str] = []
        is_running = False
        latency = 0.0
        error: Optional[str] = None

        start_time = time.perf_counter()
        try:
            for url in probe_urls:
                try:
                    res = await client.get(url)
                    if res.status_code == 200:
                        is_running = True
                        latency = (time.perf_counter() - start_time) * 1000.0
                        data = res.json()
                        # Parse Ollama /api/tags
                        if "models" in data and isinstance(data["models"], list):
                            for m in data["models"]:
                                if isinstance(m, dict) and "name" in m:
                                    models.append(m["name"])
                                elif isinstance(m, dict) and "id" in m:
                                    models.append(m["id"])
                        # Parse OpenAI /v1/models
                        elif "data" in data and isinstance(data["data"], list):
                            for item in data["data"]:
                                if isinstance(item, dict) and "id" in item:
                                    models.append(item["id"])
                        break
                except (httpx.ConnectError, httpx.TimeoutException):
                    continue
                except Exception as exc:
                    error = str(exc)
        finally:
            if close_client:
                await client.aclose()

        return LocalLLMServerInfo(
            engine_id=engine_id,
            display_name=display_name,
            base_url=base_url,
            is_running=is_running,
            models=sorted(list(set(models))),
            latency_ms=round(latency, 1),
            error_message=error,
        )

    async def detect_all(self, client: Optional[httpx.AsyncClient] = None) -> List[LocalLLMServerInfo]:
        """Probe all known local LLM backends concurrently."""
        tasks = []
        for eng in KNOWN_ENGINES:
            tasks.append(
                self.probe_engine(
                    engine_id=eng["engine_id"],
                    display_name=eng["display_name"],
                    base_url=eng["base_url"],
                    probe_urls=eng["probe_urls"],
                    client=client,
                )
            )
        return await asyncio.gather(*tasks)

    async def probe_custom_endpoint(
        self, endpoint: str, client: Optional[httpx.AsyncClient] = None
    ) -> LocalLLMServerInfo:
        """Probe an arbitrary custom endpoint using OpenAI /v1/models format."""
        norm_url = endpoint.rstrip("/")
        models_url = f"{norm_url}/models" if norm_url.endswith("/v1") else f"{norm_url}/v1/models"
        return await self.probe_engine(
            engine_id="custom",
            display_name="Custom Endpoint",
            base_url=norm_url if norm_url.endswith("/v1") else f"{norm_url}/v1",
            probe_urls=[models_url, norm_url],
            client=client,
        )
