# -*- coding: utf-8 -*-
"""alifbo_config uchun testlar.  Ishga tushirish:  python3 -m unittest -v test_alifbo_config"""
import json
import os
import tempfile
import unittest

import alifbo_config as ac


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.user = os.path.join(self._tmp.name, "user")
        self.bundle = os.path.join(self._tmp.name, "bundle")
        os.makedirs(self.bundle)

    def tearDown(self):
        self._tmp.cleanup()

    def _bundle_json(self, name, data):
        with open(os.path.join(self.bundle, name), "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def test_layers(self):
        self._bundle_json("config.json", {"hotkey": "<f9>", "backspace_undo": False})
        ac.save_user_settings({"backspace_undo": True, "apps_mode": "all"}, self.user)
        cfg = ac.load_config(self.user, [self.bundle])
        self.assertEqual(cfg["hotkey"], "<f9>")          # dastur yonidagi fayldan
        self.assertTrue(cfg["backspace_undo"])           # foydalanuvchi fayli ustun
        self.assertEqual(cfg["apps_mode"], "all")
        self.assertTrue(cfg["strip_sh_apostrophe"])      # standart qiymat

    def test_save_keeps_other_keys_and_ignores_unknown(self):
        ac.save_user_settings({"apps_mode": "all"}, self.user)
        ac.save_user_settings({"backspace_undo": False, "hotkey": "<f1>"}, self.user)
        data = ac.read_user_config(self.user)
        self.assertEqual(data, {"apps_mode": "all", "backspace_undo": False})

    def test_broken_user_file_is_ignored(self):
        os.makedirs(self.user)
        with open(ac.user_config_path(self.user), "w") as fh:
            fh.write("{yarim")
        self.assertEqual(ac.load_config(self.user, [self.bundle])["apps_mode"], "list")

    def test_app_version(self):
        self.assertEqual(ac.app_version([self.bundle]), "dev")
        with open(os.path.join(self.bundle, "app_version.txt"), "w") as fh:
            fh.write("1.2.3\n")
        self.assertEqual(ac.app_version([self.bundle]), "1.2.3")


class AppsTests(unittest.TestCase):
    def test_defaults_per_platform(self):
        mac = {a["id"] for a in ac.default_apps("darwin")}
        win = {a["id"] for a in ac.default_apps("win32")}
        self.assertIn("ru.keepcoder.Telegram", mac)
        self.assertIn("com.microsoft.edgemac", mac)
        self.assertIn("telegram.exe", win)
        self.assertIn("msedge.exe", win)
        self.assertEqual(ac.default_apps("linux"), [])

    def test_allowed(self):
        cfg = dict(ac.DEFAULT_CONFIG)
        ids = ac.allowed_ids(cfg, "win32")
        self.assertTrue(ac.app_allowed("Telegram.EXE", ids))   # katta-kichik harf farqi yoʻq
        self.assertFalse(ac.app_allowed("cmd.exe", ids))
        self.assertTrue(ac.app_allowed(None, ids))             # aniqlab boʻlmasa – ishlaydi
        cfg["apps_mode"] = "all"
        self.assertTrue(ac.app_allowed("cmd.exe", ac.allowed_ids(cfg, "win32")))

    def test_user_list(self):
        cfg = dict(ac.DEFAULT_CONFIG, apps=[{"id": "code.exe", "name": "VS Code"}, {"name": "id yoʻq"}, "x"])
        self.assertEqual(ac.config_apps(cfg, "win32"), [{"id": "code.exe", "name": "VS Code"}])
        ids = ac.allowed_ids(cfg, "win32")
        self.assertTrue(ac.app_allowed("code.exe", ids))
        self.assertFalse(ac.app_allowed("telegram.exe", ids))  # standart roʻyxat almashtirildi


class PromoTests(unittest.TestCase):
    def test_parse_filters_bad_entries(self):
        promo = ac.parse_promo({
            "links": [
                {"title": "Instagram", "url": "https://instagram.com/x"},
                {"title": "YouTube", "url": ""},                    # hali toʻldirilmagan
                {"title": "Yomon", "url": "file:///etc/passwd"},
                {"title": "", "url": "https://t.me/x"},
                "satr",
            ],
            "ads": [
                {"title": "Kurs", "text": "Matn", "url": "https://example.uz"},
                {"title": "Havolasiz", "url": "javascript:alert(1)"},
                {"text": "sarlavhasiz"},
            ],
        })
        self.assertEqual(promo["links"], [{"title": "Instagram", "url": "https://instagram.com/x"}])
        self.assertEqual([a["title"] for a in promo["ads"]], ["Kurs", "Havolasiz"])
        self.assertEqual(promo["ads"][0]["button"], "Batafsil")
        self.assertEqual(promo["ads"][1]["url"], "")

    def test_parse_garbage(self):
        self.assertEqual(ac.parse_promo(None), {"links": [], "ads": []})
        self.assertEqual(ac.parse_promo({"links": "x", "ads": 5}), {"links": [], "ads": []})

    def test_load_prefers_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = os.path.join(tmp, "b")
            user = os.path.join(tmp, "u")
            os.makedirs(bundle)
            os.makedirs(user)
            with open(os.path.join(bundle, "promo.json"), "w") as fh:
                json.dump({"links": [{"title": "Ichki", "url": "https://a.uz"}]}, fh)
            self.assertEqual(ac.load_promo(user, [bundle])["links"][0]["title"], "Ichki")
            with open(os.path.join(user, "promo-cache.json"), "w") as fh:
                json.dump({"links": [{"title": "Kesh", "url": "https://b.uz"}]}, fh)
            self.assertEqual(ac.load_promo(user, [bundle])["links"][0]["title"], "Kesh")

    def test_repo_promo_json_is_valid(self):
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "promo.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertIsInstance(ac.parse_promo(data), dict)


if __name__ == "__main__":
    unittest.main()
