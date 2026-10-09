"""Image fixtures generated in code with Pillow."""
from __future__ import annotations

import io
import struct
import zlib

from PIL import Image


def _save(img: Image.Image, fmt: str, **kw) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, **kw)
    return buf.getvalue()


def jpeg_bytes(seed: int = 0, size: tuple[int, int] = (64, 48)) -> bytes:
    img = Image.new("RGB", size, ((seed * 37) % 256, (seed * 91) % 256, (seed * 53) % 256))
    img.putpixel((0, 0), (seed % 256, 255, 0))
    return _save(img, "JPEG", quality=90)


def png_bytes(size: tuple[int, int] = (32, 32)) -> bytes:
    return _save(Image.new("RGB", size, (10, 120, 200)), "PNG")


def webp_bytes(size: tuple[int, int] = (32, 32)) -> bytes:
    return _save(Image.new("RGB", size, (200, 120, 10)), "WEBP")


def jpeg_with_gps_exif(orientation: int = 1) -> bytes:
    img = Image.new("RGB", (64, 48), (120, 60, 30))
    exif = Image.Exif()
    exif[0x010F] = "TestCam"  # Make
    exif[0x0112] = orientation
    gps = exif.get_ifd(0x8825)
    gps[1] = "N"
    gps[2] = (10.0, 46.0, 30.0)
    gps[3] = "E"
    gps[4] = (106.0, 40.0, 12.0)
    return _save(img, "JPEG", exif=exif)


def gif_bytes() -> bytes:
    return _save(Image.new("P", (16, 16), 1), "GIF")


def html_as_jpg() -> bytes:
    return b"<!DOCTYPE html><html><body><script>alert(1)</script></body></html>"


def bomb_png(width: int = 30000, height: int = 30000) -> bytes:
    """A tiny PNG whose header declares a huge canvas (decompression bomb)."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    idat = zlib.compress(b"\x00" * 64)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def animated_webp() -> bytes:
    frames = [Image.new("RGB", (16, 16), c) for c in ((255, 0, 0), (0, 255, 0), (0, 0, 255))]
    return _save(frames[0], "WEBP", save_all=True, append_images=frames[1:], duration=100, loop=0)


def animated_png() -> bytes:
    frames = [Image.new("RGB", (16, 16), c) for c in ((255, 0, 0), (0, 255, 0))]
    return _save(frames[0], "PNG", save_all=True, append_images=frames[1:], duration=100)
