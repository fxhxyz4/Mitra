from enum import StrEnum


class ProgramStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"


class MeasureStatus(StrEnum):
    DRAFT = "DRAFT"  # паспорт заповнює координатор
    PLANNED = "PLANNED"  # виконавець бачить захід
    IN_PROGRESS = "IN_PROGRESS"  # проміжні результати
    ON_REVIEW = "ON_REVIEW"  # виконавець не редагує
    RETURNED = "RETURNED"  # з обовʼязковим коментарем
    DONE = "DONE"  # лише додавання документів
    PARTIAL = "PARTIAL"  # частково виконано (стан Порталу «Частково виконано»)
    NOT_DONE = "NOT_DONE"  # з поясненням причин


FINAL_STATUSES = {MeasureStatus.DONE, MeasureStatus.PARTIAL, MeasureStatus.NOT_DONE}
EDITABLE_BY_EXECUTOR = {MeasureStatus.PLANNED, MeasureStatus.IN_PROGRESS, MeasureStatus.RETURNED}
STATUS_UA = {
    MeasureStatus.DRAFT: "Чернетка",
    MeasureStatus.PLANNED: "Заплановано",
    MeasureStatus.IN_PROGRESS: "В роботі",
    MeasureStatus.ON_REVIEW: "На перевірці",
    MeasureStatus.RETURNED: "Повернено",
    MeasureStatus.DONE: "Виконано",
    MeasureStatus.PARTIAL: "Частково виконано",
    MeasureStatus.NOT_DONE: "Не виконано",
}


class FlagType(StrEnum):

    OVERDUE = "OVERDUE"  # R1
    NO_EVIDENCE = "NO_EVIDENCE"  # E1 «Виконання не підтверджено»
    FORMAL_CLOSURE = "FORMAL_CLOSURE"  # F1
    WORSENING = "WORSENING"  # F2 «Погіршення попри виконання»
    AWAITING_EFFECT = "AWAITING_EFFECT"  # застаріле (F3): лаг тепер лише робить F1 попереднім
    VAGUE_RESULT = "VAGUE_RESULT"  # R4
    TARGET_MISSED = "TARGET_MISSED"  # R5 «Показник не досягнуто» (індикатор виконання нижче цілі)
    REPEATED_DELAY = "REPEATED_DELAY"  # R6
    REPEATED_POSTPONEMENT = "REPEATED_POSTPONEMENT"  # R6a строк переносили ≥ 2 разів
    DATE_OUT_OF_PERIOD = "DATE_OUT_OF_PERIOD"  # R7a фактична дата поза звітним періодом
    BACKDATED_EVIDENCE = "BACKDATED_EVIDENCE"  # R7b усі документи датовано пізніше за виконання
    NO_EXPLANATION = "NO_EXPLANATION"  # R7c «Не виконано» без пояснення причин
    PREMATURE_DESCRIPTION = "PREMATURE_DESCRIPTION"  # R7e опис заповнено, а строк не настав


class SignalType(StrEnum):

    TARGET_NOT_REACHED = "TARGET_NOT_REACHED"  # T1
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # D1
    BASELINE_CHANGED = "BASELINE_CHANGED"  # B1
    INCIDENT_FLOOR = "INCIDENT_FLOOR"  # P1 підстава переоцінити: інцидент
    REASSESS_UP = "REASSESS_UP"  # L+1 ризик погіршувався два квартали поспіль
    REASSESS_DOWN = "REASSESS_DOWN"  # L-1 ризик суттєво знизився два квартали поспіль
    PRIORITY_VIOLATION = "PRIORITY_VIOLATION"  # S1
    RISK_DISPLACEMENT = "RISK_DISPLACEMENT"  # X1
    EFFECT_NOT_CONFIRMED = "EFFECT_NOT_CONFIRMED"  # застаріле (G1): CE прибрано з моделі


class KriDirection(StrEnum):
    LOWER = "LOWER"  # менше — краще
    HIGHER = "HIGHER"  # більше — краще


class FlagStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class RecStatus(StrEnum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DONE = "DONE"


class InboxState(StrEnum):
    NEW = "NEW"
    LINKED = "LINKED"
    REJECTED = "REJECTED"


class OutboxState(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class Decision(StrEnum):
    APPROVED = "APPROVED"
    RETURNED = "RETURNED"


class Channel(StrEnum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"


class ReportType(StrEnum):
    NAZK = "NAZK"  # структура полів Порталу доброчесності
    PRINT = "PRINT"  # паперова форма для програм з обмеженим доступом
    INTERNAL = "INTERNAL"  # аналітична довідка


class Role(StrEnum):
    EXECUTOR = "EXECUTOR"
    COORDINATOR = "COORDINATOR"
    HEAD = "HEAD"
    ANALYST = "ANALYST"
    ADMIN = "ADMIN"


class RiskLevel(StrEnum):

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @classmethod
    def from_score(cls, score: int) -> "RiskLevel":
        return cls.CRITICAL if score >= 12 else cls.HIGH if score >= 6 else cls.MEDIUM if score >= 3 else cls.LOW


LEVEL_UA = {
    RiskLevel.LOW: "низький",
    RiskLevel.MEDIUM: "середній",
    RiskLevel.HIGH: "високий",
    RiskLevel.CRITICAL: "критичний",
}
REC_STATUS_UA = {
    RecStatus.PROPOSED: "Запропоновано",
    RecStatus.ACCEPTED: "Прийнято",
    RecStatus.REJECTED: "Відхилено",
    RecStatus.DONE: "Виконано",
}
FLAG_UA = {
    FlagType.OVERDUE: "Прострочено",
    FlagType.NO_EVIDENCE: "Виконання не підтверджено",
    FlagType.FORMAL_CLOSURE: "Формальне закриття",
    FlagType.WORSENING: "Погіршення попри виконання",
    FlagType.AWAITING_EFFECT: "Очікування ефекту",
    FlagType.VAGUE_RESULT: "Неінформативний опис",
    FlagType.TARGET_MISSED: "Показник не досягнуто",
    FlagType.REPEATED_DELAY: "Повторне порушення строків",
    FlagType.REPEATED_POSTPONEMENT: "Строк переносили двічі і більше",
    FlagType.DATE_OUT_OF_PERIOD: "Дата виконання поза звітним періодом",
    FlagType.BACKDATED_EVIDENCE: "Підтвердження «заднім числом»",
    FlagType.NO_EXPLANATION: "Не виконано без пояснення причин",
    FlagType.PREMATURE_DESCRIPTION: "Опис до настання строку",
}
SEVERITY_UA = {"INFO": "Інформація", "WARNING": "Увага", "CRITICAL": "Критично"}

NAZK_STATE = {
    MeasureStatus.DONE: "Виконано",
    MeasureStatus.PARTIAL: "Частково виконано",
    MeasureStatus.NOT_DONE: "Не виконано",
}
# Значення спадного списку Порталу (Розʼяснення НАЗК № 3, знімок екрана на с. 130).
NAZK_STATE_NOT_DUE = "Строк виконання заходу не настав"
NAZK_STATE_IN_PROGRESS = "Не виконано"

SECTION_TITLES = {
    1: "Заходи з реалізації засад загальної відомчої політики, виконання антикорупційної стратегії "
    "та державної антикорупційної програми",
    2: "Заходи з усунення корупційних ризиків",
    3: "Навчання та заходи з поширення антикорупційної інформації",
}
