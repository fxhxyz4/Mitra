import asyncio
import json
from collections.abc import Callable, Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from app import llm
from app.config import settings
from app.main import app

AUTH = {"Authorization": "Bearer demo-ex-fin"}
# /ai/chat and /ai/embed are model diagnostics for the administrator.
ADMIN = {"Authorization": "Bearer demo-admin"}
Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def fake_ollama(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/tags":
        return httpx.Response(200, json={"models": [{"name": "gemma3:4b"}, {"name": "bge-m3:latest"}]})
    if request.url.path == "/api/chat":
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "привіт"}})
    if request.url.path == "/api/embed":
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]]})
    return httpx.Response(404)


def down(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("down", request=request)


@pytest.fixture
def ollama(monkeypatch: pytest.MonkeyPatch) -> Callable[[Handler], None]:
    def use(handler: Handler) -> None:
        monkeypatch.setattr(
            llm, "client", httpx.AsyncClient(base_url="http://ollama", transport=httpx.MockTransport(handler))
        )

    return use


def test_health(client: TestClient) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


@pytest.mark.parametrize(("method", "path", "body"), [
    ("GET", "/api/ai/status", None),
    ("POST", "/api/ai/chat", {"messages": [{"role": "user", "content": "привіт"}]}),
    ("POST", "/api/ai/embed", {"texts": ["текст"]}),
])
def test_ai_requires_token(client: TestClient, ollama, method: str, path: str, body: dict | None) -> None:
    ollama(fake_ollama)
    assert client.request(method, path, json=body).status_code == 401


@pytest.mark.parametrize("path", ["/api/ai/chat", "/api/ai/embed"])
def test_raw_model_access_is_admin_only(client: TestClient, ollama, path: str) -> None:
    ollama(fake_ollama)
    body = {"messages": [{"role": "user", "content": "x"}]} if path.endswith("chat") else {"texts": ["x"]}
    assert client.post(path, headers=AUTH, json=body).status_code == 403


def test_ai_status_ready(client: TestClient, ollama) -> None:
    ollama(fake_ollama)
    data = client.get("/api/ai/status", headers=AUTH).json()
    assert data["reachable"] is True
    assert data["ready"] is True


def test_ai_status_unreachable(client: TestClient, ollama) -> None:
    ollama(down)
    data = client.get("/api/ai/status", headers=AUTH).json()
    assert data["reachable"] is False
    assert data["ready"] is False


def test_ai_chat(client: TestClient, ollama) -> None:
    ollama(fake_ollama)
    res = client.post("/api/ai/chat", headers=ADMIN, json={"messages": [{"role": "user", "content": "привіт"}]})
    assert res.status_code == 200
    assert res.json()["content"] == "привіт"


def test_ai_chat_is_deterministic(client: TestClient, ollama) -> None:
    sent: list[dict] = []

    def server(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return fake_ollama(request)

    ollama(server)
    client.post("/api/ai/chat", headers=ADMIN, json={"messages": [{"role": "user", "content": "параметри"}]})
    assert sent[0]["options"] == {"temperature": 0, "seed": 42, "num_predict": settings.llm_max_tokens}


def test_ai_chat_same_question_same_answer(client: TestClient, ollama) -> None:
    calls: list[str] = []

    def server(request: httpx.Request) -> httpx.Response:
        if request.url.path != "/api/chat":
            return fake_ollama(request)
        calls.append(json.loads(request.content)["messages"][-1]["content"])
        return httpx.Response(200, json={"message": {"role": "assistant", "content": f"відповідь {len(calls)}"}})

    ollama(server)

    def ask(question: str) -> str:
        res = client.post("/api/ai/chat", headers=ADMIN, json={"messages": [{"role": "user", "content": question}]})
        return res.json()["content"]

    first = ask("що таке корупційний ризик?")
    assert ask("що таке корупційний ризик?") == first
    assert ask("що таке конфлікт інтересів?") != first
    assert calls == ["що таке корупційний ризик?", "що таке конфлікт інтересів?"]


def test_ai_chat_unreachable(client: TestClient, ollama) -> None:
    ollama(down)
    res = client.post("/api/ai/chat", headers=ADMIN, json={"messages": [{"role": "user", "content": "недоступна"}]})
    assert res.status_code == 503


def test_ai_embed(client: TestClient, ollama) -> None:
    ollama(fake_ollama)
    res = client.post("/api/ai/embed", headers=ADMIN, json={"texts": ["текст"]})
    assert res.json()["embeddings"] == [[0.1, 0.2, 0.3]]


def test_openai_compatible_server(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, dict] = {}

    def server(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "qwen"}, {"id": "bge-m3"}]})
        if request.url.path == "/v1/chat/completions":
            seen["chat"] = json.loads(request.content)
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "добре"}}]})
        if request.url.path == "/v1/embeddings":
            return httpx.Response(200, json={"data": [{"index": 1, "embedding": [2.0]}, {"index": 0, "embedding": [1.0]}]})
        return httpx.Response(404)

    monkeypatch.setattr(settings, "llm_base_url", "http://qwen.local/v1")
    monkeypatch.setattr(settings, "llm_model", "qwen")
    monkeypatch.setattr(llm, "client", httpx.AsyncClient(base_url=settings.llm_base_url,
                                                         transport=httpx.MockTransport(server)))

    status = client.get("/api/ai/status", headers=AUTH).json()
    assert status["ready"] is True and status["chatModel"] == "qwen"

    res = client.post("/api/ai/chat", headers=ADMIN,
                      json={"messages": [{"role": "user", "content": "привіт"}]})
    assert res.json() == {"model": "qwen", "content": "добре"}
    assert seen["chat"]["model"] == "qwen" and seen["chat"]["temperature"] == 0 and seen["chat"]["seed"] == 42
    assert seen["chat"]["max_tokens"] == settings.llm_max_tokens

    vectors = client.post("/api/ai/embed", headers=ADMIN, json={"texts": ["а", "б"]}).json()["embeddings"]
    assert vectors == [[1.0], [2.0]]

    schema = {"type": "object", "properties": {"text": {"type": "string"}}}
    asyncio.run(llm.chat([{"role": "user", "content": "x"}], format=schema))
    assert seen["chat"]["response_format"] == {"type": "json_schema", "json_schema": {"name": "answer", "schema": schema}}


