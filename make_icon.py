#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dastur ikonkasini (ö belgisi) yaratadi: icon.png, icon.ico (Windows), icon.icns (macOS)
va macOS .pkg oʻrnatuvchisi foni: installer_bg.png.
Yigʻish (PyInstaller) oldidan ishga tushiriladi.  Talab: pillow."""
import sys

from PIL import Image, ImageDraw, ImageFilter

SUPERSAMPLE = 4  # ImageDraw chetlarni silliqlamaydi – katta chizib kichraytiramiz


def _tile(size: int, enabled: bool, radius: float) -> Image.Image:
    """Yashil yumaloq kvadrat ichida oq ö; radius – tomonga nisbatan."""
    big = size * SUPERSAMPLE
    s = big / 64.0
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bg = (46, 160, 67, 255) if enabled else (140, 140, 140, 255)
    d.rounded_rectangle((0, 0, big - 1, big - 1), radius=int(big * radius), fill=bg)
    white = (255, 255, 255, 255)
    d.ellipse((12 * s, 26 * s, 52 * s, 60 * s), outline=white, width=max(2, int(8 * s)))   # "o"
    d.ellipse((16 * s, 7 * s, 27 * s, 18 * s), fill=white)                                 # ikki nuqta
    d.ellipse((37 * s, 7 * s, 48 * s, 18 * s), fill=white)
    return img.resize((size, size), Image.LANCZOS)


def draw(size: int, enabled: bool = True) -> Image.Image:
    """Windows va boshqa joylar uchun: butun maydonni egallaydi."""
    return _tile(size, enabled, radius=14 / 64)


def draw_mac(size: int = 1024) -> Image.Image:
    """macOS uslubi (Apple shabloni): 1024 da 824 lik shakl, atrofida boʻsh joy va yumshoq soya –
    Dock va Cmd+Tab da boshqa ilovalar bilan bir oʻlchamda koʻrinadi."""
    body = round(size * 824 / 1024)
    pad = (size - body) // 2
    tile = _tile(body, True, radius=185 / 824)
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    alpha = tile.getchannel("A").point(lambda a: a * 0.30)
    shadow.paste((0, 0, 0, 255), (pad, pad + round(size * 12 / 1024)), alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(size * 14 / 1024))
    shadow.alpha_composite(tile, (pad, pad))
    return shadow


def installer_background() -> Image.Image:
    """macOS oʻrnatuvchi oynasining chap pastki burchagidagi belgi (fon shaffof)."""
    img = Image.new("RGBA", (620, 418), (0, 0, 0, 0))
    logo = draw(512).resize((112, 112), Image.LANCZOS)
    img.paste(logo, (28, 418 - 112 - 28), logo)
    return img


def main() -> int:
    big = draw(1024)
    big.save("icon.png")
    sizes = [16, 24, 32, 48, 64, 128, 256]
    big.save("icon.ico", sizes=[(n, n) for n in sizes])
    draw_mac(1024).save("icon.icns")
    installer_background().save("installer_bg.png")
    print("icon.png, icon.ico, icon.icns, installer_bg.png yaratildi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
