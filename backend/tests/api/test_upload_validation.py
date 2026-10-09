"""TC-22.1, 22.4, 22.6, 22.8, 22.9."""
import io
import time
import tracemalloc

from PIL import Image

from backend.tests.helpers import images
from backend.tests.helpers.uploads import ready_content, upload


def _nothing_stored(db, settings):
    n = db.execute("SELECT COUNT(*) FROM image_assets WHERE first_uploaded_by IS NOT NULL").fetchone()[0]
    assert n == 0
    assert not (settings.data_dir / "images").exists()


def test_exif_stripped(reg, db, settings):
    ready_content(reg, images.jpeg_with_gps_exif(orientation=6))
    rel = db.execute("SELECT storage_path FROM image_assets WHERE first_uploaded_by IS NOT NULL").fetchone()[0]
    raw = (settings.data_dir / rel).read_bytes()
    assert b"Exif\x00\x00" not in raw and b"TestCam" not in raw
    with Image.open(io.BytesIO(raw)) as im:
        assert len(im.getexif()) == 0


def test_gif_rejected(reg, db, settings):
    r = upload(reg, images.gif_bytes(), "a.gif", "image/gif")
    assert r.status_code == 415 and r.json()["error"] == "unsupported_image"
    _nothing_stored(db, settings)


def test_html_renamed_jpg_rejected(reg, db, settings):
    assert upload(reg, images.html_as_jpg()).status_code == 415
    _nothing_stored(db, settings)


def test_decompression_bomb_rejected_fast(reg, db, settings):
    data = images.bomb_png()
    tracemalloc.start()
    t = time.time()
    r = upload(reg, data, "b.png", "image/png")
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert r.status_code == 413 and r.json()["error"] == "image_too_large"
    assert time.time() - t < 2 and peak < 150 * 1024 * 1024
    _nothing_stored(db, settings)


def test_animated_rejected(reg, db, settings):
    assert upload(reg, images.animated_webp(), "a.webp", "image/webp").status_code == 415
    assert upload(reg, images.animated_png(), "a.png", "image/png").status_code == 415
    _nothing_stored(db, settings)
