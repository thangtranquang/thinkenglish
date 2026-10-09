"""Draw the flat-style illustrated seed scenes (Pillow only, deterministic, no network).

Writes backend/seed_assets/<seed_key>.jpg (960x640) and, because every labelled object is drawn at a
known position, also rewrites x, y and box of each label in backend/app/seed_data.json from the drawn
bounding box, so the marker always sits on the object.

Run:  python tools/make_seed_images.py
"""
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backend" / "seed_assets"
DATA = ROOT / "backend" / "app" / "seed_data.json"
W, H, S = 960, 640, 2  # output size and supersampling factor (anti-aliasing)

# soft palette
INK = (70, 60, 70)
WHITE = (250, 250, 248)
CREAM = (252, 244, 226)
WOOD = (205, 160, 110)
WOOD_D = (170, 125, 80)
WOOD_L = (226, 189, 140)
RED = (226, 96, 90)
ORANGE = (242, 160, 70)
YELLOW = (250, 211, 90)
GREEN = (120, 190, 120)
GREEN_D = (80, 150, 95)
BLUE = (100, 160, 215)
BLUE_L = (170, 208, 235)
NAVY = (60, 80, 125)
GREY = (160, 164, 172)
GREY_D = (105, 108, 118)
GREY_L = (214, 217, 222)
BROWN = (110, 75, 55)
PINK = (240, 170, 175)
SKIN = (240, 196, 160)


class Canvas:
    """Drawing surface using 960x640 units; everything is scaled by S internally."""

    def __init__(self, bg=CREAM):
        self.im = Image.new("RGB", (W * S, H * S), bg)
        self.d = ImageDraw.Draw(self.im, "RGBA")
        self.marks: dict[str, tuple[tuple, tuple | None]] = {}

    def _b(self, b):
        return [v * S for v in b]

    def _p(self, pts):
        return [(x * S, y * S) for x, y in pts]

    def rect(self, b, fill, r=0, outline=None, w=2):
        if r:
            self.d.rounded_rectangle(self._b(b), r * S, fill=fill, outline=outline, width=int(w * S))
        else:
            self.d.rectangle(self._b(b), fill=fill, outline=outline, width=int(w * S))

    def ell(self, b, fill, outline=None, w=2):
        self.d.ellipse(self._b(b), fill=fill, outline=outline, width=int(w * S))

    def pie(self, b, a0, a1, fill):
        self.d.pieslice(self._b(b), a0, a1, fill=fill)

    def poly(self, pts, fill):
        self.d.polygon(self._p(pts), fill=fill)

    def line(self, pts, fill, w=4):
        self.d.line(self._p(pts), fill=fill, width=int(w * S), joint="curve")

    def text(self, xy, s, size, fill, anchor="mm"):
        font = ImageFont.load_default(size=int(size * S))
        self.d.text((xy[0] * S, xy[1] * S), s, fill=fill, font=font, anchor=anchor)

    def shadow(self, cx, cy, rx, ry=9):
        self.ell((cx - rx, cy - ry, cx + rx, cy + ry), (60, 40, 30, 45))

    def vgradient(self, b, top, bottom):
        x1, y1, x2, y2 = b
        for i in range(int(y2 - y1)):
            t = i / max(1, y2 - y1 - 1)
            col = tuple(int(top[k] + (bottom[k] - top[k]) * t) for k in range(3))
            self.rect((x1, y1 + i, x2, y1 + i + 1.2), col)

    def mark(self, word, b, centre=None):
        """Register a label's bounding box; the marker goes to its centre unless `centre` is given."""
        self.marks[word] = (tuple(b), centre)

    def save(self, key):
        img = self.im.resize((W, H), Image.LANCZOS)
        OUT.mkdir(parents=True, exist_ok=True)
        img.save(OUT / f"{key}.jpg", "JPEG", quality=85, optimize=True, progressive=False)


# ---------- reusable objects (each returns its bounding box in units) ----------

def room(c, wall, floor, horizon=400, base=None):
    c.rect((0, 0, W, horizon), wall)
    c.rect((0, horizon, W, H), floor)
    c.rect((0, horizon - 8, W, horizon + 6), base or tuple(max(0, v - 25) for v in floor))


def cup(c, x, y, w, h, col, coffee=(110, 70, 50)):
    """Coffee cup whose body spans (x, y)-(x+w, y+h), with a handle on the right and steam."""
    c.ell((x + w - 8, y + h * 0.18, x + w + w * 0.38, y + h * 0.68), None, outline=col, w=max(4, w * 0.11))
    c.rect((x, y, x + w, y + h / 2), col)
    c.rect((x, y, x + w, y + h), col, r=h * 0.45)
    ry = w * 0.13
    c.ell((x - 2, y - ry, x + w + 2, y + ry), tuple(min(255, v + 18) for v in col))
    c.ell((x + 7, y - ry + 5, x + w - 7, y + ry - 4), coffee)
    for sx in (x + w * 0.3, x + w * 0.55, x + w * 0.78):
        c.line([(sx, y - ry - 8), (sx - 8, y - ry - 24), (sx + 6, y - ry - 40)], (190, 190, 200, 170), 5)
    return (x - 2, y - ry - 42, x + w + w * 0.4, y + h)


