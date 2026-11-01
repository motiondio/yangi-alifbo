# -*- coding: utf-8 -*-
"""
Sozlamalar (config.json), dasturlar roʻyxati, havolalar/reklama (promo.json) va yangi versiya.

Tizimga va GUI ga bogʻliq emas: asosiy dastur (yangi_alifbo.py) ham, panel va sozlamalar oynasi
(alifbo_ui.py) ham shu moduldan foydalanadi, testlar ham shuni tekshiradi.

Sozlamalar uch qatlamdan yigʻiladi (keyingisi oldingisini bosadi):
    DEFAULT_CONFIG  →  dastur yonidagi config.json  →  foydalanuvchi papkasidagi config.json
Sozlamalar oynasi faqat oxirgisiga – foydalanuvchi fayliga – yozadi.
"""
from __future__ import annotations

import json
import os
import platform as _platform
import re
import sys
import tempfile
import time
from typing import Dict, List, Optional, Set

APP_NAME = "Yangi Alifbo"

DEFAULT_CONFIG = {
    # Yoqish/oʻchirish tezkor tugmasi (pynput formati).  Mac: Ctrl+Option+U
    "hotkey": "<ctrl>+<alt>+u",
    # Dastur ishga tushganda almashtirish yoqilgan boʻlsinmi
    "enabled_on_start": True,
    # Almashtirishdan soʻng darhol Backspace bosilsa asl yozuvni qaytarish
    "backspace_undo": True,
    # "s'h" → "sh" (ş emas).  Is'hoq → Ishoq
    "strip_sh_apostrophe": True,
    # Tutuq belgisi: null – tegilmaydi;  "ʼ" – harfdan keyingi ' belgisi ʼ (U+02BC) ga almashadi
    "tutuq_belgisi": None,
    # Tizim trayida belgi koʻrsatish (pystray + pillow oʻrnatilgan boʻlsa)
    "tray": True,
    # "list" – faqat roʻyxatdagi dasturlarda ishlaydi;  "all" – hamma dasturlarda
    "apps_mode": "list",
    # Dasturlar roʻyxati: [{"id": ..., "name": ...}].  null – standart roʻyxat (pastda)
    "apps": None,
    # Kuniga bir marta GitHub'dan eng soʻnggi versiya raqamini soʻrash
    "check_updates": True,
}

# Sozlamalar oynasi oʻzgartira oladigan kalitlar
EDITABLE_KEYS = ("enabled_on_start", "backspace_undo", "strip_sh_apostrophe",
                 "tutuq_belgisi", "apps_mode", "apps", "check_updates")

# ---------------------------------------------------------------- dasturlar
# Identifikator: macOS – bundle id, Windows – .exe nomi (kichik harflarda).
MAC_DEFAULT_APPS = [
    ("ru.keepcoder.Telegram", "Telegram"),
    ("org.telegram.desktop", "Telegram Desktop"),
    ("net.whatsapp.WhatsApp", "WhatsApp"),
    ("com.viber.osx", "Viber"),
    ("com.apple.MobileSMS", "Messages"),
    ("com.apple.mail", "Mail"),
    ("com.microsoft.Word", "Microsoft Word"),
    ("com.microsoft.Excel", "Microsoft Excel"),
    ("com.microsoft.Powerpoint", "Microsoft PowerPoint"),
    ("com.microsoft.Outlook", "Microsoft Outlook"),
    ("com.apple.iWork.Pages", "Pages"),
    ("com.apple.iWork.Numbers", "Numbers"),
    ("com.apple.iWork.Keynote", "Keynote"),
    ("com.apple.Notes", "Notes"),
    ("com.apple.TextEdit", "TextEdit"),
    ("com.apple.Safari", "Safari"),
    ("com.google.Chrome", "Google Chrome"),
    ("com.microsoft.edgemac", "Microsoft Edge"),
    ("org.mozilla.firefox", "Firefox"),
    ("ru.yandex.desktop.yandex-browser", "Yandex Browser"),
    ("com.operasoftware.Opera", "Opera"),
    ("com.brave.Browser", "Brave"),
    ("company.thebrowser.Browser", "Arc"),
    ("com.tinyspeck.slackmacgap", "Slack"),
    ("com.hnc.Discord", "Discord"),
    ("notion.id", "Notion"),
]
WIN_DEFAULT_APPS = [
    ("telegram.exe", "Telegram"),
    ("whatsapp.exe", "WhatsApp"),
    ("whatsapp.root.exe", "WhatsApp"),
    ("viber.exe", "Viber"),
    ("winword.exe", "Microsoft Word"),
    ("excel.exe", "Microsoft Excel"),
    ("powerpnt.exe", "Microsoft PowerPoint"),
    ("outlook.exe", "Microsoft Outlook"),
    ("olk.exe", "Outlook (yangi)"),
    ("onenote.exe", "OneNote"),
    ("notepad.exe", "Bloknot"),
    ("wordpad.exe", "WordPad"),
    ("msedge.exe", "Microsoft Edge"),
    ("chrome.exe", "Google Chrome"),
    ("firefox.exe", "Firefox"),
    ("browser.exe", "Yandex Browser"),
    ("opera.exe", "Opera"),
    ("brave.exe", "Brave"),
    ("slack.exe", "Slack"),
    ("discord.exe", "Discord"),
    ("ms-teams.exe", "Microsoft Teams"),
    ("notion.exe", "Notion"),
]


