#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yangi Alifbo – yangi oʻzbek lotin alifbosi (2026) uchun avtomatik harf toʻgʻirlagich.

Windows va macOS da (Linux/X11 da ham) ishlaydi.  Siz odatdagidek
"o'zbek", "g'isht", "shahar", "choy" deb terasiz – dastur harflarni
istalgan dasturda (Word, Telegram, brauzer...) darhol ö, ğ, ş, ç ga almashtiradi.

Ishga tushirish:
    pip install pynput            (ixtiyoriy: pip install pystray pillow – tray belgisi uchun)
    python yangi_alifbo.py

Tezkor tugma (yoqish/oʻchirish):  Ctrl+Alt+U   (config.json da oʻzgartirish mumkin)
Almashtirishni bekor qilish:      almashgandan keyin darhol Backspace
"s" va "h" ni alohida qoldirish:  s'h  deb tering  (Is'hoq → Ishoq)

macOS da yigʻilgan .app:
  * Downloads/zip ichidan ochilsa, oʻzini Applications ga oʻrnatishni taklif qiladi
    (aks holda macOS ruxsatlarni saqlab qolmaydi – "App Translocation").
  * Accessibility va Input Monitoring ruxsatini soʻraydi va berilguncha kutadi.
"""
from __future__ import annotations

import argparse
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time

APP_NAME = "Yangi Alifbo"
BUNDLE_ID = "uz.yangialifbo.app"
IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
IS_FROZEN = bool(getattr(sys, "frozen", False))  # PyInstaller bilan yigʻilgan


def _utf8_streams() -> None:
    """Windows'da stdout/stderr quvur (pipe) boʻlsa cp1252 ishlatiladi va "ʻ ş ğ" kabi
    belgilar UnicodeEncodeError beradi – bu yigʻilgan .exe da xato oynasi sifatida chiqadi.
    Shuning uchun oqimlarni UTF-8 ga oʻtkazamiz (PyInstaller NullWriter/None boʻlsa – eʼtiborsiz)."""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_utf8_streams()

try:
    from pynput import keyboard, mouse
    from pynput.keyboard import Key, KeyCode
except Exception as exc:  # pragma: no cover  (ImportError yoki Linux'da DISPLAY yoʻqligi)
    print(f"pynput yuklanmadi: {exc}\nOʻrnating:  pip install pynput", file=sys.stderr)
    sys.exit(1)

from alifbo_apps import frontmost_app, frontmost_app_id
from alifbo_config import (CONTROL_FILE, STATE_FILE, UI_REQUEST_FILE, UPDATE_FILE, allowed_ids,
                           app_allowed, app_version, fetch_update, find_bundled, load_config,
                           load_promo, parse_version, read_runtime, runtime_path, update_due,
                           update_info, user_config_path, write_runtime)
from alifbo_core import TUTUQ, Engine

import alifbo_i18n as i18n
import alifbo_stats
from alifbo_i18n import t

_MODIFIERS = {
    Key.ctrl, Key.ctrl_l, Key.ctrl_r,
    Key.alt, Key.alt_l, Key.alt_r, Key.alt_gr,
    Key.cmd, Key.cmd_l, Key.cmd_r,
}
# Bu tugmalar kontekstni oʻzgartirmaydi (buferni tozalamaymiz)
_IGNORED = {Key.shift, Key.shift_l, Key.shift_r, Key.caps_lock}


# ----------------------------------------------------------------- dialog
def _as_str(s: str) -> str:
    """AppleScript satri uchun qochirish."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def alert(message: str, *, buttons=("OK",), default: str | None = None,
          icon: str = "caution", title: str = APP_NAME) -> str:
    """Foydalanuvchiga xabar koʻrsatadi va bosilgan tugma nomini qaytaradi.

    Yigʻilgan .app da – macOS dialogi, yigʻilgan .exe da – MessageBox,
    konsol rejimida – oddiy chop etish (standart tugma qaytariladi)."""
    print(message)
    default = default or buttons[-1]
    if IS_FROZEN and IS_MAC:
        btns = ", ".join('"' + _as_str(b) + '"' for b in buttons)
        script = (
            f'display dialog "{_as_str(message)}" with title "{_as_str(title)}" '
            f'buttons {{{btns}}} default button "{_as_str(default)}" with icon {icon}'
        )
        try:
            out = subprocess.run(["osascript", "-e", script], capture_output=True,
                                 text=True, timeout=900)
            m = re.search(r"button returned:(.*)", out.stdout or "")
            if m:
                return m.group(1).strip()
        except Exception:
            pass
        return default
    if IS_FROZEN and IS_WIN:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)
        except Exception:
            pass
    return default


# ------------------------------------------------------- bitta nusxa
_instance_lock = None


def acquire_single_instance(name: str = "") -> bool:
    """Dastur ikki marta ochilsa harflar ikki marta almashadi – shunga yoʻl qoʻymaymiz.
    name – boshqa qulf (masalan "Settings": sozlamalar oynasi ham bitta boʻlsin)."""
    global _instance_lock
    try:
        if IS_WIN:
            import ctypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            _instance_lock = kernel32.CreateMutexW(None, False, f"Local\\YangiAlifbo{name}SingleInstance")
            return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS
        import fcntl
        suffix = f"_{name.lower()}" if name else ""
        path = os.path.join(os.path.expanduser("~"), f".yangi_alifbo{suffix}.lock")
        fh = open(path, "w")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        _instance_lock = fh  # fayl ochiq turishi kerak
        return True
    except Exception:
        return True  # tekshirib boʻlmasa – ishlayveramiz


# ------------------------------------------------------- macOS: oʻrnatish
def _mac_bundle_path() -> str | None:
    """Yigʻilgan .app ning yoʻli (…/Yangi Alifbo.app), aks holda None."""
    if not (IS_MAC and IS_FROZEN):
        return None
    m = re.match(r"^(.*?\.app)/Contents/MacOS/", os.path.abspath(sys.executable))
    return m.group(1) if m else None


