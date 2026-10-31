# -*- coding: utf-8 -*-
"""
Hozir qaysi dastur oldinda (faol) ekanini va ishlab turgan dasturlar roʻyxatini aniqlaydi.

Identifikator (alifbo_config dagi roʻyxatlar bilan bir xil):
    macOS   – bundle id:  ru.keepcoder.Telegram, com.microsoft.edgemac
    Windows – .exe nomi (kichik harflarda):  telegram.exe, msedge.exe
Aniqlab boʻlmasa – None (asosiy dastur bunda ishlayveradi).
"""
from __future__ import annotations

import os
import sys
from typing import List, Optional, Tuple

OWN_IDS = {"uz.yangialifbo.app", "yangialifbo.exe"}

if sys.platform == "darwin":
    def frontmost_app_id() -> Optional[str]:
        # NSWorkspace qiymatini asosiy oqimdagi run loop (tray) yangilab turadi – arzon va aniq
        try:
            from AppKit import NSWorkspace
            app = NSWorkspace.sharedWorkspace().frontmostApplication()
            bundle_id = app.bundleIdentifier() if app is not None else None
            if bundle_id:
                return str(bundle_id)
        except Exception:
            pass
        # Zaxira: Accessibility orqali (run loop boʻlmasa ham ishlaydi)
        try:
            import HIServices as AX
            from AppKit import NSRunningApplication
            system = AX.AXUIElementCreateSystemWide()
            AX.AXUIElementSetMessagingTimeout(system, 0.25)
            err, app = AX.AXUIElementCopyAttributeValue(system, AX.kAXFocusedApplicationAttribute, None)
            if err or app is None:
                return None
            err, pid = AX.AXUIElementGetPid(app, None)
            if err:
                return None
            running = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
            bundle_id = running.bundleIdentifier() if running is not None else None
            return str(bundle_id) if bundle_id else None
        except Exception:
            return None

    def running_apps() -> List[Tuple[str, str]]:
        from AppKit import NSApplicationActivationPolicyRegular, NSWorkspace
        seen = {}
        for app in NSWorkspace.sharedWorkspace().runningApplications():
            bundle_id = app.bundleIdentifier()
            if (bundle_id and app.activationPolicy() == NSApplicationActivationPolicyRegular
                    and str(bundle_id).lower() not in OWN_IDS):
                seen[str(bundle_id)] = str(app.localizedName() or bundle_id)
        return sorted(seen.items(), key=lambda kv: kv[1].lower())

elif sys.platform.startswith("win"):
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user32.EnumChildWindows.argtypes = [wintypes.HWND, _WNDENUMPROC, wintypes.LPARAM]
    _user32.EnumWindows.argtypes = [_WNDENUMPROC, wintypes.LPARAM]
    _user32.IsWindowVisible.argtypes = [wintypes.HWND]
    _user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    _user32.GetWindow.restype = wintypes.HWND
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    # Oynasi boʻlsa ham, foydalanuvchi matn yozadigan dastur emas
    _SKIP = OWN_IDS | {"applicationframehost.exe", "textinputhost.exe", "shellexperiencehost.exe",
                       "searchhost.exe", "startmenuexperiencehost.exe", "systemsettings.exe"}

    def _pid(hwnd) -> int:
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def _exe_path(pid: int) -> Optional[str]:
        handle = _kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            buf = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buf))
            if not _kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return None
            return buf.value
        finally:
            _kernel32.CloseHandle(handle)

    def _window_exe(hwnd) -> Optional[str]:
        pid = _pid(hwnd)
        path = _exe_path(pid)
        if path and os.path.basename(path).lower() == "applicationframehost.exe":
            # UWP dasturlar: tashqi oyna ApplicationFrameHost'niki, haqiqiy dastur – ichki oynada
            found = []

            def visit(child, _):
                child_pid = _pid(child)
                if child_pid != pid:
                    found.append(child_pid)
                    return False
                return True
            _user32.EnumChildWindows(hwnd, _WNDENUMPROC(visit), 0)
            if found:
                path = _exe_path(found[0]) or path
        return path

    def frontmost_app_id() -> Optional[str]:
        try:
            hwnd = _user32.GetForegroundWindow()
            path = _window_exe(hwnd) if hwnd else None
            return os.path.basename(path).lower() if path else None
        except Exception:
            return None

    def _file_description(path: str) -> Optional[str]:
        """.exe ning "File description" maydoni (masalan "Telegram Desktop")."""
        try:
            version = ctypes.WinDLL("version")
            size = version.GetFileVersionInfoSizeW(path, None)
            if not size:
                return None
            buf = ctypes.create_string_buffer(size)
            if not version.GetFileVersionInfoW(path, 0, size, buf):
                return None
            ptr, length = ctypes.c_void_p(), wintypes.UINT()
            if not version.VerQueryValueW(buf, r"\VarFileInfo\Translation",
                                          ctypes.byref(ptr), ctypes.byref(length)) or length.value < 4:
                return None
            lang, codepage = ctypes.cast(ptr, ctypes.POINTER(wintypes.WORD * 2)).contents
            key = "\\StringFileInfo\\%04x%04x\\FileDescription" % (lang, codepage)
            if not version.VerQueryValueW(buf, key, ctypes.byref(ptr), ctypes.byref(length)) or not length.value:
                return None
            return ctypes.wstring_at(ptr, length.value).rstrip("\x00").strip() or None
        except Exception:
            return None

    def running_apps() -> List[Tuple[str, str]]:
        hwnds = []

        def visit(hwnd, _):
            # koʻrinadigan, sarlavhali, egasiz (asosiy) oynalar
            if (_user32.IsWindowVisible(hwnd) and _user32.GetWindowTextLengthW(hwnd)
                    and not _user32.GetWindow(hwnd, 4)):  # GW_OWNER
                hwnds.append(hwnd)
            return True
        _user32.EnumWindows(_WNDENUMPROC(visit), 0)

        seen = {}
        for hwnd in hwnds:
            path = _window_exe(hwnd)
            if not path:
                continue
            exe = os.path.basename(path).lower()
            if exe not in _SKIP and exe not in seen:
                seen[exe] = _file_description(path) or os.path.splitext(os.path.basename(path))[0]
        return sorted(seen.items(), key=lambda kv: kv[1].lower())

else:
    def frontmost_app_id() -> Optional[str]:
        return None

    def running_apps() -> List[Tuple[str, str]]:
        return []