def moto(c, ox, oy, k, col):
    """Side-view motorbike; local design space is about 200x125, scaled by k."""
    def P(x, y):
        return (ox + x * k, oy + y * k)

    def B(x1, y1, x2, y2):
        return (*P(x1, y1), *P(x2, y2))

    c.shadow(*P(102, 122), 100 * k, 7 * k)
    c.line([P(150, 38), P(168, 90)], GREY_D, 7 * k)  # front fork
    c.line([P(136, 26), P(160, 20)], INK, 6 * k)  # handlebar
    c.line([P(145, 26), P(152, 40)], INK, 5 * k)
    c.poly([P(52, 52), P(120, 38), P(142, 54), P(128, 82), P(60, 84)], col)  # body
    c.poly([P(14, 52), P(56, 44), P(62, 72), P(22, 70)], col)  # tail
    c.rect(B(44, 34, 108, 48), (60, 55, 65), r=8 * k)  # seat
    c.rect(B(70, 70, 122, 92), GREY_D, r=6 * k)  # engine
    for cx in (40, 166):
        x, y = P(cx, 92)
        r = 30 * k
        c.ell((x - r, y - r, x + r, y + r), (50, 48, 58))
        c.ell((x - r * 0.58, y - r * 0.58, x + r * 0.58, y + r * 0.58), (205, 208, 215))
        c.ell((x - r * 0.2, y - r * 0.2, x + r * 0.2, y + r * 0.2), (90, 92, 100))
    c.ell(B(148, 36, 166, 52), YELLOW, outline=INK, w=1.5)  # headlight
    c.rect(B(8, 52, 20, 62), RED, r=3 * k)  # tail light
    return B(8, 18, 197, 122)


def person(c, cx, ground, k, shirt, pants, hair=(60, 45, 40)):
    def P(x, y):
        return (cx + x * k, ground + y * k)

    c.shadow(cx, ground, 38 * k, 7 * k)
    for dx in (-13, 13):  # legs + shoes
        c.rect((*P(dx - 9, -150), *P(dx + 9, -12)), pants, r=6 * k)
        c.rect((*P(dx - 12 + (6 if dx > 0 else -4), -14), *P(dx + 14 + (6 if dx > 0 else -4), 0)), INK, r=6 * k)
    c.rect((*P(-30, -250), *P(30, -140)), shirt, r=16 * k)  # torso
    c.rect((*P(-46, -245), *P(-28, -150)), shirt, r=9 * k)  # arms
    c.rect((*P(28, -245), *P(46, -150)), shirt, r=9 * k)
    c.ell((*P(-46, -158), *P(-27, -138)), SKIN)
    c.ell((*P(27, -158), *P(46, -138)), SKIN)
    c.rect((*P(-8, -268), *P(8, -246)), SKIN)  # neck
    c.ell((*P(-27, -318), *P(27, -262)), SKIN)  # head
    c.pie((*P(-29, -324), *P(29, -266)), 180, 360, hair)  # hair
    c.ell((*P(-11, -296), *P(-6, -290)), INK)
    c.ell((*P(7, -296), *P(12, -290)), INK)
    return (*P(-48, -326), *P(48, 0))


def helmet(c, cx, cy, r, col):
    c.shadow(cx, cy + r * 0.62, r * 0.9, r * 0.12)
    c.pie((cx - r, cy - r, cx + r, cy + r * 0.55), 180, 360, col)
    c.rect((cx - r, cy - r * 0.08, cx + r, cy + r * 0.6), col, r=r * 0.2)
    c.rect((cx - r * 0.1, cy - r * 0.95, cx + r * 0.1, cy - r * 0.08), WHITE)  # stripe
    c.rect((cx - r * 0.15, cy - r * 0.02, cx + r * 0.95, cy + r * 0.42), (50, 60, 85), r=r * 0.2)  # visor
    c.line([(cx - r * 0.9, cy + r * 0.64), (cx + r * 0.9, cy + r * 0.64)], tuple(max(0, v - 40) for v in col), 5)
    return (cx - r, cy - r, cx + r, cy + r * 0.66)


def key(c, cx, cy, k, col=(230, 190, 70)):
    """Old-style key lying flat: ring on the left, shaft + teeth on the right (about 190x70 * k)."""
    c.shadow(cx, cy + 36 * k, 90 * k, 6 * k)
    c.ell((cx - 95 * k, cy - 35 * k, cx - 25 * k, cy + 35 * k), col, outline=(190, 150, 40), w=2)
    c.ell((cx - 74 * k, cy - 14 * k, cx - 46 * k, cy + 14 * k), (205, 210, 215))
    c.rect((cx - 30 * k, cy - 9 * k, cx + 95 * k, cy + 9 * k), col)
    c.rect((cx + 60 * k, cy + 4 * k, cx + 74 * k, cy + 30 * k), col)
    c.rect((cx + 80 * k, cy + 4 * k, cx + 95 * k, cy + 24 * k), col)
    return (cx - 95 * k, cy - 35 * k, cx + 95 * k, cy + 30 * k)