def macos_self_install() -> bool:
    """Ilova Downloads/zip ichidan yoki macOS'ning vaqtinchalik "App Translocation"
    papkasidan ochilgan boʻlsa – Applications ga koʻchirib, karantin belgisini olib
    tashlab, yangi nusxani ishga tushiradi.  True qaytsa, joriy jarayon chiqishi kerak.

    Sabab: translokatsiya qilingan ilova har safar boshqa (tasodifiy) yoʻldan ishga
    tushadi, shuning uchun berilgan Accessibility/Input Monitoring ruxsati keyingi
    ochilishda tanilmaydi va qayta-qayta soʻralaveradi."""
    bundle = _mac_bundle_path()
    if not bundle:
        return False
    home_apps = os.path.expanduser("~/Applications")
    translocated = "/AppTranslocation/" in bundle
    in_apps = bundle.startswith("/Applications/") or bundle.startswith(home_apps + "/")
    if in_apps and not translocated:
        # karantin belgisi qolgan boʻlsa tozalaymiz – keyingi safar translokatsiya boʻlmasin
        subprocess.run(["xattr", "-cr", bundle], check=False, capture_output=True)
        return False

    where = t("where_translocated" if translocated else "where_outside")
    install = t("btn_install")
    if alert(t("self_install", app=APP_NAME, where=where), buttons=(t("btn_later"), install),
             default=install, icon="note") != install:
        return False

    name = os.path.basename(bundle)
    last_error: Exception | None = None
    for dest_dir in ("/Applications", home_apps):
        dest = os.path.join(dest_dir, name)
        try:
            os.makedirs(dest_dir, exist_ok=True)
            # eski nusxa ishlayotgan boʻlsa – toʻxtatamiz (oʻzimizning yoʻlimiz boshqa)
            subprocess.run(["pkill", "-f", dest + "/Contents/MacOS/"], check=False)
            time.sleep(0.5)
            if os.path.exists(dest):
                shutil.rmtree(dest)
            subprocess.run(["ditto", bundle, dest], check=True, capture_output=True)
            subprocess.run(["xattr", "-cr", dest], check=False, capture_output=True)
            subprocess.Popen(["open", "-n", dest])
            print(f"{APP_NAME} {dest} ga oʻrnatildi va ishga tushirildi.")
            return True
        except Exception as exc:
            last_error = exc
    alert(t("self_install_failed", error=last_error))
    return False


# ------------------------------------------------------- macOS: ruxsat
def _mac_ax_trusted(prompt: bool) -> bool:
    try:
        import HIServices
        if prompt:
            return bool(HIServices.AXIsProcessTrustedWithOptions(
                {HIServices.kAXTrustedCheckOptionPrompt: True}))
        return bool(HIServices.AXIsProcessTrusted())
    except Exception:
        return True  # tekshirib boʻlmadi – davom etamiz


def _mac_listen_ok(prompt: bool) -> bool:
    try:
        import Quartz
        if Quartz.CGPreflightListenEventAccess():
            return True
        return bool(Quartz.CGRequestListenEventAccess()) if prompt else False
    except Exception:
        return True


_TCC_SERVICES = {"Accessibility": "Accessibility", "Input Monitoring": "ListenEvent"}


def _mac_tcc_reset(services, admin: bool = False) -> bool:
    """Eskirgan ruxsat yozuvlarini oʻchiradi (tccutil reset <xizmat> <bundle id>).

    macOS ruxsatni ilovaning imzosiga bogʻlaydi.  Oldingi versiyadan qolgan yozuv yangi
    imzoga mos kelmasa, roʻyxatda "yoqilgan" koʻrinsa ham ishlamaydi va ilova har safar
    qayta soʻrayveradi.  Yozuvni oʻchirsak, macOS uni toza holda qayta yaratadi."""
    if not services:
        return True
    try:
        if admin:
            cmds = " ; ".join(f"tccutil reset {svc} {BUNDLE_ID}" for svc in services)
            r = subprocess.run(["osascript", "-e", f'do shell script "{cmds}" with administrator privileges'],
                               capture_output=True, text=True, timeout=300)
            return r.returncode == 0
        ok = True
        for svc in services:
            r = subprocess.run(["tccutil", "reset", svc, BUNDLE_ID],
                               capture_output=True, text=True, timeout=30)
            ok = ok and r.returncode == 0
        return ok
    except Exception:
        return False


def _open_privacy_pane(pane: str) -> None:
    try:
        subprocess.Popen(["open", f"x-apple.systempreferences:com.apple.preference.security?{pane}"])
    except Exception:
        pass


def macos_wait_permissions(stop_event: threading.Event) -> str:
    """Accessibility va Input Monitoring ruxsatini soʻraydi; berilguncha (15 daqiqagacha) kutadi.
    Natija: "ok" – ruxsat oldindan bor edi; "granted" – hozir berildi (macOS klaviatura kuzatuvini
    koʻpincha faqat yangi ishga tushgan jarayonga beradi – ilova oʻzini qayta ochishi kerak);
    "denied" – berilmadi."""
    if not IS_MAC:
        return "ok"
    ax0, listen0 = _mac_ax_trusted(False), _mac_listen_ok(False)
    if ax0 and listen0:
        return "ok"
    # Berilmagan xizmatlar uchun eski (oldingi versiyadan qolgan) yozuvlarni jimgina tozalaymiz –
    # berilmagan ruxsatni yoʻqotish mumkin emas, lekin xalaqit beruvchi yozuv ketadi.
    _mac_tcc_reset([svc for name, svc in _TCC_SERVICES.items()
                    if not (ax0 if name == "Accessibility" else listen0)])

    ax = _mac_ax_trusted(prompt=True)      # tizimning oʻz soʻrov oynalari
    listen = _mac_listen_ok(prompt=True)
    if ax and listen:
        return "granted"

    missing = [t(key) for key, ok in (("perm_accessibility", ax), ("perm_input", listen)) if not ok]
    reset, open_settings = t("btn_reset_entries"), t("btn_open_settings")
    msg = t("perm_needed", app=APP_NAME, missing=", ".join(missing), path=t("perm_path"), reset=reset)
    pane = "Privacy_Accessibility" if not ax else "Privacy_ListenEvent"

    def ask() -> None:
        choice = alert(msg, buttons=(reset, open_settings), default=open_settings, icon="note")
        if choice == reset:
            if _mac_tcc_reset(list(_TCC_SERVICES.values()), admin=True):
                _mac_ax_trusted(True)
                _mac_listen_ok(True)
                alert(t("perm_reset_ok", app=APP_NAME, path=t("perm_path")),
                      buttons=(open_settings,), icon="note")
            else:
                alert(t("perm_reset_fail", app=APP_NAME, path=t("perm_path")), buttons=(open_settings,))
            pane_now = "Privacy_Accessibility"
        else:
            pane_now = pane
        _open_privacy_pane(pane_now)

    threading.Thread(target=ask, name="alifbo-permission-dialog", daemon=True).start()

    deadline = time.monotonic() + 15 * 60
    while time.monotonic() < deadline and not stop_event.is_set():
        time.sleep(2)
        if _mac_ax_trusted(False) and _mac_listen_ok(False):
            return "granted"
    return "denied"


