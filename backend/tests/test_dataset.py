import json
import os
import uuid
from collections import Counter

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app import audit
from app.db import Base
from app.enums import MeasureStatus, RiskLevel
from app.models import (
    AuditLogEntry,
    CorruptionRisk,
    Evidence,
    Measure,
    OrgUnit,
    Program,
    RiskFlag,
    User,
)
from app.services import dataset, reports

DATA = json.loads(dataset.DEFAULT_FILE.read_text(encoding="utf-8"))
T = DATA["tablytsi"]
# Executor reported «виконано», but the coordinator has not approved it yet: our report carries only approved
# results, so these stay «Не виконано» until approval (the reference copies the executor's status as is).
NOT_APPROVED = {z["zakhid_id"] for z in T["vykonannia_2026_h1"]
                if z["status"] in ("vykonano", "chastkovo") and z["pohodzheno_koordynatorom"] != "так"}


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    pg = os.environ.get("TEST_DATABASE_URL")
    if pg:
        url = pg.replace("postgresql://", "postgresql+psycopg://", 1)
        with create_engine(url).begin() as c:
            c.execute(text("DROP SCHEMA IF EXISTS ds CASCADE; CREATE SCHEMA ds"))
        engine = create_engine(url, connect_args={"options": "-csearch_path=ds"})
    else:
        engine = create_engine(f"sqlite:///{tmp_path_factory.mktemp('ds')}/ds.db")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        assert dataset.load(s)
        assert not dataset.load(s)  # second run is a no-op
        yield s


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_everything_is_loaded(db):
    assert _count(db, OrgUnit) == len(T["pidrozdily"]) + 1  # + the organ itself
    assert _count(db, User) == len(T["korystuvachi"])
    assert _count(db, CorruptionRisk) == len(T["ryzyky"])
    assert _count(db, Measure) == len(T["zakhody"])
    assert _count(db, Evidence) == len(T["pidtverdzhennia"])
    kr01 = db.scalars(select(CorruptionRisk).where(CorruptionRisk.code == "KR01")).one()
    assert (kr01.probability, kr01.impact, kr01.level) == (3, 4, RiskLevel.CRITICAL)
    assert float(kr01.indicators[0].values[-1].value) == 31
    assert NOT_APPROVED == {"Z-26", "Z-38"}


def test_statuses_and_log(db):
    by_status = Counter(p.status for m in db.scalars(select(Measure)) for p in m.periods if p.updates)
    assert by_status[MeasureStatus.PARTIAL] == 2 and by_status[MeasureStatus.ON_REVIEW] == len(NOT_APPROVED)
    db.expire_all()
    ok, n, _ = audit.verify_chain(db)
    assert ok and n >= len(T["zhurnal_dii"])
    first = db.scalars(select(AuditLogEntry).order_by(AuditLogEntry.id)).first()
    assert first.at.year == 2025 and first.action == "import"
    assert _count(db, RiskFlag) > 0  # rules ran as of the cut date


def test_portal_report_matches_reference(db):
    program = db.scalars(select(Program)).one()
    rep = reports.build_nazk(program, DATA["meta"]["period"], uuid.uuid4())
    rows = {m.code: m for sec in rep.sections for m in sec.measures}
    sec_no = {r["kod"]: r["nomer"] for r in T["rozdily"]}
    code = {z["id"]: f"{sec_no[z['rozdil_kod']]}.{z['nomer_u_rozdili']}" for z in T["zakhody"]}

    def fmt(d):
        return f"{d[8:10]}.{d[5:7]}.{d[:4]}" if d else None

    mismatches = []
    for ref in T["zvit_portal_2026_h1"]:
        row = rows[code[ref["zakhid_id"]]]
        got = (row.planned_deadline, row.state, row.actual_deadline, row.result_or_reason)
        want = (ref["zaplanovanyi_strok"], ref["stan_vykonannia"], fmt(ref["faktychnyi_strok_vykonannia"]),
                ref["opys_rezultatu_abo_prychyn"])
        if got != want:
            mismatches.append((ref["zakhid_id"], got, want))
    assert {z for z, *_ in mismatches} == NOT_APPROVED, mismatches
