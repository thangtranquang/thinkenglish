"""GET /api/me (minimal for now; the profile slice extends MeOut)."""
from fastapi import APIRouter, Depends

from .. import deps
from ..schemas.session import MeOut

router = APIRouter(prefix="/api")


@router.get("/me", response_model=MeOut)
def me(user: deps.CurrentUser = Depends(deps.current_user)) -> MeOut:
    return MeOut.from_row(user.row)
