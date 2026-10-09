"""Upload image validation and cleaning. Framework-free; raises typed domain errors.

Suggested HTTP mapping (done by routers): ImageTooLarge -> 413 image_too_large,
UnsupportedImage -> 415 unsupported_image, InvalidImage -> 422 invalid_image.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError


class ImagingError(Exception):
    code = "image_error"


class ImageTooLarge(ImagingError):
    code = "image_too_large"  # 413


class UnsupportedImage(ImagingError):
    code = "unsupported_image"  # 415


class InvalidImage(ImagingError):
    code = "invalid_image"  # 422


@dataclass(frozen=True)
class CleanedImage:
    data: bytes
    format: str  # jpeg | png | webp
    width: int
    height: int
    raw_sha256: str
    clean_sha256: str


_PIL_FORMAT = {"jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}


def sniff(data: bytes) -> str | None:
    """Detect type from magic bytes only (claimed content-type/extension ignored)."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def clean(data: bytes, max_bytes: int, max_pixels: int) -> CleanedImage:
    if len(data) > max_bytes:
        raise ImageTooLarge("file too large")
    kind = sniff(data)
    if kind is None:
        raise UnsupportedImage("not a JPEG, PNG or WebP image")
    try:
        # Image.open reads only the header; check pixels BEFORE any decode.
        with Image.open(io.BytesIO(data)) as probe:
            w, h = probe.size
            if w * h > max_pixels:
                raise ImageTooLarge("too many pixels")
            if getattr(probe, "is_animated", False) or getattr(probe, "n_frames", 1) > 1:
                raise UnsupportedImage("animated images are not supported")
            probe.load()
            img = ImageOps.exif_transpose(probe)
            img.load()
    except ImagingError:
        raise
    except Image.DecompressionBombError:
        raise ImageTooLarge("too many pixels") from None
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, EOFError):
        raise InvalidImage("corrupt image") from None

    img = _normalise_mode(img, kind)
    out = io.BytesIO()
    kwargs: dict = {}
    if kind == "jpeg":
        kwargs = {"quality": 88, "optimize": True}
    elif kind == "webp":
        kwargs = {"quality": 88}
    # No exif/icc_profile/xmp passed, so none is written.
    img.save(out, format=_PIL_FORMAT[kind], **kwargs)
    cleaned = out.getvalue()
    return CleanedImage(
        data=cleaned, format=kind, width=img.width, height=img.height,
        raw_sha256=hashlib.sha256(data).hexdigest(),
        clean_sha256=hashlib.sha256(cleaned).hexdigest(),
    )


def _normalise_mode(img: Image.Image, kind: str) -> Image.Image:
    if kind == "jpeg":
        return img.convert("RGB") if img.mode != "RGB" else img
    if img.mode not in ("RGB", "RGBA"):
        has_alpha = "transparency" in img.info or img.mode in ("LA", "PA")
        return img.convert("RGBA" if has_alpha else "RGB")
    return img
