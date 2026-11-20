import json
import os
import tempfile
from collections.abc import Callable

import httpx
import pytest

_tmp = tempfile.mkdtemp()
# TEST_DATABASE_URL=postgresql://app:app@localhost:5432/app_test pytest -q  (schema is wiped)
_pg = os.environ.get("TEST_DATABASE_URL")
os.environ["DATABASE_URL"] = _pg or f"sqlite:///{_tmp}/test.db".replace("\\", "/")
if _pg:
    from sqlalchemy import create_engine, text

    _url = _pg.replace("postgresql://", "postgresql+psycopg://", 1)
    with create_engine(_url).begin() as _c:
        _c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
os.environ["STORAGE_DIR"] = os.path.join(_tmp, "evidence")
# The API tests use the built-in seed; the organisers' dataset is tested separately (test_dataset.py).
os.environ["DEMO_DATASET"] = "false"
os.environ["DEMO_PUBLIC_TOKENS"] = "true"  # plain demo-coord, demo-ex-fin … only in tests
os.environ["AI_WAIT_SECONDS"] = "60"  # tests expect AI answers inline

from app.config import settings  # noqa: E402


@pytest.fixture(autouse=True)
def _ollama_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    # The root .env may point to a remote AI API; tests must not depend on it.
    monkeypatch.setattr(settings, "llm_base_url", "")


Handler = Callable[[httpx.Request], httpx.Response]


def reply(payload: dict) -> Handler:
    content = json.dumps(payload, ensure_ascii=False)
    return lambda _: httpx.Response(200, json={"message": {"role": "assistant", "content": content}})


def down(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("down", request=request)


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> Callable[[Handler], list[dict]]:
    """Підміняє чат-сервер моделі (ембединги недоступні); повертає список тіл запитів до чату.
    Збережені відповіді (`llm_answers`) очищаються: інакше той самий запит отримав би відповідь попереднього тесту."""
    from sqlalchemy import delete

    from app import llm
    from app.db import SessionLocal
    from app.models import LlmAnswer

    def use(handler: Handler) -> list[dict]:
        with SessionLocal() as db:
            db.execute(delete(LlmAnswer))
            db.commit()
        sent: list[dict] = []

        def wrapped(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/embed":
                raise httpx.ConnectError("no embeddings", request=request)
            if request.content:
                sent.append(json.loads(request.content))
            return handler(request)

        transport = httpx.MockTransport(wrapped)
        monkeypatch.setattr(llm, "client", httpx.AsyncClient(base_url="http://ollama", transport=transport))
        return sent
    return use
