# -*- coding: utf-8 -*-
"""
"Natijamni ulashish": statistikadan Instagram / Telegram uchun kvadrat rasm (1080×1080 PNG).

Rasm Yuklanmalar (Downloads) papkasiga saqlanadi va fayl menejerida koʻrsatiladi – foydalanuvchi
uni oʻzi xohlagan joyga joylaydi.  Hech narsa internetga yuborilmaydi.
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

import alifbo_stats
from alifbo_i18n import fmt_num, t

SIZE = 1080
GREEN_TOP = (46, 160, 67)
GREEN_BOTTOM = (20, 108, 46)
WHITE = (255, 255, 255)
LINK = "github.com/motiondio/yangi-alifbo"
_FONTS = {
    # (qalin, oddiy) – oʻzbekcha (ʻ ö ğ ş ç) va kirill harflari bor shriftlar
    "darwin": (("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/SFNS.ttf"),
               ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/SFNS.ttf")),
    "win": ((r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
            (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf")),
    "linux": (("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",),
              ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",)),
}


def _font(bold: bool, size: int):
    from PIL import ImageFont
    key = "darwin" if sys.platform == "darwin" else "win" if sys.platform.startswith("win") else "linux"
    for path in _FONTS[key][0 if bold else 1]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:  # eski Pillow
        return ImageFont.load_default()


def _fit(draw, text: str, bold: bool, size: int, width: int):
    """Matn kenglikka sigʻguncha shrift kichraytiriladi."""
    while size > 12:
        font = _font(bold, size)
        if draw.textlength(text, font=font) <= width:
            return font
        size -= 4
    return _font(bold, size)


def _logo(size: int):
    """Oq kvadrat ichida yashil ö (ilova belgisining teskari ranglisi)."""
    from PIL import Image, ImageDraw
    big = size * 4
    s = big / 64.0
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, big - 1, big - 1), radius=int(14 * s), fill=WHITE + (255,))
    green = GREEN_TOP + (255,)
    d.ellipse((12 * s, 26 * s, 52 * s, 60 * s), outline=green, width=int(8 * s))
    d.ellipse((16 * s, 7 * s, 27 * s, 18 * s), fill=green)
    d.ellipse((37 * s, 7 * s, 48 * s, 18 * s), fill=green)
    return img.resize((size, size), Image.LANCZOS)


def make_image(stats: alifbo_stats.Stats):
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (SIZE, SIZE))
    d = ImageDraw.Draw(img)
    for y in range(SIZE):  # yashil gradient
        k = y / (SIZE - 1)
        d.line([(0, y), (SIZE, y)], fill=tuple(int(a + (b - a) * k) for a, b in zip(GREEN_TOP, GREEN_BOTTOM)))
    over = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    o = ImageDraw.Draw(over)
    o.ellipse((620, -220, 1300, 460), fill=(255, 255, 255, 18))     # bezak doiralar
    o.ellipse((-260, 700, 380, 1340), fill=(255, 255, 255, 12))

    # yuqorida: belgi va nom
    over.alpha_composite(_logo(112), (90, 90))
    o.text((228, 146), "Yangi Alifbo", font=_font(True, 54), fill=WHITE + (255,), anchor="lm")

    # oʻrtada: katta son va izoh
    number = fmt_num(stats.total())
    o.text((SIZE // 2, 470), number, font=_fit(o, number, True, 250, SIZE - 160), fill=WHITE + (255,),
           anchor="mm")
    line = t("share_line")
    o.text((SIZE // 2, 615), line, font=_fit(o, line, False, 52, SIZE - 160), fill=WHITE + (235,),
           anchor="mm")

    # harflar
    letters = [(ch, n) for ch, n in stats.letters().items() if n]
    if letters:
        f_letter, f_count = _font(True, 46), _font(False, 38)
        chips = [(ch, fmt_num(n)) for ch, n in letters]
        widths = [o.textlength(ch, font=f_letter) + 16 + o.textlength(n, font=f_count) + 64 for ch, n in chips]
        gap = 20
        x = (SIZE - (sum(widths) + gap * (len(chips) - 1))) / 2
        for (ch, n), w in zip(chips, widths):
            o.rounded_rectangle((x, 700, x + w, 790), radius=45, fill=(255, 255, 255, 40))
            o.text((x + 32, 745), ch, font=f_letter, fill=WHITE + (255,), anchor="lm")
            o.text((x + 32 + o.textlength(ch, font=f_letter) + 16, 747), n, font=f_count,
                   fill=WHITE + (230,), anchor="lm")
            x += w + gap

    # pastda: dastur haqida
    o.text((SIZE // 2, 930), t("share_footer"), font=_font(True, 38), fill=WHITE + (255,), anchor="mm")
    o.text((SIZE // 2, 985), LINK, font=_font(False, 32), fill=WHITE + (200,), anchor="mm")
    img = img.convert("RGBA")
    img.alpha_composite(over)
    return img.convert("RGB")


def downloads_dir() -> str:
    home = os.path.expanduser("~")
    folder = os.path.join(home, "Downloads")
    return folder if os.path.isdir(folder) else home


def save_image(img, day: str, folder: Optional[str] = None) -> str:
    folder = folder or downloads_dir()
    path = os.path.join(folder, f"YangiAlifbo-{day}.png")
    n = 2
    while os.path.exists(path):
        path = os.path.join(folder, f"YangiAlifbo-{day}-{n}.png")
        n += 1
    img.save(path, "PNG")
    return path


def reveal(path: str) -> None:
    """Faylni Finder / Explorer da belgilab koʻrsatadi."""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        elif sys.platform.startswith("win"):
            subprocess.Popen(["explorer", f"/select,{os.path.normpath(path)}"])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])
    except Exception:
        pass
