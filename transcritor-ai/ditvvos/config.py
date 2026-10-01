"""Configuração persistente em ~/.ditvvos/config.json (ou $DITVVOS_HOME)."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List

# Estilo por aplicativo: o padrão é comparado (minúsculas) com o processo e o título da janela.
DEFAULT_APP_STYLES: Dict[str, str] = {
    "whatsapp": "casual", "telegram": "casual", "slack": "casual", "discord": "casual",
    "teams": "casual", "instagram": "casual", "messenger": "casual",
    "outlook": "formal", "gmail": "formal", "thunderbird": "formal", "mail": "formal",
    "winword": "formal", "word": "formal", "docs.google": "formal", "notion": "formal",
    "code": "codigo", "cursor": "codigo", "terminal": "codigo", "windowsterminal": "codigo",
    "powershell": "codigo", "cmd.exe": "codigo", "iterm": "codigo", "warp": "codigo",
    "konsole": "codigo", "gnome-terminal": "codigo", "alacritty": "codigo", "kitty": "codigo",
    "claude": "codigo", "pycharm": "codigo", "intellij": "codigo",
}


def home() -> Path:
    return Path(os.environ.get("DITVVOS_HOME", Path.home() / ".ditvvos"))


@dataclass
class LLMConfig:
    # IA local opcional via Ollama (gratuito): polimento e Modo Comando.
    enabled: bool = False
    url: str = "http://127.0.0.1:11434"
    model: str = "gemma3:4b"  # melhor português entre os modelos leves testados
    polish: bool = False      # reescreve todo ditado (mais lento); o Modo Comando funciona sem isso
    timeout: float = 30.0


@dataclass
class Config:
    hotkey: str = "ctrl_r"
    output: str = "digitar" if sys.platform.startswith("linux") else "colar"
    submit: bool = False
    model: str = "large-v3-turbo"
    language: str = "pt"
    microphone: int | None = None
    sounds: bool = True
    overlay: bool = True
    remove_fillers: bool = True
    backtrack: bool = True
    voice_commands: bool = True
    app_styles_enabled: bool = True
    default_style: str = "normal"
    app_styles: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_APP_STYLES))
    vocabulary: List[str] = field(default_factory=list)
    replacements: Dict[str, str] = field(default_factory=dict)
    snippets: Dict[str, str] = field(default_factory=dict)
    history: bool = True
    llm: LLMConfig = field(default_factory=LLMConfig)

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or home() / "config.json"
        if not path.exists():
            cfg = cls()
            cfg.save(path)
            return cfg
        data = json.loads(path.read_text(encoding="utf-8"))
        llm = LLMConfig(**{k: v for k, v in data.pop("llm", {}).items() if k in LLMConfig.__dataclass_fields__})
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(llm=llm, **known)

    def save(self, path: Path | None = None) -> Path:
        path = path or home() / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def style_for(self, process: str, title: str) -> str:
        if not self.app_styles_enabled:
            return self.default_style
        haystack = f"{process} {title}".lower()
        # padrões mais longos primeiro: "docs.google" vence "google"
        for pattern in sorted(self.app_styles, key=len, reverse=True):
            if pattern.lower() in haystack:
                return self.app_styles[pattern]
        return self.default_style