def default_apps(platform: str = sys.platform) -> List[Dict[str, str]]:
    pairs = (WIN_DEFAULT_APPS if platform.startswith("win")
             else MAC_DEFAULT_APPS if platform == "darwin" else [])
    return [{"id": i, "name": n} for i, n in pairs]


def config_apps(cfg: dict, platform: str = sys.platform) -> List[Dict[str, str]]:
    """Joriy dasturlar roʻyxati: foydalanuvchiniki yoki standart."""
    apps = cfg.get("apps")
    if not isinstance(apps, list):
        return default_apps(platform)
    out = []
    for a in apps:
        if isinstance(a, dict) and isinstance(a.get("id"), str) and a["id"]:
            out.append({"id": a["id"], "name": str(a.get("name") or a["id"])})
    return out


def allowed_ids(cfg: dict, platform: str = sys.platform) -> Optional[Set[str]]:
    """Ruxsat berilgan dasturlar (kichik harflarda); None – hamma dasturlarda ishlaydi."""
    if cfg.get("apps_mode") == "all":
        return None
    return {a["id"].lower() for a in config_apps(cfg, platform)}


def app_allowed(app_id: Optional[str], ids: Optional[Set[str]]) -> bool:
    # Dasturni aniqlab boʻlmasa – ishlayveramiz (eski xatti-harakat)
    return ids is None or app_id is None or app_id.lower() in ids


def set_app_enabled(cfg: dict, app_id: str, name: Optional[str], enabled: bool,
                    platform: str = sys.platform) -> List[Dict[str, str]]:
    """Dasturni roʻyxatga qoʻshadi yoki olib tashlaydi – yangi roʻyxatni qaytaradi (panel uchun)."""
    apps = [a for a in config_apps(cfg, platform) if a["id"].lower() != app_id.lower()]
    if enabled:
        apps.append({"id": app_id, "name": name or app_id})
    return apps


# ------------------------------------------------------------------- fayllar
def user_config_dir() -> str:
    if sys.platform.startswith("win"):
        return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME)
    if sys.platform == "darwin":
        return os.path.expanduser(f"~/Library/Application Support/{APP_NAME}")
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "yangi-alifbo")


def user_config_path(user_dir: Optional[str] = None) -> str:
    return os.path.join(user_dir or user_config_dir(), "config.json")


def bundled_dirs() -> List[str]:
    """Dastur bilan birga keladigan fayllar qidiriladigan papkalar (birinchisi ustun)."""
    if getattr(sys, "frozen", False):  # PyInstaller bilan yigʻilgan
        dirs = [os.path.dirname(os.path.abspath(sys.executable))]
    else:
        dirs = [os.path.dirname(os.path.abspath(__file__))]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs.append(meipass)
    return dirs


def find_bundled(name: str, dirs: Optional[List[str]]) -> Optional[str]:
    for d in dirs if dirs is not None else bundled_dirs():
        path = os.path.join(d, name)
        if os.path.isfile(path):
            return path
    return None


def _read_json(path: Optional[str]) -> Optional[dict]:
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError) as exc:
        print(f"{os.path.basename(path)} oʻqilmadi ({exc}); eʼtiborsiz qoldirildi.")
        return None