def test_server_without_embedding_model_is_ready(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def server(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "gemma4-26b"}]})

    monkeypatch.setattr(settings, "llm_base_url", "http://gemma.local/v1")
    monkeypatch.setattr(settings, "llm_model", "gemma4-26b")
    monkeypatch.setattr(llm, "client", httpx.AsyncClient(base_url=settings.llm_base_url,
                                                         transport=httpx.MockTransport(server)))

    status = client.get("/api/ai/status", headers=AUTH).json()
    assert status["ready"] is True and status["chatModel"] == "gemma4-26b"


@pytest.mark.parametrize("raw, expected", [
    ('{"a": 1}', '{"a": 1}'),
    ('<think>\nmhm\n</think>\n\n{"a": 1}', '{"a": 1}'),
    ('<think>x</think>```json\n{"a": 1}\n```', '{"a": 1}'),
    ("<think>never closed", ""),
    (None, ""),
])
def test_clean_reasoning_output(raw: str | None, expected: str) -> None:
    assert llm.clean(raw) == expected


def test_measure_search_treats_wildcards_literally(client: TestClient) -> None:
    every = client.get("/api/measures", headers=AUTH).json()
    assert every
    assert client.get("/api/measures", headers=AUTH, params={"q": "%"}).json() == [
        m for m in every if "%" in m["title"] or "%" in m["code"]]
    assert client.get("/api/measures", headers=AUTH, params={"q": "_"}).json() == [
        m for m in every if "_" in m["title"] or "_" in m["code"]]


def test_ai_status_asks_the_model_once_per_interval(client: TestClient, ollama) -> None:
    calls: list[str] = []

    def counting(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return fake_ollama(request)

    ollama(counting)
    for _ in range(3):
        assert client.get("/api/ai/status", headers=AUTH).json()["ready"] is True
    assert calls == ["/api/tags"]