def bowl(c, cx, cy, rx, h, col, content=None, steam=False):
    """Front-view bowl; rim ellipse centred on (cx, cy)."""
    c.shadow(cx, cy + h + 4, rx * 0.9, 9)
    c.pie((cx - rx, cy - h, cx + rx, cy + h), 0, 180, col)
    c.ell((cx - rx * 0.4, cy + h - 4, cx + rx * 0.4, cy + h + 6), tuple(max(0, v - 30) for v in col))
    c.ell((cx - rx, cy - 18, cx + rx, cy + 18), tuple(min(255, v + 15) for v in col))
    if content:
        c.ell((cx - rx + 8, cy - 14, cx + rx - 8, cy + 14), content)
        c.ell((cx - rx * 0.6, cy - 42, cx + rx * 0.6, cy + 8), content)
    if steam:
        for sx in (cx - rx * 0.4, cx, cx + rx * 0.4):
            c.line([(sx, cy - 50), (sx - 9, cy - 74), (sx + 7, cy - 98)], (200, 200, 210, 160), 6)
    return (cx - rx, cy - (98 if steam else 44), cx + rx, cy + h + 6)


def lamp(c, cx, base_y, k, col, glow=True):
    """Table lamp with cone shade; returns bbox."""
    c.ell((cx - 28 * k, base_y - 12 * k, cx + 28 * k, base_y + 4 * k), (95, 90, 100))
    c.rect((cx - 5 * k, base_y - 110 * k, cx + 5 * k, base_y - 8 * k), (125, 120, 130))
    top = base_y - 175 * k
    if glow:
        c.ell((cx - 95 * k, top + 40 * k, cx + 95 * k, top + 190 * k), (255, 236, 150, 70))
    c.poly([(cx - 22 * k, top), (cx + 22 * k, top), (cx + 52 * k, top + 66 * k), (cx - 52 * k, top + 66 * k)], col)
    c.ell((cx - 52 * k, top + 60 * k, cx + 52 * k, top + 74 * k), tuple(max(0, v - 30) for v in col))
    return (cx - 56 * k, top, cx + 56 * k, base_y + 4 * k)


# ---------- scenes ----------

def scene_c1():
    c = Canvas()
    c.vgradient((0, 0, W, 400), (255, 233, 190), (250, 215, 160))
    for i in range(0, W, 96):  # awning stripes
        c.rect((i, 40, i + 48, 120), RED)
        c.rect((i + 48, 40, i + 96, 120), WHITE)
    c.rect((0, 112, W, 130), (200, 80, 75))
    c.rect((60, 170, 380, 380), BLUE_L, r=10, outline=(240, 240, 240), w=6)  # shop window
    c.text((220, 210), "CAFE", 40, NAVY)
    c.rect((0, 400, W, 545), (226, 216, 198))  # pavement
    c.rect((0, 545, W, H), (140, 142, 152))  # road
    for x in range(30, W, 140):
        c.rect((x, 600, x + 70, 612), (235, 235, 230))
    c.shadow(255, 515, 120, 10)  # table
    c.rect((246, 440, 264, 515), GREY_D)
    c.ell((205, 505, 305, 525), GREY_D)
    c.ell((115, 405, 395, 465), (170, 110, 80))
    c.ell((115, 395, 395, 450), (200, 140, 100))
    box = cup(c, 215, 350, 90, 62, WHITE)
    c.mark("coffee cup", (box[0], box[1] + 25, box[2], box[3]))
    c.mark("motorcycle", moto(c, 450, 330, 1.7, RED))
    c.mark("pedestrian", person(c, 880, 545, 1.0, BLUE, NAVY))
    return c


