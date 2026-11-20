import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..auth import DbDep, Head, Staff, UserDep
from ..enums import RecStatus
from ..models import Recommendation
from ..schemas import domain as s
from ..services import control, scope
from ..services.dashboards import rec_out

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("", response_model=list[s.RecommendationOut])
def list_recs(db: DbDep, user: Staff, status: RecStatus | None = None):
    """Рекомендації за явними правилами; `basis` пояснює, на підставі яких даних."""
    q = select(Recommendation)
    if status:
        q = q.where(Recommendation.status == status)
    see = scope.of(db, user)
    recs = [r for r in db.scalars(q) if see.recommendation(r)]
    return [rec_out(r) for r in sorted(recs, key=lambda r: (r.basis.get("priority", 9), r.created_at))]


def _get(db, rec_id: uuid.UUID, user=None) -> Recommendation:
    r = db.get(Recommendation, rec_id)
    if not r:
        raise HTTPException(404, "Рекомендацію не знайдено")
    if user is not None:
        scope.of(db, user).ensure_recommendation(r)
    return r


@router.post("/{rec_id}/accept", response_model=s.RecommendationOut)
def accept(rec_id: uuid.UUID, data: s.AcceptIn, db: DbDep, user: Head):
    """Рішення ухвалює посадова особа: прийнята рекомендація має відповідального і строк."""
    r = control.decide_recommendation(db, user, _get(db, rec_id, user), True, data)
    db.commit()
    return rec_out(r)


@router.post("/{rec_id}/reject", response_model=s.RecommendationOut)
def reject(rec_id: uuid.UUID, data: s.RejectIn, db: DbDep, user: Head):
    r = control.decide_recommendation(db, user, _get(db, rec_id, user), False, data)
    db.commit()
    return rec_out(r)


@router.post("/{rec_id}/complete", response_model=s.RecommendationOut)
def complete(rec_id: uuid.UUID, data: s.RejectIn, db: DbDep, user: UserDep):
    """Прийняту рекомендацію позначає виконаною відповідальний або керівник (з коментарем)."""
    r = control.complete_recommendation(db, user, _get(db, rec_id, user), data.comment)
    db.commit()
    return rec_out(r)
