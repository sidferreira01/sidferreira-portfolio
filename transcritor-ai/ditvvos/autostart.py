"""Iniciar o DitvvOS junto com o sistema (Windows, macOS, Linux)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

PROJECT_DIR = Path(__file__).resolve().parents[1]


def _python(platform: str) -> str:
    exe = Path(sys.executable)
    if platform == "win32":
        # pythonw.exe roda sem abrir janela de console
        windowless = exe.with_name("pythonw.exe")
        if windowless.exists():
            return str(windowless)
    return str(exe)


def target_path(platform: str = sys.platform, user_home: Optional[Path] = None) -> Path:
    user_home = user_home or Path.home()
    if platform == "win32":
        appdata = Path(os.environ.get("APPDATA", user_home / "AppData" / "Roaming"))
        return appdata / "Microsoft/Windows/Start Menu/Programs/Startup/DitvvOS.vbs"
    if platform == "darwin":
        return user_home / "Library/LaunchAgents/com.ditvvos.agent.plist"
    return user_home / ".config/autostart/ditvvos.desktop"


def render(platform: str = sys.platform, project_dir: Path = PROJECT_DIR) -> str:
    py = _python(platform)
    if platform == "win32":
        return (
            'Set sh = CreateObject("WScript.Shell")\r\n'
            f'sh.CurrentDirectory = "{project_dir}"\r\n'
            f'sh.Run """{py}"" -m ditvvos iniciar", 0, False\r\n'
        )
    if platform == "darwin":
        log = Path.home() / ".ditvvos" / "ditvvos.log"
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.ditvvos.agent</string>
  <key>ProgramArguments</key><array>
    <string>{py}</string><string>-m</string><string>ditvvos</string><string>iniciar</string>
  </array>
  <key>WorkingDirectory</key><string>{project_dir}</string>
  <key>RunAtLoad</key><true/>
  <key>StandardErrorPath</key><string>{log}</string>
</dict></plist>
"""
    return (
        "[Desktop Entry]\nType=Application\nName=DitvvOS\n"
        "Comment=Ditado por voz local\n"
        f"Exec=sh -c 'cd \"{project_dir}\" && \"{py}\" -m ditvvos iniciar'\n"
        "X-GNOME-Autostart-enabled=true\nTerminal=false\n"
    )


def enable(platform: str = sys.platform, user_home: Optional[Path] = None) -> Path:
    path = target_path(platform, user_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(platform), encoding="utf-8")
    return path


def disable(platform: str = sys.platform, user_home: Optional[Path] = None) -> Optional[Path]:
    path = target_path(platform, user_home)
    if path.exists():
        path.unlink()
        return path
    return None