def scene_c2():
    c = Canvas()
    room(c, (232, 238, 246), (214, 170, 120), 380, WOOD_D)
    c.rect((0, 380, W, H), WOOD_L)
    for y in (470, 560):
        c.rect((0, y, W, y + 3), (190, 150, 105))
    # monitor
    c.rect((470, 340, 490, 395), GREY_D)
    c.rect((425, 385, 535, 402), GREY_D, r=6)
    c.rect((330, 90, 630, 345), (60, 62, 72), r=14)
    c.rect((342, 102, 618, 333), (140, 195, 235))
    c.rect((355, 118, 480, 134), WHITE)
    c.rect((355, 146, 560, 156), (255, 255, 255, 180))
    c.rect((355, 168, 520, 178), (255, 255, 255, 180))
    c.rect((355, 200, 440, 300), (90, 150, 210))
    c.rect((455, 200, 600, 300), (250, 211, 120))
    c.mark("monitor", (330, 90, 630, 402))
    # laptop
    c.shadow(180, 400, 140, 9)
    c.rect((70, 240, 290, 372), (50, 52, 62), r=10)
    c.rect((80, 250, 280, 362), (255, 233, 170))
    c.rect((92, 268, 190, 280), (255, 255, 255, 200))
    c.rect((92, 292, 240, 302), (255, 255, 255, 160))
    c.ell((150, 318, 210, 350), (240, 170, 80))
    c.poly([(48, 376), (312, 376), (330, 404), (30, 404)], GREY)
    c.rect((30, 402, 330, 410), GREY_D, r=3)
    c.mark("laptop", (30, 240, 330, 410))
    # keyboard and mouse
    c.rect((360, 460, 620, 530), (60, 62, 72), r=8)
    for r_ in range(3):
        for k_ in range(10):
            c.rect((370 + k_ * 25, 468 + r_ * 20, 391 + k_ * 25, 482 + r_ * 20), (205, 208, 214), r=3)
    c.rect((660, 450, 800, 560), (120, 130, 160), r=14)  # mouse pad
    c.shadow(730, 538, 30, 6)
    c.ell((700, 470, 760, 540), WHITE, outline=GREY_D, w=3)
    c.line([(730, 472), (730, 500)], GREY_D, 3)
    c.line([(702, 500), (758, 500)], GREY_D, 3)
    c.mark("mouse", (700, 470, 760, 540))
    # decoration: pencil cup and plant
    c.rect((820, 300, 890, 380), ORANGE, r=8)
    for i, col in enumerate((RED, BLUE, GREEN)):
        c.line([(840 + i * 14, 300), (835 + i * 20, 255)], col, 7)
    return c


def scene_c3():
    c = Canvas()
    room(c, (252, 228, 200), (215, 165, 115), 330, WOOD_D)
    c.rect((0, 330, W, H), WOOD_L)
    for y in (420, 520):
        c.rect((0, y, W, y + 3), (190, 150, 105))
    c.rect((70, 60, 330, 250), BLUE_L, r=6, outline=WHITE, w=8)  # window
    c.line([(200, 60), (200, 250)], WHITE, 6)
    c.rect((600, 80, 880, 230), (240, 205, 160), r=8)  # shelf / wall picture
    c.rect((616, 96, 864, 214), (250, 232, 200), r=6)
    # bowl of rice
    c.mark("bowl", bowl(c, 205, 450, 100, 72, (90, 150, 200), (252, 252, 245), steam=True))
    # plate with fish
    c.shadow(500, 545, 170, 12)
    c.ell((330, 440, 670, 550), WHITE)
    c.ell((365, 458, 635, 535), (236, 238, 242))
    c.poly([(420, 495), (500, 465), (580, 490), (500, 520)], ORANGE)
    c.poly([(580, 490), (610, 470), (610, 512)], ORANGE)
    c.ell((458, 482, 468, 492), INK)
    c.ell((380, 470, 410, 492), GREEN)
    c.mark("plate", (330, 440, 670, 550))
    # chopsticks on a rest
    c.rect((725, 520, 835, 545), (200, 90, 85), r=8)
    c.line([(700, 575), (865, 455)], (120, 80, 55), 9)
    c.line([(720, 590), (890, 470)], (150, 100, 70), 9)
    c.mark("chopsticks", (695, 450, 895, 595))
    return c


def scene_c4():
    c = Canvas()
    c.vgradient((0, 0, W, 300), (200, 226, 245), (240, 245, 250))
    c.rect((0, 220, W, 300), (210, 205, 215))  # distant building
    for x in range(20, W, 90):
        c.rect((x, 235, x + 50, 270), (236, 232, 240))
    c.rect((0, 300, W, H), (125, 128, 138))  # asphalt
    c.rect((0, 296, W, 312), (170, 170, 180))
    for i in range(7):  # parking bays
        x = 40 + i * 130
        c.poly([(x, 580), (x + 22, 580), (x + 70, 340), (x + 48, 340)], (240, 240, 235))
    c.poly([(40 + 7 * 130, 580), (62 + 7 * 130, 580), (110 + 7 * 130, 340), (88 + 7 * 130, 340)], (240, 240, 235))
    # parking sign
    c.rect((152, 60, 166, 330), GREY_D)
    c.rect((92, 40, 226, 174), BLUE, r=12, outline=WHITE, w=6)
    c.text((159, 108), "P", 100, WHITE)
    c.mark("parking lot", (92, 40, 226, 174))
    # motorbike in a bay
    c.mark("motorcycle", moto(c, 370, 330, 1.9, BLUE))
    c.mark("helmet", helmet(c, 250, 475, 58, RED))
    c.mark("key", key(c, 760, 545, 0.95))
    return c