def _write_json(path: str, data: dict) -> None:
    """Atomik yozish: yarim yozilgan fayl asosiy dasturga tushib qolmasin."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def read_user_config(user_dir: Optional[str] = None) -> dict:
    return _read_json(user_config_path(user_dir)) or {}


def load_config(user_dir: Optional[str] = None, dirs: Optional[List[str]] = None) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(_read_json(find_bundled("config.json", dirs)) or {})
    cfg.update(read_user_config(user_dir))
    return cfg


def save_user_settings(changes: dict, user_dir: Optional[str] = None) -> None:
    """Faqat berilgan kalitlarni foydalanuvchi fayliga yozadi (qolganlari saqlanadi)."""
    data = read_user_config(user_dir)
    data.update({k: v for k, v in changes.items() if k in EDITABLE_KEYS})
    _write_json(user_config_path(user_dir), data)


# ------------------------------------------- asosiy dastur ↔ oyna aloqasi
# Tarmoq porti ochilmaydi (klaviatura kuzatuvchi dastur port ochsa, antiviruslarga shubhali):
#   state.json    asosiy dastur → oyna: yoqilganmi, oxirgi faol dastur, hisoblagich
#   control.json  oyna → asosiy dastur: yoqish/oʻchirish, chiqish
#   ui.json       ikkinchi nusxa → ishlab turgan oyna jarayoni: "panelni / sozlamalarni koʻrsat"
#   update.json   oyna yoki fon tekshiruvi → hammaga: GitHub'dagi eng soʻnggi versiya
STATE_FILE = "state.json"
CONTROL_FILE = "control.json"
UI_REQUEST_FILE = "ui.json"
UPDATE_FILE = "update.json"


def runtime_path(name: str, user_dir: Optional[str] = None) -> str:
    return os.path.join(user_dir or user_config_dir(), name)


def read_runtime(name: str, user_dir: Optional[str] = None) -> dict:
    return _read_json(runtime_path(name, user_dir)) or {}


def write_runtime(name: str, data: dict, user_dir: Optional[str] = None) -> None:
    _write_json(runtime_path(name, user_dir), data)


def app_version(dirs: Optional[List[str]] = None) -> str:
    """CI yozgan app_version.txt dan; manbadan ishga tushirilganda – "dev"."""
    path = find_bundled("app_version.txt", dirs)
    if path:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read().strip() or "dev"
        except OSError:
            pass
    return "dev"


# ------------------------------------------------------- havolalar/reklama
# Yangi versiya chiqarmasdan oʻzgartirish uchun: GitHub'da promo.json ni tahrirlang.
PROMO_URL = "https://raw.githubusercontent.com/motiondio/yangi-alifbo/main/promo.json"
_PROMO_CACHE = "promo-cache.json"


def _url_ok(url) -> bool:
    # Faqat https – masofadagi fayl file://, javascript: kabi havolalarni ochtira olmasin
    return isinstance(url, str) and url.startswith("https://") and len(url) <= 2000


def _text(value, limit: int) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _items(value) -> list:
    return value if isinstance(value, list) else []


def parse_promo(data) -> dict:
    """promo.json ni tekshiradi: notoʻgʻri yoki boʻsh havolali yozuvlar tashlab yuboriladi."""
    out = {"links": [], "ads": []}
    if not isinstance(data, dict):
        return out
    for item in _items(data.get("links")):
        if isinstance(item, dict) and _url_ok(item.get("url")) and _text(item.get("title"), 40):
            out["links"].append({"title": _text(item["title"], 40), "url": item["url"]})
    for item in _items(data.get("ads")):
        if not isinstance(item, dict) or not _text(item.get("title"), 80):
            continue
        ad = {"title": _text(item["title"], 80), "text": _text(item.get("text"), 400),
              "button": _text(item.get("button"), 30) or "Batafsil", "url": ""}
        if _url_ok(item.get("url")):
            ad["url"] = item["url"]
        out["ads"].append(ad)
    out["links"] = out["links"][:8]
    out["ads"] = out["ads"][:3]
    return out


def load_promo(user_dir: Optional[str] = None, dirs: Optional[List[str]] = None) -> dict:
    """Internetsiz: avval oxirgi yuklab olingan nusxa, boʻlmasa dastur ichidagi promo.json."""
    cached = _read_json(os.path.join(user_dir or user_config_dir(), _PROMO_CACHE))
    if cached is not None:
        return parse_promo(cached)
    return parse_promo(_read_json(find_bundled("promo.json", dirs)))


def _ssl_context():
    import ssl
    try:
        import certifi  # yigʻilgan macOS ilovasida tizim sertifikatlari topilmaydi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _user_agent() -> str:
    return f"{APP_NAME}/{app_version()}"


def fetch_promo(user_dir: Optional[str] = None, url: str = PROMO_URL,
                timeout: float = 6.0) -> Optional[dict]:
    """GitHub'dan yangi promo.json ni yuklab, keshga yozadi.  Xato boʻlsa – None.
    Faqat oyna jarayoni chaqiradi: klaviatura kuzatuvchi jarayon internetga ulanmaydi."""
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _user_agent()})
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            data = json.loads(resp.read(256 * 1024).decode("utf-8"))
        if not isinstance(data, dict):
            return None
        _write_json(os.path.join(user_dir or user_config_dir(), _PROMO_CACHE), data)
        return parse_promo(data)
    except Exception as exc:
        print(f"promo.json yuklanmadi: {exc!r}")
        return None


# ------------------------------------------------------------- yangi versiya
# Faqat versiya raqami soʻraladi, hech qanday maʼlumot yuborilmaydi.  Klaviatura kuzatuvchi
# jarayon internetga ulanmaydi: tekshiruvni oyna jarayoni yoki alohida fon jarayoni
# (yangi_alifbo --update-check) qiladi va natijani update.json ga yozadi.
REPO_URL = "https://github.com/motiondio/yangi-alifbo"
RELEASES_URL = REPO_URL + "/releases"
RELEASES_API = "https://api.github.com/repos/motiondio/yangi-alifbo/releases/latest"
UPDATE_EVERY_S = 20 * 3600   # "kuniga bir marta" – har kuni bir xil soatda ochilsa ham
MAC_ASSETS = {"arm64": "YangiAlifbo-macos-apple-silicon.pkg", "x86_64": "YangiAlifbo-macos-intel.pkg"}
WIN_ASSETS = {"setup": "YangiAlifbo-Setup-windows-x64.exe", "exe": "YangiAlifbo-windows-x64.exe",
              "portable": "YangiAlifbo-windows-x64-portable.zip"}


def parse_version(value) -> Optional[tuple]:
    """"yangi-alifbo-v1.0.6", "1.0.6", "v1.2" → (1, 0, 6) / (1, 2, 0);  "dev" → None."""
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", value) if isinstance(value, str) else None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)) if m else None


def _gh_url(url) -> bool:
    # Yuklab olish havolasi faqat oʻz repomizga olib borsin
    return _url_ok(url) and url.startswith(REPO_URL + "/")


def install_kind() -> str:
    """Dastur qanday oʻrnatilgan – yangi versiyaning aynan shu turi taklif qilinadi.
    Windows: "setup" (oʻrnatuvchi), "exe" (bitta fayl), "portable" (papka);  macOS: "pkg"."""
    if sys.platform == "darwin":
        return "pkg"
    if not sys.platform.startswith("win") or not getattr(sys, "frozen", False):
        return "setup"
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    meipass = os.path.abspath(getattr(sys, "_MEIPASS", exe_dir))
    try:
        onefile = os.path.commonpath([meipass, exe_dir]) != exe_dir  # %TEMP%\_MEIxxxx
    except ValueError:  # boshqa disk
        onefile = True
    if onefile:
        return "exe"
    return "setup" if os.path.isfile(os.path.join(exe_dir, "unins000.exe")) else "portable"


def release_asset(platform: str = sys.platform, machine: Optional[str] = None,
                  kind: Optional[str] = None) -> Optional[str]:
    """Shu kompyuterga mos fayl nomi (GitHub Release'dagi)."""
    if platform == "darwin":
        machine = (machine or _platform.machine()).lower()
        return MAC_ASSETS["arm64" if machine in ("arm64", "aarch64") else "x86_64"]
    if platform.startswith("win"):
        return WIN_ASSETS.get(kind if kind is not None else install_kind(), WIN_ASSETS["setup"])
    return None


def parse_release(data) -> Optional[dict]:
    """GitHub API javobi (releases/latest) → {"version", "tag", "page", "assets": {nom: havola}}."""
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    tag = data.get("tag_name")
    version = parse_version(tag)
    if version is None:
        return None
    page = data.get("html_url")
    assets = {}
    for item in _items(data.get("assets")):
        if isinstance(item, dict) and isinstance(item.get("name"), str) \
                and _gh_url(item.get("browser_download_url")):
            assets[item["name"]] = item["browser_download_url"]
    return {"version": "%d.%d.%d" % version, "tag": tag,
            "page": page if _gh_url(page) else f"{RELEASES_URL}/tag/{tag}", "assets": assets}


def release_from_location(location) -> Optional[dict]:
    """Zaxira yoʻl: github.com/…/releases/latest yoʻnaltiradigan manzildan (…/releases/tag/<tag>).
    API soatiga 60 soʻrov bilan cheklangan – bitta IP dagi koʻp foydalanuvchida tugab qolishi mumkin."""
    prefix = RELEASES_URL + "/tag/"
    if not isinstance(location, str) or not location.startswith(prefix):
        return None
    tag = location[len(prefix):].split("?")[0].strip("/")
    names = list(MAC_ASSETS.values()) + list(WIN_ASSETS.values())
    return parse_release({"tag_name": tag, "html_url": location, "assets": [
        {"name": n, "browser_download_url": f"{RELEASES_URL}/download/{tag}/{n}"} for n in names]})


def _release_from_api(timeout: float) -> Optional[dict]:
    import urllib.request
    req = urllib.request.Request(RELEASES_API, headers={
        "User-Agent": _user_agent(), "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        return parse_release(json.loads(resp.read(1024 * 1024).decode("utf-8")))


def _release_from_redirect(timeout: float) -> Optional[dict]:
    import urllib.error
    import urllib.request

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None  # Location sarlavhasining oʻzi kerak

    opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=_ssl_context()))
    req = urllib.request.Request(RELEASES_URL + "/latest", method="HEAD",
                                 headers={"User-Agent": _user_agent()})
    try:
        with opener.open(req, timeout=timeout):
            return None
    except urllib.error.HTTPError as exc:
        return release_from_location(exc.headers.get("Location")) if exc.code in (301, 302, 303, 307) else None


def fetch_update(user_dir: Optional[str] = None, timeout: float = 8.0) -> Optional[dict]:
    """Eng soʻnggi versiyani aniqlab, update.json ga yozadi.  Internet boʻlmasa – None."""
    release = None
    for source in (_release_from_api, _release_from_redirect):
        try:
            release = source(timeout)
        except Exception as exc:
            print(f"Yangi versiya tekshirilmadi ({source.__name__}): {exc!r}")
        if release is not None:
            break
    if release is None:
        return None
    release["checked"] = time.time()
    write_runtime(UPDATE_FILE, release, user_dir)
    return release


def update_due(user_dir: Optional[str] = None, now: Optional[float] = None) -> bool:
    checked = read_runtime(UPDATE_FILE, user_dir).get("checked")
    now = time.time() if now is None else now
    return not isinstance(checked, (int, float)) or not 0 <= now - checked < UPDATE_EVERY_S


def update_info(current: Optional[str] = None, user_dir: Optional[str] = None,
                platform: str = sys.platform, machine: Optional[str] = None,
                kind: Optional[str] = None) -> Optional[dict]:
    """Oʻrnatilganidan yangi versiya bormi (update.json boʻyicha, internetsiz).
    Bor boʻlsa – {"version", "url" (shu kompyuterga mos fayl), "page" (Release sahifasi)}."""
    cur = parse_version(app_version() if current is None else current)
    data = read_runtime(UPDATE_FILE, user_dir)
    latest = parse_version(data.get("version"))
    if cur is None or latest is None or latest <= cur:
        return None
    page = data["page"] if _gh_url(data.get("page")) else RELEASES_URL + "/latest"
    assets = data.get("assets") if isinstance(data.get("assets"), dict) else {}
    url = assets.get(release_asset(platform, machine, kind) or "")
    return {"version": "%d.%d.%d" % latest, "url": url if _gh_url(url) else page, "page": page}
