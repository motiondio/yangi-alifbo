# -*- coding: utf-8 -*-
"""
Yangi Alifbo – sozlamalar oynasi (tkinter).

Asosiy dastur uni alohida jarayon sifatida ochadi:  yangi_alifbo.py --settings
Har bir oʻzgarish darhol foydalanuvchi config.json iga yoziladi; asosiy dastur faylni
kuzatib turadi va oʻzgarishni bir soniya ichida qoʻllaydi.  "Biz bilan" boʻlimidagi
havolalar va reklama GitHub'dagi promo.json dan yangilanadi (internetga faqat shu oyna ulanadi).
"""
from __future__ import annotations

import base64
import io
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import font as tkfont
from tkinter import messagebox, ttk

import alifbo_config as ac
from alifbo_apps import running_apps
from alifbo_core import TUTUQ

IS_MAC = sys.platform == "darwin"
REPO_URL = "https://github.com/motiondio/yangi-alifbo"


def _logo_photo(size: int):
    """ö belgisi (make_icon.py dagi bilan bir xil) – tk.PhotoImage, Pillow boʻlmasa None."""
    try:
        from PIL import Image, ImageDraw
        big = size * 4  # katta chizib kichraytiramiz – chetlari silliq chiqadi
        s = big / 64.0
        img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, big - 1, big - 1), radius=int(14 * s), fill=(46, 160, 67, 255))
        white = (255, 255, 255, 255)
        d.ellipse((12 * s, 26 * s, 52 * s, 60 * s), outline=white, width=int(8 * s))
        d.ellipse((16 * s, 7 * s, 27 * s, 18 * s), fill=white)
        d.ellipse((37 * s, 7 * s, 48 * s, 18 * s), fill=white)
        buf = io.BytesIO()
        img.resize((size, size), Image.LANCZOS).save(buf, "PNG")
        return tk.PhotoImage(data=base64.b64encode(buf.getvalue()))
    except Exception:
        return None


def pretty_hotkey(hotkey: str) -> str:
    """'<ctrl>+<alt>+u' → 'Ctrl+Option+U' (Mac) / 'Ctrl+Alt+U'."""
    names = {"ctrl": "Ctrl", "alt": "Option" if IS_MAC else "Alt", "shift": "Shift",
             "cmd": "Cmd" if IS_MAC else "Win"}
    parts = []
    for part in hotkey.split("+"):
        key = part.strip().strip("<>").lower()
        parts.append(names.get(key, key.upper()))
    return "+".join(parts)


def _open_url(url: str) -> None:
    if url.startswith("https://"):
        webbrowser.open(url)


def _wrapping_label(parent, text: str, **kw) -> ttk.Label:
    """Oyna kengligiga qarab satrga oʻraladigan matn (oʻzgarmas wraplength kesib qoʻyadi)."""
    label = ttk.Label(parent, text=text, justify="left", **kw)
    label.bind("<Configure>", lambda e: label.configure(wraplength=max(e.width - 4, 100)))
    return label