def macos_relaunch() -> bool:
    """Ruxsat endigina berildi – ilovani qayta ochamiz.  Aks holda klaviatura kuzatuvchisi
    jimgina hech narsa eshitmay qolishi mumkin va foydalanuvchi uni oʻzi qayta ochishi kerak boʻladi."""
    global _instance_lock
    bundle = _mac_bundle_path()
    if not bundle:
        return False
    try:
        if _instance_lock is not None:
            _instance_lock.close()  # yangi nusxa "allaqachon ishlamoqda" demasin
            _instance_lock = None
        # 1 soniya kutib ochamiz – bu jarayon toʻxtab ulgursin (ikki nusxa harfni ikki marta almashtirardi)
        subprocess.Popen(["/bin/sh", "-c", 'sleep 1; open -n "$0"', bundle])
        return True
    except Exception as exc:
        print(f"Qayta ishga tushirib boʻlmadi: {exc!r}")
        return False


# -------------------------------------------------------- avtomatik start
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_supported() -> bool:
    return IS_WIN or (IS_MAC and IS_FROZEN)


def autostart_enabled() -> bool:
    """Kompyuter yoqilganda dastur oʻzi ishga tushadimi."""
    try:
        if IS_WIN:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
                winreg.QueryValueEx(key, "YangiAlifbo")
            return True
        if IS_MAC and IS_FROZEN:
            from ServiceManagement import SMAppService
            return int(SMAppService.mainAppService().status()) == 1  # SMAppServiceStatusEnabled
    except Exception:
        pass
    return False


def set_autostart(enable: bool) -> bool:
    try:
        if IS_WIN:
            import winreg
            if IS_FROZEN:
                cmd = f'"{sys.executable}"'
            else:
                pyw = sys.executable.replace("python.exe", "pythonw.exe")
                cmd = f'"{pyw}" "{os.path.abspath(__file__)}"'
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                if enable:
                    winreg.SetValueEx(key, "YangiAlifbo", 0, winreg.REG_SZ, cmd)
                else:
                    try:
                        winreg.DeleteValue(key, "YangiAlifbo")
                    except FileNotFoundError:
                        pass
            return True
        if IS_MAC and IS_FROZEN:
            from ServiceManagement import SMAppService  # macOS 13+
            svc = SMAppService.mainAppService()
            ok, err = svc.registerAndReturnError_(None) if enable else svc.unregisterAndReturnError_(None)
            if not ok:
                print(f"Login Items: {err}")
            return bool(ok)
    except Exception as exc:
        print(f"Avtomatik ishga tushirishni sozlab boʻlmadi: {exc!r}")
    return False


# --------------------------------------------------------------- caps lock
if IS_WIN:
    import ctypes

    def _caps_lock_on() -> bool:
        return bool(ctypes.windll.user32.GetKeyState(0x14) & 1)  # VK_CAPITAL
else:
    def _caps_lock_on() -> bool:
        return False


# ------------------------------------------------------ belgilangan taklif
# Brauzer manzil satri (Edge, Chrome, Safari), Win+R oynasi va shunga oʻxshash maydonlar
# terilgan matnga taklifni belgilangan holda qoʻshib qoʻyadi: "Sh[opify.com]".  Bunday
# paytda birinchi Backspace faqat belgilangan qismni oʻchiradi va "Shahzod" → "Sşahzod"
# boʻlib qoladi.  Shuning uchun almashtirishdan oldin fokusdagi maydonda matn OXIRIGACHA
# belgilangan qism bor-yoʻqligini tekshiramiz (terminalda sichqoncha bilan belgilangan matn
# kabi boshqa belgilashlar hisobga olinmaydi).  Tekshirib boʻlmasa – False (eski xatti-harakat).
if IS_MAC:
    def autocomplete_selected() -> bool:
        try:
            import HIServices as AX
            system = AX.AXUIElementCreateSystemWide()
            AX.AXUIElementSetMessagingTimeout(system, 0.25)  # osilgan dastur bizni ham toʻxtatmasin
            err, el = AX.AXUIElementCopyAttributeValue(system, AX.kAXFocusedUIElementAttribute, None)
            if err or el is None:
                return False
            err, rng = AX.AXUIElementCopyAttributeValue(el, AX.kAXSelectedTextRangeAttribute, None)
            if err or rng is None:
                return False
            ok, (start, length) = AX.AXValueGetValue(rng, AX.kAXValueCFRangeType, None)
            if not ok or length <= 0:
                return False
            err, total = AX.AXUIElementCopyAttributeValue(el, AX.kAXNumberOfCharactersAttribute, None)
            if err or total is None:
                err, value = AX.AXUIElementCopyAttributeValue(el, AX.kAXValueAttribute, None)
                if err or not isinstance(value, str):
                    return False
                total = len(value.encode("utf-16-le")) // 2  # CFRange UTF-16 birliklarida
            return start + length == int(total)
        except Exception:
            return False

elif IS_WIN:
    _uia_local = threading.local()

    def _uia():
        """UI Automation mijozi (har bir oqim uchun alohida – COM obyektlari oqimga bogʻliq)."""
        client = getattr(_uia_local, "client", None)
        if client is None:
            import comtypes
            import comtypes.client
            try:
                comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
            except OSError:
                pass  # oqim COM bilan allaqachon ishga tushirilgan
            try:
                from comtypes.gen import UIAutomationClient as mod  # CI oldindan yaratadi
            except ImportError:
                mod = comtypes.client.GetModule("UIAutomationCore.dll")
            uia = comtypes.client.CreateObject(mod.CUIAutomation, interface=mod.IUIAutomation)
            try:
                uia2 = uia.QueryInterface(mod.IUIAutomation2)
                uia2.ConnectionTimeout = 250  # ms – osilgan dastur bizni ham toʻxtatmasin
                uia2.TransactionTimeout = 250
            except Exception:
                pass
            client = _uia_local.client = (mod, uia)
        return client

    def autocomplete_selected() -> bool:
        try:
            mod, uia = _uia()
            pattern = uia.GetFocusedElement().GetCurrentPattern(10014)  # UIA_TextPatternId
            if not pattern:
                return False
            text = pattern.QueryInterface(mod.IUIAutomationTextPattern)
            sel = text.GetSelection()
            if not sel or sel.Length < 1:
                return False
            rng = sel.GetElement(0)
            if not rng.GetText(1):
                return False  # faqat kursor, belgilangan matn yoʻq
            # 1 = TextPatternRangeEndpoint_End: belgilash matn oxirigacha boradimi
            return rng.CompareEndpoints(1, text.DocumentRange, 1) == 0
        except Exception:
            return False

