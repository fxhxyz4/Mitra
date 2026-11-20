import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..auth import is_assigned
from ..enums import Role
from ..models import (
    CorruptionRisk,
    Indicator,
    Measure,
    OrgUnit,
    Recommendation,
    User,
)
from .performance import unit_subtree


@dataclass(frozen=True)
class Scope:
    """Who sees which measures. EXECUTOR: assigned ones; HEAD of a non-root unit: that unit and below; others: all."""

    user: User
    units: frozenset[uuid.UUID] | None

    @property
    def whole_program(self) -> bool:
        return self.user.role != Role.EXECUTOR and self.units is None

    def measure(self, m: Measure) -> bool:
        if self.user.role == Role.EXECUTOR:
            return is_assigned(self.user, m)
        return self.units is None or any(a.org_unit_id in self.units for a in m.assignments)

    def measures(self, ms: Iterable[Measure]) -> list[Measure]:
        return [m for m in ms if self.measure(m)]

    def risk(self, r: CorruptionRisk) -> bool:
        return self.whole_program or any(self.measure(m) for m in r.measures)

    def indicator(self, i: Indicator) -> bool:
        return self.whole_program or (i.risk is not None and self.risk(i.risk))

    def recommendation(self, r: Recommendation) -> bool:
        return self.whole_program or (r.measure is not None and self.measure(r.measure))

    def unit(self, unit_id: uuid.UUID) -> bool:
        return self.units is None or unit_id in self.units

    def ensure_measure(self, m: Measure) -> None:
        if not self.measure(m):
            raise HTTPException(403, "Захід поза вашою зоною відповідальності")

    def ensure_recommendation(self, r: Recommendation) -> None:
        if not self.recommendation(r):
            raise HTTPException(403, "Рекомендація поза вашою зоною відповідальності")

    def ensure_risk(self, r: CorruptionRisk) -> None:
        if not self.risk(r):
            raise HTTPException(403, "Ризик поза вашою зоною відповідальності")


def of(db: Session, user: User) -> Scope:
    if user.role == Role.HEAD and user.org_unit_id:
        unit = db.get(OrgUnit, user.org_unit_id)
        if unit is not None and unit.parent_id is not None:
            return Scope(user, frozenset(unit_subtree(db, unit.id)))
    return Scope(user, None)


MeasureFilter = Callable[[Measure], bool]
