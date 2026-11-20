"""Ключ організаторів (kliuch/ochikuvani-sygnaly.csv): 29 навмисних кейсів Завдання 2.

Генератор набору перевіряє, що правила дають рівно ці сигнали, «не більше й не менше». Тут те саме для
системи: кожен кейс ключа ловить відповідне правило, і жодне правило з ключа не дає зайвих прапорців."""
import csv
import json
import os
from collections import defaultdict

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.db import Base
from app.enums import FlagStatus, FlagType, RiskLevel
from app.models import Program, RiskFlag
from app.services import coverage, dataset

KEY_FILE = dataset.DEFAULT_FILE.parent / "kliuch" / "ochikuvani-sygnaly.csv"
KEY = list(csv.DictReader(KEY_FILE.open(encoding="utf-8")))
DATA = json.loads(dataset.DEFAULT_FILE.read_text(encoding="utf-8"))
MEASURE_ID = {z["zmist"]: z["id"] for z in DATA["tablytsi"]["zakhody"]}
UNIT_ID = {u["nazva"]: u["id"] for u in DATA["tablytsi"]["pidrozdily"]}

# Код організаторів → тип прапорця системи (правило системи — у дужках).
RULE = {
    "RF1": {FlagType.OVERDUE},  # R1
    "RF2": {FlagType.NO_EVIDENCE},  # E1
    "RF3": {FlagType.FORMAL_CLOSURE, FlagType.WORSENING},  # F1 / F2
    "RF4": {FlagType.VAGUE_RESULT},  # R4
    "RF5": {FlagType.TARGET_MISSED},  # R5
    "RF6": {FlagType.REPEATED_POSTPONEMENT},  # R6a (захід); підрозділ — R6
    "RF7a": {FlagType.DATE_OUT_OF_PERIOD},  # R7a
    "RF7b": {FlagType.BACKDATED_EVIDENCE},  # R7b
    "RF7c": {FlagType.NO_EXPLANATION},  # R7c
    "RF7e": {FlagType.PREMATURE_DESCRIPTION},  # R7e
}


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    pg = os.environ.get("TEST_DATABASE_URL")
    if pg:
        url = pg.replace("postgresql://", "postgresql+psycopg://", 1)
        with create_engine(url).begin() as c:
            c.execute(text("DROP SCHEMA IF EXISTS keycases CASCADE; CREATE SCHEMA keycases"))
        engine = create_engine(url, connect_args={"options": "-csearch_path=keycases"})
    else:
        engine = create_engine(f"sqlite:///{tmp_path_factory.mktemp('key')}/key.db")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        assert dataset.load(s)  # завантажує набір і проганяє правила на дату зрізу
        yield s


@pytest.fixture(scope="module")
def found(db):
    """(код ключа, id обʼєкта) для всіх відкритих прапорців системи."""
    by_type = {t: code for code, types in RULE.items() for t in types}
    out: set[tuple[str, str]] = set()
    for f in db.scalars(select(RiskFlag).where(RiskFlag.status == FlagStatus.OPEN)):
        if f.type == FlagType.REPEATED_DELAY:  # підрозділ із ≥ 2 простроченими заходами
            out.add(("RF6", UNIT_ID[f.facts["orgUnit"]]))
        elif f.type in by_type:
            out.add((by_type[f.type], MEASURE_ID[f.measure.title]))
    program = db.scalar(select(Program))
    out |= {("RF7d", g.risk_code) for g in coverage.gaps(db, program)  # C1: високий чи критичний ризик без заходів
            if g.rule_code == "C1" and g.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)}
    return out


def test_key_has_29_cases():
    assert len(KEY) == 29


@pytest.mark.parametrize("case", KEY, ids=[f"{r['kod']}-{r['id']}" for r in KEY])
def test_every_key_case_is_caught(case, found):
    assert (case["kod"], case["id"]) in found, f"{case['kod']} {case['id']}: {case['poiasnennia']}"


def test_no_extra_signals_for_key_rules(found):
    expected = {(r["kod"], r["id"]) for r in KEY}
    extra = sorted(found - expected)
    assert not extra, f"зайві сигнали: {extra}"


def test_formal_closure_is_preliminary_while_lag_runs(db):
    """KR11 (ВЛК): заходи виконано, індикатор 25 → 26 при цілі 95 — F1 одразу, але з позначкою «попередньо»."""
    by_code = defaultdict(list)
    for f in db.scalars(select(RiskFlag).where(RiskFlag.type == FlagType.FORMAL_CLOSURE)):
        by_code[f.facts["risk"]].append(f)
    vlk = by_code["KR11"]
    assert len(vlk) == 2 and all(f.facts["preliminary"] and f.facts["lagMonths"] == 6 for f in vlk)
    assert all("попередній" in f.explanation and "25 → 26" in f.explanation for f in vlk)
    assert not db.scalars(select(RiskFlag).where(RiskFlag.type == FlagType.AWAITING_EFFECT)).first()
