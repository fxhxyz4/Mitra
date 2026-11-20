from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

_is_sqlite = settings.database_url.startswith("sqlite")
if _is_sqlite:
    Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_ADDED_COLUMNS = {
    "users": {"deleted_at": "TIMESTAMP WITH TIME ZONE", "token_expires_at": "TIMESTAMP WITH TIME ZONE"},
    "corruption_risks": {"probability": "INTEGER", "impact": "INTEGER", "program_id": "UUID REFERENCES programs(id)",
                         "process": "TEXT DEFAULT ''", "content": "TEXT DEFAULT ''", "sources": "TEXT DEFAULT ''",
                         "existing_controls": "TEXT DEFAULT ''", "owner_unit_id": "UUID REFERENCES org_units(id)"},
    "measures": {"deadline_text": "TEXT DEFAULT ''", "evidence_form": "TEXT DEFAULT ''", "contribution": "NUMERIC(6, 4)",
                 "indicator_text": "TEXT DEFAULT ''"},
    "indicators": {
        "direction": "VARCHAR(32)", "weight": "NUMERIC(8, 4) DEFAULT 1", "lag_months": "INTEGER DEFAULT 6",
        "source": "TEXT DEFAULT ''", "independent": "BOOLEAN DEFAULT TRUE", "min_sample": "INTEGER",
        "noise_threshold": "NUMERIC(14, 4)", "target_date": "DATE", "paired_with_id": "UUID",
        "baseline_frozen_at": "TIMESTAMP WITH TIME ZONE", "baseline_hash": "VARCHAR(64)",
    },
    "indicator_values": {"sample_size": "INTEGER"},
    "evidence_files": {"doc_type": "TEXT DEFAULT ''", "document_date": "DATE"},
    "reports": {"revoked_at": "TIMESTAMP WITH TIME ZONE", "revoked_by": "UUID REFERENCES users(id)",
                "revoke_reason": "TEXT DEFAULT ''"},
}


def add_missing_columns() -> None:
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in _ADDED_COLUMNS.items():
            if not insp.has_table(table):
                continue
            have = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols.items():
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
