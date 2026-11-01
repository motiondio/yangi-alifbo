# -*- coding: utf-8 -*-
"""
Statistika: kunlar, harflar va dasturlar boʻyicha nechta harf toʻgʻirlangani.

Faqat sonlar saqlanadi – yozilgan matn emas.  Fayl foydalanuvchi papkasida (stats.json),
uni faqat asosiy dastur yozadi; panel va sozlamalar oynasi oʻqiydi.  Tozalash – control.json
orqali ("reset_stats"), aks holda asosiy dastur xotiradagi nusxani qayta yozib yuborardi.

    {"since": "2026-11-01",
     "days": {"2026-11-01": {"n": 128, "l": {"ş": 60, "ç": 30, "ö": 25, "ğ": 13},
                             "a": {"Telegram": 100, "Word": 28}}},
     "before": {"n": 0, "l": {}, "a": {}}}     ← KEEP_DAYS dan eski kunlar yigʻindisi
"""
from __future__ import annotations

import datetime
from typing import Dict, List, Optional, Tuple

import alifbo_config as ac

STATS_FILE = "stats.json"
LETTERS = ("ş", "ç", "ö", "ğ")
MILESTONES = (100, 1_000, 10_000, 100_000, 1_000_000)
KEEP_DAYS = 400
MAX_APPS = 50          # bitta kunda shuncha dasturdan ortigʻi "boshqa" ga qoʻshiladi
OTHER = ""             # nomi nomaʼlum yoki roʻyxatdan tashqari dasturlar


def letter_of(text) -> Optional[str]:
    """Almashtirishda yozilgan harf: "Ş" → "ş"; boshqa narsa → None."""
    for ch in text or "":
        if ch.lower() in LETTERS:
            return ch.lower()
    return None


def _day(value) -> Optional[datetime.date]:
    try:
        return value if isinstance(value, datetime.date) else datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _counts(value) -> Dict[str, int]:
    out = {}
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool) and v > 0:
                out[k] = v
    return out


def _bucket(value) -> dict:
    value = value if isinstance(value, dict) else {}
    n = value.get("n")
    return {"n": n if isinstance(n, int) and not isinstance(n, bool) and n > 0 else 0,
            "l": _counts(value.get("l")), "a": _counts(value.get("a"))}


def _merge(into: dict, other: dict) -> None:
    into["n"] += other["n"]
    for key in ("l", "a"):
        for k, v in other[key].items():
            into[key][k] = into[key].get(k, 0) + v


class Stats:
    def __init__(self, data: Optional[dict] = None) -> None:
        data = data if isinstance(data, dict) else {}
        self.days: Dict[str, dict] = {}
        days = data.get("days")
        for day, bucket in (days.items() if isinstance(days, dict) else ()):
            if isinstance(day, str) and _day(day) is not None:
                self.days[day] = _bucket(bucket)
        self.before = _bucket(data.get("before"))
        since = data.get("since")
        self.since = since if _day(since) is not None else (min(self.days) if self.days else None)

    def to_dict(self) -> dict:
        return {"since": self.since, "days": self.days, "before": self.before}

    def empty(self) -> bool:
        return self.total() == 0 and self.since is None

    # ---- yozish (asosiy dastur) ---------------------------------------------------
    def add(self, day: str, letter: Optional[str] = None, app: Optional[str] = None, n: int = 1) -> None:
        bucket = self.days.get(day)
        if bucket is None:
            bucket = self.days[day] = {"n": 0, "l": {}, "a": {}}
            self._trim(day)
        bucket["n"] += n
        if letter:
            bucket["l"][letter] = bucket["l"].get(letter, 0) + n
        app = (app or OTHER).strip()[:60]
        if app not in bucket["a"] and len(bucket["a"]) >= MAX_APPS:
            app = OTHER
        bucket["a"][app] = bucket["a"].get(app, 0) + n
        if self.since is None or day < self.since:
            self.since = day

    def _trim(self, today: str) -> None:
        """KEEP_DAYS dan eski kunlar "before" ga qoʻshiladi – fayl cheksiz oʻsmasin."""
        end = _day(today)
        if end is None:
            return
        limit = (end - datetime.timedelta(days=KEEP_DAYS)).isoformat()
        for day in [d for d in self.days if d < limit]:
            _merge(self.before, self.days.pop(day))

    def migrate(self, total: int, today_count: int, day: str) -> None:
        """Statistikadan oldingi versiyalarning hisoblagichi (state.json: today, total)."""
        today_count = max(0, min(today_count, total))
        if today_count:
            self.days.setdefault(day, {"n": 0, "l": {}, "a": {}})["n"] += today_count
        self.before["n"] += total - today_count
        if total:
            self.since = self.since or day

    def reset(self) -> None:
        self.days, self.before, self.since = {}, {"n": 0, "l": {}, "a": {}}, None

    # ---- oʻqish (panel, sozlamalar) ------------------------------------------------
    def total(self) -> int:
        return self.before["n"] + sum(b["n"] for b in self.days.values())

    def day_count(self, day: str) -> int:
        return self.days.get(day, {}).get("n", 0)

    def series(self, end_day: str, days: int = 30) -> List[Tuple[str, int]]:
        end = _day(end_day)
        if end is None:
            return []
        out = []
        for i in range(days - 1, -1, -1):
            day = (end - datetime.timedelta(days=i)).isoformat()
            out.append((day, self.day_count(day)))
        return out

    def range_count(self, end_day: str, days: int) -> int:
        return sum(n for _, n in self.series(end_day, days))

    def _sum(self, key: str) -> Dict[str, int]:
        out = dict(self.before[key])
        for bucket in self.days.values():
            for k, v in bucket[key].items():
                out[k] = out.get(k, 0) + v
        return out

    def letters(self) -> Dict[str, int]:
        counts = self._sum("l")
        return {letter: counts.get(letter, 0) for letter in LETTERS}

    def apps(self, top: int = 5) -> List[Tuple[str, int]]:
        """Eng koʻp ishlatilgan dasturlar; qolganlari (va nomaʼlumlar) bitta "boshqa" qatorda."""
        counts = self._sum("a")
        other = counts.pop(OTHER, 0)
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
        other += sum(v for _, v in ranked[top:])
        ranked = ranked[:top]
        if other:
            ranked.append((OTHER, other))
        return ranked

    def streak(self, today: str) -> int:
        """Ketma-ket kunlar (bugun yoki kechagacha) – bugun hali yozmagan boʻlsa ham seriya uzilmaydi."""
        day = _day(today)
        if day is None:
            return 0
        if self.day_count(day.isoformat()) == 0:
            day -= datetime.timedelta(days=1)
        count = 0
        while self.day_count(day.isoformat()) > 0:
            count += 1
            day -= datetime.timedelta(days=1)
        return count

    def best_day(self) -> Optional[Tuple[str, int]]:
        if not self.days:
            return None
        day, bucket = max(self.days.items(), key=lambda kv: (kv[1]["n"], kv[0]))
        return (day, bucket["n"]) if bucket["n"] else None

    def milestone(self) -> int:
        """Erishilgan eng katta marra (100, 1 000, 10 000 …); hali yoʻq boʻlsa – 0."""
        total = self.total()
        reached = [m for m in MILESTONES if total >= m]
        return reached[-1] if reached else 0


def load(user_dir: Optional[str] = None) -> Stats:
    return Stats(ac.read_runtime(STATS_FILE, user_dir))


def save(stats: Stats, user_dir: Optional[str] = None) -> None:
    ac.write_runtime(STATS_FILE, stats.to_dict(), user_dir)
