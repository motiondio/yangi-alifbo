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


class PanelHelpersTests(unittest.TestCase):
    def test_set_app_enabled_adds_and_removes(self):
        cfg = dict(ac.DEFAULT_CONFIG)
        apps = ac.set_app_enabled(cfg, "code.exe", "VS Code", True, "win32")
        self.assertIn({"id": "code.exe", "name": "VS Code"}, apps)
        self.assertIn("telegram.exe", {a["id"] for a in apps})     # standart roʻyxat saqlanadi
        cfg["apps"] = apps
        apps = ac.set_app_enabled(cfg, "TELEGRAM.EXE", None, False, "win32")
        self.assertNotIn("telegram.exe", {a["id"] for a in apps})  # katta-kichik harf farqi yoʻq
        cfg["apps"] = ac.set_app_enabled(cfg, "code.exe", None, True, "win32")
        self.assertEqual([a["id"] for a in cfg["apps"]].count("code.exe"), 1)  # takrorlanmaydi

    def test_runtime_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(ac.read_runtime(ac.STATE_FILE, tmp), {})
            ac.write_runtime(ac.STATE_FILE, {"enabled": False, "today": 3}, tmp)
            self.assertEqual(ac.read_runtime(ac.STATE_FILE, tmp), {"enabled": False, "today": 3})


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



class UpdateTests(unittest.TestCase):
    REL = "https://github.com/motiondio/yangi-alifbo/releases"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.user = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _api(self, tag="yangi-alifbo-v1.0.7", **extra):
        names = ["YangiAlifbo-macos-apple-silicon.pkg", "YangiAlifbo-macos-intel.pkg",
                 "YangiAlifbo-Setup-windows-x64.exe", "YangiAlifbo-windows-x64.exe"]
        data = {"tag_name": tag, "html_url": f"{self.REL}/tag/{tag}", "draft": False, "prerelease": False,
                "assets": [{"name": n, "browser_download_url": f"{self.REL}/download/{tag}/{n}"} for n in names]
                + [{"name": "YangiAlifbo-windows-x64-portable.zip",
                    "browser_download_url": "https://evil.example/x.zip"}]}
        data.update(extra)
        return data

    def test_parse_version(self):
        self.assertEqual(ac.parse_version("yangi-alifbo-v1.0.6"), (1, 0, 6))
        self.assertEqual(ac.parse_version("1.10.0"), (1, 10, 0))
        self.assertEqual(ac.parse_version("v2.1"), (2, 1, 0))
        self.assertGreater(ac.parse_version("1.0.10"), ac.parse_version("1.0.9"))
        for bad in ("dev", "", None, 106):
            self.assertIsNone(ac.parse_version(bad))

    def test_release_asset(self):
        self.assertEqual(ac.release_asset("darwin", "arm64"), "YangiAlifbo-macos-apple-silicon.pkg")
        self.assertEqual(ac.release_asset("darwin", "x86_64"), "YangiAlifbo-macos-intel.pkg")
        self.assertEqual(ac.release_asset("win32", kind="setup"), "YangiAlifbo-Setup-windows-x64.exe")
        self.assertEqual(ac.release_asset("win32", kind="exe"), "YangiAlifbo-windows-x64.exe")
        self.assertEqual(ac.release_asset("win32", kind="portable"), "YangiAlifbo-windows-x64-portable.zip")
        self.assertIsNone(ac.release_asset("linux"))

    def test_parse_release(self):
        rel = ac.parse_release(self._api())
        self.assertEqual(rel["version"], "1.0.7")
        self.assertEqual(rel["page"], f"{self.REL}/tag/yangi-alifbo-v1.0.7")
        self.assertIn("YangiAlifbo-windows-x64.exe", rel["assets"])
        self.assertNotIn("YangiAlifbo-windows-x64-portable.zip", rel["assets"])  # begona sayt
        self.assertIsNone(ac.parse_release(self._api(draft=True)))
        self.assertIsNone(ac.parse_release(self._api(prerelease=True)))
        self.assertIsNone(ac.parse_release(self._api(tag="nightly")))
        self.assertIsNone(ac.parse_release("garbage"))

    def test_release_from_location(self):
        rel = ac.release_from_location(f"{self.REL}/tag/yangi-alifbo-v1.0.7")
        self.assertEqual(rel["version"], "1.0.7")
        self.assertEqual(rel["assets"]["YangiAlifbo-macos-intel.pkg"],
                         f"{self.REL}/download/yangi-alifbo-v1.0.7/YangiAlifbo-macos-intel.pkg")
        self.assertIsNone(ac.release_from_location("https://evil.example/releases/tag/v9.9.9"))
        self.assertIsNone(ac.release_from_location(None))

    def test_update_info(self):
        self.assertIsNone(ac.update_info("1.0.6", self.user))  # hali tekshirilmagan
        ac.write_runtime(ac.UPDATE_FILE, ac.parse_release(self._api()), self.user)
        info = ac.update_info("1.0.6", self.user, platform="darwin", machine="arm64")
        self.assertEqual(info["version"], "1.0.7")
        self.assertTrue(info["url"].endswith("/yangi-alifbo-v1.0.7/YangiAlifbo-macos-apple-silicon.pkg"))
        info = ac.update_info("1.0.6", self.user, platform="win32", kind="exe")
        self.assertTrue(info["url"].endswith("/YangiAlifbo-windows-x64.exe"))
        # mos fayl yoʻq (begona havola tashlab yuborilgan) – Release sahifasi
        info = ac.update_info("1.0.6", self.user, platform="win32", kind="portable")
        self.assertEqual(info["url"], info["page"])
        self.assertIsNone(ac.update_info("1.0.7", self.user))
        self.assertIsNone(ac.update_info("1.1.0", self.user))
        self.assertIsNone(ac.update_info("dev", self.user))

    def test_update_due(self):
        self.assertTrue(ac.update_due(self.user))
        ac.write_runtime(ac.UPDATE_FILE, {"checked": 1000.0}, self.user)
        self.assertFalse(ac.update_due(self.user, now=1000.0 + 3600))
        self.assertTrue(ac.update_due(self.user, now=1000.0 + ac.UPDATE_EVERY_S + 1))
        self.assertTrue(ac.update_due(self.user, now=500.0))  # soat orqaga surilgan

    def test_fetch_falls_back_to_redirect(self):
        calls = []
        api, redirect = ac._release_from_api, ac._release_from_redirect

        def failing_api(timeout):
            calls.append("api")
            raise OSError("HTTP 403 rate limit")

        def fake_redirect(timeout):
            calls.append("redirect")
            return ac.release_from_location(f"{self.REL}/tag/yangi-alifbo-v1.0.7")
        ac._release_from_api, ac._release_from_redirect = failing_api, fake_redirect
        try:
            rel = ac.fetch_update(self.user)
        finally:
            ac._release_from_api, ac._release_from_redirect = api, redirect
        self.assertEqual(calls, ["api", "redirect"])
        self.assertEqual(rel["version"], "1.0.7")
        self.assertFalse(ac.update_due(self.user))
        self.assertEqual(ac.update_info("1.0.6", self.user)["version"], "1.0.7")

    def test_check_updates_setting(self):
        self.assertTrue(ac.DEFAULT_CONFIG["check_updates"])
        ac.save_user_settings({"check_updates": False}, self.user)
        self.assertFalse(ac.load_config(self.user, [])["check_updates"])


if __name__ == "__main__":
    unittest.main()