else:
    def autocomplete_selected() -> bool:
        return False


# -------------------------------------------------------------------- app
class App:
    def __init__(self, cfg: dict, overrides: dict | None = None) -> None:
        self.cfg = cfg
        # Buyruq qatoridagi sozlamalar (--no-undo …) config qayta oʻqilganda ham saqlanadi
        self._overrides = dict(overrides or {})
        self.app_ids = allowed_ids(cfg)   # None – hamma dasturlarda
        self._app_id = None               # oxirgi aniqlangan faol dastur
        self._app_checked = 0.0           # qachon aniqlangan (monotonic); 0 – qayta aniqlash kerak
        self.engine = Engine(
            strip_sh_apostrophe=bool(cfg["strip_sh_apostrophe"]),
            tutuq=cfg["tutuq_belgisi"] or None,
            backspace_undo=bool(cfg["backspace_undo"]),
        )
        self.enabled = bool(cfg["enabled_on_start"])
        # Panel uchun: oxirgi faol dastur (id, nomi) va almashtirishlar hisobi (state.json da saqlanadi)
        self.last_app = None
        self._state_dirty = True
        self._stats_lock = threading.Lock()
        saved = read_runtime(STATE_FILE)
        self._day = time.strftime("%Y-%m-%d")
        self.stats = alifbo_stats.load()
        if self.stats.empty():
            # Oldingi versiyalarda faqat "bugun" va "jami" hisoblangan (state.json) – yoʻqolmasin
            try:
                total = int(saved.get("total") or 0)
                today = int(saved.get("today") or 0) if saved.get("date") == self._day else 0
            except (TypeError, ValueError):
                total = today = 0
            self.stats.migrate(total, today, self._day)
        self._stats_dirty = False
        self._milestone = self.stats.milestone()
        self._milestone_at = saved.get("milestone_at") if saved.get("milestone") == self._milestone else None
        # Yangi versiya: update.json dan (internetga fon jarayoni chiqadi, bu jarayon emas)
        self.version = app_version()
        self.update = None                # {"version", "url", "page"} – oʻrnatilganidan yangisi
        self._update_notified = saved.get("update_notified")  # Windows xabari har versiyaga bir marta
        self._update_proc = None
        self._update_spawned = None       # fon tekshiruvi oxirgi marta qachon ishga tushirilgan (monotonic)
        self._started = time.monotonic()
        self.controller = keyboard.Controller()
        self.q: "queue.Queue[tuple]" = queue.Queue()
        self._injecting = threading.Event()
        self._mods: set = set()
        # Yozgan harfimizdan keyin maydon taklif qoʻshdi – keyingi Backspace faqat uni oʻchiradi
        self._suggestion = False
        self._stop = threading.Event()
        self.tray = None
        self._kb_listener = None
        self._mouse_listener = None
        self._hotkeys = None

    # ---- listener callbacks (pynput threads) -------------------------------
    def on_press(self, key, injected=False):
        if injected and self._injecting.is_set():
            return  # bu bizning oʻzimiz yuborgan tugma
        if self._injecting.is_set() and not (key in _MODIFIERS or key in _IGNORED):
            return  # almashtirish paytida kelgan tugma – buferga olmaymiz
        self.q.put(("press", key))

    def on_release(self, key, injected=False):
        if key in _MODIFIERS:
            self.q.put(("release", key))

    def on_click(self, x, y, button, pressed):
        if pressed:
            self.q.put(("reset", None))

    def _win32_filter(self, msg, data):
        # Windows: biz yuborgan (injected) tugmalarni listener'ga umuman bermaymiz
        try:
            if self._injecting.is_set() and (data.flags & 0x10):  # LLKHF_INJECTED
                return False
        except AttributeError:
            pass
        return True

    # ---- worker thread -------------------------------------------------------
    def worker(self):
        while not self._stop.is_set():
            try:
                kind, key = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self._handle(kind, key)
            except Exception as exc:  # hech qachon oʻlmasin
                print(f"Xatolik: {exc!r}")
                self.engine.reset()

    def _handle(self, kind, key):
        if kind == "reset":
            self.engine.reset()
            self._app_checked = 0.0  # sichqoncha bilan boshqa dasturga oʻtilgan boʻlishi mumkin
            return
        if kind == "release":
            self._mods.discard(key)
            return
        if key in _MODIFIERS:
            self._mods.add(key)
            self.engine.reset()
            self._app_checked = 0.0  # Cmd+Tab / Alt+Tab
            return
        if key in _IGNORED:
            return
        if not self.enabled:
            return
        if self._mods:
            # Ctrl/Alt/Cmd + tugma – bu matn emas, buyruq
            self.engine.reset()
            return
        if not self._app_allowed():
            self.engine.reset()
            return

        suggestion, self._suggestion = self._suggestion, False
        action = None
        if key == Key.backspace:
            if suggestion:
                # Bu Backspace harfimizni emas, brauzer taklifini oʻchirdi – undo keyingisiga qoladi
                return
            action = self.engine.feed_backspace()
        elif key == Key.space:
            self.engine.feed_char(" ")
        elif isinstance(key, KeyCode) and key.char:
            ch = key.char
            if IS_WIN and ch.isalpha() and _caps_lock_on():
                # pynput Windows'da Caps Lock ni hisobga olmaydi
                ch = ch.swapcase()
            action = self.engine.feed_char(ch)
        else:
            # Enter, Tab, Esc, strelkalar, Home/End, F-tugmalar ...
            self.engine.reset()

        if action is not None:
            self._apply(action)

    def _apply(self, action):
        self._injecting.set()
        try:
            time.sleep(0.004)  # asl tugma dasturga yetib borsin
            delete = action.delete
            if delete and autocomplete_selected():
                delete += 1    # birinchi Backspace belgilangan taklifni oʻchiradi
            for _ in range(delete):
                self.controller.tap(Key.backspace)
            if action.insert:
                self.controller.type(action.insert)
            time.sleep(0.03)   # listener bizning tugmalarni koʻrib boʻlsin
            self._suggestion = bool(action.undo) and autocomplete_selected()
        finally:
            self._injecting.clear()
        if action.undo:  # haqiqiy almashtirish (s'h → sh va tutuq belgisi hisoblanmaydi)
            self._count(action.insert)

    def _count(self, inserted: str) -> None:
        """Statistika: kun, harf va dastur (faqat son – matn saqlanmaydi)."""
        app = self.last_app[1] if self.last_app else None
        with self._stats_lock:
            self._roll_day()
            self.stats.add(self._day, alifbo_stats.letter_of(inserted), app)
            self._stats_dirty = self._state_dirty = True
            milestone = self.stats.milestone()
            if milestone > self._milestone:
                self._milestone, self._milestone_at = milestone, time.time()
                self._notify(t("notify_milestone", n=i18n.fmt_num(milestone)))

    def _roll_day(self) -> None:
        self._day = time.strftime("%Y-%m-%d")

    def _app_allowed(self) -> bool:
        """Faol dastur roʻyxatdami.  Har tugmada emas – 0.5 s da bir marta, yoki dastur
        almashgan boʻlishi mumkin boʻlganda (sichqoncha, Cmd/Alt+Tab) qayta aniqlanadi."""
        ids = self.app_ids
        if ids is None:
            return True
        now = time.monotonic()
        if now - self._app_checked > 0.5:
            app_id = frontmost_app_id()
            if app_id != self._app_id:
                self._app_id = app_id
                self.engine.reset()  # boshqa dastur – eski kontekst yaroqsiz
            self._app_checked = now
        return app_allowed(self._app_id, ids)

    # ---- sozlamalar --------------------------------------------------------------
    def apply_config(self, cfg: dict) -> None:
        cfg.update(self._overrides)
        cfg["hotkey"] = self.cfg["hotkey"]  # tezkor tugma faqat qayta ishga tushirilganda oʻzgaradi
        self.cfg = cfg
        self.engine.strip_sh_apostrophe = bool(cfg["strip_sh_apostrophe"])
        self.engine.tutuq = cfg["tutuq_belgisi"] or None
        self.engine.backspace_undo = bool(cfg["backspace_undo"])
        self.app_ids = allowed_ids(cfg)
        self._app_checked = 0.0
        if i18n.resolve(cfg) != i18n.language():
            i18n.set_language(i18n.resolve(cfg))
            self._update_tray()
            self._refresh_tray_menu()

    def _apply_control(self, ctl: dict) -> None:
        """Panel yoki sozlamalar oynasidan kelgan buyruq (control.json)."""
        if ctl.get("quit"):
            print(f"[{APP_NAME}] paneldan chiqish")
            self.stop()
        elif ctl.get("reset_stats"):
            with self._stats_lock:
                self.stats.reset()
                self._milestone, self._milestone_at = 0, None
                self._stats_dirty = self._state_dirty = True
        elif isinstance(ctl.get("enabled"), bool) and ctl["enabled"] != self.enabled:
            self.toggle()

    def write_state(self) -> None:
        """Panel va sozlamalar oynasi uchun holat; hisoblagich ham shu faylda saqlanadi."""
        with self._stats_lock:
            self._roll_day()
            app = {"id": self.last_app[0], "name": self.last_app[1]} if self.last_app else None
            data = {"enabled": self.enabled, "app": app, "date": self._day,
                    "today": self.stats.day_count(self._day), "total": self.stats.total(),
                    "milestone": self._milestone, "milestone_at": self._milestone_at,
                    "update_notified": self._update_notified, "pid": os.getpid(), "updated": time.time()}
            self._state_dirty = False
        try:
            write_runtime(STATE_FILE, data)
        except OSError as exc:
            print(f"state.json yozilmadi: {exc!r}")

    def save_stats(self) -> None:
        with self._stats_lock:
            if not self._stats_dirty:
                return
            data = alifbo_stats.Stats(self.stats.to_dict())  # nusxa – yozish lock tashqarisida
            self._stats_dirty = False
        try:
            alifbo_stats.save(data)
        except OSError as exc:
            print(f"stats.json yozilmadi: {exc!r}")

    def _housekeeping(self):
        """Fon ishlari, 0.5 s da bir: oyna oʻzgartirgan config.json va control.json ni qoʻllash,
        oxirgi faol dasturni eslab qolish, panel uchun state.json ni yozish (kamida 5 s da bir –
        oyna shundan asosiy dastur ishlayotganini biladi), yangi versiyani kuzatish."""
        def mtime(path):
            try:
                return os.stat(path).st_mtime_ns
            except OSError:
                return None
        cfg_path, ctl_path, upd_path = user_config_path(), runtime_path(CONTROL_FILE), runtime_path(UPDATE_FILE)
        last_cfg, last_ctl = mtime(cfg_path), mtime(ctl_path)
        last_upd = -1  # birinchi aylanishda avvalgi tekshiruv natijasini ham oʻqiymiz
        last_write = last_stats = 0.0
        while not self._stop.wait(0.5):
            try:
                now = mtime(cfg_path)
                if now != last_cfg:
                    last_cfg = now
                    self.apply_config(load_config())
                    print(f"[{APP_NAME}] sozlamalar yangilandi")
                now = mtime(ctl_path)
                if now != last_ctl:
                    last_ctl = now
                    self._apply_control(read_runtime(CONTROL_FILE))
                now = mtime(upd_path)
                if now != last_upd:
                    last_upd = now
                    self._on_update_file()
                self._maybe_check_updates()
                app = frontmost_app()
                # oʻzimizning oynalar (panel) "oxirgi dastur" boʻlmasin
                if app is not None and app[2] not in _own_pids() and app[:2] != self.last_app:
                    self.last_app = app[:2]
                    self._state_dirty = True
                if self._state_dirty or time.monotonic() - last_write > 5:
                    self.write_state()
                    last_write = time.monotonic()
                if self._stats_dirty and time.monotonic() - last_stats > 2:  # har harfda emas
                    self.save_stats()
                    last_stats = time.monotonic()
            except Exception as exc:  # fon oqimi hech qachon oʻlmasin
                print(f"Fon ishlarida xatolik: {exc!r}")

    # ---- yangi versiya -----------------------------------------------------------
    def _on_update_file(self) -> None:
        """update.json oʻzgardi (fon tekshiruvi yoki oyna yozdi): tray menyusi, belgi, xabar."""
        info = update_info(self.version)
        if info == self.update:
            return
        self.update = info
        self._update_tray()
        self._refresh_tray_menu()
        if info and info["version"] != self._update_notified:
            self._update_notified = info["version"]
            self._state_dirty = True
            print(f"[{APP_NAME}] yangi versiya: {info['version']}")
            self._notify(t("notify_update", app=APP_NAME, version=info["version"]))

    def _notify(self, message: str) -> None:
        # macOS da pystray xabari "Script Editor" nomidan chiqadi – u yerda panel va belgi yetarli
        try:
            if IS_WIN and self.tray is not None:
                self.tray.notify(message, APP_NAME)
        except Exception:
            pass

    def _maybe_check_updates(self) -> None:
        """Kuniga bir marta: alohida fon jarayoni GitHub'dan versiya raqamini soʻraydi."""
        if self._update_proc is not None and self._update_proc.poll() is not None:
            self._update_proc = None
        now = time.monotonic()
        if (not self.cfg.get("check_updates", True) or self._update_proc is not None
                or now - self._started < 60  # kompyuter yoqilganda internet hali boʻlmasligi mumkin
                or (self._update_spawned is not None and now - self._update_spawned < 3 * 3600)
                or parse_version(self.version) is None or not update_due()):
            return
        self._update_spawned = now
        try:
            self._update_proc = subprocess.Popen(_self_cmd() + ["--update-check"], close_fds=True)
        except Exception as exc:
            print(f"Yangi versiya tekshiruvi ishga tushmadi: {exc!r}")

    def open_update(self, *_):
        if self.update:
            import webbrowser
            webbrowser.open(self.update["url"])

    def _refresh_tray_menu(self) -> None:
        if self.tray is None:
            return
        try:
            if IS_MAC:
                from PyObjCTools import AppHelper
                AppHelper.callAfter(self.tray.update_menu)  # AppKit – faqat asosiy oqimda
            else:
                self.tray.update_menu()
        except Exception as exc:
            print(f"Tray menyusi yangilanmadi: {exc!r}")

    # ---- boshqaruv -------------------------------------------------------------
    def toggle(self, *_):
        self.enabled = not self.enabled
        self._state_dirty = True
        self.engine.reset()
        state = "YOQILDI" if self.enabled else "OʻCHIRILDI"
        print(f"[{APP_NAME}] {state}   (tezkor tugma: {self.cfg['hotkey']})")
        self._update_tray()

    def _update_tray(self):
        if self.tray is None:
            return
        try:
            self.tray.icon = make_icon_image(self.enabled, badge=self.update is not None)
            self.tray.title = (t("tray_title_on" if self.enabled else "tray_title_off", app=APP_NAME)
                               + (t("tray_title_update", version=self.update["version"]) if self.update else ""))
        except Exception:
            pass

    def stop(self, *_):
        self._stop.set()
        self.save_stats()
        for lst in (self._hotkeys, self._mouse_listener, self._kb_listener):
            try:
                if lst is not None:
                    lst.stop()
            except Exception:
                pass
        if self.tray is not None:
            try:
                self.tray.stop()
            except Exception:
                pass

    def start(self):
        kwargs = {}
        if IS_WIN:
            kwargs["win32_event_filter"] = self._win32_filter
        self._kb_listener = keyboard.Listener(
            on_press=self.on_press, on_release=self.on_release, **kwargs
        )
        self._mouse_listener = mouse.Listener(on_click=self.on_click)
        try:
            self._hotkeys = keyboard.GlobalHotKeys({self.cfg["hotkey"]: self.toggle})
        except ValueError as exc:
            print(f"Tezkor tugma notoʻgʻri ({self.cfg['hotkey']!r}): {exc}.  Tezkor tugmasiz davom etamiz.")
            self._hotkeys = None

        threading.Thread(target=self.worker, name="alifbo-worker", daemon=True).start()
        threading.Thread(target=self._housekeeping, name="alifbo-housekeeping", daemon=True).start()
        self._kb_listener.start()
        self._mouse_listener.start()
        if self._hotkeys is not None:
            self._hotkeys.start()

    def healthy(self) -> bool:
        """macOS da ruxsat boʻlmasa pynput kuzatuvchisi xatosiz, jimgina toʻxtaydi –
        oqim tirikligini tekshiramiz."""
        time.sleep(0.8)
        return all(l is not None and l.is_alive()
                   for l in (self._kb_listener, self._mouse_listener))

    def join(self):
        if self._kb_listener is not None:
            self._kb_listener.join()


