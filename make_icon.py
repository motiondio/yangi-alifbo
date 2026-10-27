#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dastur ikonkasini (ö belgisi) yaratadi: icon.png, icon.ico (Windows), icon.icns (macOS).
Yigʻish (PyInstaller) oldidan ishga tushiriladi.  Talab: pillow."""
import sys

from PIL import Image, ImageDraw


def draw(size: int, enabled: bool = True) -> Image.Image:
    s = size / 64.0
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bg = (46, 160, 67, 255) if enabled else (140, 140, 140, 255)
    # yumaloq fon
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=int(14 * s), fill=bg)
    white = (255, 255, 255, 255)
    # "o"
    d.ellipse((12 * s, 26 * s, 52 * s, 60 * s), outline=white, width=max(2, int(8 * s)))
    # ikki nuqta
    d.ellipse((16 * s, 7 * s, 27 * s, 18 * s), fill=white)
    d.ellipse((37 * s, 7 * s, 48 * s, 18 * s), fill=white)
    return img


def main() -> int:
    big = draw(1024)
    big.save("icon.png")
    sizes = [16, 24, 32, 48, 64, 128, 256]
    big.save("icon.ico", sizes=[(n, n) for n in sizes])
    big.save("icon.icns")
    print("icon.png, icon.ico, icon.icns yaratildi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
