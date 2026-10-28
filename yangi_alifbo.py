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
import json
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

from alifbo_core import TUTUQ, Engine

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
}

_MODIFIERS = {
    Key.ctrl, Key.ctrl_l, Key.ctrl_r,
    Key.alt, Key.alt_l, Key.alt_r, Key.alt_gr,
    Key.cmd, Key.cmd_l, Key.cmd_r,
}
# Bu tugmalar kontekstni oʻzgartirmaydi (buferni tozalamaymiz)
_IGNORED = {Key.shift, Key.shift_l, Key.shift_r, Key.caps_lock}


# ------------------------------------------------------------------ config
def _base_dir() -> str:
    if IS_FROZEN:
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    candidates = [os.path.join(_base_dir(), "config.json")]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "config.json"))
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    cfg.update(json.load(fh))
            except (OSError, ValueError) as exc:
                print(f"config.json oʻqilmadi ({exc}); standart sozlamalar ishlatiladi.")
            break
    return cfg


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


def acquire_single_instance() -> bool:
    """Dastur ikki marta ochilsa harflar ikki marta almashadi – shunga yoʻl qoʻymaymiz."""
    global _instance_lock
    try:
        if IS_WIN:
            import ctypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            _instance_lock = kernel32.CreateMutexW(None, False, "Local\\YangiAlifboSingleInstance")
            return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS
        import fcntl
        path = os.path.join(os.path.expanduser("~"), ".yangi_alifbo.lock")
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

    where = ("macOS'ning vaqtinchalik xavfsizlik papkasidan" if translocated
             else "Applications papkasidan tashqaridan")
    msg = (f"{APP_NAME} hozir {where} ishga tushdi. Bu holatda macOS siz bergan "
           "ruxsatlarni saqlab qolmaydi va dastur har safar qayta ruxsat soʻrayveradi.\n\n"
           "Ilovani Applications papkasiga oʻrnatib, u yerdan ishga tushiraylikmi?")
    if alert(msg, buttons=("Keyinroq", "Oʻrnatish"), default="Oʻrnatish", icon="note") != "Oʻrnatish":
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
    alert(f"Applications papkasiga koʻchirib boʻlmadi: {last_error}\n\n"
          "Ilovani Finder orqali qoʻlda Applications papkasiga koʻchiring va u yerdan oching.")
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


