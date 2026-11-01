# -*- coding: utf-8 -*-
"""
Yangi Alifbo – oynalar (CustomTkinter): menyu satri / tray paneli va toʻliq sozlamalar oynasi.

Asosiy dastur ularni alohida jarayonda ochadi:  yangi_alifbo.py --ui panel | settings
(tray va Tk bitta asosiy oqimni boʻlisha olmaydi; internetga ham faqat shu jarayon ulanadi).

* Panel – belgi bosilganda chiqadigan kichik oyna: yoqish/oʻchirish, hozir oldindagi dasturda
  ishlashi (bitta tugma bilan roʻyxatga qoʻshiladi), bugungi hisob, havolalar.  Boshqa joy
  bosilsa yopiladi.
* Sozlamalar – yon panelli toʻliq oyna: Umumiy (sinov maydoni bilan), Dasturlar, Biz bilan.

Jarayon oynalar yopilgach ham 10 daqiqa kutib turadi – keyingi bosishda panel darhol chiqadi.
Asosiy dastur bilan aloqa – alifbo_config dagi fayllar (state.json, control.json, config.json, ui.json).
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser

import customtkinter as ctk

import alifbo_config as ac
from alifbo_apps import running_apps
from alifbo_core import TUTUQ, convert_text

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")
IDLE_EXIT_S = 10 * 60      # oynalar yopilgach jarayon shuncha kutadi
MAIN_ALIVE_S = 15          # asosiy dastur state.json ni kamida 5 s da bir yozadi

# Ranglar: (yorugʻ, qorongʻi) – CustomTkinter tizim rejimiga qarab tanlaydi
GREEN = "#2EA043"
GREEN_HOVER = "#2A8F3E"
ON_GREEN = "#FFFFFF"        # yashil fon ustidagi matn
TEXT = ("gray10", "gray92")
TEXT_MUTED = ("gray40", "gray62")
TEXT_OK = ("#1A7F37", "#3FB950")
WINDOW_BG = ("#F5F5F7", "#1F1F21")
SIDEBAR_BG = ("#ECECEF", "#29292C")
NAV_ACTIVE = ("#DCDCE1", "#3A3A3F")
CARD_BG = ("#FFFFFF", "#2A2A2D")
CARD_BORDER = ("#E0E0E5", "#3A3A3F")
UPDATE_BG = ("#E6F6EA", "#16301F")       # yangi versiya xabari
UPDATE_BORDER = ("#B4E2C0", "#245A35")


# ------------------------------------------------------------------ yordamchilar
def _logo_image(size: int):
    """ö belgisi (make_icon.py dagi bilan bir xil); Pillow boʻlmasa – None."""
    try:
        from PIL import Image, ImageDraw
        big = size * 4  # katta chizib kichraytiramiz – chetlari silliq
        s = big / 64.0
        img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, big - 1, big - 1), radius=int(14 * s), fill=(46, 160, 67, 255))
        white = (255, 255, 255, 255)
        d.ellipse((12 * s, 26 * s, 52 * s, 60 * s), outline=white, width=int(8 * s))
        d.ellipse((16 * s, 7 * s, 27 * s, 18 * s), fill=white)
        d.ellipse((37 * s, 7 * s, 48 * s, 18 * s), fill=white)
        return img.resize((size * 2, size * 2), Image.LANCZOS)  # Retina uchun 2x
    except Exception:
        return None


def hotkey_keys(hotkey: str) -> list:
    """'<ctrl>+<alt>+u' → ['Ctrl', 'Option', 'U'] (Mac) / ['Ctrl', 'Alt', 'U']."""
    names = {"ctrl": "Ctrl", "alt": "Option" if IS_MAC else "Alt", "shift": "Shift",
             "cmd": "Cmd" if IS_MAC else "Win"}
    return [names.get(p.strip().strip("<>").lower(), p.strip().strip("<>").upper())
            for p in hotkey.split("+")]


def _fmt(n) -> str:
    try:
        return f"{int(n):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def _set_switch(sw, on: bool, active: bool = True) -> None:
    """CTkSwitch oʻchirilgan (disabled) holatda select()/deselect() ni eʼtiborsiz qoldiradi."""
    sw.configure(state="normal")
    (sw.select if on else sw.deselect)()
    if not active:
        sw.configure(state="disabled")


def _open_url(url: str) -> None:
    if isinstance(url, str) and url.startswith("https://"):
        webbrowser.open(url)


def _app_active(win) -> bool:
    """Bu jarayon hozir oldindami (panel boshqa joy bosilganda yopilishi uchun)."""
    if IS_MAC:
        try:
            from AppKit import NSApplication
            return bool(NSApplication.sharedApplication().isActive())
        except Exception:
            pass
    if IS_WIN:
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.GetForegroundWindow.restype = wintypes.HWND
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
            return pid.value == os.getpid()
        except Exception:
            pass
    return win.focus_displayof() is not None


def _activate(win) -> None:
    if IS_MAC:
        try:
            # Ilova Dock'da yoʻq (LSUIElement) – oynani oʻzimiz oldinga chiqaramiz
            from AppKit import NSApplication
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        except Exception:
            pass
    try:
        win.lift()
        win.focus_force()
    except tk.TclError:
        pass


def _work_area(win) -> tuple:
    """Ekranning foydalanish mumkin boʻlgan qismi (taskbar / menyu satrisiz): chap, yuqori, oʻng, past."""
    if IS_WIN:
        try:
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
                return rect.left, rect.top, rect.right, rect.bottom
        except Exception:
            pass
    if IS_MAC:
        try:
            from AppKit import NSScreen
            screen = NSScreen.screens()[0]  # menyu satri joylashgan ekran
            full, vis = screen.frame(), screen.visibleFrame()
            top = full.size.height - (vis.origin.y + vis.size.height)  # Cocoa: y pastdan
            return (int(vis.origin.x), int(top),
                    int(vis.origin.x + vis.size.width), int(top + vis.size.height))
        except Exception:
            pass
    return 0, 0, win.winfo_screenwidth(), win.winfo_screenheight()


def _win11_round_corners(win) -> None:
    """Windows 11: chegarasiz panel burchaklarini tizim yumaloqlaydi (Windows 10 da – oʻzgarishsiz)."""
    try:
        import ctypes
        hwnd = int(win.wm_frame(), 16)
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
    except Exception:
        pass


# --------------------------------------------------------------------- boshqaruv
class UI:
    """Bitta jarayondagi barcha oynalar va asosiy dastur bilan aloqa."""

    def __init__(self, autostart=None) -> None:
        ctk.set_appearance_mode("system")
        self.root = ctk.CTk()
        self.root.withdraw()
        self.autostart = autostart  # (supported, enabled, set) – asosiy moduldan
        self.cfg = ac.load_config()
        self.state = ac.read_runtime(ac.STATE_FILE)
        self.promo = ac.load_promo()
        self.version = ac.app_version()
        self.update_data = ac.read_runtime(ac.UPDATE_FILE)   # oxirgi tekshiruv natijasi
        self.update = ac.update_info(self.version)          # oʻrnatilganidan yangisi boʻlsa
        self.update_status = ""                             # "checking" / "done" / "failed"

        self.f_title = ctk.CTkFont(size=24, weight="bold")
        self.f_head = ctk.CTkFont(size=15, weight="bold")
        self.f_body = ctk.CTkFont(size=13)
        self.f_bold = ctk.CTkFont(size=13, weight="bold")
        self.f_small = ctk.CTkFont(size=11)
        self.f_big = ctk.CTkFont(size=26, weight="bold")
        logo = _logo_image(40)
        self.logo40 = ctk.CTkImage(logo, logo, size=(40, 40)) if logo else None
        self.logo28 = ctk.CTkImage(logo, logo, size=(28, 28)) if logo else None
        self.icon_photo = None
        if logo is not None:
            try:
                import base64
                import io
                buf = io.BytesIO()
                logo.save(buf, "PNG")
                self.icon_photo = tk.PhotoImage(master=self.root, data=base64.b64encode(buf.getvalue()))
            except Exception:
                pass

        self.panel: Panel | None = None
        self.settings: SettingsWindow | None = None
        self._panel_closed_at = 0.0
        self._idle_since = time.monotonic()
        self._req_mtime = self._mtime(ac.runtime_path(ac.UI_REQUEST_FILE))
        self._promo_q: "queue.Queue[dict]" = queue.Queue()
        self._update_q: "queue.Queue[bool]" = queue.Queue()
        self._upd_mtime = self._mtime(ac.runtime_path(ac.UPDATE_FILE))
        self._tick = 0
        threading.Thread(target=self._fetch_promo, name="promo", daemon=True).start()
        if self.cfg.get("check_updates", True) and ac.parse_version(self.version) and ac.update_due():
            self.check_update()
        self.root.after(250, self._poll)

    # ---- asosiy dastur bilan aloqa -------------------------------------------
    @staticmethod
    def _mtime(path: str):
        try:
            return os.stat(path).st_mtime_ns
        except OSError:
            return None

    def main_alive(self) -> bool:
        try:
            return time.time() - float(self.state.get("updated") or 0) < MAIN_ALIVE_S
        except (TypeError, ValueError):
            return False

    def enabled(self) -> bool:
        return self.main_alive() and bool(self.state.get("enabled", True))

    def set_enabled(self, value: bool) -> None:
        ac.write_runtime(ac.CONTROL_FILE, {"enabled": bool(value), "at": time.time()})
        self.state["enabled"] = bool(value)  # asosiy dastur 0.5 s ichida qoʻllaydi
        self.refresh()

    def quit_main(self) -> None:
        ac.write_runtime(ac.CONTROL_FILE, {"quit": True, "at": time.time()})

    def save(self, **changes) -> None:
        self.cfg.update(changes)
        ac.save_user_settings(changes)  # asosiy dastur 0.5 s ichida qayta oʻqiydi
        self.refresh()

    # ---- oynalar ---------------------------------------------------------------
    def show(self, mode: str) -> None:
        if mode == "panel":
            self.toggle_panel()
        else:
            self.open_settings()

    def toggle_panel(self) -> None:
        if self.panel is not None and self.panel.visible:
            self.panel.close()
            return
        if time.monotonic() - self._panel_closed_at < 0.6:
            return  # panel belgining oʻzi bosilgani uchun yopildi – qayta ochmaymiz
        self.cfg = ac.load_config()
        if self.panel is None:
            self.panel = Panel(self)
        self.panel.show()

    def open_settings(self, page: str | None = None) -> None:
        if self.panel is not None and self.panel.visible:
            self.panel.close()
        if self.settings is None or not self.settings.exists():
            self.cfg = ac.load_config()
            self.settings = SettingsWindow(self)
        self.settings.show(page)

    def any_visible(self) -> bool:
        return bool((self.panel and self.panel.visible)
                    or (self.settings and self.settings.exists()))

    def refresh(self) -> None:
        for win in (self.panel, self.settings):
            if win is not None:
                try:
                    win.refresh()
                except tk.TclError:
                    pass

    # ---- yangi versiya ------------------------------------------------------------
    def check_update(self) -> None:
        if self.update_status == "checking":
            return
        self.update_status = "checking"
        # tarmoq – alohida oqimda; natija update.json ga yoziladi, _poll uni oʻqiydi
        threading.Thread(target=lambda: self._update_q.put(ac.fetch_update() is not None),
                         name="update", daemon=True).start()
        self.refresh()

    def open_update(self) -> None:
        if self.update:
            _open_url(self.update["url"])

    # ---- fon ------------------------------------------------------------------
    def _fetch_promo(self) -> None:
        promo = ac.fetch_promo()  # tarmoq – alohida oqimda, oyna qotmasin
        if promo is not None:
            self._promo_q.put(promo)

    def _poll(self) -> None:
        """250 ms da bir: yangi soʻrovlar (ui.json), 1 s da bir: asosiy dastur holati."""
        self._tick += 1
        mtime = self._mtime(ac.runtime_path(ac.UI_REQUEST_FILE))
        if mtime != self._req_mtime:
            self._req_mtime = mtime
            mode = ac.read_runtime(ac.UI_REQUEST_FILE).get("mode")
            if mode in ("panel", "settings"):
                self.show(mode)
        try:
            self.promo = self._promo_q.get_nowait()
            for win in (self.panel, self.settings):
                if win is not None:
                    win.refresh_promo()
        except queue.Empty:
            pass
        except tk.TclError:
            pass
        checked = False
        try:
            self.update_status = "done" if self._update_q.get_nowait() else "failed"
            checked = True
        except queue.Empty:
            pass
        mtime = self._mtime(ac.runtime_path(ac.UPDATE_FILE))
        if mtime != self._upd_mtime or checked:  # fon tekshiruvi (asosiy dastur) ham yozishi mumkin
            self._upd_mtime = mtime
            self.update_data = ac.read_runtime(ac.UPDATE_FILE)
            self.update = ac.update_info(self.version)
            self.refresh()
        if self._tick % 4 == 0:
            self.state = ac.read_runtime(ac.STATE_FILE)
            self.refresh()
        if self.any_visible():
            self._idle_since = time.monotonic()
        elif (time.monotonic() - self._idle_since > IDLE_EXIT_S
              or (not self.main_alive() and time.monotonic() - self._idle_since > 3)):
            self.root.destroy()  # hech qanday oyna yoʻq – jarayon tugaydi
            return
        self.root.after(250, self._poll)


# -------------------------------------------------------------------------- panel
class Panel:
    """Belgi bosilganda chiqadigan kichik oyna (macOS popover / Windows flyout uslubida)."""

    def __init__(self, ui: UI) -> None:
        self.ui = ui
        self.visible = False
        self._had_focus = False
        self._shown_at = 0.0
        self.win = tk.Toplevel(ui.root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        radius, extra = 0, {}
        if IS_MAC:
            try:
                # Shaffof fon + yumaloq ramka – popover koʻrinishi
                self.win.attributes("-transparent", True)
                self.win.configure(bg="systemTransparent")
                radius, extra = 16, {"bg_color": "systemTransparent"}
            except tk.TclError:
                pass
        # Windows 11 da burchaklarni tizim yumaloqlaydi (_win11_round_corners)
        self.body = ctk.CTkFrame(self.win, corner_radius=radius, border_width=1,
                                 border_color=CARD_BORDER, fg_color=WINDOW_BG, **extra)
        self.body.pack(fill="both", expand=True)
        self.win.bind("<Escape>", lambda e: self.close())
        self._build()

    def _build(self) -> None:
        ui, body = self.ui, self.body
        ctk.CTkFrame(body, width=300, height=0, fg_color="transparent").pack()  # eng kam kenglik

        head = ctk.CTkFrame(body, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 10))
        if ui.logo28:
            ctk.CTkLabel(head, image=ui.logo28, text="").pack(side="left")
        names = ctk.CTkFrame(head, fg_color="transparent")
        names.pack(side="left", padx=10)
        ctk.CTkLabel(names, text=ac.APP_NAME, font=ui.f_head, anchor="w").pack(anchor="w")
        self.status = ctk.CTkLabel(names, text="", font=ui.f_small, text_color=TEXT_MUTED, anchor="w",
                                   height=14)
        self.status.pack(anchor="w")
        self.master = ctk.CTkSwitch(head, text="", width=46, switch_width=42, switch_height=22,
                                    progress_color=GREEN, command=self._on_master)
        self.master.pack(side="right")

        # Yangi versiya – faqat bor boʻlsa koʻrinadi (refresh)
        self.update_box = ctk.CTkFrame(body, fg_color=UPDATE_BG, corner_radius=12, border_width=1,
                                       border_color=UPDATE_BORDER)
        top = ctk.CTkFrame(self.update_box, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(10, 0))
        self.update_title = ctk.CTkLabel(top, text="", font=ui.f_bold, anchor="w")
        self.update_title.pack(side="left")
        ctk.CTkButton(top, text="Yuklab olish", width=10, height=28, font=ui.f_bold, fg_color=GREEN,
                      hover_color=GREEN_HOVER, text_color=ON_GREEN, command=self._on_update).pack(side="right")
        ctk.CTkLabel(self.update_box, text="Yuklangan faylni ochib oʻrnating – sozlamalar saqlanadi.",
                     font=ui.f_small, text_color=TEXT_MUTED, anchor="w", justify="left",
                     wraplength=270).pack(anchor="w", padx=14, pady=(2, 10))

        card = self.app_card = ctk.CTkFrame(body, fg_color=CARD_BG, corner_radius=12, border_width=1,
                                            border_color=CARD_BORDER)
        card.pack(fill="x", padx=12)
        ctk.CTkLabel(card, text="Hozir oldinda", font=ui.f_small, text_color=TEXT_MUTED,
                     height=14).pack(anchor="w", padx=14, pady=(10, 0))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(2, 0))
        self.app_name = ctk.CTkLabel(row, text="", font=ui.f_bold, anchor="w")
        self.app_name.pack(side="left")
        self.app_switch = ctk.CTkSwitch(row, text="", width=46, progress_color=GREEN,
                                        command=self._on_app)
        self.app_switch.pack(side="right")
        self.app_hint = ctk.CTkLabel(card, text="", font=ui.f_small, text_color=TEXT_MUTED, anchor="w",
                                     justify="left", wraplength=270)
        self.app_hint.pack(anchor="w", padx=14, pady=(0, 10))

        stats = ctk.CTkFrame(body, fg_color="transparent")
        stats.pack(fill="x", padx=16, pady=(12, 4))
        stats.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(stats, text="Bugun toʻgʻirlandi", font=ui.f_small, text_color=TEXT_MUTED,
                     height=14).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(stats, text="Jami", font=ui.f_small, text_color=TEXT_MUTED,
                     height=14).grid(row=0, column=1, sticky="w")
        self.today = ctk.CTkLabel(stats, text="0", font=ui.f_big, anchor="w")
        self.today.grid(row=1, column=0, sticky="w")
        self.total = ctk.CTkLabel(stats, text="0", font=ui.f_big, anchor="w", text_color=TEXT_MUTED)
        self.total.grid(row=1, column=1, sticky="w")

        self.links = ctk.CTkFrame(body, fg_color="transparent")
        self.links.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkFrame(body, height=1, fg_color=CARD_BORDER).pack(fill="x", padx=12, pady=(6, 0))
        foot = ctk.CTkFrame(body, fg_color="transparent")
        foot.pack(fill="x", padx=8, pady=(4, 10))
        ctk.CTkButton(foot, text="Barcha sozlamalar  →", font=ui.f_bold, fg_color="transparent",
                      text_color=TEXT_OK, hover_color=NAV_ACTIVE, width=10, anchor="w",
                      command=lambda: ui.open_settings()).pack(side="left")
        ctk.CTkButton(foot, text="Chiqish", fg_color="transparent", text_color=TEXT_MUTED,
                      hover_color=NAV_ACTIVE, width=10, command=self._quit).pack(side="right")
        self.refresh_promo()

    # ---- holat -------------------------------------------------------------------
    def refresh(self) -> None:
        ui = self.ui
        alive, enabled = ui.main_alive(), ui.enabled()
        keys = "+".join(hotkey_keys(ui.cfg.get("hotkey", "")))
        _set_switch(self.master, enabled, alive)
        self.status.configure(text=(("Yoqilgan" if enabled else "Oʻchirilgan") + f"  ·  {keys}")
                              if alive else "Dastur ishlamayapti")
        self.today.configure(text=_fmt(ui.state.get("today")))
        self.total.configure(text=_fmt(ui.state.get("total")))
        self._refresh_update()

        app = ui.state.get("app") if isinstance(ui.state.get("app"), dict) else None
        ids = ac.allowed_ids(ui.cfg)
        if not app or not app.get("id"):
            self.app_name.configure(text="Aniqlanmadi")
            _set_switch(self.app_switch, False, active=False)
            self.app_hint.configure(text="Biror dasturga oʻtib, panelni qayta oching.")
            return
        self.app_name.configure(text=app.get("name") or app["id"])
        on = ac.app_allowed(app["id"], ids)
        _set_switch(self.app_switch, on, active=ids is not None)
        if ids is None:
            hint = "Hamma dasturlarda ishlaydi (sozlamalarda oʻzgartiriladi)."
        elif on:
            hint = "Shu dasturda harflar almashtiriladi."
        else:
            hint = "Bu dasturda ishlamaydi – yoqish uchun tugmani bosing."
        if alive and not enabled:
            hint = "Dastur oʻchirilgan – yuqoridagi tugma bilan yoqing."
        self.app_hint.configure(text=hint)

    def _refresh_update(self) -> None:
        upd = self.ui.update
        if upd:
            self.update_title.configure(text=f"Yangi versiya: {upd['version']}")
        if bool(upd) != bool(self.update_box.winfo_manager()):
            if upd:
                self.update_box.pack(fill="x", padx=12, pady=(0, 10), before=self.app_card)
            else:
                self.update_box.pack_forget()
            if self.visible:
                self._place()  # balandlik oʻzgardi

    def refresh_promo(self) -> None:
        for child in self.links.winfo_children():
            child.destroy()
        links = self.ui.promo["links"]
        for i, link in enumerate(links):
            self.links.grid_columnconfigure(i, weight=1)
            ctk.CTkButton(self.links, text=link["title"], height=30, fg_color=CARD_BG, text_color=TEXT,
                          border_width=1, border_color=CARD_BORDER, hover_color=NAV_ACTIVE, width=10,
                          command=lambda u=link["url"]: _open_url(u)).grid(row=0, column=i, sticky="ew",
                                                                            padx=4)

    def _on_master(self) -> None:
        self.ui.set_enabled(bool(self.master.get()))

    def _on_app(self) -> None:
        app = self.ui.state.get("app")
        if isinstance(app, dict) and app.get("id"):
            on = bool(self.app_switch.get())
            self.ui.save(apps=ac.set_app_enabled(self.ui.cfg, app["id"], app.get("name"), on))

    def _quit(self) -> None:
        self.ui.quit_main()
        self.close()

    def _on_update(self) -> None:
        self.ui.open_update()
        self.close()

    # ---- koʻrsatish / yopish -------------------------------------------------------
    def show(self) -> None:
        self.refresh()
        win = self.win
        self._anchor = win.winfo_pointerxy()  # belgi bosilgan joy (kursor hali shu yerda)
        self._place()
        win.deiconify()
        if IS_WIN:
            _win11_round_corners(win)
        _activate(win)
        self.visible, self._had_focus, self._shown_at = True, False, time.monotonic()
        win.after(150, self._watch_focus)

    def _place(self) -> None:
        win = self.win
        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        px, py = self._anchor
        left, top, right, bottom = _work_area(win)
        x = min(max(px - w // 2, left + 8), right - w - 8)
        # Menyu satri tepada (macOS) – pastga ochamiz; taskbar pastda (Windows) – yuqoriga
        y = py + 14 if py < (top + bottom) / 2 else py - h - 14
        y = min(max(y, top + 6), bottom - h - 6)
        win.geometry(f"{w}x{h}+{int(x)}+{int(y)}")

    def _watch_focus(self) -> None:
        if not self.visible:
            return
        if _app_active(self.win):
            self._had_focus = True
        elif self._had_focus or time.monotonic() - self._shown_at > 60:
            self.close()  # boshqa joy bosildi
            return
        self.win.after(200, self._watch_focus)

    def close(self) -> None:
        if self.visible:
            self.visible = False
            self.ui._panel_closed_at = time.monotonic()
            self.win.withdraw()


# --------------------------------------------------------------- toʻliq oyna
class SettingsWindow:
    PAGES = (("general", "Umumiy"), ("apps", "Dasturlar"), ("about", "Biz bilan"))
    SAMPLE = "O'zbekiston sho'x g'isht, choy va shahar"

    def __init__(self, ui: UI) -> None:
        self.ui = ui
        win = self.win = ctk.CTkToplevel(ui.root)
        win.title(f"{ac.APP_NAME} — Sozlamalar")
        win.geometry("880x620")
        win.minsize(780, 540)
        win.configure(fg_color=WINDOW_BG)
        win.protocol("WM_DELETE_WINDOW", self.close)
        if ui.icon_photo is not None:
            # CustomTkinter Windows'da 200 ms dan keyin oʻz belgisini qoʻyadi – bizniki undan keyin
            win.after(300, lambda: win.iconphoto(False, ui.icon_photo))
        win.grid_columnconfigure(1, weight=1)
        win.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self.content = ctk.CTkFrame(win, fg_color="transparent", corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        self.pages = {"general": self._build_general(), "apps": self._build_apps(),
                      "about": self._build_about()}
        self.select("general")
        self.refresh()

    def exists(self) -> bool:
        try:
            return bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def show(self, page: str | None = None) -> None:
        if page:
            self.select(page)
        self.win.deiconify()
        _activate(self.win)

    def close(self) -> None:
        self.win.destroy()
        self.ui.settings = None

    # ---- yon panel -----------------------------------------------------------------
    def _build_sidebar(self) -> None:
        ui = self.ui
        side = ctk.CTkFrame(self.win, width=220, corner_radius=0, fg_color=SIDEBAR_BG)
        side.grid(row=0, column=0, sticky="nsw")
        side.grid_propagate(False)
        side.grid_columnconfigure(0, weight=1)
        brand = ctk.CTkFrame(side, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=16, pady=(20, 18))
        if ui.logo40:
            ctk.CTkLabel(brand, image=ui.logo40, text="").pack(side="left")
        names = ctk.CTkFrame(brand, fg_color="transparent")
        names.pack(side="left", padx=10)
        ctk.CTkLabel(names, text=ac.APP_NAME, font=ui.f_head, anchor="w").pack(anchor="w")
        self.side_version = ctk.CTkLabel(names, text=f"versiya {ui.version}", font=ui.f_small,
                                         text_color=TEXT_MUTED, anchor="w", height=14)
        self.side_version.pack(anchor="w")
        self.side_version.bind("<Button-1>", lambda e: self.ui.update and self.select("about"))

        self.nav = {}
        for i, (key, title) in enumerate(self.PAGES, start=1):
            btn = ctk.CTkButton(side, text=f"   {title}", anchor="w", height=36, corner_radius=8,
                                font=ui.f_body, fg_color="transparent", text_color=TEXT,
                                hover_color=NAV_ACTIVE, command=lambda k=key: self.select(k))
            btn.grid(row=i, column=0, sticky="ew", padx=10, pady=2)
            self.nav[key] = btn
        side.grid_rowconfigure(len(self.PAGES) + 1, weight=1)

        bottom = ctk.CTkFrame(side, fg_color="transparent")
        bottom.grid(row=len(self.PAGES) + 2, column=0, sticky="ew", padx=10, pady=16)
        self.status_btn = ctk.CTkButton(bottom, text="", height=34, corner_radius=17, font=ui.f_bold,
                                        border_width=1, border_color=CARD_BORDER, fg_color=CARD_BG,
                                        hover_color=NAV_ACTIVE, command=self._toggle_enabled)
        self.status_btn.pack(fill="x")
        self.status_hint = ctk.CTkLabel(bottom, text="", font=ui.f_small, text_color=TEXT_MUTED, height=16)
        self.status_hint.pack(pady=(6, 0))

    def select(self, key: str) -> None:
        for k, btn in self.nav.items():
            btn.configure(fg_color=NAV_ACTIVE if k == key else "transparent",
                          font=self.ui.f_bold if k == key else self.ui.f_body)
        for k, page in self.pages.items():
            if k == key:
                page.grid(row=0, column=0, sticky="nsew")
            else:
                page.grid_remove()

    def _toggle_enabled(self) -> None:
        if self.ui.main_alive():
            self.ui.set_enabled(not self.ui.enabled())

    # ---- umumiy elementlar --------------------------------------------------------------
    def _page(self, title: str, subtitle: str, scroll: bool = True):
        ui = self.ui
        page = (ctk.CTkScrollableFrame(self.content, fg_color="transparent", corner_radius=0)
                if scroll else ctk.CTkFrame(self.content, fg_color="transparent", corner_radius=0))
        inner = ctk.CTkFrame(page, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=28, pady=(22, 24))
        ctk.CTkLabel(inner, text=title, font=ui.f_title, anchor="w").pack(anchor="w")
        ctk.CTkLabel(inner, text=subtitle, font=ui.f_body, text_color=TEXT_MUTED, anchor="w",
                     justify="left", wraplength=560).pack(anchor="w", pady=(2, 4))
        return page, inner

    def _section(self, parent, title: str, expand: bool = False):
        ctk.CTkLabel(parent, text=title, font=self.ui.f_bold, text_color=TEXT_MUTED,
                     anchor="w").pack(anchor="w", padx=4, pady=(18, 6))
        card = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=12, border_width=1,
                            border_color=CARD_BORDER)
        card.pack(fill="both" if expand else "x", expand=expand)
        return card

    def _row(self, card, text: str, sub: str | None = None, first: bool = False):
        if not first:
            ctk.CTkFrame(card, height=1, fg_color=CARD_BORDER).pack(fill="x", padx=16)
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=10)
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(left, text=text, font=self.ui.f_body, anchor="w").pack(anchor="w")
        if sub:
            ctk.CTkLabel(left, text=sub, font=self.ui.f_small, text_color=TEXT_MUTED, anchor="w",
                         justify="left", wraplength=440, height=14).pack(anchor="w")
        return row

    def _switch(self, row, value: bool, command):
        sw = ctk.CTkSwitch(row, text="", width=46, progress_color=GREEN)
        (sw.select if value else sw.deselect)()
        sw.configure(command=lambda: command(bool(sw.get())))
        sw.pack(side="right")
        return sw

    # ---- Umumiy ------------------------------------------------------------------------
    def _build_general(self):
        ui, cfg = self.ui, self.ui.cfg
        page, inner = self._page("Umumiy", "Harflar qanday almashtirilishi va dastur qachon ishga tushishi.")

        card = self._section(inner, "Sinab koʻring")
        self.try_entry = ctk.CTkEntry(card, height=38, font=ui.f_body, border_color=CARD_BORDER,
                                      placeholder_text="Eski yozuvda yozing: o'zbek, g'isht, choy…")
        self.try_entry.pack(fill="x", padx=16, pady=(14, 8))
        self.try_entry.insert(0, self.SAMPLE)
        self.try_out = ctk.CTkTextbox(card, height=44, font=ctk.CTkFont(size=20), wrap="word",
                                      fg_color="transparent", border_width=0, activate_scrollbars=False)
        self.try_out.pack(fill="x", padx=10, pady=(0, 10))
        self.try_out.tag_config("hl", foreground=GREEN)
        self.try_entry.bind("<KeyRelease>", lambda e: self._update_try())
        self._update_try()

        card = self._section(inner, "Ishga tushish")
        first = True
        if ui.autostart and ui.autostart[0]():
            _, enabled, set_enabled = ui.autostart
            row = self._row(card, "Kompyuter yoqilganda ishga tushsin",
                            "Belgi menyu satrida / soat yonida paydo boʻladi.", first=True)

            def on_autostart(value: bool) -> None:
                set_enabled(value)
                _set_switch(sw, enabled())  # sozlanmagan boʻlsa – haqiqiy holatni koʻrsatamiz
            sw = self._switch(row, enabled(), on_autostart)
            first = False
        row = self._row(card, "Ochilganda almashtirish yoqilgan boʻlsin", first=first)
        self._switch(row, bool(cfg["enabled_on_start"]), lambda v: ui.save(enabled_on_start=v))

        card = self._section(inner, "Yozish")
        row = self._row(card, "Backspace – asl yozuvni qaytaradi",
                        "Almashgandan keyin darhol bosilsa: ş → sh", first=True)
        self._switch(row, bool(cfg["backspace_undo"]), lambda v: ui.save(backspace_undo=v))
        row = self._row(card, "s'h – ş emas, sh boʻlib qoladi", "Is'hoq → Ishoq, as'hob → ashob")
        self._switch(row, bool(cfg["strip_sh_apostrophe"]),
                     lambda v: (ui.save(strip_sh_apostrophe=v), self._update_try()))
        row = self._row(card, "Apostrof – rasmiy tutuq belgisi", "ma'no → maʼno (U+02BC)")
        self._switch(row, bool(cfg["tutuq_belgisi"]),
                     lambda v: (ui.save(tutuq_belgisi=TUTUQ if v else None), self._update_try()))

        card = self._section(inner, "Tezkor tugma")
        row = self._row(card, "Yoqish / oʻchirish", "Inglizcha yozayotganda vaqtincha oʻchirish uchun",
                        first=True)
        keys = ctk.CTkFrame(row, fg_color="transparent")
        keys.pack(side="right")
        for key in hotkey_keys(cfg.get("hotkey", "")):
            ctk.CTkLabel(keys, text=key, font=ui.f_bold, fg_color=WINDOW_BG, corner_radius=6,
                         width=34, height=28).pack(side="left", padx=2)
        return page

    def _update_try(self) -> None:
        cfg = self.ui.cfg
        out = convert_text(self.try_entry.get(), strip_sh_apostrophe=bool(cfg["strip_sh_apostrophe"]),
                           tutuq=cfg["tutuq_belgisi"] or None)
        box = self.try_out
        box.configure(state="normal")
        box.delete("1.0", "end")
        for ch in out:
            box.insert("end", ch, ("hl",) if ch in "öÖğĞşŞçÇʼ" else ())
        box.configure(state="disabled")

    # ---- Dasturlar ----------------------------------------------------------------------
    def _build_apps(self):
        ui = self.ui
        page, inner = self._page("Dasturlar", "Harflar faqat tanlangan dasturlarda almashtiriladi – terminal, "
                                              "kod muharriri, oʻyinlarda dastur aralashmaydi.", scroll=False)
        self.mode = ctk.CTkSegmentedButton(inner, values=["Faqat roʻyxatdagilarda", "Hamma dasturlarda"],
                                           selected_color=GREEN, selected_hover_color=GREEN_HOVER,
                                           text_color=ON_GREEN, font=ui.f_body, height=34, command=self._on_mode)
        self.mode.pack(anchor="w", pady=(12, 0))
        self.mode_hint = ctk.CTkLabel(inner, text="", font=ui.f_small, text_color=TEXT_MUTED, anchor="w")
        self.mode_hint.pack(anchor="w", pady=(4, 0))

        card = self._section(inner, "Roʻyxat", expand=True)
        self.app_list = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.app_list.pack(fill="both", expand=True, padx=4, pady=4)

        buttons = ctk.CTkFrame(inner, fg_color="transparent")
        buttons.pack(fill="x", pady=(12, 0))
        ctk.CTkButton(buttons, text="+  Dastur qoʻshish", font=ui.f_bold, fg_color=GREEN,
                      hover_color=GREEN_HOVER, text_color=ON_GREEN, height=34,
                      command=self._pick_app).pack(side="left")
        ctk.CTkButton(buttons, text="Standart roʻyxat", fg_color="transparent", border_width=1,
                      border_color=CARD_BORDER, text_color=TEXT, hover_color=NAV_ACTIVE, height=34,
                      command=self._reset_apps).pack(side="right")
        self._fill_apps()
        return page

    def _on_mode(self, value: str) -> None:
        self.ui.save(apps_mode="all" if value.startswith("Hamma") else "list")

    def _fill_apps(self) -> None:
        ui = self.ui
        for child in self.app_list.winfo_children():
            child.destroy()
        seen = set()
        apps = sorted(ac.config_apps(ui.cfg), key=lambda a: a["name"].lower())
        for app in apps:
            if app["id"].lower() in seen:
                continue
            if seen:
                ctk.CTkFrame(self.app_list, height=1, fg_color=CARD_BORDER).pack(fill="x", padx=10)
            seen.add(app["id"].lower())
            row = ctk.CTkFrame(self.app_list, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=6)
            text = ctk.CTkFrame(row, fg_color="transparent")
            text.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(text, text=app["name"], font=ui.f_body, anchor="w", height=18).pack(anchor="w")
            ctk.CTkLabel(text, text=app["id"], font=ui.f_small, text_color=TEXT_MUTED, anchor="w",
                         height=14).pack(anchor="w")
            ctk.CTkButton(row, text="Olib tashlash", width=110, height=28, fg_color="transparent",
                          border_width=1, border_color=CARD_BORDER, text_color=TEXT_MUTED,
                          hover_color=NAV_ACTIVE,
                          command=lambda i=app["id"]: self._remove_app(i)).pack(side="right")
        if not seen:
            ctk.CTkLabel(self.app_list, text="Roʻyxat boʻsh – «Dastur qoʻshish» ni bosing.",
                         text_color=TEXT_MUTED).pack(pady=20)

    def _remove_app(self, app_id: str) -> None:
        self.ui.save(apps=ac.set_app_enabled(self.ui.cfg, app_id, None, False))
        self._fill_apps()

    def _reset_apps(self) -> None:
        self.ui.save(apps=None)  # null – keyingi versiyalardagi standart roʻyxat ham ishlaydi
        self._fill_apps()

    def _pick_app(self) -> None:
        ui = self.ui
        dlg = ctk.CTkToplevel(self.win)
        dlg.title("Dastur qoʻshish")
        dlg.geometry("460x520")
        dlg.configure(fg_color=WINDOW_BG)
        dlg.transient(self.win)
        ctk.CTkLabel(dlg, text="Hozir ochiq dasturlar", font=ui.f_head, anchor="w").pack(
            anchor="w", padx=20, pady=(18, 0))
        ctk.CTkLabel(dlg, text="Kerakli dastur koʻrinmasa – uni oching va «Yangilash» ni bosing.",
                     font=ui.f_small, text_color=TEXT_MUTED, anchor="w").pack(anchor="w", padx=20)
        lst = ctk.CTkScrollableFrame(dlg, fg_color=CARD_BG, corner_radius=12, border_width=1,
                                     border_color=CARD_BORDER)
        lst.pack(fill="both", expand=True, padx=16, pady=12)

        def add(app_id: str, name: str, btn) -> None:
            ui.save(apps=ac.set_app_enabled(ui.cfg, app_id, name, True))
            btn.configure(text="Qoʻshildi ✓", state="disabled")
            self._fill_apps()

        def refresh() -> None:
            for child in lst.winfo_children():
                child.destroy()
            have = {a["id"].lower() for a in ac.config_apps(ui.cfg)}
            found = [(i, n) for i, n in running_apps() if i.lower() not in have]
            for app_id, name in found:
                row = ctk.CTkFrame(lst, fg_color="transparent")
                row.pack(fill="x", padx=8, pady=5)
                ctk.CTkLabel(row, text=name, font=ui.f_body, anchor="w").pack(side="left")
                btn = ctk.CTkButton(row, text="Qoʻshish", width=90, height=28, fg_color=GREEN,
                                    hover_color=GREEN_HOVER, text_color=ON_GREEN)
                btn.configure(command=lambda i=app_id, n=name, b=btn: add(i, n, b))
                btn.pack(side="right")
            if not found:
                ctk.CTkLabel(lst, text="Qoʻshiladigan dastur yoʻq.", text_color=TEXT_MUTED).pack(pady=20)

        row = ctk.CTkFrame(dlg, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(row, text="Yangilash", fg_color="transparent", border_width=1, border_color=CARD_BORDER,
                      text_color=TEXT, hover_color=NAV_ACTIVE, command=refresh).pack(side="left")
        ctk.CTkButton(row, text="Tayyor", fg_color=GREEN, hover_color=GREEN_HOVER, text_color=ON_GREEN,
                      command=dlg.destroy).pack(side="right")
        refresh()
        dlg.after(150, lambda: (dlg.lift(), dlg.focus_force()))

    # ---- Biz bilan ---------------------------------------------------------------------
    def _build_about(self):
        page, self.about = self._page("Biz bilan", "Eʼlonlar, yangiliklar va ijtimoiy tarmoqlar.")
        self.about_body = ctk.CTkFrame(self.about, fg_color="transparent")
        self.about_body.pack(fill="x")
        self._build_version_card(self.about)
        self.refresh_promo()
        return page

    def _build_version_card(self, parent) -> None:
        ui = self.ui
        card = self._section(parent, "Dastur haqida")
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=10)
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(left, text=f"{ac.APP_NAME} {ui.version}", font=ui.f_body, anchor="w").pack(anchor="w")
        self.upd_text = ctk.CTkLabel(left, text="", font=ui.f_small, text_color=TEXT_MUTED, anchor="w",
                                     justify="left", wraplength=400)
        self.upd_text.pack(anchor="w")
        self.upd_btn = ctk.CTkButton(row, text="", width=170, height=32, border_color=CARD_BORDER,
                                     command=self._on_update_btn)
        self.upd_btn.pack(side="right")
        self._upd_view = None
        row = self._row(card, "Yangi versiyani avtomatik tekshirish",
                        "Kuniga bir marta GitHub'dan faqat versiya raqami soʻraladi, boshqa hech narsa yuborilmaydi.")
        self._switch(row, bool(ui.cfg.get("check_updates", True)), lambda v: ui.save(check_updates=v))
        row = self._row(card, "Yangi oʻzbek lotin alifbosi (OʻRQ-1184)", "Ochiq manba kodi va barcha versiyalar")
        ctk.CTkButton(row, text="GitHub", width=80, fg_color="transparent", border_width=1,
                      border_color=CARD_BORDER, text_color=TEXT, hover_color=NAV_ACTIVE,
                      command=lambda: _open_url(ac.RELEASES_URL)).pack(side="right")

    def _on_update_btn(self) -> None:
        if self.ui.update:
            self.ui.open_update()
        else:
            self.ui.check_update()

    def _refresh_update(self) -> None:
        ui = self.ui
        upd, status, data = ui.update, ui.update_status, ui.update_data
        if upd:
            text = f"Yangi versiya chiqdi: {upd['version']}. Yuklab olib, ustidan oʻrnating – sozlamalar saqlanadi."
            button = (f"{upd['version']} ni yuklab olish", True)
        else:
            if status == "checking":
                text = "Tekshirilmoqda…"
            elif status == "failed":
                text = "Tekshirib boʻlmadi – internet aloqasini tekshiring."
            elif ac.parse_version(ui.version) is None:
                text = "Manba koddan ishga tushirilgan" + (f" · eng soʻnggi: {data['version']}"
                                                          if data.get("version") else "")
            elif isinstance(data.get("checked"), (int, float)):
                text = "Eng soʻnggi versiya oʻrnatilgan · tekshirildi " + time.strftime(
                    "%d.%m %H:%M", time.localtime(data["checked"]))
            else:
                text = "Hali tekshirilmagan"
            button = ("Tekshirish", False)
        view = (text, button, status == "checking", bool(upd))
        if view == self._upd_view:
            return  # har soniyada qayta chizmaymiz
        self._upd_view = view
        self.upd_text.configure(text=text, text_color=TEXT_OK if upd else TEXT_MUTED)
        green = button[1]
        self.upd_btn.configure(text=button[0], fg_color=GREEN if green else "transparent",
                               hover_color=GREEN_HOVER if green else NAV_ACTIVE,
                               text_color=ON_GREEN if green else TEXT, border_width=0 if green else 1,
                               font=ui.f_bold if green else ui.f_body,
                               state="disabled" if status == "checking" else "normal")
        self.side_version.configure(
            text=f"{ui.version}  →  {upd['version']} chiqdi" if upd else f"versiya {ui.version}",
            text_color=TEXT_OK if upd else TEXT_MUTED)

    def refresh_promo(self) -> None:
        ui = self.ui
        for child in self.about_body.winfo_children():
            child.destroy()
        for ad in ui.promo["ads"]:
            card = self._section(self.about_body, "Eʼlon")
            ctk.CTkLabel(card, text=ad["title"], font=ui.f_head, anchor="w").pack(anchor="w", padx=16,
                                                                               pady=(14, 2))
            if ad["text"]:
                ctk.CTkLabel(card, text=ad["text"], font=ui.f_body, anchor="w", justify="left",
                             wraplength=540).pack(anchor="w", padx=16)
            if ad["url"]:
                ctk.CTkButton(card, text=ad["button"], fg_color=GREEN, hover_color=GREEN_HOVER,
                              text_color=ON_GREEN, font=ui.f_bold, command=lambda u=ad["url"]: _open_url(u)).pack(
                    anchor="w", padx=16, pady=(10, 14))
            else:
                ctk.CTkFrame(card, height=12, fg_color="transparent").pack()
        card = self._section(self.about_body, "Bizni kuzatib boring")
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=12)
        if ui.promo["links"]:
            for i, link in enumerate(ui.promo["links"]):
                row.grid_columnconfigure(i, weight=1)
                ctk.CTkButton(row, text=link["title"], height=36, fg_color=WINDOW_BG, text_color=TEXT,
                              border_width=1, border_color=CARD_BORDER, hover_color=NAV_ACTIVE,
                              command=lambda u=link["url"]: _open_url(u)).grid(row=0, column=i,
                                                                                sticky="ew", padx=4)
        else:
            ctk.CTkLabel(row, text="Havolalar tez orada qoʻshiladi.", text_color=TEXT_MUTED).pack(anchor="w")

    # ---- holat -------------------------------------------------------------------------
    def refresh(self) -> None:
        ui = self.ui
        if ui.main_alive():
            on = ui.enabled()
            self.status_btn.configure(text="●  Yoqilgan" if on else "○  Oʻchirilgan",
                                      text_color=TEXT_OK if on else TEXT_MUTED, state="normal")
            self.status_hint.configure(text="Bosing – " + ("oʻchirish" if on else "yoqish"))
        else:
            self.status_btn.configure(text="Dastur ishlamayapti", text_color=TEXT_MUTED, state="disabled")
            self.status_hint.configure(text="Yangi Alifbo ni qayta oching")
        mode_all = ui.cfg.get("apps_mode") == "all"
        self.mode.set("Hamma dasturlarda" if mode_all else "Faqat roʻyxatdagilarda")
        self.mode_hint.configure(text="Roʻyxat hisobga olinmaydi – hamma joyda almashtiriladi." if mode_all
                                 else "Roʻyxatdagi dasturlarda ishlaydi. Panel orqali ham qoʻshish mumkin.")
        self._refresh_update()


# ----------------------------------------------------------------------- kirish
def run_ui(mode: str = "settings", autostart=None, lock=None) -> int:
    """lock() False qaytarsa – oyna jarayoni allaqachon ishlayapti: unga soʻrov yozib chiqamiz."""
    if lock is not None and not lock():
        try:
            ac.write_runtime(ac.UI_REQUEST_FILE, {"mode": mode, "at": time.time()})
        except OSError:
            pass
        return 0
    ui = UI(autostart)
    ui.root.after(50, lambda: ui.show(mode))
    ui.root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(run_ui(sys.argv[1] if len(sys.argv) > 1 else "settings"))
