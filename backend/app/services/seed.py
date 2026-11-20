from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, halfyear
from ..auth import demo_token, issue_token
from ..config import today as get_today
from ..enums import Decision, MeasureStatus, RiskLevel, Role
from ..models import Approval, CorruptionRisk, Evidence, Indicator, IndicatorValue, MeasurePeriod, OrgUnit, User
from ..schemas import domain as s
from . import control, measures as svc, storage



def _evidence(db: Session, user: User, p: MeasurePeriod, name: str) -> Evidence:
    body = f"Демонстраційний підтвердний документ «{name}» для періоду {p.period}.".encode()
    key, digest = storage.put_object(db, f"measure-periods/{p.id}", name, body)
    e = Evidence(measure_period=p, uploaded_by=user.id, file_name=name, content_type="text/plain",
                 size=len(body), object_key=key, sha256=digest, version=1)
    db.add(e)
    db.flush()
    audit.record(db, user, "evidence", e.id, "upload", None, {"fileName": name, "sha256": digest})
    return e


def _submit(db, user, p, text, files=(), reason=None):
    for f in files:
        _evidence(db, user, p, f)
    if p.status == MeasureStatus.PLANNED:
        svc._transition(db, user, p, MeasureStatus.IN_PROGRESS, "Розпочато виконання")
    p.result_description, p.non_execution_reason = text, reason
    svc._transition(db, user, p, MeasureStatus.ON_REVIEW, text or reason or "")


def _approve(db, coord, p, when: date, comment="Погоджено"):
    db.add(Approval(measure_period=p, reviewer_id=coord.id, decision=Decision.APPROVED, comment=comment))
    p.actual_date = when
    svc._transition(db, coord, p, MeasureStatus.DONE if p.result_description else MeasureStatus.NOT_DONE, comment)


def _return(db, coord, p, comment):
    db.add(Approval(measure_period=p, reviewer_id=coord.id, decision=Decision.RETURNED, comment=comment))
    svc._transition(db, coord, p, MeasureStatus.RETURNED, comment)


