"""Upload pipeline: clean -> dedupe by raw sha -> claim -> background AI analysis (at most 6 calls/image)."""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from ..ai.schema import AnalysisResult
from ..clock import Clock, iso
from ..config import Settings
from ..db import connect, transaction
from ..errors import AppError
from ..repositories import content as repo
from ..seed import audio_name
from . import imaging, policy, storage

MAX_AI_CALLS = 6
ATTEMPTS_PER_RUN = 2  # first call + 1 automatic retry
AUDIO_DIR = Path(__file__).resolve().parents[3] / "frontend" / "audio"


@dataclass
class UploadResult:
    content_id: str
    status: str
    dedupe: str
    ai_calls: int
    run: bool


def read_limited(stream, limit: int) -> bytes:
    data = stream.read(limit + 1)
    if len(data) > limit:
        raise imaging.ImageTooLarge("file too large")
    return data


def imaging_error(exc: imaging.ImagingError) -> AppError:
    status = {"image_too_large": 413, "unsupported_image": 415}.get(exc.code, 422)
    return AppError(status, exc.code)


def start_upload(conn: sqlite3.Connection, settings: Settings, clock: Clock, user_id: str,
                 data: bytes) -> UploadResult:
    try:
        cleaned = imaging.clean(data, settings.max_upload_bytes, settings.max_pixels)
    except imaging.ImagingError as exc:
        raise imaging_error(exc) from None
    now = iso(clock.now())
    cutoff = iso(clock.now() - timedelta(seconds=settings.processing_stale_seconds))
    with transaction(conn):  # the write lock also serializes the (non-thread-safe) file write
        path = storage.write_file(settings.data_dir, cleaned.clean_sha256, cleaned.format, cleaned.data)
        rel = path.relative_to(Path(settings.data_dir).resolve()).as_posix()
        asset = repo.asset_by_source(conn, cleaned.raw_sha256)
        if asset is None:
            content_id = str(uuid.uuid4())
            repo.insert_asset(conn, str(uuid.uuid4()), cleaned.raw_sha256, cleaned.clean_sha256, rel,
                              cleaned.width, cleaned.height, user_id, now)
            repo.insert_content(conn, content_id, _last_asset_id(conn, cleaned.raw_sha256), now)
            status, dedupe, calls, run = "processing", "none", 0, True
        else:
            content = repo.content_by_asset(conn, asset["id"])
            content_id, calls = content["id"], content["ai_calls"]
            repo.expire_if_stale(conn, content_id, cutoff)
            status = repo.get_content(conn, content_id)["status"]
            if status == "ready":
                dedupe, run = "ready", False
            elif status == "processing":
                dedupe, run = "in_flight", False
            else:
                if calls >= MAX_AI_CALLS:
                    raise AppError(409, "analysis_unavailable")
                repo.restart_processing(conn, content_id, now)
                status, dedupe, run = "processing", "none", True
        repo.insert_claim(conn, user_id, content_id, now)
    return UploadResult(content_id, status, dedupe, calls, run)


def _last_asset_id(conn: sqlite3.Connection, source_sha: str) -> str:
    return repo.asset_by_source(conn, source_sha)["id"]


def current_status(conn: sqlite3.Connection, settings: Settings, clock: Clock, content_id: str) -> dict | None:
    """Content row with stale ``processing`` rows reported (and stored) as failed."""
    cutoff = iso(clock.now() - timedelta(seconds=settings.processing_stale_seconds))
    repo.expire_if_stale(conn, content_id, cutoff)
    return repo.get_content(conn, content_id)


def _audio_or_none(text: str) -> str | None:
    name = audio_name(text)
    return name if (AUDIO_DIR / name).exists() else None


def _store(conn: sqlite3.Connection, content_id: str, result: AnalysisResult, model: str) -> None:
    faces, personal = result.safety.has_identifiable_faces, result.safety.has_personal_info
    unsuitable = result.safety.has_nsfw_or_violence or not result.safety.is_suitable_for_students
    decision = policy.share_decision(faces, personal, result.safety.has_nsfw_or_violence,
                                     result.safety.is_suitable_for_students)
    with transaction(conn):
        repo.clear_children(conn, content_id)
        repo.save_result(conn, content_id, model=model, topic=result.topic, topic_tags=result.topic_tags,
                         cefr_level=result.cefr_level,
                         safety={"faces": faces, "personal_info": personal, "unsuitable": unsuitable},
                         moderation_status=decision.moderation_status)
        for i, lab in enumerate(result.labels):
            repo.insert_label(conn, str(uuid.uuid4()), content_id, i, lab.name, lab.ipa, lab.vi,
                              lab.accepted_answers, lab.cefr, lab.confidence, lab.x, lab.y,
                              _audio_or_none(lab.name))
        for i, d in enumerate(result.descriptions):
            repo.insert_sentence(conn, str(uuid.uuid4()), content_id, "description", i, d.en, d.vi,
                                 _audio_or_none(d.en))
        repo.insert_sentence(conn, str(uuid.uuid4()), content_id, "story", 0, result.story.en,
                             result.story.vi, _audio_or_none(result.story.en))


def run_analysis(settings: Settings, provider, content_id: str) -> None:
    """Background job (runs in a worker thread with its own connection)."""
    conn = connect(settings.db_path)
    try:
        content = repo.get_content(conn, content_id)
        if content is None:
            return
        image = (Path(settings.data_dir).resolve() / content["storage_path"]).read_bytes()
        error = "analysis_failed"
        for _ in range(ATTEMPTS_PER_RUN):
            with transaction(conn):
                calls = repo.get_content(conn, content_id)["ai_calls"]
                if calls >= MAX_AI_CALLS:
                    break
                repo.bump_ai_calls(conn, content_id)  # committed BEFORE the provider call
            try:
                result = provider.analyze(image)
            except Exception:  # provider failure of any kind counts as a failed attempt
                continue
            _store(conn, content_id, result, type(provider).__name__)
            return
        with transaction(conn):
            repo.mark_failed(conn, content_id, error)
    finally:
        conn.close()
