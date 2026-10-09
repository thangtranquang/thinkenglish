"""Content-addressed file storage confined under DATA_DIR."""
from __future__ import annotations

import os
import re
from pathlib import Path

_SHA = re.compile(r"^[0-9a-f]{64}$")
_EXT = {"jpeg": "jpg", "png": "png", "webp": "webp"}


class StorageError(Exception):
    pass


class UnsafePath(StorageError):
    pass


def path_for(data_dir: Path | str, sha256: str, fmt: str) -> Path:
    """data_dir/images/ab/cd/<sha>.<ext>; rejects anything that is not a hex digest."""
    if not _SHA.match(sha256) or fmt not in _EXT:
        raise UnsafePath("invalid storage key")
    base = Path(data_dir).resolve()
    target = (base / "images" / sha256[:2] / sha256[2:4] / f"{sha256}.{_EXT[fmt]}").resolve()
    if base not in target.parents:
        raise UnsafePath("path escapes data dir")
    return target


def write_file(data_dir: Path | str, sha256: str, fmt: str, data: bytes) -> Path:
    target = path_for(data_dir, sha256, fmt)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return target
    tmp = target.with_name(target.name + f".{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, target)
    return target


def delete_file(data_dir: Path | str, sha256: str, fmt: str) -> bool:
    target = path_for(data_dir, sha256, fmt)
    try:
        target.unlink()
        return True
    except FileNotFoundError:
        return False
