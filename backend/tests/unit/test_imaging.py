import hashlib
import io

import pytest
from PIL import Image

from backend.app.services import imaging
from backend.app.services.imaging import ImageTooLarge, InvalidImage, UnsupportedImage
from backend.tests.helpers import images as fx

MAX_BYTES = 5_000_000
MAX_PIXELS = 4_000_000


def clean(data):
    return imaging.clean(data, max_bytes=MAX_BYTES, max_pixels=MAX_PIXELS)


def test_sniff_table():
    assert imaging.sniff(fx.jpeg_bytes()) == "jpeg"
    assert imaging.sniff(fx.png_bytes()) == "png"
    assert imaging.sniff(fx.webp_bytes()) == "webp"
    rejected = [
        fx.gif_bytes(),
        b"BM" + b"\x00" * 40,
        b"II*\x00" + b"\x00" * 40,
        fx.html_as_jpg(),
        b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        b"%PDF-1.4\n" + b"\x00" * 20,
        b"",
    ]
    for blob in rejected:
        assert imaging.sniff(blob) is None


@pytest.mark.parametrize("blob", [fx.gif_bytes(), fx.html_as_jpg(), b"", b"%PDF-1.4 x"])
def test_clean_rejects_non_images(blob):
    with pytest.raises(UnsupportedImage):
        clean(blob)


def test_clean_ok_returns_metadata():
    raw = fx.jpeg_bytes(3)
    r = clean(raw)
    assert r.format == "jpeg"
    assert (r.width, r.height) == (64, 48)
    assert r.raw_sha256 == hashlib.sha256(raw).hexdigest()
    assert r.clean_sha256 == hashlib.sha256(r.data).hexdigest()
    assert Image.open(io.BytesIO(r.data)).size == (64, 48)


def test_gps_exif_stripped():
    raw = fx.jpeg_with_gps_exif()
    assert b"Exif" in raw
    r = clean(raw)
    assert b"Exif" not in r.data
    assert b"TestCam" not in r.data
    assert len(Image.open(io.BytesIO(r.data)).getexif()) == 0


def test_exif_orientation_applied():
    r = clean(fx.jpeg_with_gps_exif(orientation=6))
    assert (r.width, r.height) == (48, 64)


def test_bomb_rejected_before_decode():
    with pytest.raises(ImageTooLarge):
        clean(fx.bomb_png())


def test_byte_cap():
    with pytest.raises(ImageTooLarge):
        imaging.clean(fx.jpeg_bytes(), max_bytes=100, max_pixels=MAX_PIXELS)


def test_animated_rejected():
    with pytest.raises(UnsupportedImage):
        clean(fx.animated_webp())
    with pytest.raises(UnsupportedImage):
        clean(fx.animated_png())


def test_corrupt_rejected():
    raw = fx.jpeg_bytes()
    with pytest.raises(InvalidImage):
        clean(raw[:40])
