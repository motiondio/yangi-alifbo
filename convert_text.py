#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tayyor matn/fayllarni eski lotin yozuvidan yangi alifboga (ö ğ ş ç) oʻgirish.

    python convert_text.py "O'zbekiston sho'x g'isht choy"
    python convert_text.py -i matn.txt -o yangi.txt
    echo "ko'cha" | python convert_text.py
    python convert_text.py --tutuq -i matn.txt          # ' → ʼ (tutuq belgisi)
    python convert_text.py --keep-sh-apostrophe ...      # s'h ni oʻzgartirmaslik
"""
import argparse
import sys

from alifbo_core import TUTUQ, convert_text

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # Windows quvurlarida cp1252 oʻrniga UTF-8
    except Exception:
        pass


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Eski yozuv → yangi alifbo (ö ğ ş ç).")
    p.add_argument("text", nargs="*", help="oʻgiriladigan matn (berilmasa, stdin/-i dan oʻqiladi)")
    p.add_argument("-i", "--input", help="kirish fayli (UTF-8)")
    p.add_argument("-o", "--output", help="chiqish fayli (berilmasa – ekranga)")
    p.add_argument("--tutuq", action="store_true", help="harfdan keyingi ' ni ʼ ga almashtirish")
    p.add_argument("--keep-sh-apostrophe", action="store_true", help="s'h ni oʻzgartirmaslik")
    a = p.parse_args(argv)

    if a.text:
        src = " ".join(a.text)
    elif a.input:
        with open(a.input, "r", encoding="utf-8") as fh:
            src = fh.read()
    else:
        src = sys.stdin.read()

    out = convert_text(src, strip_sh_apostrophe=not a.keep_sh_apostrophe,
                       tutuq=TUTUQ if a.tutuq else None)
    if a.output:
        with open(a.output, "w", encoding="utf-8") as fh:
            fh.write(out)
    else:
        sys.stdout.write(out)
        if not out.endswith("\n"):
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
