import asyncio
import hashlib
import json
import re
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from .config import settings
from .db import SessionLocal
from .models import LlmAnswer, as_utc, utcnow


def is_openai_compatible() -> bool:
    return bool(settings.llm_base_url)


def chat_model() -> str:
    if is_openai_compatible() and settings.llm_model:
        return settings.llm_model
    return settings.ollama_model


def _make_client() -> httpx.AsyncClient:
    if is_openai_compatible():
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"} if settings.llm_api_key else {}
        return httpx.AsyncClient(base_url=settings.llm_base_url, headers=headers, timeout=settings.llm_timeout)
    return httpx.AsyncClient(base_url=settings.ollama_url, timeout=settings.llm_timeout)


client: httpx.AsyncClient | None = None  # set to override (tests); otherwise one client per event loop
_clients: dict[asyncio.AbstractEventLoop, httpx.AsyncClient] = {}


def _client() -> httpx.AsyncClient:
    if client is not None:
        return client
    loop = asyncio.get_running_loop()
    c = _clients.get(loop)
    if c is None or c.is_closed:
        c = _clients[loop] = _make_client()
    return c


async def aclose() -> None:
    c = _clients.pop(asyncio.get_running_loop(), None)
    if c is not None:
        await c.aclose()


def has_model(available: list[str], name: str) -> bool:
    return name in available or f"{name}:latest" in available


async def list_models() -> list[str]:
    if is_openai_compatible():
        res = await _client().get("/models")
        res.raise_for_status()
        return [m["id"] for m in res.json().get("data", [])]
    res = await _client().get("/api/tags")
    res.raise_for_status()
    return [m["name"] for m in res.json().get("models", [])]


def _response_format(format: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(format, dict):
        return {"type": "json_schema", "json_schema": {"name": "answer", "schema": format}}
    return {"type": "json_object"}


_THINK = re.compile(r"<think>.*?</think>", re.S)
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.S)


def clean(content: str | None) -> str:
    """Qwen3: drop <think>…</think> and ```json fences around the answer."""
    text = _THINK.sub("", content or "").strip()
    if text.startswith("<think>"):  # unterminated reasoning (max_tokens)
        return ""
    if m := _FENCE.match(text):
        text = m.group(1).strip()
    return text


def sampling() -> dict[str, float | int]:
    return {"temperature": settings.llm_temperature, "seed": settings.llm_seed}


async def chat(messages: list[dict[str, str]], format: str | dict[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {"model": chat_model(), "messages": messages, "stream": False}
    if is_openai_compatible():
        payload.update(sampling(), max_tokens=settings.llm_max_tokens)
        if format is not None:
            payload["response_format"] = _response_format(format)
        res = await _client().post("/chat/completions", json=payload)
        res.raise_for_status()
        return clean(res.json()["choices"][0]["message"].get("content"))
    payload["options"] = {**sampling(), "num_predict": settings.llm_max_tokens}
    payload["keep_alive"] = settings.ollama_keep_alive
    if format is not None:
        payload["format"] = format
    res = await _client().post("/api/chat", json=payload)
    res.raise_for_status()
    return clean(res.json()["message"].get("content"))


def request_key(messages: list[dict[str, str]], format: str | dict[str, Any] | None) -> str:
    request = {"model": chat_model(), **sampling(), "messages": messages, "format": format}
    return hashlib.sha256(json.dumps(request, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _fresh(row: LlmAnswer) -> bool:
    return as_utc(row.created_at) > utcnow() - timedelta(days=settings.llm_cache_days)


def _usable(content: str, format: str | dict[str, Any] | None) -> bool:
    if not content:
        return False
    if format is None:
        return True
    try:
        json.loads(content)
    except ValueError:
        return False
    return True


def _stored(key: str, format: str | dict[str, Any] | None) -> str | None:
    with SessionLocal() as cache:
        row = cache.get(LlmAnswer, key)
        if row is None:
            return None
        if _fresh(row) and _usable(clean(row.content), format):
            return row.content
        cache.delete(row)
        cache.commit()
        return None


def clear_cache() -> int:
    with SessionLocal() as cache:
        n = cache.execute(delete(LlmAnswer)).rowcount
        cache.commit()
    return n


def forget(messages: list[dict[str, str]], format: str | dict[str, Any] | None = None) -> None:
    with SessionLocal() as cache:
        if row := cache.get(LlmAnswer, request_key(messages, format)):
            cache.delete(row)
            cache.commit()


def _store(key: str, content: str) -> str:
    if settings.llm_cache_days <= 0:
        return content
    with SessionLocal() as cache:
        cache.add(LlmAnswer(key=key, model=chat_model(), content=content))
        try:
            cache.commit()
        except IntegrityError:
            cache.rollback()
            row = cache.get(LlmAnswer, key)
            if row is None:
                raise
            return row.content
    return content


async def answer(messages: list[dict[str, str]], format: str | dict[str, Any] | None = None) -> str:
    key = request_key(messages, format)
    if (stored := _stored(key, format)) is not None:
        return clean(stored)
    content = await chat(messages, format)
    return _store(key, content) if _usable(content, format) else content


async def embed(texts: list[str]) -> list[list[float]]:
    body = {"model": settings.embed_model, "input": texts}
    if is_openai_compatible():
        res = await _client().post("/embeddings", json=body)
        res.raise_for_status()
        return [item["embedding"] for item in sorted(res.json()["data"], key=lambda item: item["index"])]
    res = await _client().post("/api/embed", json=body)
    res.raise_for_status()
    return res.json()["embeddings"]
