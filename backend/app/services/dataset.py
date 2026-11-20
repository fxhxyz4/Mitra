import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, halfyear
from ..auth import demo_token, issue_token
from ..enums import Decision, KriDirection, MeasureStatus, ProgramStatus, RiskLevel, Role
from ..models import (
    Approval,
    CorruptionRisk,
    DeadlineChange,
    Evidence,
    Indicator,
    IndicatorValue,
    Measure,
    MeasureAssignment,
    MeasurePeriod,
    OrgUnit,
    Program,
    ProgressUpdate,
    Section,
    User,
)
from . import control, storage

DATASET_DIR = Path(__file__).resolve().parent.parent / "datasets" / "zavdannia-2"
DEFAULT_FILE = DATASET_DIR / "nabir.json"

try:
    from zoneinfo import ZoneInfo

    _TZ = ZoneInfo("Europe/Kyiv")
except (ImportError, KeyError):  # no tz database on the host (ZoneInfoNotFoundError is a KeyError)
    _TZ = timezone(timedelta(hours=3))

ROLES = {"ADMIN": Role.ADMIN, "KOORD": Role.COORDINATOR, "VYK": Role.EXECUTOR, "KER": Role.HEAD, "ANAL": Role.ANALYST}
# Effect lag of a measure on the KRI (docs/model_ryzyku.md): procurement 3–6 months, property/land 6–12.
LAG_BY_PROCESS = {"Публічні закупівлі": 3, "Матеріально-технічне забезпечення": 3, "Управління майном": 6}
DEFAULT_LAG = 6
EVIDENCE_LABEL = "Підтвердження:"
INDICATOR_LABEL = "Індикатор виконання:"
LEVELS = {"низький": RiskLevel.LOW, "середній": RiskLevel.MEDIUM, "високий": RiskLevel.HIGH,
          "критичний": RiskLevel.CRITICAL}
DEMO_NAMES = {"U-001": "admin", "U-002": "coord", "U-003": "head-sector", "U-004": "head", "U-005": "analyst"}


def executor_name(unit_id: str) -> str:
    return f"ex-{unit_id.lower()}"  # ex-p01 … ex-p14


def executor_token(unit_id: str) -> str:
    return demo_token(executor_name(unit_id))


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=_TZ)


def _d(s: str) -> date | None:
    return date.fromisoformat(s) if s else None


def _num(v) -> Decimal | None:
    return None if v in ("", None) else Decimal(str(v))


def read(path: Path = DEFAULT_FILE) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cut_date(path: Path = DEFAULT_FILE) -> date:
    return date.fromisoformat(read(path)["meta"]["data_zrizu"])


def is_loaded(db: Session, path: Path = DEFAULT_FILE) -> bool:
    title = read(path)["tablytsi"]["prohrama"][0]["nazva"]
    return db.scalars(select(Program).where(Program.title == title)).first() is not None


