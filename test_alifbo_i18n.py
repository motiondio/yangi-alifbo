# -*- coding: utf-8 -*-
"""Tillar (alifbo_i18n) va statistika (alifbo_stats) uchun testlar.

    python3 -m unittest -v test_alifbo_i18n
"""
import os
import re
import tempfile
import unittest

import alifbo_config as ac
import alifbo_i18n as i18n
import alifbo_stats
from alifbo_stats import Stats

PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


class I18nTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language(i18n.DEFAULT)

    def test_every_string_in_every_language(self):
        for key, row in i18n.STRINGS.items():
            self.assertEqual(len(row), 3, key)
            for text in row:
                self.assertTrue(isinstance(text, str) and text.strip(), key)
        for key in i18n.UZ_NEW:
            self.assertIn(key, i18n.STRINGS)

    def test_placeholders_match(self):
        for key, row in i18n.STRINGS.items():
            want = set(PLACEHOLDER.findall(row[0]))
            for lang in i18n.LANGS:
                i18n.set_language(lang)
                self.assertEqual(set(PLACEHOLDER.findall(i18n.t(key))), want, (key, lang))

    def test_new_alphabet_is_generated(self):
        i18n.set_language("uz-new")
        self.assertEqual(i18n.t("btn_quit"), "Çiqiş")
        self.assertEqual(i18n.t("stat_today_fixed"), "Bugun töğirlandi")
        # {oʻrinbosarlar} oʻgirilmaydi, qiymat qoʻyiladi
        self.assertEqual(i18n.t("upd_latest", when="01.11 10:00"),
                         "Eng sönggi versiya örnatilgan · tekşirildi 01.11 10:00")
        # eski yozuv misollari oʻzgarmaydi
        self.assertEqual(i18n.t("sh_sub"), "Is'hoq → Ishoq, as'hob → ashob")
        self.assertIn("o'zbek, g'isht, choy", i18n.t("try_placeholder"))

    def test_translations_differ(self):
        for lang, word in (("uz", "Chiqish"), ("ru", "Выход"), ("en", "Quit")):
            i18n.set_language(lang)
            self.assertEqual(i18n.t("btn_quit"), word)
        self.assertEqual(i18n.t("tray_hotkey", hotkey="F9"), "Shortcut: F9")
        self.assertEqual(i18n.t("no_such_key"), "no_such_key")

    def test_normalize(self):
        self.assertEqual(i18n.normalize("ru-RU"), "ru")
        self.assertEqual(i18n.normalize("uz_Latn_UZ"), "uz")
        self.assertEqual(i18n.normalize("uz-new"), "uz-new")
        self.assertEqual(i18n.normalize("EN"), "en")
        self.assertIsNone(i18n.normalize("de"))
        self.assertIsNone(i18n.normalize(None))
        self.assertEqual(i18n.set_language("fr"), i18n.DEFAULT)

    def test_resolve(self):
        self.assertEqual(i18n.resolve({"language": "en"}), "en")
        self.assertEqual(i18n.resolve({"language": "uz-new"}), "uz-new")
        self.assertIn(i18n.resolve({"language": None}), ("uz", "ru"))
        self.assertIn(i18n.resolve({"language": "klingon"}), ("uz", "ru"))

    def test_dates_and_numbers(self):
        self.assertEqual(i18n.fmt_date("2026-11-01", "uz"), "1-noyabr")
        self.assertEqual(i18n.fmt_date("2026-11-01", "uz-new"), "1-noyabr")
        self.assertEqual(i18n.fmt_date("2026-11-01", "ru"), "1 ноября")
        self.assertEqual(i18n.fmt_date("2026-11-01", "en"), "Nov 1")
        self.assertEqual(i18n.fmt_date_year("2026-11-01", "uz"), "2026-yil 1-noyabr")
        self.assertEqual(i18n.fmt_date("garbage"), "garbage")
        i18n.set_language("en")
        self.assertEqual(i18n.fmt_num(1234567), "1,234,567")
        i18n.set_language("ru")
        self.assertEqual(i18n.fmt_num(1234567), "1 234 567")
        self.assertEqual(i18n.fmt_num(None), "0")

    def test_language_setting(self):
        self.assertIn("language", ac.EDITABLE_KEYS)
        self.assertIsNone(ac.DEFAULT_CONFIG["language"])


