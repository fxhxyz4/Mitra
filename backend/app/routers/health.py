from fastapi import APIRouter

from ..schemas.analytics import Health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health)
def health() -> Health:
    return Health()