def scene_e1():
    c = Canvas()
    room(c, (250, 232, 210), (214, 170, 120), 380, WOOD_D)
    c.rect((0, 380, W, H), WOOD)
    c.rect((680, 60, 900, 260), BLUE_L, r=6, outline=WHITE, w=8)
    c.line([(790, 60), (790, 260)], WHITE, 6)
    c.shadow(450, 560, 280, 14)
    c.ell((140, 450, 760, 580), WHITE)  # saucer
    c.ell((200, 470, 700, 560), (232, 235, 240))
    c.mark("saucer", (140, 450, 760, 580))
    cup(c, 255, 320, 230, 180, WHITE, (110, 70, 50))
    c.mark("cup", (253, 262, 560, 500))
    c.line([(560, 510), (690, 478)], GREY, 9)  # spoon
    c.ell((655, 458, 715, 500), GREY)
    c.ell((662, 464, 706, 494), (226, 229, 234))
    c.mark("spoon", (548, 452, 718, 520))
    return c


def scene_e2():
    c = Canvas()
    room(c, (246, 214, 190), (150, 105, 90), 400, (115, 78, 66))
    for x in (230, 500, 770):  # hanging lamps
        c.line([(x, 0), (x, 90)], GREY_D, 4)
        c.poly([(x - 40, 140), (x + 40, 140), (x + 16, 90), (x - 16, 90)], YELLOW)
        c.ell((x - 70, 130, x + 70, 240), (255, 236, 150, 45))
    c.rect((60, 190, 160, 290), (240, 200, 170), r=6)  # wall picture
    c.rect((72, 202, 148, 278), (150, 190, 160))
    # table
    c.shadow(580, 580, 260, 12)
    c.rect((290, 520, 310, 575), (95, 70, 55))
    c.rect((840 - 270, 520, 860 - 270, 575), (95, 70, 55))
    c.rect((300, 410, 860, 440), WOOD_L)
    c.rect((300, 440, 860, 520), WOOD, r=6)
    c.rect((300, 440, 860, 452), WOOD_D)
    c.rect((320, 440, 345, 580), WOOD_D)
    c.rect((815, 440, 840, 580), WOOD_D)
    c.mark("table", (290, 410, 870, 580))
    # menu
    c.poly([(560, 405), (700, 405), (685, 285), (575, 285)], WHITE)
    c.rect((575, 285, 685, 300), RED)
    c.text((630, 322), "MENU", 24, INK)
    for y in (345, 362, 379):
        c.rect((592, y, 668, y + 5), GREY)
    c.mark("menu", (560, 285, 700, 410))
    # cups / plate on table
    c.ell((380, 396, 500, 426), WHITE, outline=GREY_L)
    c.ell((405, 402, 475, 420), (240, 150, 90))
    c.ell((735, 392, 765, 414), BLUE_L)
    # chair
    c.shadow(150, 595, 100, 10)
    c.rect((75, 290, 215, 440), (186, 104, 96), r=12)
    for i in range(3):
        c.rect((95 + i * 40, 304, 115 + i * 40, 426), (150, 80, 76), r=4)
    c.rect((60, 440, 230, 475), (186, 104, 96), r=10)
    c.rect((80, 475, 98, 595), (120, 70, 66))
    c.rect((190, 475, 208, 595), (120, 70, 66))
    c.mark("chair", (60, 290, 230, 595))
    return c


def scene_e3():
    c = Canvas()
    room(c, (222, 232, 240), (205, 160, 110), 360, WOOD_D)
    c.rect((0, 360, W, H), WOOD_L)
    for y in (450, 545):
        c.rect((0, y, W, y + 3), (190, 150, 105))
    c.rect((90, 70, 310, 250), WHITE, r=6, outline=GREY_L, w=5)  # poster / board
    for i in range(4):
        c.rect((115, 100 + i * 36, 285 - (i % 2) * 40, 112 + i * 36), (150, 180, 220))
    # notebook (open)
    c.shadow(380, 560, 220, 12)
    c.poly([(150, 420), (385, 435), (385, 560), (130, 548)], WHITE)
    c.poly([(390, 435), (625, 420), (645, 548), (390, 560)], (248, 246, 238))
    c.line([(388, 435), (388, 560)], GREY, 4)
    for i in range(5):
        y = 458 + i * 20
        c.line([(165 - i, y - 2 + i * 1), (372, y + 9)], (170, 195, 225), 3)
        c.line([(404, y + 9), (612, y - 4)], (170, 195, 225), 3)
    c.rect((140, 426, 150, 556), BLUE)
    c.mark("notebook", (130, 420, 645, 560))
    # pen
    c.shadow(700, 585, 90, 6)
    c.poly([(670, 560), (680, 548), (840, 505), (846, 520), (688, 574)], BLUE)
    c.poly([(840, 505), (846, 520), (878, 502), (872, 494)], NAVY)
    c.poly([(660, 568), (670, 560), (688, 574), (672, 580)], (230, 220, 210))
    c.line([(742, 548), (798, 531)], WHITE, 4)
    c.mark("pen", (655, 495, 880, 585))
    # lamp
    c.mark("lamp", lamp(c, 790, 450, 1.35, (240, 120, 100)))
    return c