# ------------------------------------------------------------------- tray
def make_icon_image(enabled: bool, badge: bool = False):
    """ö harfiga oʻxshash oddiy belgi (shrift talab qilmaydi); badge – yangi versiya nuqtasi."""
    from PIL import Image, ImageDraw

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = (46, 160, 67, 255) if enabled else (140, 140, 140, 255)
    d.ellipse((10, 24, 54, 62), outline=color, width=9)       # "o"
    d.ellipse((14, 4, 26, 16), fill=color)                     # chap nuqta
    d.ellipse((38, 4, 50, 16), fill=color)                     # oʻng nuqta
    if badge:
        d.ellipse((38, 38, 66, 66), fill=(0, 0, 0, 0))         # atrofida boʻsh joy
        d.ellipse((43, 43, 61, 61), fill=(229, 83, 75, 255))   # qizil nuqta
    return img


_ui_proc = None


def _own_pids() -> set:
    pids = {os.getpid()}
    if _ui_proc is not None:
        pids.add(_ui_proc.pid)
    return pids


def _self_cmd() -> list:
    """Shu dasturni yana bir jarayon sifatida ishga tushirish buyrugʻi (oyna, fon tekshiruvi)."""
    if IS_FROZEN:
        return [sys.executable]
    python = sys.executable
    if IS_WIN:
        python = python.replace("python.exe", "pythonw.exe")  # konsol oynasiz
    return [python, os.path.abspath(__file__)]