def seed(db: Session) -> bool:
    if db.scalars(select(User).limit(1)).first():
        return False
    t = get_today()
    p_start, p_end = date(t.year - 1, 1, 1), date(t.year, 12, 31)
    clamp = lambda d: min(max(d, p_start), p_end)  # noqa: E731

    root = OrgUnit(name="Орган сектору безпеки і оборони (демо)")
    db.add(root)
    db.flush()
    units = {k: OrgUnit(name=n, parent_id=root.id) for k, n in {
        "acp": "Сектор з питань запобігання та виявлення корупції",
        "proc": "Департамент державних закупівель",
        "hr": "Управління персоналу",
        "fin": "Фінансово-економічне управління",
        "com": "Управління комунікацій",
        "log": "Управління логістики та матеріального забезпечення",
        "legal": "Юридичне управління",
        "it": "Управління інформаційних технологій",
        "aud": "Відділ внутрішнього аудиту",
    }.items()}
    db.add_all(units.values())
    db.flush()
    users = {k: User(display_name=n, role=r, org_unit_id=units[u].id if u else root.id)
             for k, (n, r, u) in {
                 "coord": ("Координатор програми", Role.COORDINATOR, "acp"),
                 "head": ("Керівник органу", Role.HEAD, None),
                 "analyst": ("Аналітик", Role.ANALYST, "acp"),
                 "admin": ("Адміністратор системи", Role.ADMIN, "acp"),
                 "ex_proc": ("Виконавець — закупівлі", Role.EXECUTOR, "proc"),
                 "ex_hr": ("Виконавець — персонал", Role.EXECUTOR, "hr"),
                 "ex_fin": ("Виконавець — фінанси", Role.EXECUTOR, "fin"),
                 "ex_com": ("Виконавець — комунікації", Role.EXECUTOR, "com"),
                 "ex_log": ("Виконавець — логістика", Role.EXECUTOR, "log"),
                 "ex_legal": ("Виконавець — юридичне", Role.EXECUTOR, "legal"),
                 "ex_it": ("Виконавець — ІТ", Role.EXECUTOR, "it"),
                 "ex_aud": ("Виконавець — внутрішній аудит", Role.EXECUTOR, "aud"),
             }.items()}
    for k, u in users.items():
        issue_token(u, demo_token(k.replace("_", "-")))
    db.add_all(users.values())
    db.flush()
    coord = users["coord"]

    xy = {RiskLevel.LOW: (1, 2), RiskLevel.MEDIUM: (2, 2), RiskLevel.HIGH: (3, 3), RiskLevel.CRITICAL: (3, 4)}

    def risk(code, desc, level, ind_name, unit, base, target, values):
        x, y = xy[level]
        r = CorruptionRisk(code=code, description=desc, level=level, probability=x, impact=y)
        i = Indicator(risk=r, name=ind_name, unit=unit, baseline=Decimal(base), target=Decimal(target),
                      lag_months=1, source="внутрішній моніторинг (демо)")
        i.values = [IndicatorValue(value=Decimal(v), measured_at=d) for v, d in values]
        db.add_all([r, i])
        return r, i

    r1, i1 = risk("КР-01", "Дискреційні повноваження під час визначення постачальника без конкурентних процедур",
                  RiskLevel.HIGH, "Частка закупівель без конкурентних процедур", "%", 42, 20,
                  [(42, p_start), (35, t - timedelta(days=25))])
    r2, i2 = risk("КР-02", "Неврегульований конфлікт інтересів членів конкурсних комісій з добору персоналу",
                  RiskLevel.MEDIUM, "Виявлені неврегульовані конфлікти інтересів", "випадків", 7, 2,
                  [(7, p_start), (7, t - timedelta(days=30))])
    r3, i3 = risk("КР-03", "Відсутність ефективного контролю за витрачанням паливно-мастильних матеріалів",
                  RiskLevel.HIGH, "Розбіжність обліку ПММ", "%", 12, 3, [(12, p_start), (9, t - timedelta(days=40))])
    r4, i4 = risk("КР-04", "Непрозорий розподіл службового житла", RiskLevel.MEDIUM,
                  "Частка рішень про розподіл житла, оприлюднених у реєстрі", "%", 30, 100, [(30, p_start)])
    r5, i5 = risk("КР-05", "Завищення обсягів списання матеріальних цінностей на складах", RiskLevel.HIGH,
                  "Частка актів списання без інвентаризаційного підтвердження", "%", 25, 5,
                  [(25, p_start), (18, t - timedelta(days=20))])
    r6, i6 = risk("КР-06", "Укладення договорів без юридичної експертизи на корупційні ризики", RiskLevel.MEDIUM,
                  "Частка договорів, що пройшли антикорупційну експертизу", "%", 55, 100,
                  [(55, p_start), (78, t - timedelta(days=35))])
    r7, i7 = risk("КР-07", "Несанкціонований доступ до даних про закупівлі та кадрові рішення", RiskLevel.MEDIUM,
                  "Інциденти несанкціонованого доступу", "випадків", 9, 1, [(9, p_start), (4, t - timedelta(days=18))])
    r8, i8 = risk("КР-08", "Формальний характер внутрішніх аудитів у підрозділах з високими ризиками", RiskLevel.LOW,
                  "Частка аудитів із виявленими і усунутими порушеннями", "%", 20, 60, [(20, p_start)])
    i_train = Indicator(name="Посадові особи, що пройшли антикорупційне навчання", unit="осіб",
                        baseline=Decimal(0), target=Decimal(300),
                        values=[IndicatorValue(value=Decimal(180), measured_at=t - timedelta(days=15))])
    db.add(i_train)
    db.flush()

    program = svc.create_program(db, coord, s.ProgramIn(
        title=f"Антикорупційна програма (демо) на {p_start.year}–{p_end.year} роки",
        org_unit_id=root.id, period_start=p_start, period_end=p_end, has_restricted_info=False,
    ))
    sec = {x.number: x for x in program.sections}

    def A(unit, user=None):  # noqa: N802
        return [s.AssignmentIn(org_unit_id=units[unit].id, user_id=users[user].id if user else None, is_responsible=True)]

    def measure(n, code, title, deadline, assign, risk=None, ind=None, permanent=False, req=""):
        m = svc.create_measure(db, coord, s.MeasureIn(
            section_id=sec[n].id, code=code, title=title, planned_deadline=clamp(deadline), is_permanent=permanent,
            risk_id=risk.id if risk else None, indicator_text=ind.name if ind else "", required_evidence=req,
            assignments=assign,
        ))
        if ind is not None:  # кількісний індикатор виконання з історією значень
            m.indicator = ind
        return m

    m = {
        "1.1": measure(1, "1.1", "Затвердження порядку роботи з повідомленнями викривачів", t - timedelta(days=60),
                       A("acp"), req="Наказ про затвердження порядку"),
        "1.2": measure(1, "1.2", "Проведення оцінки корупційних ризиків у діяльності органу", p_end, A("acp"),
                       permanent=True, req="Звіт за результатами оцінки"),
        "1.3": measure(1, "1.3", "Оприлюднення інформації про стан виконання антикорупційної програми",
                       t + timedelta(days=5), A("com", "ex_com"), req="Посилання на публікацію"),
        "2.1": measure(2, "2.1", "Запровадження електронних конкурентних процедур для допорогових закупівель",
                       t - timedelta(days=20), A("proc", "ex_proc"), r1, i1, req="Наказ, звіт з Prozorro"),
        "2.2": measure(2, "2.2", "Запровадження декларування відсутності конфлікту інтересів членами конкурсних комісій",
                       t - timedelta(days=40), A("hr", "ex_hr"), r2, i2),
        "2.3": measure(2, "2.3", "Запровадження GPS-моніторингу витрачання паливно-мастильних матеріалів",
                       t - timedelta(days=10), A("fin", "ex_fin"), r3, i3, req="Акт введення системи в експлуатацію"),
        "2.4": measure(2, "2.4", "Щомісячна звірка даних обліку ПММ з даними моніторингу", t - timedelta(days=3),
                       A("fin", "ex_fin"), r3, i3, req="Протоколи звірок"),
        "2.5": measure(2, "2.5", "Оприлюднення рішень про розподіл службового житла у відкритому реєстрі",
                       t + timedelta(days=25), A("hr", "ex_hr"), r4, i4, req="Посилання на реєстр"),
        "2.6": measure(2, "2.6", "Аналіз цін за договорами закупівель порівняно з ринковими", t + timedelta(days=12),
                       A("proc", "ex_proc"), r1, i1, req="Аналітична довідка"),
        "3.1": measure(3, "3.1", "Навчання посадових осіб з питань запобігання корупції", p_end, A("hr"),
                       ind=i_train, permanent=True, req="Списки учасників, програма навчання"),
        "3.2": measure(3, "3.2", "Розміщення роз'яснень щодо конфлікту інтересів на офіційному вебсайті",
                       t + timedelta(days=40), A("com", "ex_com"), req="Посилання на публікацію"),
        "1.4": measure(1, "1.4", "Перегляд посадових інструкцій щодо обовʼязків із запобігання корупції",
                       t - timedelta(days=30), A("legal", "ex_legal"), req="Наказ про затвердження інструкцій"),
        "1.5": measure(1, "1.5", "Антикорупційна експертиза проєктів нормативно-правових актів органу", p_end,
                       A("legal", "ex_legal"), r6, i6, permanent=True, req="Висновки експертизи"),
        "1.6": measure(1, "1.6", "Внутрішній аудит виконання антикорупційної програми у підрозділах",
                       t + timedelta(days=50), A("aud", "ex_aud"), r8, i8, req="Звіт внутрішнього аудиту"),
        "2.7": measure(2, "2.7", "Щоквартальна інвентаризація матеріальних цінностей на складах",
                       t - timedelta(days=15), A("log", "ex_log"), r5, i5, req="Інвентаризаційні описи"),
        "2.8": measure(2, "2.8", "Запровадження електронного обліку руху матеріальних цінностей",
                       t + timedelta(days=35), A("log", "ex_log"), r5, i5, req="Акт введення в експлуатацію"),
        "2.9": measure(2, "2.9", "Обовʼязкова юридична експертиза договорів понад 200 тис. грн",
                       t - timedelta(days=50), A("legal", "ex_legal"), r6, i6, req="Реєстр експертиз"),
        "2.10": measure(2, "2.10", "Розмежування прав доступу до інформаційних систем закупівель і кадрів",
                        t - timedelta(days=5), A("it", "ex_it"), r7, i7, req="Матриця доступу, наказ"),
        "2.11": measure(2, "2.11", "Журналювання доступу до персональних даних та щомісячний аналіз журналів",
                        t + timedelta(days=18), A("it", "ex_it"), r7, i7, req="Звіти аналізу журналів"),
        "2.12": measure(2, "2.12", "Позапланові аудити підрозділів з високим рівнем корупційних ризиків",
                        t - timedelta(days=8), A("aud", "ex_aud"), r8, i8, req="Акти аудитів"),
        "3.3": measure(3, "3.3", "Тренінг з доброчесності для членів тендерного комітету", t + timedelta(days=8),
                       A("aud", "ex_aud"), ind=i_train, req="Програма тренінгу, список учасників"),
        "3.4": measure(3, "3.4", "Інформаційна кампанія про канали повідомлення про корупцію",
                       t + timedelta(days=60), A("com", "ex_com"), req="Матеріали кампанії, посилання"),
    }
    svc.approve_program(db, coord, program, t)

    for key, text, files in (
        ("1.2", "Проведено оцінку корупційних ризиків у 5 підрозділах, ідентифіковано 4 ризики (протокол № {n}).",
         ["Звіт оцінки ризиків.pdf"]),
        ("3.1", "Навчання пройшли {k} посадових осіб, проведено 6 тренінгів (наказ № {n}).", ["Список учасників.xlsx"]),
    ):
        ex = users["ex_hr"] if key == "3.1" else coord
        for i, p in enumerate(m[key].periods):
            if halfyear.end(p.period) < t:
                if p.status == MeasureStatus.PLANNED:
                    svc._transition(db, ex, p, MeasureStatus.IN_PROGRESS, "Розпочато виконання")
                _submit(db, ex, p, text.format(n=10 + i, k=60 + 30 * i), files)
                _approve(db, coord, p, halfyear.end(p.period) - timedelta(days=5))

    cur = lambda k: m[k].period_for(t)  # noqa: E731
    ex_proc, ex_hr, ex_fin = users["ex_proc"], users["ex_hr"], users["ex_fin"]

    # 1.1 — done properly
    _submit(db, coord, cur("1.1"), "Наказом № 214 затверджено порядок; за період опрацьовано 14 повідомлень викривачів.",
            ["Наказ 214.pdf"])
    _approve(db, coord, cur("1.1"), t - timedelta(days=62))
    # 2.1 — submitted, waiting for coordinator
    svc.add_progress(db, ex_proc, cur("2.1"), "Підготовлено проєкт наказу, проведено 3 пілотні закупівлі.")
    _submit(db, ex_proc, cur("2.1"),
            "Наказ № 87 від 02.09; 64% допорогових закупівель проведено через електронні процедури (було 42%).",
            ["Наказ 87.pdf", "Звіт Prozorro.xlsx"])
    # 2.2 — formal closure: vague description, no documents, indicator unchanged
    _submit(db, ex_hr, cur("2.2"), "Запроваджено декларування відсутності конфлікту інтересів членами конкурсних комісій")
    _approve(db, coord, cur("2.2"), t - timedelta(days=41))
    # 2.3 — overdue, in progress
    svc.add_progress(db, ex_fin, cur("2.3"), "Укладено договір на постачання 40 GPS-трекерів.")
    # 2.4 — returned with comment (overdue → repeated delay for the finance unit)
    _submit(db, ex_fin, cur("2.4"), "Звірку проведено.", ["Протокол звірки.pdf"])
    _return(db, coord, cur("2.4"), "Додайте кількість виявлених розбіжностей та протоколи за кожен місяць.")
    ex_log, ex_legal, ex_it, ex_aud = users["ex_log"], users["ex_legal"], users["ex_it"], users["ex_aud"]
    # 1.4 — done properly
    _submit(db, ex_legal, cur("1.4"), "Наказом № 156 оновлено 48 посадових інструкцій у 9 підрозділах.",
            ["Наказ 156.pdf", "Перелік інструкцій.xlsx"])
    _approve(db, coord, cur("1.4"), t - timedelta(days=32))
    # 1.5 — permanent: closed half-years done, current one in progress
    for p in m["1.5"].periods:
        if halfyear.end(p.period) < t:
            _submit(db, ex_legal, p, "Проведено експертизу 23 проєктів актів, усунуто 5 корупціогенних факторів.",
                    ["Висновки експертизи.pdf"])
            _approve(db, coord, p, halfyear.end(p.period) - timedelta(days=3))
    svc.add_progress(db, ex_legal, cur("1.5"), "Проведено експертизу 11 проєктів актів.")
    # 2.7 — overdue, executor reported nothing
    # 2.9 — not done, with a reason
    _submit(db, ex_legal, cur("2.9"), None, reason="Не затверджено штатну посаду юриста-експерта; "
            "експертиза проводилась вибірково (31 з 57 договорів).")
    _approve(db, coord, cur("2.9"), t - timedelta(days=48), "Погоджено як невиконаний; перенести на наступний період")
    # 2.10 — submitted, waiting for coordinator
    svc.add_progress(db, ex_it, cur("2.10"), "Розроблено матрицю доступу для 6 інформаційних систем.")
    _submit(db, ex_it, cur("2.10"), "Наказ № 301; переглянуто права 214 облікових записів, відкликано 37 надлишкових.",
            ["Наказ 301.pdf", "Матриця доступу.xlsx"])
    # 2.11 — in progress
    svc.add_progress(db, ex_it, cur("2.11"), "Увімкнено журналювання у 4 з 6 систем.")
    # 2.12 — returned with comment
    _submit(db, ex_aud, cur("2.12"), "Аудити проведено.", ["Акт аудиту.pdf"])
    _return(db, coord, cur("2.12"), "Зазначте, які підрозділи перевірено, кількість порушень і вжиті заходи.")
    # 3.3 — submitted, waiting for coordinator
    _submit(db, ex_aud, cur("3.3"), "Проведено тренінг для 18 членів тендерного комітету (протокол № 7).",
            ["Список учасників.xlsx"])
    # 2.8 — intermediate progress
    svc.add_progress(db, ex_log, cur("2.8"), "Обрано програмне рішення, триває налаштування довідників.")
    # 3.2 — intermediate progress
    svc.add_progress(db, users["ex_com"], cur("3.2"), "Підготовлено 2 з 5 роз'яснень, погоджуються з юристами.")

    db.commit()
    control.run_daily(db, t)
    return True