def macos_wait_permissions(stop_event: threading.Event) -> bool:
    """Accessibility va Input Monitoring ruxsatini soʻraydi; berilguncha (15 daqiqagacha)
    kutadi.  Ruxsat berilgach ilovani qayta ochish shart emas – kuzatuvchi shundan
    keyin yaratiladi."""
    if not IS_MAC:
        return True
    ax0, listen0 = _mac_ax_trusted(False), _mac_listen_ok(False)
    if ax0 and listen0:
        return True
    # Berilmagan xizmatlar uchun eski (oldingi versiyadan qolgan) yozuvlarni jimgina tozalaymiz –
    # berilmagan ruxsatni yoʻqotish mumkin emas, lekin xalaqit beruvchi yozuv ketadi.
    _mac_tcc_reset([svc for name, svc in _TCC_SERVICES.items()
                    if not (ax0 if name == "Accessibility" else listen0)])

    ax = _mac_ax_trusted(prompt=True)      # tizimning oʻz soʻrov oynalari
    listen = _mac_listen_ok(prompt=True)
    if ax and listen:
        return True

    missing = [n for n, ok in (("Accessibility", ax), ("Input Monitoring", listen)) if not ok]
    msg = (f"{APP_NAME} ishlashi uchun ruxsat kerak: {', '.join(missing)}.\n\n"
           "System Settings → Privacy & Security → Accessibility va Input Monitoring "
           f"roʻyxatlarida \"{APP_NAME}\" ni yoqing. Ruxsat berilgach dastur oʻzi davom etadi "
           "(macOS \"Quit & Reopen\" desa – bosing, ilova qayta ochiladi).\n\n"
           f"Roʻyxatda \"{APP_NAME}\" allaqachon YOQILGAN koʻrinsa-yu, bu oyna baribir chiqaversa – bu "
           "eski versiyadan qolgan yozuv. \"Eski yozuvlarni tozalash\" ni bosing (administrator paroli "
           "soʻraladi) yoki roʻyxatda uni − bilan oʻchirib, qayta qoʻshing.")
    pane = "Privacy_Accessibility" if not ax else "Privacy_ListenEvent"

    def ask() -> None:
        choice = alert(msg, buttons=("Eski yozuvlarni tozalash", "Sozlamalarni ochish"),
                       default="Sozlamalarni ochish", icon="note")
        if choice == "Eski yozuvlarni tozalash":
            if _mac_tcc_reset(list(_TCC_SERVICES.values()), admin=True):
                _mac_ax_trusted(True)
                _mac_listen_ok(True)
                alert("Eski yozuvlar tozalandi. Endi System Settings → Privacy & Security → "
                      f"Accessibility va Input Monitoring da \"{APP_NAME}\" ni qayta yoqing.",
                      buttons=("Sozlamalarni ochish",), icon="note")
            else:
                alert("Tozalab boʻlmadi. Qoʻlda: System Settings → Privacy & Security → Accessibility "
                      f"va Input Monitoring roʻyxatlarida \"{APP_NAME}\" ni belgilab − bilan oʻchiring, "
                      "soʻng ilovani qayta oching.", buttons=("Sozlamalarni ochish",))
            pane_now = "Privacy_Accessibility"
        else:
            pane_now = pane
        _open_privacy_pane(pane_now)

    threading.Thread(target=ask, name="alifbo-permission-dialog", daemon=True).start()

    deadline = time.monotonic() + 15 * 60
    while time.monotonic() < deadline and not stop_event.is_set():
        time.sleep(2)
        if _mac_ax_trusted(False) and _mac_listen_ok(False):
            return True
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
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.engine = Engine(
            strip_sh_apostrophe=bool(cfg["strip_sh_apostrophe"]),
            tutuq=cfg["tutuq_belgisi"] or None,
            backspace_undo=bool(cfg["backspace_undo"]),
        )
        self.enabled = bool(cfg["enabled_on_start"])
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
            return
        if kind == "release":
            self._mods.discard(key)
            return
        if key in _MODIFIERS:
            self._mods.add(key)
            self.engine.reset()
            return
        if key in _IGNORED:
            return
        if not self.enabled:
            return
        if self._mods:
            # Ctrl/Alt/Cmd + tugma – bu matn emas, buyruq
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

    # ---- boshqaruv -------------------------------------------------------------
    def toggle(self, *_):
        self.enabled = not self.enabled
        self.engine.reset()
        state = "YOQILDI" if self.enabled else "OʻCHIRILDI"
        print(f"[{APP_NAME}] {state}   (tezkor tugma: {self.cfg['hotkey']})")
        self._update_tray()

    def _update_tray(self):
        if self.tray is None:
            return
        try:
            self.tray.icon = make_icon_image(self.enabled)
            self.tray.title = f"{APP_NAME}: {'yoqilgan' if self.enabled else 'oʻchirilgan'}"
        except Exception:
            pass

    def stop(self, *_):
        self._stop.set()
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
def make_icon_image(enabled: bool):
    """ö harfiga oʻxshash oddiy belgi (shrift talab qilmaydi)."""
    from PIL import Image, ImageDraw

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = (46, 160, 67, 255) if enabled else (140, 140, 140, 255)
    d.ellipse((10, 24, 54, 62), outline=color, width=9)       # "o"
    d.ellipse((14, 4, 26, 16), fill=color)                     # chap nuqta
    d.ellipse((38, 4, 50, 16), fill=color)                     # oʻng nuqta
    return img


