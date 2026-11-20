"""
    python -m scripts.eval_intake --split test             # модель з .env (Ollama або LLM_BASE_URL)
    python -m scripts.eval_intake --split test --no-model  # лише детерміновані правила
"""
import argparse
import asyncio
import json
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import llm
from app.auth import is_assigned, user_by_token
from app.config import settings
from app.db import Base, engine as app_engine
from app.models import Measure, OrgUnit, Program
from app.services import dataset, documents, intake, templates
from app.services.assistant import Assistant

from .generate_samples import DEFAULT_OUT


def ratio(hits: int, total: int) -> float:
    return round(hits / total, 3) if total else 0.0


async def eval_report(db: Session, case: dict[str, Any], data: bytes) -> dict[str, Any]:
    user = user_by_token(db, case["token"])
    assert user
    try:
        fields = templates.extract(templates.REPORT, documents.read(case["file"], data))
    except HTTPException as e:
        return {"status": e.status_code}
    pairs = [(m, m.periods[0]) for m in db.scalars(select(Measure)) if is_assigned(user, m)]
    ai = Assistant(db)
    warnings: list[str] = []
    candidates, chosen, _ = await intake.choose_measure(ai, fields, pairs, warnings)
    outcome, _ = await intake.decide_outcome(ai, fields, warnings)
    exp = case["expected"]
    if "foreignCode" in exp:
        return {"status": 200, "foreignRejected": not chosen or chosen[0].code != exp["foreignCode"]}
    return {
        "status": 200,
        "top1": bool(chosen) and chosen[0].code == exp["measureCode"],
        "top3": any(c.code == exp["measureCode"] for c in candidates),
        "outcome": outcome == exp["outcome"],
        "paraphrased": exp["paraphrased"],
        "modelUsed": ai.used,
    }


async def eval_card(db: Session, case: dict[str, Any], data: bytes) -> dict[str, Any]:
    user = user_by_token(db, case["token"])
    program = db.scalars(select(Program)).first()
    assert user and program
    draft = await intake.measure_draft(db, user, program, case["file"], data)
    v, exp = draft.measure, case["expected"]
    units = {u.id: u.name for u in db.scalars(select(OrgUnit))}
    section = next((s.number for s in program.sections if s.id == v.section_id), None)
    risk = next((m.risk.code for m in db.scalars(select(Measure)) if m.risk_id == v.risk_id and m.risk), None) \
        if v.risk_id else None
    return {
        "status": 200,
        "section": section == exp["section"],
        "code": v.code == exp["code"],
        "deadline": (v.planned_deadline.isoformat() if v.planned_deadline else None) == exp["deadline"],
        "isPermanent": v.is_permanent == exp["isPermanent"],
        "units": [units[a.org_unit_id] for a in v.assignments] == exp["units"],
        "risk": risk == exp["risk"],
        "modelUsed": draft.model_used,
    }


async def run(root: Path, split: str) -> dict[str, Any]:
    cases = [c for c in json.loads((root / "expected.json").read_text(encoding="utf-8"))
             if c["file"].startswith(f"{split}/")]
    engine = create_engine(f"sqlite:///{tempfile.mkdtemp()}/eval.db")
    Base.metadata.create_all(engine)
    Base.metadata.create_all(app_engine)  # llm.answer caches model replies in the app database
    results: dict[str, list[dict[str, Any]]] = {"A": [], "B": [], "negative": []}
    started = time.perf_counter()
    with Session(engine) as db:
        dataset.load(db)
        db.commit()
        for case in cases:
            data = (root / case["file"]).read_bytes()
            r = await (eval_report if case["template"] == "A" else eval_card)(db, case, data)
            if case["expect_status"] != 200 or "foreignCode" in case["expected"]:
                ok = r["status"] == case["expect_status"] and r.get("foreignRejected", True)
                results["negative"].append({"file": case["file"], "ok": ok})
            else:
                results[case["template"]].append({"file": case["file"], **r})
    a, b = results["A"], results["B"]
    paraphrased = [r for r in a if r["paraphrased"]]
    return {
        "split": split,
        "model": llm.chat_model() if settings.ai_enabled else None,
        "seconds": round(time.perf_counter() - started, 1),
        "A": {
            "n": len(a),
            "top1": ratio(sum(r["top1"] for r in a), len(a)),
            "top3": ratio(sum(r["top3"] for r in a), len(a)),
            "top1Paraphrased": ratio(sum(r["top1"] for r in paraphrased), len(paraphrased)),
            "outcome": ratio(sum(r["outcome"] for r in a), len(a)),
            "modelCalls": sum(r["modelUsed"] for r in a),
        },
        "B": {"n": len(b), **{k: ratio(sum(r[k] for r in b), len(b))
                              for k in ("section", "code", "deadline", "isPermanent", "units", "risk")}},
        "negative": {"n": len(results["negative"]), "ok": sum(r["ok"] for r in results["negative"])},
        "errors": [r["file"] for r in a if not r["top1"]] + [r["file"] for r in results["negative"] if not r["ok"]],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--split", choices=("dev", "test"), default="test")
    parser.add_argument("--no-model", action="store_true")
    args = parser.parse_args()
    # expected.json names users by plain demo tokens; the eval runs on its own throwaway database
    settings.demo_public_tokens = True
    if args.no_model:
        settings.ai_enabled = False
    print(json.dumps(asyncio.run(run(args.root, args.split)), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
