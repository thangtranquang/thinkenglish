"""Upload routes: POST /api/uploads (202), GET status, GET image (claim required)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse

from .. import deps
from ..config import Settings
from ..schemas.uploads import UploadOut, UploadStatusOut
from ..services import upload as svc
from ..services.imaging import ImagingError
from .cards import serve_image

router = APIRouter(prefix="/api")


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
        tasks.add_task(svc.run_analysis, settings, svc.provider_for(request.app.state), result.content_id)
    return svc.upload_out(user.conn, user.id, result)


@router.get("/uploads/{content_id}", response_model=UploadStatusOut)
def upload_status(content_id: UUID, user: deps.CurrentUser = Depends(deps.registered_user("camera")),
                  settings: Settings = Depends(deps.settings_of), clock=Depends(deps.clock_of)) -> dict:
    content = svc.claimed_content(user.conn, settings, clock, user.id, str(content_id))
    return svc.status_out(user.conn, user.id, content)


@router.get("/uploads/{content_id}/image")
def upload_image(content_id: UUID, user: deps.CurrentUser = Depends(deps.registered_user("camera")),
                 settings: Settings = Depends(deps.settings_of), clock=Depends(deps.clock_of)) -> FileResponse:
    content = svc.claimed_content(user.conn, settings, clock, user.id, str(content_id))
    return serve_image(settings, content["storage_path"])