def open_ui(mode: str = "settings") -> None:
    """Panel ("panel") yoki toʻliq sozlamalar ("settings") – alohida jarayonda: tray va Tk bitta
    asosiy oqimni boʻlisha olmaydi, internetga ham faqat u ulanadi (klaviatura kuzatuvchi jarayon emas).
    Oyna jarayoni ishlab tursa, yangisini ochmaymiz (onefile .exe sekin ishga tushadi) – ui.json orqali soʻraymiz."""
    global _ui_proc
    if IS_WIN:
        try:
            ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY: panel oldinga chiqa olsin
        except Exception:
            pass
    if _ui_proc is not None and _ui_proc.poll() is None:
        try:
            write_runtime(UI_REQUEST_FILE, {"mode": mode, "at": time.time()})
            return
        except OSError:
            pass
    try:
        _ui_proc = subprocess.Popen(_self_cmd() + ["--ui", mode], close_fds=True)
    except Exception as exc:
        print(f"Oynani ochib boʻlmadi: {exc!r}")


def _mac_icon_class(pystray):
    """macOS: chap bosish – panel (menyuning standart bandi), oʻng bosish yoki Control+bosish –
    menyu.  pystray menyu biriktirilgan belgida chap bosishni ushlamaydi, shuning uchun menyuni
    belgiga biriktirmay, faqat oʻng bosishda koʻrsatamiz."""
    try:
        import AppKit

        class MacIcon(pystray.Icon):
            def _update_menu(self):
                super()._update_menu()
                self._status_item.setMenu_(None)
                self._status_item.button().sendActionOn_(
                    AppKit.NSEventMaskLeftMouseUp | AppKit.NSEventMaskRightMouseUp)

            def __call__(self):
                event = AppKit.NSApp.currentEvent()
                handle = getattr(self, "_menu_handle", None)
                right = event is not None and (
                    event.type() == AppKit.NSEventTypeRightMouseUp
                    or event.modifierFlags() & AppKit.NSEventModifierFlagControl)
                if right and handle:
                    self._status_item.setMenu_(handle[0])
                    self._status_item.button().performClick_(None)  # menyu yopilguncha kutadi
                    self._status_item.setMenu_(None)
                else:
                    super().__call__()
        return MacIcon
    except Exception as exc:
        print(f"Menyu satri belgisini sozlab boʻlmadi: {exc!r}")
        return pystray.Icon