def make_tray(app: App):
    try:
        import pystray
        image = make_icon_image(app.enabled)
    except Exception as exc:
        print(f"Tray belgisi yaratilmadi: {exc}")
        return None

    def label(_item):
        return "Oʻchirish" if app.enabled else "Yoqish"

    def toggle_autostart(icon=None, item=None):
        set_autostart(not autostart_enabled())

    menu = pystray.Menu(
        pystray.MenuItem(label, app.toggle, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Kompyuter bilan ishga tushirish", toggle_autostart,
                         checked=lambda item: autostart_enabled(),
                         visible=lambda item: autostart_supported()),
        pystray.MenuItem(f"Tezkor tugma: {app.cfg['hotkey']}", None, enabled=False),
        pystray.MenuItem("Chiqish", app.stop),
    )
    return pystray.Icon("yangi-alifbo", image, f"{APP_NAME}: yoqilgan", menu)


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
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.check:
        return run_check()
    if args.autostart:
        ok = set_autostart(args.autostart == "on")
        print("Avtomatik ishga tushirish:", ("yoqildi" if args.autostart == "on" else "oʻchirildi") if ok else "sozlanmadi")
        return 0 if ok else 1

    cfg = load_config()
    if args.hotkey:
        cfg["hotkey"] = args.hotkey
    if args.off:
        cfg["enabled_on_start"] = False
    if args.no_undo:
        cfg["backspace_undo"] = False
    if args.keep_sh_apostrophe:
        cfg["strip_sh_apostrophe"] = False
    if args.tutuq:
        cfg["tutuq_belgisi"] = TUTUQ
    if args.no_tray:
        cfg["tray"] = False

    # macOS: Downloads/zip ichidan ochilgan boʻlsa – Applications ga oʻrnatib, qayta ochamiz
    if macos_self_install():
        return 0

    if not acquire_single_instance():
        alert(f"{APP_NAME} allaqachon ishlamoqda.\n\n"
              + ("Menyu satridagi (yuqori oʻngdagi) ö belgisiga qarang." if IS_MAC
                 else "Soat yonidagi ö belgisiga qarang."), icon="note")
        return 0

    app = App(cfg)
    tray = make_tray(app) if cfg.get("tray", True) else None
    app.tray = tray
    if tray is None and IS_FROZEN and IS_MAC:
        alert("Menyu satri belgisini yaratib boʻlmadi, shuning uchun dastur ishga tushmadi.")
        return 1

    print(f"{APP_NAME} ishga tushmoqda.")
    print("  oʻ/o' → ö    gʻ/g' → ğ    sh → ş    ch → ç")
    print(f"  Yoqish/oʻchirish: {cfg['hotkey']}    Chiqish: Ctrl+C / tray → Chiqish")

    def startup(icon=None) -> None:
        if icon is not None:
            icon.visible = True
        if not macos_wait_permissions(app._stop):
            if not app._stop.is_set():
                alert(f"Ruxsat berilmadi, {APP_NAME} ishlay olmaydi.\n\n"
                      "System Settings → Privacy & Security → Accessibility va Input Monitoring "
                      f"da \"{APP_NAME}\" ni yoqib, ilovani qayta oching.")
                app.stop()
            return
        try:
            app.start()
            ok = app.healthy()
        except Exception as exc:
            ok = False
            print(f"Klaviatura kuzatuvchisini ishga tushirib boʻlmadi: {exc!r}")
        if not ok:
            alert(f"Klaviatura kuzatuvchisi ishga tushmadi.\n\n"
                  + ("Ruxsat endigina berilgan boʻlsa, ilovani yopib qayta oching. "
                     "System Settings → Privacy & Security → Accessibility va Input Monitoring "
                     f"da \"{APP_NAME}\" yoqilganini tekshiring." if IS_MAC
                     else "Dasturni qayta ishga tushirib koʻring."))
            app.stop()
            return
        app._update_tray()
        print(f"{APP_NAME} ishga tushdi.")
        if IS_FROZEN and IS_WIN and tray is None:
            alert(f"{APP_NAME} ishlamoqda.\nYoqish/oʻchirish: {cfg['hotkey']}\n"
                  "Toʻxtatish: Task Manager orqali.", icon="note")

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
