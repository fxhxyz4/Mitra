import logging
import re
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..enums import Channel
from ..models import NotificationDelivery, Reminder, UserContact, as_utc, utcnow

log = logging.getLogger("app.notify")

SENT, FAILED, SKIPPED = "SENT", "FAILED", "SKIPPED"
EXTERNAL = (Channel.EMAIL,)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_address(channel: Channel, address: str) -> str | None:
    if channel == Channel.EMAIL and not _EMAIL.match(address):
        return "Некоректна адреса e-mail"
    if channel == Channel.IN_APP:
        return "IN_APP не потребує контакту"
    return None


def configured(channel: Channel) -> bool:
    if channel == Channel.EMAIL:
        return bool(settings.smtp_host)
    return False


def send_email(to: str, subject: str, text: str) -> None:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.smtp_from, to, subject
    msg.set_content(text)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)


SENDERS = {
    Channel.EMAIL: lambda addr, r: send_email(addr, "Нагадування про строк заходу антикорупційної програми", r.text),
}


def dispatch(db: Session, now: datetime | None = None) -> int:
    now = now or utcnow()
    for r in db.scalars(select(Reminder).where(Reminder.sent.is_(False))):
        if as_utc(r.send_at) <= now:
            r.sent = True
    db.flush()

    channels = [c for c in EXTERNAL if configured(c)]
    if not channels:
        return 0
    contacts: dict = {}
    for c in db.scalars(select(UserContact).where(UserContact.channel.in_(channels))):
        contacts.setdefault(c.user_id, []).append(c)
    oldest = now - timedelta(days=settings.notify_max_age_days)
    n = 0
    for r in db.scalars(select(Reminder).where(Reminder.sent.is_(True), Reminder.user_id.in_(contacts.keys()))):
        done = {d.channel for d in r.deliveries}
        for c in contacts[r.user_id]:
            if c.channel in done:
                continue
            d = NotificationDelivery(reminder=r, channel=c.channel, address=c.address)
            if as_utc(r.send_at) < oldest:
                d.status, d.error = SKIPPED, "Нагадування застаріло"
            else:
                try:
                    SENDERS[c.channel](c.address, r)
                    d.status = SENT
                    n += 1
                except Exception as e:
                    log.warning("delivery %s → %s failed: %s", c.channel, c.address, e)
                    d.status, d.error = FAILED, str(e)[:500]
            db.add(d)
    db.flush()
    return n
