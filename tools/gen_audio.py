"""Tạo sẵn file âm thanh (mp3) cho prototype bằng giọng nam trẻ neural của Microsoft
(en-US-BrianNeural, nâng cao độ +20Hz cho giống giọng bé trai; Microsoft không có giọng bé trai thật).

Đọc mọi từ/câu tiếng Anh trong docs/reflex_app.html (L('...') và D('...')),
sinh docs/audio/<slug>-<hash>.mp3 nếu chưa có. Tên file phải khớp hàm audioName() trong HTML.

Chạy:  pip install edge-tts
       python tools/gen_audio.py [--voice en-US-BrianNeural] [--rate -8%] [--pitch +20Hz] [--force]

Ghi chú: edge-tts dùng dịch vụ đọc của Microsoft Edge (không chính thức), chỉ dùng để
dựng prototype. Bản thật dùng Azure AI Speech với cùng tên giọng (JennyNeural...),
sinh một lần lúc xử lý ảnh và lưu vào bảng audio_assets.
"""
import argparse, asyncio, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "docs" / "reflex_app.html"
OUT = ROOT / "docs" / "audio"


def djb2(s: str) -> str:
    h = 5381
    for ch in s:
        h = (h * 33 + ord(ch)) & 0xFFFFFFFF
    return format(h, "x")


def audio_name(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]
    return f"{slug}-{djb2(text)}.mp3"


def collect_texts() -> list[str]:
    src = HTML.read_text(encoding="utf-8")
    found = re.findall(r"\bL\('([^']+)'", src) + re.findall(r"\bD\('([^']+)'", src)
    seen, out = set(), []
    for t in found:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


async def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252
    ap =argparse.ArgumentParser()
    ap.add_argument("--voice", default="en-US-BrianNeural", help="giọng nam trẻ; Microsoft không có giọng bé trai")
    ap.add_argument("--rate", default="-8%", help="chậm hơn một chút để dễ shadowing")
    ap.add_argument("--pitch", default="+20Hz", help="nâng cao độ để nghe trẻ hơn, '+0Hz' để giữ nguyên")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    try:
        import edge_tts
    except ImportError:
        print("Thiếu thư viện: pip install edge-tts", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    texts = collect_texts()
    print(f"{len(texts)} đoạn, giọng {a.voice}, tốc độ {a.rate}, cao độ {a.pitch}")
    failed = 0
    for t in texts:
        path = OUT / audio_name(t)
        if path.exists() and not a.force:
            continue
        try:
            await edge_tts.Communicate(t, a.voice, rate=a.rate, pitch=a.pitch).save(str(path))
            print("  +", path.name)
        except Exception as e:  # mạng lỗi, dịch vụ từ chối...
            failed += 1
            print("  !", t, "->", e, file=sys.stderr)
    print("xong" if not failed else f"xong, {failed} đoạn lỗi (chạy lại để thử tiếp)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
