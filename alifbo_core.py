# -*- coding: utf-8 -*-
"""
Yangi oʻzbek lotin alifbosi (2026, OʻRQ-1184) uchun harf almashtirish mantiqi.

Eski yozuv  →  Yangi yozuv
    oʻ / o'  →  ö        Oʻ / O'  →  Ö
    gʻ / g'  →  ğ        Gʻ / G'  →  Ğ
    sh       →  ş        Sh / SH  →  Ş
    ch       →  ç        Ch / CH  →  Ç

"ng" birikmasi oʻzgarmaydi (alifbodan chiqarilgan, lekin yozilishi saqlanadi).
Tutuq belgisi (maʼno, sheʼr → şeʼr) saqlanadi.

Bu modulda tizimga bogʻliq hech narsa yoʻq: u faqat "qaysi tugma bosildi"
ketma-ketligini qabul qilib, "nechta belgini oʻchirib, oʻrniga nima yozish
kerak" degan javobni qaytaradi. Shuning uchun uni istalgan platformada
(Windows, macOS, Linux) bir xil ishlatish va testlash mumkin.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

__all__ = ["APOSTROPHES", "TUTUQ", "Action", "Engine", "convert_text"]

# Foydalanuvchilar "oʻ" ni turli belgilar bilan terishadi: oddiy apostrof,
# ʻ (U+02BB, rasmiy), ʼ (U+02BC), ‘ ’ (Word avtomatik qoʻyadigan), ` va ´.
APOSTROPHES = "'ʻʼ‘’`´"

# Rasmiy tutuq belgisi (U+02BC)
TUTUQ = "ʼ"

# harf + apostrof  →  yangi harf
_SINGLE = {"o": "ö", "O": "Ö", "g": "ğ", "G": "Ğ"}

# birinchi harf (s/c) + h  →  yangi harf.  Katta-kichikligi birinchi harfdan olinadi.
_DIGRAPH = {"s": "ş", "S": "Ş", "c": "ç", "C": "Ç"}


@dataclass
class Action:
    """Klaviatura dasturi bajarishi kerak boʻlgan amal.

    delete  – ekrandan nechta belgi oʻchiriladi (Backspace soni).
    insert  – oʻchirilgandan keyin yoziladigan matn.
    undo    – harf almashtirilgan boʻlsa, asl matn (Backspace bilan qaytarish uchun).
    """

    delete: int
    insert: str
    undo: Optional[str] = None


class _Cell:
    __slots__ = ("char", "locked")

    def __init__(self, char: str, locked: bool = False) -> None:
        self.char = char
        # locked=True – bu harf keyingi almashtirishda "birinchi harf" sifatida
        # ishlatilmaydi (masalan, foydalanuvchi "s'h" deb yozib, s va h ni
        # alohida qoldirmoqchi boʻlsa, yoki Backspace bilan qaytargan boʻlsa).
        self.locked = locked


class Engine:
    """Terilayotgan belgilarni kuzatib, almashtirish kerak boʻlganda Action qaytaradi.

    Foydalanish:
        eng = Engine()
        eng.feed_char("s")   -> None
        eng.feed_char("h")   -> Action(delete=2, insert="ş", undo="sh")
        eng.feed_backspace() -> Action(delete=0, insert="sh")   (Backspace-undo)
        eng.reset()          -> kursor koʻchganda / sichqoncha bosilganda
    """

    def __init__(
        self,
        *,
        strip_sh_apostrophe: bool = True,
        tutuq: Optional[str] = None,
        backspace_undo: bool = True,
        maxlen: int = 32,
    ) -> None:
        # "s'h" → "sh" (ş emas).  Masalan: Is'hoq → Ishoq, as'hob → ashob.
        self.strip_sh_apostrophe = strip_sh_apostrophe
        # None – apostroflar oʻzgartirilmaydi; "ʼ" – harfdan keyingi apostrof
        # rasmiy tutuq belgisiga (U+02BC) almashtiriladi.
        self.tutuq = tutuq
        # Almashtirishdan soʻng darhol Backspace bosilsa, asl yozuv qaytariladi.
        self.backspace_undo = backspace_undo
        self.maxlen = maxlen
        self._buf: List[_Cell] = []
        self._undo: Optional[str] = None

    # ------------------------------------------------------------------ API
    def reset(self) -> None:
        """Kursor koʻchdi (strelka, Enter, sichqoncha...) – kontekst yoʻqoldi."""
        self._buf.clear()
        self._undo = None

    @property
    def context(self) -> str:
        """Hozirgi bufer (faqat test/diagnostika uchun)."""
        return "".join(c.char for c in self._buf)

    def feed_char(self, ch: str) -> Optional[Action]:
        """Foydalanuvchi bitta belgi terdi (u allaqachon ekranda)."""
        if len(ch) != 1 or not (ch.isalpha() or ch in APOSTROPHES):
            # boʻsh joy, raqam, tinish belgisi, boshqaruv belgisi ...
            self.reset()
            return None
        self._undo = None
        self._push(ch)
        return self._match()

    def feed_backspace(self) -> Optional[Action]:
        """Foydalanuvchi Backspace bosdi (bitta belgi allaqachon oʻchdi)."""
        undo = self._undo
        self._undo = None
        if self._buf:
            self._buf.pop()
        if undo and self.backspace_undo:
            # Almashtirilgan harf hozirgina oʻchdi – asl yozuvni qaytaramiz,
            # birinchi harfni qulflaymiz, toki u yana almashtirilmasin.
            self._push(undo[0], locked=True)
            for c in undo[1:]:
                self._push(c)
            return Action(delete=0, insert=undo)
        return None

    # -------------------------------------------------------------- ichki
    def _push(self, ch: str, locked: bool = False) -> None:
        self._buf.append(_Cell(ch, locked))
        if len(self._buf) > self.maxlen:
            del self._buf[: len(self._buf) - self.maxlen]

    def _match(self) -> Optional[Action]:
        b = self._buf
        n = len(b)
        last = b[-1].char

        # 1) s + ' + h  →  "sh"  (s va h alohida harflar; ş EMAS)
        if (
            self.strip_sh_apostrophe
            and n >= 3
            and last in "hH"
            and b[-2].char in APOSTROPHES
            and b[-3].char in "sS"
        ):
            s = b[-3].char
            del b[-3:]
            self._push(s, locked=True)
            self._push(last)
            return Action(delete=3, insert=s + last)

        # 2) o' / g'  →  ö / ğ
        if last in APOSTROPHES:
            if n >= 2:
                prev = b[-2]
                if prev.char in _SINGLE and not prev.locked:
                    repl = _SINGLE[prev.char]
                    orig = prev.char + last
                    del b[-2:]
                    self._push(repl)
                    self._undo = orig
                    return Action(delete=2, insert=repl, undo=orig)
                # 2b) tutuq belgisini rasmiy koʻrinishga keltirish (ixtiyoriy)
                if self.tutuq and last != self.tutuq and prev.char.isalpha():
                    b[-1].char = self.tutuq
                    return Action(delete=1, insert=self.tutuq)
            return None

        # 3) sh / ch  →  ş / ç
        if last in "hH" and n >= 2:
            prev = b[-2]
            if prev.char in _DIGRAPH and not prev.locked:
                repl = _DIGRAPH[prev.char]
                orig = prev.char + last
                del b[-2:]
                self._push(repl)
                self._undo = orig
                return Action(delete=2, insert=repl, undo=orig)

        return None


# ---------------------------------------------------------------- matn
_AP = "[" + re.escape(APOSTROPHES) + "]"
_RE_SH_APOS = re.compile(r"([sS])" + _AP + r"([hH])")
_RE_SINGLE = re.compile(r"([oOgG])" + _AP)
_RE_DIGRAPH = re.compile(r"([sScC])[hH]")
_RE_TUTUQ = re.compile(r"(?<=[^\W\d_])" + _AP)
_SENTINEL = "\x00"


def convert_text(
    text: str, *, strip_sh_apostrophe: bool = True, tutuq: Optional[str] = None
) -> str:
    """Tayyor matnni eski yozuvdan yangi alifboga oʻgiradi.

    >>> convert_text("O'zbekiston, sho'x, g'isht, choy, Is'hoq")
    'Özbekiston, şöx, ğişt, çoy, Ishoq'
    """
    if strip_sh_apostrophe:
        text = _RE_SH_APOS.sub(lambda m: m.group(1) + _SENTINEL + m.group(2), text)
    text = _RE_SINGLE.sub(lambda m: _SINGLE[m.group(1)], text)
    text = _RE_DIGRAPH.sub(lambda m: _DIGRAPH[m.group(1)], text)
    if tutuq:
        text = _RE_TUTUQ.sub(tutuq, text)
    return text.replace(_SENTINEL, "")
