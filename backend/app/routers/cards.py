"""Card routes: list/detail/image, create, save/unsave, share/unshare, delete, topics."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import FileResponse

from .. import deps
from ..config import Settings
from ..db import transaction
from ..errors import AppError
from ..schemas.cards import CardCreateIn, CardDetail, CardPage, TopicsOut
from ..services import cards as svc

router = APIRouter(prefix="/api")

_MEDIA = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def serve_image(settings: Settings, storage_path: str) -> FileResponse:
    base = Path(settings.data_dir).resolve()
    target = (base / storage_path).resolve()
    if base not in target.parents or not target.is_file():
        raise AppError(404, "not_found")
    return FileResponse(target, media_type=_MEDIA.get(target.suffix.lower(), "application/octet-stream"),
                        headers={"Cache-Control": "private, max-age=3600"})


@router.get("/cards", response_model=CardPage)
def list_cards(request_user: deps.CurrentUser = Depends(deps.not_gated_user),
               clock=Depends(deps.clock_of),
               scope: Literal["explore", "mine", "saved", "due"] = "explore",
               topic: Annotated[str | None, Query(max_length=80)] = None,
               cefr: Literal["A1", "A2", "B1", "B2"] | None = None,
               q: Annotated[str | None, Query(max_length=60)] = None,
               offset: Annotated[int, Query(ge=0)] = 0,
               limit: Annotated[int, Query(ge=1, le=50)] = 20) -> dict:
    return svc.list_page(request_user.conn, clock, request_user.id, scope, topic, cefr, q, offset, limit)


@router.get("/topics", response_model=TopicsOut)
def topics(user: deps.CurrentUser = Depends(deps.not_gated_user)) -> dict:
    return svc.topics(user.conn)


@router.post("/cards", response_model=CardDetail)
def create_card(body: CardCreateIn, response: Response,
                user: deps.CurrentUser = Depends(deps.registered_user("camera")),
                clock=Depends(deps.clock_of)) -> dict:
    with transaction(user.conn):
        out, created = svc.create_card(user.conn, clock, user.id, body)
    response.status_code = 201 if created else 200
    deps.mark_write(user)
    return out


@router.get("/cards/{card_id}", response_model=CardDetail)
def card_detail(card_id: UUID, user: deps.CurrentUser = Depends(deps.not_gated_user)) -> dict:
    return svc.get_detail(user.conn, user.id, str(card_id))


@router.get("/cards/{card_id}/image")
def card_image(card_id: UUID, request_settings: Settings = Depends(deps.settings_of),
               user: deps.CurrentUser = Depends(deps.not_gated_user)) -> FileResponse:
    row = svc.visible_card(user.conn, user.id, str(card_id))
    return serve_image(request_settings, row["storage_path"])


@router.post("/cards/{card_id}/save", status_code=204)
def save_card(card_id: UUID, user: deps.CurrentUser = Depends(deps.not_gated_user),
              clock=Depends(deps.clock_of)) -> Response:
    with transaction(user.conn):
        svc.save(user.conn, clock, user.id, str(card_id))
    deps.mark_write(user)
    return Response(status_code=204)


@router.delete("/cards/{card_id}/save", status_code=204)
def unsave_card(card_id: UUID, user: deps.CurrentUser = Depends(deps.not_gated_user)) -> Response:
    with transaction(user.conn):
        svc.unsave(user.conn, user.id, str(card_id))
    return Response(status_code=204)


@router.post("/cards/{card_id}/share", response_model=CardDetail)
def share_card(card_id: UUID, user: deps.CurrentUser = Depends(deps.registered_user("camera")),
               clock=Depends(deps.clock_of)) -> dict:
    with transaction(user.conn):
        return svc.share(user.conn, clock, user.id, str(card_id))


@router.delete("/cards/{card_id}/share", response_model=CardDetail)
def unshare_card(card_id: UUID, user: deps.CurrentUser = Depends(deps.registered_user("camera"))) -> dict:
    with transaction(user.conn):
        return svc.unshare(user.conn, user.id, str(card_id))


@router.delete("/cards/{card_id}", status_code=204)
def delete_card(card_id: UUID, user: deps.CurrentUser = Depends(deps.registered_user("camera"))) -> Response:
    with transaction(user.conn):
        svc.delete(user.conn, user.id, str(card_id))
    return Response(status_code=204)
