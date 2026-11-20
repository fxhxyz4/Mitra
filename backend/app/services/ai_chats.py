import uuid
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..models import AiChat, AiChatMessage, User, utcnow
from ..schemas import ai as a
from .data_chat import Turn, ask

DEFAULT_TITLE = "Нова розмова"
TITLE_CHARS = 80
MAX_MESSAGES = 200


def owned(db: Session, user: User, chat_id: uuid.UUID) -> AiChat:
    chat = db.get(AiChat, chat_id)
    if chat is None or chat.deleted_at is not None or chat.user_id != user.id:
        raise HTTPException(404, "Розмову не знайдено")
    return chat


def of_user(db: Session, user: User) -> list[AiChat]:
    return list(db.scalars(select(AiChat).where(AiChat.user_id == user.id, AiChat.deleted_at.is_(None))
                           .order_by(AiChat.updated_at.desc())))


def create(db: Session, user: User, title: str | None) -> AiChat:
    chat = AiChat(user_id=user.id, title=(title or DEFAULT_TITLE).strip())
    db.add(chat)
    db.flush()
    audit.record(db, user, "ai_chat", chat.id, "create", None, audit.snapshot(chat, "title"))
    return chat


def rename(db: Session, user: User, chat: AiChat, title: str) -> None:
    old = audit.snapshot(chat, "title")
    chat.title = title.strip()
    audit.record(db, user, "ai_chat", chat.id, "update", old, audit.snapshot(chat, "title"))


def delete(db: Session, user: User, chat: AiChat) -> None:
    chat.deleted_at = utcnow()
    audit.record(db, user, "ai_chat", chat.id, "delete", audit.snapshot(chat, "title"), None)


def turns(chat: AiChat) -> list[Turn]:
    pairs = zip(chat.messages[::2], chat.messages[1::2], strict=False)
    return [Turn(q.content, r.content, frozenset((ref["type"], ref["id"]) for ref in r.references))
            for q, r in pairs if q.role == "user" and r.role == "assistant"]


def _title(question: str) -> str:
    text = " ".join(question.split())
    return text if len(text) <= TITLE_CHARS else text[:TITLE_CHARS].rsplit(" ", 1)[0] + "…"


async def send(db: Session, user: User, chat: AiChat, question: str, today: date) -> None:
    if len(chat.messages) >= MAX_MESSAGES:
        raise HTTPException(409, "Розмова задовга: почніть нову")
    reply = await ask(db, user, question, today, turns(chat), chat.id)
    if not chat.messages and chat.title == DEFAULT_TITLE:
        chat.title = _title(question)
    chat.messages += [
        AiChatMessage(role="user", content=question),
        AiChatMessage(role="assistant", content=reply.answer, answer_source=reply.answer_source,
                      references=[r.model_dump(mode="json") for r in reply.references],
                      model=reply.model, model_used=reply.model_used),
    ]
    chat.updated_at = utcnow()
    db.flush()


def summary(chat: AiChat) -> a.AiChatSummary:
    return a.AiChatSummary(id=chat.id, title=chat.title, message_count=len(chat.messages),
                           created_at=chat.created_at, updated_at=chat.updated_at)


def out(chat: AiChat) -> a.AiChatOut:
    messages = [a.AiChatMessageOut.model_validate(m, from_attributes=True) for m in chat.messages]
    return a.AiChatOut(**summary(chat).model_dump(), messages=messages)
