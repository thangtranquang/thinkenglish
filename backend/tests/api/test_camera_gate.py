"""TC-20.8: guests and gated guests cannot upload."""
from backend.tests.helpers.images import jpeg_bytes
from backend.tests.helpers.uploads import upload


def test_guest_upload_blocked(guest, db):
    r = upload(guest, jpeg_bytes())
    assert r.status_code == 403 and r.json() == {"error": "registration_required", "reason": "camera"}
    assert db.execute("SELECT COUNT(*) FROM image_assets WHERE first_uploaded_by IS NOT NULL").fetchone()[0] == 0


def test_gated_guest_blocked(gated):
    r = upload(gated, jpeg_bytes())
    assert r.status_code == 403 and r.json()["reason"] == "second_visit"
