"""Descobre o aplicativo em foco (para aplicar o estilo certo)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Tuple


def _run(cmd) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=1).stdout.strip()
    except Exception:
        return ""


def _windows() -> Tuple[str, str]:
    import ctypes
    from ctypes import wintypes

    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    name = ""
    handle = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if handle:
        size = wintypes.DWORD(1024)
        path = ctypes.create_unicode_buffer(1024)
        if kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
            name = Path(path.value).name
        kernel32.CloseHandle(handle)
    return name, buf.value


def _mac() -> Tuple[str, str]:
    name = _run(["osascript", "-e",
                 'tell application "System Events" to get name of first process whose frontmost is true'])
    return name, ""


def _linux() -> Tuple[str, str]:
    title = _run(["xdotool", "getactivewindow", "getwindowname"])
    pid = _run(["xdotool", "getactivewindow", "getwindowpid"])
    name = ""
    if pid.isdigit():
        try:
            name = Path(f"/proc/{pid}/comm").read_text().strip()
        except OSError:
            pass
    return name, title


def active_app() -> Tuple[str, str]:
    """(processo, título da janela). Vazio se não for possível descobrir."""
    try:
        if sys.platform == "win32":
            return _windows()
        if sys.platform == "darwin":
            return _mac()
        return _linux()
    except Exception:
        return "", ""
