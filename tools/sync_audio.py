"""Copy the pre-generated mp3 files from docs/audio to frontend/audio (served at /audio/).

Run:  python tools/sync_audio.py
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "audio"
DST = ROOT / "frontend" / "audio"


def main() -> int:
    files = sorted(SRC.glob("*.mp3"))
    if not files:
        print(f"No mp3 files found in {SRC}", file=sys.stderr)
        return 1
    DST.mkdir(parents=True, exist_ok=True)
    copied = 0
    for f in files:
        target = DST / f.name
        if not target.exists() or target.stat().st_size != f.stat().st_size:
            shutil.copyfile(f, target)
            copied += 1
    print(f"{len(files)} files in {DST} ({copied} copied)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
