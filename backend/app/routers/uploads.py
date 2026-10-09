"""Upload routes: POST /api/uploads (202), GET status, GET image (claim required)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Request, Response, UploadFile
from fastapi.responses import FileResponse

from .. import deps
from ..ai.provider import select_provider
from ..config import Settings
from ..errors import AppError
from ..repositories import cards as cards_repo
from ..repositories import content as content_repo
from ..schemas.uploads import UploadOut, UploadStatusOut
from ..services import cards as cards_svc
from ..services import upload as svc
from ..services.imaging import ImagingError
from .cards import serve_image

router = APIRouter(prefix="/api")


def _provider(request: Request):
    if request.app.state.provider is None:
        request.app.state.provider = select_provider(request.app.state.settings.gemini_api_key)
    return request.app.state.provider


def _claimed(user: deps.CurrentUser, settings: Settings, clock, content_id: UUID) -> dict:
    cid = str(content_id)
    if not content_repo.claim_exists(user.conn, user.id, cid):
        raise AppError(404, "not_found")
    return svc.current_status(user.conn, settings, clock, cid)


@router.post("/uploads", status_code=202, response_model=UploadOut)
def upload(request: Request, tasks: BackgroundTasks, file: UploadFile = File(...),
           user: deps.CurrentUser = Depends(deps.registered_user("camera")),
           settings: Settings = Depends(deps.settings_of), clock=Depends(deps.clock_of)) -> dict:
    try:
        data = svc.read_limited(file.file, settings.max_upload_bytes)
    except ImagingError as exc:
        raise svc.imaging_error(exc) from None
    result = svc.start_upload(user.conn, settings, clock, user.id, data)
    deps.mark_write(user)
    if result.run:
        tasks.add_task(svc.run_analysis, settings, _provider(request), result.content_id)
    return {"content_id": result.content_id, "status": result.status, "dedupe": result.dedupe,
            "ai_calls": result.ai_calls, "card_id": cards_repo.find_by_owner_content(user.conn, user.id,
                                                                                      result.content_id)}


@router.get("/uploads/{content_id}", response_model=UploadStatusOut)
def upload_status(content_id: UUID, user: deps.CurrentUser = Depends(deps.registered_user("camera")),
                  settings: Settings = Depends(deps.settings_of), clock=Depends(deps.clock_of)) -> dict:
    content = _claimed(user, settings, clock, content_id)
    out: dict = {"content_id": content["id"], "status": content["status"], "ai_calls": content["ai_calls"],
                 "retryable": content["status"] == "failed" and content["ai_calls"] < svc.MAX_AI_CALLS,
                 "card_id": cards_repo.find_by_owner_content(user.conn, user.id, content["id"])}
    if content["status"] == "ready":
        labels = content_repo.labels_for(user.conn, [content["id"]])[content["id"]]
        out.update(topic=content["topic"], cefr_level=content["cefr_level"],
                   image_url=f"/api/uploads/{content['id']}/image",
                   labels=[cards_svc._label_detail(lab) for lab in labels],
                   sentences=[cards_svc.sentence_out(s) for s in content_repo.sentences_for(user.conn, content["id"])])
    return out


@router.get("/uploads/{content_id}/image")
def upload_image(content_id: UUID, user: deps.CurrentUser = Depends(deps.registered_user("camera")),
                 settings: Settings = Depends(deps.settings_of), clock=Depends(deps.clock_of)) -> FileResponse:
    content = _claimed(user, settings, clock, content_id)
    return serve_image(settings, content["storage_path"])