def scene_s1():
    c = Canvas()
    room(c, (236, 238, 226), (206, 170, 128), 380, (160, 125, 90))
    # blackboard
    c.rect((150, 50, 810, 300), (170, 125, 85), r=10)
    c.rect((166, 66, 794, 284), (58, 98, 88), r=6)
    c.text((300, 130), "ABC", 80, WHITE)
    c.text((500, 130), "1+2=3", 70, (255, 240, 170))
    c.line([(200, 222), (420, 222)], (255, 255, 255, 190), 5)
    c.line([(470, 215), (480, 250), (500, 205), (520, 250), (530, 215)], (255, 255, 255, 190), 5)
    c.rect((180, 288, 300, 300), (230, 225, 215))
    c.mark("blackboard", (150, 50, 810, 300))
    # desk
    c.shadow(450, 600, 260, 12)
    c.rect((260, 470, 276, 600), GREY_D)
    c.rect((624, 470, 640, 600), GREY_D)
    c.rect((230, 430, 670, 472), WOOD_L, r=6)
    c.rect((230, 462, 670, 478), WOOD_D)
    c.rect((340, 480, 560, 545), WOOD, r=6, outline=WOOD_D, w=3)  # drawer
    c.rect((435, 505, 465, 515), WOOD_D, r=3)
    c.mark("desk", (230, 430, 670, 600))
    # book on the desk
    c.rect((345, 372, 500, 432), RED, r=5)
    c.rect((345, 408, 500, 432), WHITE)
    c.rect((345, 372, 366, 432), (176, 60, 58), r=3)
    c.rect((385, 386, 465, 396), (255, 255, 255, 200))
    c.mark("book", (345, 372, 500, 432))
    # pencil (unlabelled)
    c.poly([(540, 420), (610, 400), (614, 410), (544, 430)], YELLOW)
    # backpack on the floor
    c.shadow(820, 592, 100, 10)
    c.rect((740, 395, 900, 585), BLUE, r=40)
    c.rect((755, 480, 885, 570), (70, 120, 180), r=18)
    c.rect((780, 500, 860, 512), YELLOW)
    c.rect((805, 372, 835, 400), (70, 120, 180), r=10)
    c.line([(745, 440), (745, 560)], NAVY, 7)
    c.line([(895, 440), (895, 560)], NAVY, 7)
    c.mark("backpack", (740, 372, 900, 585))
    return c


def scene_s2():
    c = Canvas()
    c.vgradient((0, 0, W, 330), (255, 244, 222), (252, 230, 196))
    c.rect((0, 330, W, H), WOOD)
    for y in (420, 520):
        c.rect((0, y, W, y + 3), WOOD_D)
    c.shadow(480, 560, 370, 18)
    c.ell((80, 400, 880, 590), WHITE)
    c.ell((125, 425, 835, 570), (236, 238, 242))
    # apple
    c.shadow(250, 520, 100, 12)
    c.ell((155, 305, 345, 510), RED)
    c.ell((225, 300, 275, 340), (210, 70, 70))
    c.ell((190, 335, 225, 380), (240, 140, 130, 150))
    c.line([(250, 310), (254, 255)], BROWN, 9)
    c.poly([(256, 270), (310, 240), (300, 288), (262, 292)], GREEN)
    c.mark("apple", (155, 255, 345, 510))
    # banana
    c.poly([(395, 470), (450, 505), (555, 505), (640, 455), (690, 395), (640, 405), (580, 455), (500, 470), (420, 445)], YELLOW)
    c.poly([(395, 470), (420, 445), (440, 472), (428, 496)], YELLOW)
    c.poly([(450, 505), (555, 505), (640, 455), (690, 395), (676, 392), (625, 440), (545, 482), (460, 486)], (232, 186, 60))
    c.poly([(690, 395), (704, 380), (712, 398), (692, 408)], BROWN)
    c.poly([(395, 470), (385, 478), (400, 490), (410, 478)], BROWN)
    c.mark("banana", (385, 380, 712, 506), centre=(530, 488))
    # orange
    c.shadow(760, 540, 85, 10)
    c.ell((680, 380, 850, 545), ORANGE)
    c.ell((700, 405, 735, 440), (255, 200, 120, 160))
    c.ell((758, 380, 772, 392), (190, 120, 40))
    c.poly([(774, 386), (822, 358), (824, 392), (782, 398)], GREEN)
    for dx, dy in ((20, 30), (60, 20), (90, 80), (45, 100), (110, 50), (70, 60)):
        c.ell((700 + dx, 410 + dy, 704 + dx, 414 + dy), (220, 130, 40))
    c.mark("orange", (680, 358, 850, 545))
    return c


