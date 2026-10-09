"""POST /api/attempts and the reflex session endpoints."""
from fastapi import APIRouter, Depends, Request, Response

from .. import deps
from ..schemas.practice import AttemptIn, AttemptOut, ReflexCompleteOut, ReflexStartIn, ReflexStartOut
from ..services import practice as service

router = APIRouter(prefix="/api")


@router.post("/attempts", response_model=AttemptOut, status_code=201)
def post_attempt(data: AttemptIn, request: Request, response: Response,
                 user: deps.CurrentUser = Depends(deps.not_gated_user)) -> AttemptOut:
    out, created = service.record_attempt(user.conn, deps.clock_of(request), user.id, data)
    if created:
        deps.mark_write(user)
    else:
        response.status_code = 200
    return out


@router.post("/reflex/sessions", response_model=ReflexStartOut, status_code=201)
def start_reflex(data: ReflexStartIn, request: Request,
                 user: deps.CurrentUser = Depends(deps.not_gated_user)) -> dict:
    out = service.start_reflex(user.conn, deps.clock_of(request), user.row, data.level)
    deps.mark_write(user)
    return out


@router.post("/reflex/sessions/{session_id}/complete", response_model=ReflexCompleteOut)
def complete_reflex(session_id: str, request: Request,
                    user: deps.CurrentUser = Depends(deps.not_gated_user)) -> dict:
    return service.complete_reflex(user.conn, deps.clock_of(request), user.row, session_id)