def _url_opener(url: str):
    def open_url():
        import webbrowser
        webbrowser.open(url)
    return open_url


def make_tray(app: App):
    try:
        import pystray
        image = make_icon_image(app.enabled)
    except Exception as exc:
        print(f"Tray belgisi yaratilmadi: {exc}")
        return None

    def label(_item):
        return t("tray_turn_off" if app.enabled else "tray_turn_on")

    def toggle_autostart(icon=None, item=None):
        set_autostart(not autostart_enabled())

    links = [pystray.MenuItem(link["title"], _url_opener(link["url"]))
             for link in load_promo()["links"]]
    # Matnlar funksiya: til almashganda update_menu() ularni qayta oʻqiydi
    items = [
        pystray.MenuItem(lambda item: t("tray_update", version=app.update["version"]) if app.update else "",
                         app.open_update, visible=lambda item: app.update is not None),
        # Standart band: Windows'da chap bosish, macOS'da belgini bosish – panel
        pystray.MenuItem(lambda item: t("tray_open_panel"), lambda: open_ui("panel"), default=True),
        pystray.MenuItem(label, app.toggle),
        pystray.MenuItem(lambda item: t("tray_settings"), lambda: open_ui("settings")),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(lambda item: t("tray_autostart"), toggle_autostart,
                         checked=lambda item: autostart_enabled(),
                         visible=lambda item: autostart_supported()),
    ]
    if links:
        items.append(pystray.MenuItem(lambda item: t("tray_links"), pystray.Menu(*links)))
    items += [
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(lambda item: t("tray_hotkey", hotkey=app.cfg["hotkey"]), None, enabled=False),
        pystray.MenuItem(f"{APP_NAME} {app_version()}", None, enabled=False),
        pystray.MenuItem(lambda item: t("btn_quit"), app.stop),
    ]
    icon_class = _mac_icon_class(pystray) if IS_MAC else pystray.Icon
    return icon_class("yangi-alifbo", image, t("tray_title_on", app=APP_NAME), pystray.Menu(*items))


# ------------------------------------------------------------------ check
def run_check() -> int:
    """CI uchun tekshiruv: yigʻilgan dastur barcha modullarni yuklay oladimi.
    Hech qanday ruxsat soʻramaydi, kuzatuvchi yaratmaydi."""
    problems = []
    try:
        import pystray  # noqa: F401
        make_icon_image(True)
        print("tray (pystray + pillow): OK")
    except Exception as exc:
        problems.append(f"tray: {exc!r}")
    try:
        keyboard.Controller()
        print("pynput controller: OK")
    except Exception as exc:
        problems.append(f"pynput controller: {exc!r}")
    if IS_MAC:
        try:
            import HIServices
            import Quartz
            assert callable(HIServices.AXIsProcessTrusted)
            assert callable(Quartz.CGPreflightListenEventAccess)
            assert callable(HIServices.AXUIElementCreateSystemWide)
            assert callable(HIServices.AXValueGetValue)
            assert HIServices.kAXValueCFRangeType is not None
            print("macOS ruxsat va Accessibility API (HIServices/Quartz): OK")
        except Exception as exc:
            problems.append(f"macOS API: {exc!r}")
        try:
            from ServiceManagement import SMAppService  # noqa: F401
            print("macOS Login Items API (ServiceManagement): OK")
        except Exception as exc:
            problems.append(f"macOS ServiceManagement: {exc!r}")
    if IS_WIN:
        try:
            _uia()
            print("Windows UI Automation (comtypes): OK")
        except Exception as exc:
            problems.append(f"Windows UI Automation: {exc!r}")
    try:
        import tkinter

        import customtkinter

        import alifbo_ui  # noqa: F401
        print(f"panel va sozlamalar (tkinter {tkinter.TkVersion}, customtkinter {customtkinter.__version__}): OK")
        if IS_FROZEN and not os.path.isdir(os.path.join(os.path.dirname(customtkinter.__file__), "assets")):
            problems.append("customtkinter assets dastur ichida yoʻq (--collect-data customtkinter)")
    except Exception as exc:
        problems.append(f"panel va sozlamalar: {exc!r}")
    try:
        for lang in i18n.LANGS:
            i18n.set_language(lang)
            assert t("tray_open_panel") != "tray_open_panel"
        i18n.set_language(i18n.DEFAULT)
        alifbo_stats.Stats().add("2026-01-01", "ş", "Telegram")
        print(f"tillar ({', '.join(i18n.LANGS)}; tizim tili: {i18n.system_language()}) va statistika: OK")
    except Exception as exc:
        problems.append(f"tillar/statistika: {exc!r}")
    version = app_version()
    print(f"versiya: {version}")
    if IS_FROZEN:
        # CI fayllarni --add-data bilan qoʻshishni unutmasin
        for name in ("app_version.txt", "promo.json", "config.json"):
            if not find_bundled(name, None):
                problems.append(f"{name} dastur ichida yoʻq")
    eng = Engine()
    eng.feed_char("s")
    act = eng.feed_char("h")
    if act is None or act.insert != "ş":
        problems.append("engine: sh → ş ishlamadi")
    else:
        print("engine (sh → ş): OK")
    for p in problems:
        print("XATO:", p)
    print("TEKSHIRUV:", "XATO" if problems else "OK")
    return 1 if problems else 0