def scene_s3():
    c = Canvas()
    room(c, (214, 226, 246), (200, 160, 120), 400, WOOD_D)
    c.rect((60, 70, 300, 270), BLUE_L, r=6, outline=WHITE, w=9)  # window with moon
    c.line([(180, 70), (180, 270)], WHITE, 6)
    c.ell((100, 100, 140, 140), (255, 246, 200))
    # bed
    c.shadow(340, 560, 300, 12)
    c.rect((60, 250, 90, 560), WOOD_D)  # headboard
    c.rect((60, 250, 150, 340), WOOD, r=12)
    c.rect((75, 405, 90, 560), WOOD_D)
    c.rect((560, 470, 580, 560), WOOD_D)
    c.rect((90, 380, 580, 480), (240, 240, 245), r=18)  # mattress
    c.rect((90, 400, 580, 478), (96, 150, 200), r=18)  # blanket
    c.rect((90, 400, 580, 424), (140, 185, 225))
    c.mark("bed", (60, 250, 580, 560))
    c.rect((110, 332, 290, 408), WHITE, r=30)  # pillow
    c.rect((110, 332, 290, 345), (225, 228, 235), r=8)
    c.mark("pillow", (110, 332, 290, 408))
    # bedside table
    c.rect((640, 470, 900, 500), WOOD_L, r=6)
    c.rect((655, 500, 885, 590), WOOD, r=6)
    c.rect((755, 530, 785, 541), WOOD_D)
    c.rect((645, 590, 665, 610), WOOD_D)
    c.rect((875, 590, 895, 610), WOOD_D)
    # lamp
    c.mark("lamp", lamp(c, 830, 470, 1.15, (250, 200, 90)))
    # alarm clock
    c.ell((655, 385, 685, 410), (200, 70, 70))  # bells
    c.ell((735, 385, 765, 410), (200, 70, 70))
    c.ell((662, 400, 755, 480), RED)
    c.ell((672, 408, 745, 472), WHITE)
    c.line([(708, 440), (708, 418)], INK, 4)
    c.line([(708, 440), (728, 448)], INK, 4)
    c.ell((704, 436, 713, 445), INK)
    c.mark("clock", (655, 385, 765, 482))
    return c


def scene_s4():
    c = Canvas()
    c.vgradient((0, 0, W, 360), (160, 210, 245), (225, 240, 250))
    c.ell((120, 80, 340, 150), (255, 255, 255, 200))  # clouds
    c.ell((60, 100, 220, 170), (255, 255, 255, 220))
    c.ell((480, 140, 700, 200), (255, 255, 255, 190))
    # sun with rays
    for i in range(12):
        a = i * math.pi / 6
        c.line([(830 + 66 * math.cos(a), 110 + 66 * math.sin(a)), (830 + 92 * math.cos(a), 110 + 92 * math.sin(a))], YELLOW, 8)
    c.ell((772, 52, 888, 168), YELLOW)
    c.mark("sun", (738, 18, 922, 202))
    c.pie((-200, 330, 1160, 900), 180, 360, GREEN)
    c.rect((0, 400, W, H), (138, 200, 125))
    c.poly([(380, 640), (580, 640), (560, 470), (430, 470)], (232, 214, 170))  # path
    # tree
    c.shadow(190, 520, 120, 12)
    c.poly([(165, 520), (215, 520), (208, 300), (172, 300)], (130, 92, 62))
    for (x1, y1, x2, y2) in ((50, 100, 260, 290), (120, 60, 330, 250), (20, 190, 230, 350), (140, 160, 350, 340)):
        c.ell((x1, y1, x2, y2), GREEN_D)
    c.ell((90, 130, 220, 230), (110, 178, 108))
    c.ell((225, 170, 275, 220), RED)
    c.ell((100, 240, 150, 290), RED)
    c.mark("tree", (20, 60, 350, 520))
    # bench
    c.shadow(640, 560, 190, 10)
    c.rect((470, 380, 810, 400), WOOD_L, r=4)
    c.rect((470, 410, 810, 430), WOOD_L, r=4)
    c.rect((490, 380, 505, 520), (95, 70, 55))
    c.rect((775, 380, 790, 520), (95, 70, 55))
    c.rect((450, 470, 830, 500), WOOD, r=6)
    c.rect((480, 500, 500, 565), (95, 70, 55))
    c.rect((780, 500, 800, 565), (95, 70, 55))
    c.mark("bench", (450, 380, 830, 565))
    # bird (on the bench back, facing left)
    c.line([(668, 340), (668, 384)], (230, 150, 60), 5)
    c.line([(690, 340), (690, 384)], (230, 150, 60), 5)
    c.poly([(715, 320), (770, 300), (745, 340)], NAVY)  # tail
    c.ell((620, 262, 740, 352), BLUE)  # body
    c.ell((610, 232, 672, 292), BLUE)  # head
    c.ell((630, 306, 715, 350), (245, 245, 240))  # belly
    c.poly([(610, 252), (582, 262), (610, 274)], ORANGE)  # beak
    c.ell((627, 248, 639, 260), INK)
    c.ell((652, 278, 722, 322), (70, 120, 180))  # wing
    c.mark("bird", (580, 230, 772, 386))
    return c