def load(db: Session, path: Path = DEFAULT_FILE) -> bool:
    if db.scalars(select(User).limit(1)).first():
        return False
    data = read(path)
    T = data["tablytsi"]
    cut = date.fromisoformat(data["meta"]["data_zrizu"])
    prog = T["prohrama"][0]

    root = OrgUnit(name=prog["organ"])
    db.add(root)
    db.flush()
    units = {u["id"]: OrgUnit(name=u["nazva"], parent_id=root.id) for u in T["pidrozdily"]}
    db.add_all(units.values())
    db.flush()
    users: dict[str, User] = {}
    for u in T["korystuvachi"]:
        unit = units.get(u["pidrozdil_id"]) or root
        role = ROLES[u["rol"]]
        name = f"Виконавець — {unit.name}" if role == Role.EXECUTOR else u["posada"]
        users[u["id"]] = User(display_name=name, role=role, org_unit_id=unit.id)
        issue_token(users[u["id"]], demo_token(DEMO_NAMES.get(u["id"]) or executor_name(u["pidrozdil_id"])))
    db.add_all(users.values())
    db.flush()

    values_by_risk: dict[str, list[dict]] = {}
    for v in T["vymiriuvannia_indykatoriv"]:
        values_by_risk.setdefault(v["ryzyk_id"], []).append(v)
    risks: dict[str, CorruptionRisk] = {}
    risk_ind: dict[str, Indicator] = {}
    for r in T["ryzyky"]:
        level = LEVELS.get(r["riven"]) or RiskLevel.from_score(int(r["bal"]))
        owner = units.get(r["vlasnyk_pidrozdil_id"])
        risks[r["id"]] = cr = CorruptionRisk(code=r["id"], description=r["nazva"], level=level,
                                            probability=int(r["imovirnist_x"]), impact=int(r["naslidky_y"]),
                                            process=r["funktsiia_protses"], content=r["zmist"], sources=r["dzherela"],
                                            existing_controls=r["isnuiuchi_zakhody_kontroliu"],
                                            owner_unit_id=owner.id if owner else None)
        ind = Indicator(risk=cr, name=r["indykator_ryzyku"], unit=r["odynytsia"],
                        baseline=_num(r["indykator_bazove"]), target=_num(r["indykator_tsil"]),
                        direction=KriDirection.LOWER if r["napriam"] == "менше" else KriDirection.HIGHER,
                        weight=Decimal(1), lag_months=LAG_BY_PROCESS.get(r["funktsiia_protses"], DEFAULT_LAG),
                        source="; ".join(sorted({v["dzherelo"] for v in values_by_risk.get(r["id"], [])})),
                        independent=True, target_date=_d(r["data_tsili"]))
        ind.values = [IndicatorValue(value=_num(v["znachennia"]), measured_at=_d(v["data"]))
                      for v in sorted(values_by_risk.get(r["id"], []), key=lambda v: v["data"])]
        risk_ind[r["id"]] = ind
        db.add_all([cr, ind])
    db.flush()

    program = Program(org_unit_id=root.id,
                      title=prog["nazva"], period_start=_d(prog["period_pochatok"]),
                      period_end=_d(prog["period_kinets"]),
                      has_restricted_info=prog["mistyt_informatsiiu_z_obmezhenym_dostupom"] == "так",
                      status=ProgramStatus.APPROVED)
    db.add(program)
    db.flush()
    sections = {r["kod"]: Section(program_id=program.id, number=int(r["nomer"]), title=r["nazva_portal"])
                for r in T["rozdily"]}
    db.add_all(sections.values())
    db.flush()

    execution = {v["zakhid_id"]: v for v in T["vykonannia_2026_h1"]}
    log_by_object: dict[tuple[str, str], list[dict]] = {}
    for e in T["zhurnal_dii"]:
        log_by_object.setdefault((e["diia"], e["obiekt_id"]), []).append(e)
    coord = next(u for k, u in users.items() if u.role == Role.COORDINATOR)
    report_period = data["meta"]["period"]  # 2026-H1

    measures: dict[str, Measure] = {}
    data_period: dict[str, MeasurePeriod] = {}
    for z in T["zakhody"]:
        sec = sections[z["rozdil_kod"]]
        permanent = z["strok_typ"] != "data"  # «постійно» і «періодично»: фактичний строк — кінець півріччя
        deadline = _d(z["strok_data"]) or program.period_end
        hint = [z["potribni_pidtverdzhennia"] and f"{EVIDENCE_LABEL} {z['potribni_pidtverdzhennia']}."]
        # Індикатор виконання — окреме поле заходу (indicator_text / indicator), а не підказка про документи
        m = Measure(section_id=sec.id, code=f"{sec.number}.{z['nomer_u_rozdili']}", title=z["zmist"],
                    is_permanent=permanent, planned_deadline=deadline, deadline_text=z["strok_tekst"],
                    required_evidence=" ".join(h for h in hint if h), indicator_text=z["indykator_vykonannia"])
        if z["ryzyk_id"]:
            m.risk = risks[z["ryzyk_id"]]  # індикатор ризику належить ризику, а не заходу
        if z["indykator_tsil"] not in ("", None):  # кількісний індикатор виконання — власний індикатор заходу
            m.indicator = Indicator(name=z["indykator_vykonannia"], unit=z["indykator_odynytsia"],
                                    baseline=Decimal(0), target=_num(z["indykator_tsil"]), weight=Decimal(1),
                                    lag_months=0, source="звіт виконавця", independent=False)  # самозвіт
        m.assignments = [MeasureAssignment(org_unit_id=units[z["vidpovidalnyi_pidrozdil_id"]].id,
                                           user_id=users[z["vykonavets_korystuvach_id"]].id, is_responsible=True)]
        m.assignments += [MeasureAssignment(org_unit_id=units[u.strip()].id)
                          for u in z["spivvykonavtsi"].split(";") if u.strip()]
        wanted = program.half_years if permanent else [halfyear.of(deadline)]
        m.periods = [MeasurePeriod(period=hy, status=MeasureStatus.PLANNED) for hy in wanted]
        db.add(m)
        measures[z["id"]] = m
        target_period = report_period if permanent else halfyear.of(deadline)
        data_period[z["id"]] = next(p for p in m.periods if p.period == target_period)
    db.flush()

    facts: dict[str, IndicatorValue] = {}
    for zid, v in execution.items():
        m, p = measures[zid], data_period[zid]
        z = next(x for x in T["zakhody"] if x["id"] == zid)
        executor = users.get(v["vnis_korystuvach_id"]) or users[z["vykonavets_korystuvach_id"]]
        entered = _dt(v["data_vnesennia"]) if v["data_vnesennia"] else None
        approved = log_by_object.get(("погоджено координатором", zid))
        approved_at = _dt(approved[0]["chas"]) if approved else entered
        text, status = v["opys_rezultatu"] or None, v["status"]

        def step(frm, to, body, who=executor, at=entered, p=p):
            p.updates.append(ProgressUpdate(author_id=who.id, status_from=frm, status_to=to, body=body or "",
                                            created_at=at))

        if status in ("vykonano", "chastkovo"):
            p.result_description = text
            p.actual_date = _d(v["fakt_data"])
            step(MeasureStatus.PLANNED, MeasureStatus.ON_REVIEW, text)
            if v["pohodzheno_koordynatorom"] == "так":
                final = MeasureStatus.DONE if status == "vykonano" else MeasureStatus.PARTIAL
                p.approvals.append(Approval(reviewer_id=coord.id, decision=Decision.APPROVED,
                                            comment="Погоджено координатором", created_at=approved_at))
                step(MeasureStatus.ON_REVIEW, final, "Погоджено координатором", coord, approved_at)
                p.status = final
            else:
                p.status = MeasureStatus.ON_REVIEW  # чекає погодження координатора
        elif status == "ne_vykonano":
            p.non_execution_reason = text
            p.status = MeasureStatus.NOT_DONE
            step(MeasureStatus.PLANNED, MeasureStatus.NOT_DONE, text or "Не виконано")
        elif status == "v_roboti":
            if m.deadline_for(p) < cut:
                p.non_execution_reason = text  # строк минув: опис виконавця — пояснення причин
            else:
                p.result_description = text  # строк не настав: опис внесено передчасно (правило R7e)
            p.status = MeasureStatus.IN_PROGRESS
            step(MeasureStatus.PLANNED, MeasureStatus.IN_PROGRESS, text or "Розпочато виконання")
        # ne_rozpochato → stays PLANNED

        if v["indykator_fakt"] not in ("", None) and m.indicator is not None:  # факт індикатора виконання
            facts[zid] = iv = IndicatorValue(value=_num(v["indykator_fakt"]),
                                             measured_at=(entered or datetime.now(_TZ)).date())
            m.indicator.values.append(iv)

    evidence: dict[str, Evidence] = {}
    for e in T["pidtverdzhennia"]:
        p = data_period[e["zakhid_id"]]
        body = "\n".join(x for x in (
            f"{e['typ'].capitalize()}: {e['nazva']}", f"Дата документа: {e['data_dokumenta']}",
            e["posylannia"] and f"Посилання: {e['posylannia']}",
            f"Синтетичний підтвердний матеріал {e['id']} (контрольна сума в наборі: {e['sha256']}).",
        ) if x).encode()
        key, digest = storage.put_object(db, f"measure-periods/{p.id}", f"{e['id']}.txt", body)
        name = e["nazva"] if e["typ"] != "посилання" else f"Посилання: {e['nazva']}"
        evidence[e["id"]] = ev = Evidence(measure_period=p, uploaded_by=users[e["zavantazhyv_korystuvach_id"]].id,
                                          file_name=name, content_type="text/plain; charset=utf-8", doc_type=e["typ"],
                                          size=len(body), object_key=key, sha256=digest,
                                          uploaded_at=_dt(e["zavantazheno"]), document_date=_d(e["data_dokumenta"]))
        db.add(ev)
    db.flush()
    for zid, iv in facts.items():  # факт підтверджено першим документом періоду (IndicatorValue.source_evidence_id)
        docs = sorted(data_period[zid].evidence, key=lambda e: e.uploaded_at)
        if docs:
            iv.source_evidence_id = docs[0].id
    for x in T["perenesennia_strokiv"]:  # внутрішні рішення про перенесення строку
        decided_by = users.get(x["pohodyv_korystuvach_id"])
        db.add(DeadlineChange(measure=measures[x["zakhid_id"]], decided_on=_d(x["data_rishennia"]),
                              old_deadline=_d(x["staryi_strok"]), new_deadline=_d(x["novyi_strok"]),
                              reason=x["prychyna"], decided_by=decided_by.id if decided_by else None,
                              created_at=_dt(f"{x['data_rishennia']}T12:00")))
    db.flush()

    approved_at = min(_dt(e["chas"]) for e in T["zhurnal_dii"])
    for ind in [*risk_ind.values(), *(m.indicator for m in measures.values() if m.indicator is not None)]:
        ind.freeze_baseline(approved_at)

    postponements = {(x["zakhid_id"], x["staryi_strok"]): x for x in T["perenesennia_strokiv"]}
    for e in sorted(T["zhurnal_dii"], key=lambda x: (x["chas"], x["id"])):
        who, at, oid = users.get(e["korystuvach_id"]), _dt(e["chas"]), e["obiekt_id"]
        if e["obiekt"] == "pidtverdzhennia":
            ev = evidence[oid]
            audit.record(db, who, "evidence", ev.id, "upload", None,
                         {"fileName": ev.file_name, "sha256": ev.sha256, "source": e["id"]}, at=at)
        elif e["diia"].startswith("створено"):
            m = measures[oid]
            audit.record(db, who, "measure", m.id, "import", None, {"code": m.code, "title": m.title,
                                                                   "source": e["id"]}, at=at)
        elif e["diia"].startswith("змінено внутрішній строк"):
            m = measures[oid]
            reason = postponements.get((oid, e["stare_znachennia"]), {}).get("prychyna", "")
            audit.record(db, who, "measure", m.id, "postpone", {"internalDeadline": e["stare_znachennia"]},
                         {"internalDeadline": e["nove_znachennia"], "reason": reason, "source": e["id"]}, at=at)
        elif e["diia"].startswith("погоджено"):
            audit.record(db, who, "measure_period", data_period[oid].id, "approve", None,
                         {"decision": "APPROVED", "source": e["id"]}, at=at)
        else:  # внесено інформацію про виконання
            audit.record(db, who, "measure_period", data_period[oid].id, "submit",
                         {e["pole"] or "status": e["stare_znachennia"]},
                         {e["pole"] or "status": e["nove_znachennia"], "source": e["id"]}, at=at)
    audit.record(db, None, "program", program.id, "import", None,
                 {"source": data["meta"]["nazva"], "cutDate": cut.isoformat(), "measures": len(measures)})
    db.commit()
    control.run_daily(db, cut)
    return True
