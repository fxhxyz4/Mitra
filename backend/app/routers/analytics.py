import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from ..auth import Analyst, DbDep, Executor, require_roles
from ..config import today
from ..schemas.analytics import AnalyticsOverview
from ..enums import Role
from ..models import User
from ..schemas.performance import AnalyticsSummary, PeerReport, PerformanceReport
from ..services import analytics as svc
from ..services import performance
from ..services import exporters
from ..services.dashboards import resolve_program

router = APIRouter(prefix="/analytics", tags=["analytics"])

ProgramQ = Annotated[uuid.UUID | None, Query(alias="programId")]
Weeks = Annotated[int, Query(ge=1, le=104, description="Кількість тижнів у трендах")]


@router.get("/overview", response_model=AnalyticsOverview)
def overview(db: DbDep, _: Analyst, program_id: ProgramQ = None, weeks: Weeks = 12) -> AnalyticsOverview:
    """Аналітика програми: KPI, тренди статусів і Risk Flags, динаміка корупційних ризиків, розділи, підрозділи."""
    return svc.overview(db, resolve_program(db, program_id), today(), weeks)


@router.get("/export")
def export(
    db: DbDep, _: Analyst, program_id: ProgramQ = None, weeks: Weeks = 12,
    format: Literal["xlsx", "csv", "json"] = "xlsx",
):
    """Експорт аналітики: XLSX (аркуш на кожну таблицю), CSV (усі таблиці в одному файлі) або JSON."""
    o = svc.overview(db, resolve_program(db, program_id), today(), weeks)
    name = f"analytics-{o.as_of.isoformat()}"
    if format == "json":
        return Response(o.model_dump_json(by_alias=True, indent=2), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{name}.json"'})
    tables = svc.export_tables(o)
    if format == "csv":
        return Response(exporters.to_csv(tables), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})
    return Response(exporters.to_xlsx(tables), media_type=exporters.XLSX_TYPE,
                    headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'})


PeriodQ = Annotated[str | None, Query(pattern=r"^\d{4}-H[12]$", description="Півріччя YYYY-H1/H2; порожньо — усі")]
UnitQ = Annotated[uuid.UUID | None, Query(alias="orgUnitId")]
UserQ = Annotated[uuid.UUID | None, Query(alias="userId")]
Viewer = Annotated[User, Depends(require_roles(Role.HEAD, Role.ANALYST))]


def _scope(db, user: User) -> tuple[set[uuid.UUID] | None, str | None]:
    if user.role == Role.ANALYST:
        return None, None
    return performance.unit_subtree(db, user.org_unit_id), user.org_unit.name


def _report(db, user: User, program_id, period, org_unit_id, user_id):
    scope, name = _scope(db, user)
    if scope is not None:
        if org_unit_id and org_unit_id not in scope:
            raise HTTPException(403, "Аналітика доступна лише за ваш підрозділ")
        if user_id and ((u := db.get(User, user_id)) is None or u.org_unit_id not in scope):
            raise HTTPException(403, "Аналітика доступна лише за ваш підрозділ")
    return performance.report(db, resolve_program(db, program_id), today(), period, org_unit_id, user_id,
                              scope=scope, scope_name=name)


@router.get("/summary", response_model=AnalyticsSummary)
def summary(db: DbDep, user: Viewer, program_id: ProgramQ = None) -> AnalyticsSummary:
    """Основний режим: чи йде програма за планом — висновок за правилом, прогрес, розділи, найближчі строки,"""
    scope, name = _scope(db, user)
    return performance.summary(db, resolve_program(db, program_id), today(), scope, name)


@router.get("/performance", response_model=PerformanceReport)
def performance_report(
    db: DbDep, user: Viewer, program_id: ProgramQ = None, period: PeriodQ = None, org_unit_id: UnitQ = None,
    user_id: UserQ = None,
) -> PerformanceReport:
    """Розширений режим: підрозділи, виконавці, перевіряючі, реєстр завдань і хронологія подань, погоджень"""
    return _report(db, user, program_id, period, org_unit_id, user_id)


@router.get("/performance/export")
def performance_export(
    db: DbDep, user: Viewer, program_id: ProgramQ = None, period: PeriodQ = None, org_unit_id: UnitQ = None,
    user_id: UserQ = None,
):
    """Експорт розширеної аналітики в XLSX (аркуш на кожну таблицю) з тими самими фільтрами й обмеженнями."""
    r = _report(db, user, program_id, period, org_unit_id, user_id)
    name = f"analytics-{r.period or 'all'}-{r.as_of.isoformat()}.xlsx"
    return Response(exporters.to_xlsx(performance.export_tables(r)), media_type=exporters.XLSX_TYPE,
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/peers", response_model=PeerReport)
def peers(db: DbDep, user: Executor, program_id: ProgramQ = None) -> PeerReport:
    """Виконавцю: статистика колег, з якими він виконує спільні заходи, і власна для порівняння."""
    return performance.peers(db, resolve_program(db, program_id), today(), user)