# ------------------------------------------------------------------- main
def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="yangi_alifbo",
        description="Yangi oʻzbek lotin alifbosi (ö ğ ş ç) uchun avtomatik harf toʻgʻirlagich.",
    )
    p.add_argument("--hotkey", help="yoqish/oʻchirish tugmasi, masalan '<ctrl>+<alt>+u'")
    p.add_argument("--off", action="store_true", help="oʻchirilgan holda ishga tushirish")
    p.add_argument("--no-undo", action="store_true", help="Backspace bilan qaytarishni oʻchirish")
    p.add_argument("--keep-sh-apostrophe", action="store_true",
                   help="s'h dagi apostrofni olib tashlamaslik")
    p.add_argument("--tutuq", action="store_true",
                   help="harfdan keyingi ' belgisini rasmiy tutuq belgisi (ʼ) ga almashtirish")
    p.add_argument("--no-tray", action="store_true", help="tray belgisini koʻrsatmaslik")
    p.add_argument("--check", action="store_true",
                   help="faqat tekshiruv: modullar yuklanadimi (CI uchun), soʻng chiqish")
    p.add_argument("--autostart", choices=("on", "off"),
                   help="kompyuter bilan avtomatik ishga tushirishni yoqish/oʻchirish va chiqish")
    p.add_argument("--settings", action="store_true", help="sozlamalar oynasini ochish")
    p.add_argument("--ui", choices=("panel", "settings"),
                   help="panel yoki sozlamalar oynasi (asosiy dastur oʻzi ochadi)")
    p.add_argument("--update-check", action="store_true",
                   help="yangi versiyani tekshirib, natijani update.json ga yozish (asosiy dastur kuniga bir marta ishga tushiradi)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.check:
        return run_check()
    if args.update_check:
        return 0 if fetch_update() else 1
    if args.autostart:
        ok = set_autostart(args.autostart == "on")
        print("Avtomatik ishga tushirish:", ("yoqildi" if args.autostart == "on" else "oʻchirildi") if ok else "sozlanmadi")
        return 0 if ok else 1

    if args.ui or args.settings:
        from alifbo_ui import run_ui
        return run_ui(args.ui or "settings",
                      autostart=(autostart_supported, autostart_enabled, set_autostart),
                      lock=lambda: acquire_single_instance("UI"))

    overrides = {}
    if args.hotkey:
        overrides["hotkey"] = args.hotkey
    if args.off:
        overrides["enabled_on_start"] = False
    if args.no_undo:
        overrides["backspace_undo"] = False
    if args.keep_sh_apostrophe:
        overrides["strip_sh_apostrophe"] = False
    if args.tutuq:
        overrides["tutuq_belgisi"] = TUTUQ
    if args.no_tray:
        overrides["tray"] = False
    cfg = load_config()
    cfg.update(overrides)
    i18n.set_language(i18n.resolve(cfg))

    # macOS: Downloads/zip ichidan ochilgan boʻlsa – Applications ga oʻrnatib, qayta ochamiz
    if macos_self_install():
        return 0

    if not acquire_single_instance():
        # Dastur allaqachon ishlamoqda – qayta ochilgani sozlamalarni koʻrmoqchi degani
        open_ui("settings")
        return 0

    app = App(cfg, overrides)
    tray = make_tray(app) if cfg.get("tray", True) else None
    app.tray = tray
    if tray is None and IS_FROZEN and IS_MAC:
        alert(t("tray_failed"))
        return 1

    print(f"{APP_NAME} ishga tushmoqda.")
    print("  oʻ/o' → ö    gʻ/g' → ğ    sh → ş    ch → ç")
    print(f"  Yoqish/oʻchirish: {cfg['hotkey']}    Chiqish: Ctrl+C / tray → Chiqish")

    def startup(icon=None) -> None:
        if icon is not None:
            icon.visible = True
        permissions = macos_wait_permissions(app._stop)
        if permissions == "denied":
            if not app._stop.is_set():
                alert(t("perm_denied", app=APP_NAME, path=t("perm_path")))
                app.stop()
            return
        if permissions == "granted" and macos_relaunch():
            print(f"Ruxsat berildi – {APP_NAME} qayta ishga tushirilmoqda.")
            app.stop()
            return
        try:
            app.start()
            ok = app.healthy()
        except Exception as exc:
            ok = False
            print(f"Klaviatura kuzatuvchisini ishga tushirib boʻlmadi: {exc!r}")
        if not ok:
            alert(t("listener_failed") + "\n\n"
                  + (t("listener_hint_mac", app=APP_NAME, path=t("perm_path")) if IS_MAC
                     else t("listener_hint_win")))
            app.stop()
            return
        app._update_tray()
        print(f"{APP_NAME} ishga tushdi.")
        if IS_FROZEN and IS_WIN and tray is None:
            alert(t("running_no_tray", app=APP_NAME, hotkey=cfg["hotkey"]), icon="note")

    try:
        if tray is not None:
            tray.run(setup=startup)   # macOS da tray asosiy oqimda boʻlishi shart
        else:
            startup()
            app.join()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()
    print(f"{APP_NAME} toʻxtadi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