def scene_s5():
    c = Canvas()
    c.vgradient((0, 0, W, 330), (190, 220, 245), (240, 245, 250))
    for (x1, y1, x2, col) in ((0, 90, 200, (226, 205, 190)), (180, 40, 360, (204, 215, 232)), (480, 120, 700, (232, 220, 200)),
                              (690, 60, 960, (214, 222, 214))):
        c.rect((x1, y1, x2, 340), col)
        for wx in range(x1 + 16, x2 - 30, 44):
            for wy in range(y1 + 20, 320, 52):
                c.rect((wx, wy, wx + 26, wy + 32), (250, 250, 245, 190))
    c.rect((0, 340, W, 380), (222, 214, 200))  # pavement
    c.rect((0, 380, W, H), (128, 130, 140))  # road
    for x in range(40, W, 140):
        c.rect((x, 614, x + 70, 626), (240, 240, 235))
    # traffic light
    c.shadow(100, 392, 40, 7)
    c.rect((92, 175, 108, 392), GREY_D)
    c.rect((50, 70, 150, 245), (55, 58, 68), r=16)
    c.ell((74, 84, 126, 136), (240, 80, 70))
    c.ell((60, 76, 140, 144), (240, 80, 70, 70))
    c.ell((74, 150, 126, 190), (110, 100, 70))
    c.ell((74, 200, 126, 240), (60, 100, 70))
    c.mark("traffic light", (50, 70, 150, 245))
    # bus
    c.shadow(760, 450, 190, 10)
    c.rect((580, 230, 940, 440), YELLOW, r=22)
    c.rect((580, 400, 940, 424), (230, 180, 60))
    for x in range(598, 880, 66):
        c.rect((x, 255, x + 50, 320), BLUE_L, r=6)
    c.rect((895, 255, 930, 355), BLUE_L, r=6)
    for cx in (670, 840):
        c.ell((cx - 36, 405, cx + 36, 477), (50, 48, 58))
        c.ell((cx - 18, 423, cx + 18, 459), (200, 204, 210))
    c.rect((585, 340, 598, 356), RED, r=3)
    c.mark("bus", (580, 230, 940, 477))
    # car
    c.shadow(380, 560, 160, 11)
    c.poly([(210, 500), (230, 430), (290, 392), (440, 392), (500, 435), (545, 462), (545, 540), (210, 540)], RED)
    c.poly([(250, 440), (298, 403), (360, 403), (360, 440)], BLUE_L)
    c.poly([(372, 403), (435, 403), (480, 440), (372, 440)], BLUE_L)
    c.rect((200, 495, 560, 548), (210, 80, 75), r=14)
    c.ell((508, 500, 546, 522), YELLOW)
    c.rect((205, 505, 218, 522), (250, 140, 110))
    for cx in (290, 470):
        c.ell((cx - 38, 508, cx + 38, 584), (50, 48, 58))
        c.ell((cx - 18, 528, cx + 18, 564), (205, 208, 215))
    c.mark("car", (200, 392, 560, 584))
    return c


SCENES = {
    "c1": scene_c1, "c2": scene_c2, "c3": scene_c3, "c4": scene_c4,
    "e1": scene_e1, "e2": scene_e2, "e3": scene_e3,
    "s1": scene_s1, "s2": scene_s2, "s3": scene_s3, "s4": scene_s4, "s5": scene_s5,
}


def _norm(mark, pad=4):
    (x1, y1, x2, y2), centre = mark
    cx, cy = centre or ((x1 + x2) / 2, (y1 + y2) / 2)
    n = lambda v, m: round(min(1.0, max(0.0, v / m)), 3)
    bx = [n(x1 - pad, W), n(y1 - pad, H), n(x2 + pad, W), n(y2 + pad, H)]
    return n(cx, W), n(cy, H), bx


def main() -> int:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    cards = {c["seed_key"]: c for c in data["cards"]}
    for key, fn in SCENES.items():
        canvas = fn()
        canvas.save(key)
        card = cards.get(key)
        if card is None:
            print(f"{key}: image written, no card in seed_data.json", file=sys.stderr)
            continue
        missing = {lab["word"] for lab in card["labels"]} - set(canvas.marks)
        if missing:
            print(f"{key}: labels without a drawn mark: {sorted(missing)}", file=sys.stderr)
            return 1
        for lab in card["labels"]:
            lab["x"], lab["y"], lab["box"] = _norm(canvas.marks[lab["word"]])
        print(f"{key}: {(OUT / (key + '.jpg')).stat().st_size // 1024} KB")
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