class StatsTests(unittest.TestCase):
    def test_letter_of(self):
        self.assertEqual(alifbo_stats.letter_of("Ş"), "ş")
        self.assertEqual(alifbo_stats.letter_of("ö"), "ö")
        self.assertIsNone(alifbo_stats.letter_of("sh"))
        self.assertIsNone(alifbo_stats.letter_of(None))

    def test_add_and_totals(self):
        s = Stats()
        self.assertTrue(s.empty())
        s.add("2026-10-30", "ş", "Telegram", 3)
        s.add("2026-11-01", "ç", "Word")
        s.add("2026-11-01", "ş", None)
        self.assertEqual(s.total(), 5)
        self.assertEqual(s.day_count("2026-11-01"), 2)
        self.assertEqual(s.letters(), {"ş": 4, "ç": 1, "ö": 0, "ğ": 0})
        self.assertEqual(s.since, "2026-10-30")
        self.assertEqual(s.range_count("2026-11-01", 7), 5)
        self.assertEqual(s.range_count("2026-11-01", 2), 2)
        series = s.series("2026-11-01", 3)
        self.assertEqual(series, [("2026-10-30", 3), ("2026-10-31", 0), ("2026-11-01", 2)])

    def test_apps_top_and_other(self):
        s = Stats()
        for i, name in enumerate(["A", "B", "C", "D", "E", "F", "G"]):
            s.add("2026-11-01", "ş", name, 10 - i)
        s.add("2026-11-01", "ş", None, 2)
        apps = s.apps(top=3)
        self.assertEqual(apps[:3], [("A", 10), ("B", 9), ("C", 8)])
        self.assertEqual(apps[3], (alifbo_stats.OTHER, 7 + 6 + 5 + 4 + 2))

    def test_streak_and_best(self):
        s = Stats()
        for day in ("2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31"):
            s.add(day, "ş")
        s.add("2026-10-29", "ş", n=10)
        self.assertEqual(s.streak("2026-11-01"), 4)   # bugun hali yozilmagan – seriya davom etadi
        s.add("2026-11-01", "ş")
        self.assertEqual(s.streak("2026-11-01"), 5)
        self.assertEqual(s.streak("2026-11-03"), 0)
        self.assertEqual(s.best_day(), ("2026-10-29", 11))
        self.assertIsNone(Stats().best_day())

    def test_milestones(self):
        s = Stats()
        self.assertEqual(s.milestone(), 0)
        s.add("2026-11-01", "ş", n=99)
        self.assertEqual(s.milestone(), 0)
        s.add("2026-11-01", "ş")
        self.assertEqual(s.milestone(), 100)
        s.add("2026-11-01", "ş", n=12_000)
        self.assertEqual(s.milestone(), 10_000)

    def test_old_days_are_folded(self):
        s = Stats()
        s.add("2025-01-01", "ö", "Telegram", 5)
        s.add("2026-11-01", "ş", "Telegram", 1)  # yangi kun – 400 kundan eskilar yigʻiladi
        self.assertNotIn("2025-01-01", s.days)
        self.assertEqual(s.before["n"], 5)
        self.assertEqual(s.total(), 6)
        self.assertEqual(s.letters()["ö"], 5)
        self.assertEqual(dict(s.apps())["Telegram"], 6)
        self.assertEqual(s.since, "2025-01-01")

    def test_migrate_and_reset(self):
        s = Stats()
        s.migrate(total=1500, today_count=40, day="2026-11-01")
        self.assertEqual(s.total(), 1500)
        self.assertEqual(s.day_count("2026-11-01"), 40)
        self.assertEqual(s.milestone(), 1000)
        s.reset()
        self.assertTrue(s.empty())
        empty = Stats()
        empty.migrate(0, 0, "2026-11-01")
        self.assertTrue(empty.empty())

    def test_load_save_and_garbage(self):
        with tempfile.TemporaryDirectory() as user:
            s = Stats()
            s.add("2026-11-01", "ğ", "Notes", 2)
            alifbo_stats.save(s, user)
            again = alifbo_stats.load(user)
            self.assertEqual(again.to_dict(), s.to_dict())
            ac.write_runtime(alifbo_stats.STATS_FILE, {
                "days": {"bad": {"n": 1}, "2026-11-01": {"n": "x", "l": {"ş": -1, "ç": True}, "a": []},
                         "2026-11-02": {"n": 3, "l": {"ş": 3}}},
                "before": "garbage", "since": 5}, user)
            s = alifbo_stats.load(user)
            self.assertEqual(s.total(), 3)
            self.assertEqual(s.letters()["ş"], 3)
            self.assertEqual(s.since, "2026-11-01")
            self.assertTrue(os.path.isfile(ac.runtime_path(alifbo_stats.STATS_FILE, user)))


class PromoLanguageTests(unittest.TestCase):
    def test_localized_ads_and_links(self):
        data = {"links": [{"title": "Telegram", "url": "https://t.me/x", "ru": {"title": "Телеграм"}}],
                "ads": [{"title": "Salom", "text": "Matn", "url": "https://a.uz",
                         "ru": {"title": "Привет", "text": "Текст"}, "en": {"title": "Hello"}}]}
        self.assertEqual(ac.parse_promo(data)["ads"][0]["title"], "Salom")
        ru = ac.parse_promo(data, "ru")
        self.assertEqual((ru["ads"][0]["title"], ru["ads"][0]["text"]), ("Привет", "Текст"))
        self.assertEqual(ru["links"][0]["title"], "Телеграм")
        en = ac.parse_promo(data, "en")
        self.assertEqual((en["ads"][0]["title"], en["ads"][0]["text"]), ("Hello", "Matn"))


if __name__ == "__main__":
    unittest.main()