class SettingsWindow:
    def __init__(self, root: tk.Tk, autostart=None) -> None:
        self.root = root
        self.cfg = ac.load_config()
        self.apps = ac.config_apps(self.cfg)
        self._autostart = autostart  # (supported, enabled, set) – asosiy moduldan
        self._promo_q: "queue.Queue[dict | None]" = queue.Queue()

        root.title(f"{ac.APP_NAME} — Sozlamalar")
        root.geometry("580x640")
        root.minsize(520, 560)

        base = tkfont.nametofont("TkDefaultFont")
        self.f_title = base.copy()
        self.f_title.configure(size=base.cget("size") + 8, weight="bold")
        self.f_bold = base.copy()
        self.f_bold.configure(weight="bold")
        style = ttk.Style(root)
        style.configure("Muted.TLabel", foreground="gray")

        self._logo = _logo_photo(56)
        if self._logo is not None:
            try:
                root.iconphoto(True, self._logo)
            except tk.TclError:
                pass

        self._build_header()
        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        nb.add(self._build_general(nb), text="Umumiy")
        nb.add(self._build_apps(nb), text="Dasturlar")
        nb.add(self._build_about(nb), text="Biz bilan")

        threading.Thread(target=self._fetch_promo, name="promo", daemon=True).start()
        root.after(200, self._poll_promo)

    # ------------------------------------------------------------- umumiy
    def _save(self, **changes) -> None:
        self.cfg.update(changes)
        try:
            ac.save_user_settings(changes)
        except OSError as exc:
            messagebox.showerror(ac.APP_NAME, f"Sozlamani saqlab boʻlmadi:\n{exc}", parent=self.root)

    def _build_header(self) -> None:
        head = ttk.Frame(self.root, padding=(16, 14, 16, 10))
        head.pack(fill="x")
        if self._logo is not None:
            ttk.Label(head, image=self._logo).pack(side="left", padx=(0, 12))
        text = ttk.Frame(head)
        text.pack(side="left", fill="x", expand=True)
        ttk.Label(text, text=ac.APP_NAME, font=self.f_title).pack(anchor="w")
        ttk.Label(text, text=f"Yangi oʻzbek lotin alifbosi  ·  versiya {ac.app_version()}",
                  style="Muted.TLabel").pack(anchor="w")
        ttk.Label(text, text="oʻ → ö    gʻ → ğ    sh → ş    ch → ç").pack(anchor="w", pady=(2, 0))

    def _check(self, parent, text: str, value: bool, on_change) -> tk.BooleanVar:
        var = tk.BooleanVar(value=value)
        ttk.Checkbutton(parent, text=text, variable=var,
                        command=lambda: on_change(var.get())).pack(anchor="w", pady=3)
        return var

    def _build_general(self, nb) -> ttk.Frame:
        tab = ttk.Frame(nb, padding=14)

        start = ttk.LabelFrame(tab, text="Ishga tushish", padding=10)
        start.pack(fill="x")
        if self._autostart and self._autostart[0]():
            _, enabled, set_enabled = self._autostart

            def on_autostart(value: bool) -> None:
                set_enabled(value)
                self._autostart_var.set(enabled())  # sozlanmagan boʻlsa – haqiqiy holatni koʻrsatamiz
            self._autostart_var = self._check(start, "Kompyuter yoqilganda avtomatik ishga tushsin",
                                              enabled(), on_autostart)
        self._check(start, "Dastur ochilganda almashtirish yoqilgan boʻlsin",
                    bool(self.cfg["enabled_on_start"]), lambda v: self._save(enabled_on_start=v))

        typing = ttk.LabelFrame(tab, text="Yozish", padding=10)
        typing.pack(fill="x", pady=(12, 0))
        self._check(typing, "Almashgandan keyin darhol Backspace – asl yozuv qaytadi (ş → sh)",
                    bool(self.cfg["backspace_undo"]), lambda v: self._save(backspace_undo=v))
        self._check(typing, "s'h deb yozilsa – ş emas, sh qoladi (Is'hoq → Ishoq)",
                    bool(self.cfg["strip_sh_apostrophe"]), lambda v: self._save(strip_sh_apostrophe=v))
        self._check(typing, "Harfdan keyingi apostrof – rasmiy tutuq belgisi (ma'no → maʼno)",
                    bool(self.cfg["tutuq_belgisi"]),
                    lambda v: self._save(tutuq_belgisi=TUTUQ if v else None))

        keys = ttk.LabelFrame(tab, text="Tezkor tugma", padding=10)
        keys.pack(fill="x", pady=(12, 0))
        ttk.Label(keys, text=f"Yoqish / oʻchirish:  {pretty_hotkey(self.cfg['hotkey'])}",
                  font=self.f_bold).pack(anchor="w")
        ttk.Label(keys, text="Ingliz tilida yozayotganda vaqtincha oʻchirib qoʻyish uchun.",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 0))

        ttk.Label(tab, text="Oʻzgarishlar darhol kuchga kiradi.",
                  style="Muted.TLabel").pack(anchor="w", pady=(14, 0))
        return tab

    # ------------------------------------------------------------ dasturlar
    def _build_apps(self, nb) -> ttk.Frame:
        tab = ttk.Frame(nb, padding=14)
        _wrapping_label(tab, "Harflar faqat tanlangan dasturlarda almashtiriladi. Terminal, kod "
                             "muharriri, oʻyinlar kabi joylarda dastur aralashmaydi.").pack(fill="x")

        self._mode = tk.StringVar(value="all" if self.cfg.get("apps_mode") == "all" else "list")
        modes = ttk.Frame(tab)
        modes.pack(anchor="w", pady=(10, 6))
        ttk.Radiobutton(modes, text="Faqat roʻyxatdagi dasturlarda (tavsiya etiladi)", value="list",
                        variable=self._mode, command=self._on_mode).pack(anchor="w")
        ttk.Radiobutton(modes, text="Hamma dasturlarda", value="all",
                        variable=self._mode, command=self._on_mode).pack(anchor="w")

        box = ttk.Frame(tab)
        box.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(box, columns=("name", "id"), show="headings", height=10,
                                 selectmode="extended")
        self.tree.heading("name", text="Dastur")
        self.tree.heading("id", text="Identifikator")
        self.tree.column("name", width=200)
        self.tree.column("id", width=260)
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        buttons = ttk.Frame(tab)
        buttons.pack(fill="x", pady=(8, 0))
        self._app_buttons = [
            ttk.Button(buttons, text="Qoʻshish…", command=self._pick_app),
            ttk.Button(buttons, text="Olib tashlash", command=self._remove_apps),
        ]
        for b in self._app_buttons:
            b.pack(side="left", padx=(0, 6))
        reset = ttk.Button(buttons, text="Standart roʻyxat", command=self._reset_apps)
        reset.pack(side="right")
        self._app_buttons.append(reset)

        self._fill_tree()
        self._on_mode(save=False)
        return tab

    def _fill_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for app in sorted(self.apps, key=lambda a: a["name"].lower()):
            if not self.tree.exists(app["id"]):  # qoʻlda tahrirlangan faylda takror boʻlishi mumkin
                self.tree.insert("", "end", iid=app["id"], values=(app["name"], app["id"]))

    def _on_mode(self, save: bool = True) -> None:
        mode = self._mode.get()
        for b in self._app_buttons:
            b.state(["disabled"] if mode == "all" else ["!disabled"])
        if save:
            self._save(apps_mode=mode)

    def _set_apps(self, apps) -> None:
        self.apps = apps
        self._save(apps=apps)
        self._fill_tree()

    def _remove_apps(self) -> None:
        chosen = set(self.tree.selection())
        if chosen:
            self._set_apps([a for a in self.apps if a["id"] not in chosen])

    def _reset_apps(self) -> None:
        if messagebox.askyesno(ac.APP_NAME, "Dasturlar roʻyxati standart holatga qaytarilsinmi?",
                               parent=self.root):
            self.apps = ac.default_apps()
            self._save(apps=None)  # null – keyingi versiyalardagi standart roʻyxat ham ishlaydi
            self._fill_tree()

    def _pick_app(self) -> None:
        dlg = tk.Toplevel(self.root)
        dlg.title("Dastur qoʻshish")
        dlg.geometry("420x420")
        dlg.transient(self.root)
        frame = ttk.Frame(dlg, padding=12)
        frame.pack(fill="both", expand=True)
        _wrapping_label(frame, "Hozir ochiq dasturlar. Kerakli dastur koʻrinmasa – uni oching va "
                               "«Yangilash» ni bosing.").pack(fill="x")
        lst = tk.Listbox(frame, selectmode="extended", activestyle="none", height=14)
        lst.pack(fill="both", expand=True, pady=8)
        found: list = []

        def refresh() -> None:
            have = {a["id"].lower() for a in self.apps}
            found[:] = [(i, n) for i, n in running_apps() if i.lower() not in have]
            lst.delete(0, "end")
            for _id, name in found:
                lst.insert("end", name)
            if not found:
                lst.insert("end", "(qoʻshiladigan dastur yoʻq)")

        def add(*_) -> None:
            picked = [found[i] for i in lst.curselection() if i < len(found)]
            if picked:
                self._set_apps(self.apps + [{"id": i, "name": n} for i, n in picked])
                dlg.destroy()

        lst.bind("<Double-Button-1>", add)
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Button(row, text="Yangilash", command=refresh).pack(side="left")
        ttk.Button(row, text="Bekor qilish", command=dlg.destroy).pack(side="right")
        ttk.Button(row, text="Qoʻshish", command=add).pack(side="right", padx=6)
        refresh()
        dlg.grab_set()

    # -------------------------------------------------------------- biz bilan
    def _build_about(self, nb) -> ttk.Frame:
        self._about = ttk.Frame(nb, padding=14)
        self._render_promo(ac.load_promo())
        return self._about

    def _render_promo(self, promo: dict) -> None:
        for child in self._about.winfo_children():
            child.destroy()
        for ad in promo["ads"]:
            card = ttk.LabelFrame(self._about, text=ad["title"], padding=10)
            card.pack(fill="x", pady=(0, 10))
            if ad["text"]:
                _wrapping_label(card, ad["text"]).pack(fill="x")
            if ad["url"]:
                ttk.Button(card, text=ad["button"],
                           command=lambda u=ad["url"]: _open_url(u)).pack(anchor="w", pady=(8, 0))
        social = ttk.LabelFrame(self._about, text="Bizni kuzatib boring", padding=10)
        social.pack(fill="x", pady=(0, 10))
        if promo["links"]:
            row = ttk.Frame(social)
            row.pack(anchor="w")
            for link in promo["links"]:
                ttk.Button(row, text=link["title"],
                           command=lambda u=link["url"]: _open_url(u)).pack(side="left", padx=(0, 6))
        else:
            ttk.Label(social, text="Havolalar tez orada qoʻshiladi.", style="Muted.TLabel").pack(anchor="w")
        footer = ttk.Frame(self._about)
        footer.pack(fill="x", side="bottom")
        ttk.Button(footer, text="Dastur sahifasi (GitHub)",
                   command=lambda: _open_url(REPO_URL)).pack(side="left")
        ttk.Button(footer, text="Yangi versiyalar",
                   command=lambda: _open_url(REPO_URL + "/releases/latest")).pack(side="left", padx=6)
        self._promo_status = ttk.Label(self._about, text="", style="Muted.TLabel")
        self._promo_status.pack(side="bottom", anchor="w", pady=(0, 6))

    def _fetch_promo(self) -> None:
        self._promo_q.put(ac.fetch_promo())  # tarmoq – alohida oqimda, oyna qotmasin

    def _poll_promo(self) -> None:
        try:
            promo = self._promo_q.get_nowait()
        except queue.Empty:
            self.root.after(200, self._poll_promo)
            return
        if promo is not None:
            self._render_promo(promo)
        else:
            self._promo_status.configure(text="Internetga ulanib boʻlmadi – saqlangan maʼlumot koʻrsatilmoqda.")


def _bring_to_front(root: tk.Tk) -> None:
    root.lift()
    root.attributes("-topmost", True)
    root.after(400, lambda: root.attributes("-topmost", False))
    if IS_MAC:
        try:
            # Ilova Dock'da yoʻq (LSUIElement), shuning uchun oynani oʻzimiz oldinga chiqaramiz
            from AppKit import NSApplication
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        except Exception:
            pass
    root.focus_force()


def run_settings(autostart=None) -> int:
    root = tk.Tk()
    SettingsWindow(root, autostart)
    _bring_to_front(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(run_settings())
