"""Hardware: microfone (sounddevice), teclado e área de transferência (pynput/pyperclip).

Tudo é importado sob demanda para que o restante do DitvvOS (e os testes) funcione
mesmo em máquinas sem áudio ou sem interface gráfica.
"""

from __future__ import annotations

import sys
import threading
import time
from typing import List, Optional

import numpy as np

SAMPLE_RATE = 16000
MIN_SECONDS = 0.4
MAX_SECONDS = 300.0       # 5 min: limite do modo mãos-livres
SILENCE_PEAK = 0.002


def prepare_audio(samples: Optional[np.ndarray]) -> Optional[np.ndarray]:
    """Mono float32 com nível normalizado. None se for curto demais ou só silêncio."""
    if samples is None or len(samples) < MIN_SECONDS * SAMPLE_RATE:
        return None
    samples = np.asarray(samples, dtype=np.float32).reshape(-1)
    samples = samples - float(np.mean(samples))  # remove offset DC de alguns microfones
    peak = float(np.max(np.abs(samples)))
    if peak < SILENCE_PEAK:
        return None
    return samples * min(0.9 / peak, 100.0)  # voz baixa fica audível; o VAD descarta ruído


class Recorder:
    """Captura do microfone. `level` (0–1) alimenta o medidor do indicador visual."""

    def __init__(self, device: Optional[int] = None):
        self.device = device
        self.level = 0.0
        self._chunks: List[np.ndarray] = []
        self._stream = None
        self._lock = threading.Lock()

    def _callback(self, data, frames, time_info, status):  # thread de áudio
        mono = data[:, 0]
        self.level = min(float(np.sqrt(np.mean(mono ** 2))) * 12, 1.0)
        with self._lock:
            if len(self._chunks) * frames < MAX_SECONDS * SAMPLE_RATE:
                self._chunks.append(mono.copy())

    def start(self) -> None:
        import sounddevice as sd

        with self._lock:
            self._chunks = []
        self._stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                                      blocksize=1024, device=self.device, callback=self._callback)
        self._stream.start()

    def stop(self) -> np.ndarray:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self.level = 0.0
        with self._lock:
            chunks, self._chunks = self._chunks, []
        return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)

    def elapsed(self) -> float:
        with self._lock:
            return sum(len(c) for c in self._chunks) / SAMPLE_RATE


class FileRecorder(Recorder):
    """Usa um arquivo de áudio no lugar do microfone (testes e demonstrações)."""

    def __init__(self, path: str):
        super().__init__()
        from faster_whisper import decode_audio

        self._audio = decode_audio(path, sampling_rate=SAMPLE_RATE)

    def start(self) -> None:
        self.level = 0.5

    def stop(self) -> np.ndarray:
        self.level = 0.0
        return self._audio


class Keyboard:
    """Entrega texto na janela ativa e lê a seleção atual.

    colar   -> área de transferência + Ctrl/Cmd+V (rápido, preserva acentos)
    digitar -> simula digitação (funciona em qualquer terminal)
    copiar  -> só copia
    """

    def __init__(self, method: str = "colar", controller=None, clipboard=None, keys=None,
                 platform: str = sys.platform):
        if method not in ("colar", "digitar", "copiar"):
            raise ValueError("saída deve ser colar, digitar ou copiar")
        self.method = method
        self.platform = platform
        self._kb, self._clip, self._keys = controller, clipboard, keys

    # dependências preguiçosas -------------------------------------------------
    @property
    def kb(self):
        if self._kb is None:
            from pynput.keyboard import Controller

            self._kb = Controller()
        return self._kb

    @property
    def clip(self):
        if self._clip is None:
            import pyperclip

            self._clip = pyperclip
        return self._clip

    @property
    def keys(self):
        if self._keys is None:
            from pynput.keyboard import Key

            self._keys = Key
        return self._keys

    @property
    def _mod(self):
        return self.keys.cmd if self.platform == "darwin" else self.keys.ctrl

    def _chord(self, char: str) -> None:
        with self.kb.pressed(self._mod):
            self.kb.press(char)
            self.kb.release(char)

    def _safe_paste(self) -> Optional[str]:
        try:
            return self.clip.paste()
        except Exception:
            return None

    # API ---------------------------------------------------------------------
    def send(self, text: str, submit: bool = False, restore_clipboard: bool = True) -> None:
        if not text:
            return
        if self.method == "digitar":
            self.kb.type(text)
        else:
            previous = self._safe_paste() if restore_clipboard and self.method == "colar" else None
            self.clip.copy(text)
            if self.method == "copiar":
                return
            time.sleep(0.05)
            self._chord("v")
            if previous is not None:
                # espera o app ler a área de transferência antes de restaurar
                threading.Timer(0.6, self.clip.copy, args=(previous,)).start()
        if submit:
            time.sleep(0.15)
            self.kb.press(self.keys.enter)
            self.kb.release(self.keys.enter)

    def selected_text(self, wait: float = 0.25) -> str:
        """Copia a seleção atual (Ctrl/Cmd+C) sem perder o conteúdo da área de transferência."""
        previous = self._safe_paste()
        marker = f"__ditvvos_{time.time_ns()}__"
        try:
            self.clip.copy(marker)
            self._chord("c")
            deadline = time.time() + wait
            value = marker
            while time.time() < deadline:
                value = self._safe_paste()
                if value != marker:
                    break
                time.sleep(0.02)
            return "" if value in (marker, None) else value
        finally:
            if previous is not None:
                self.clip.copy(previous)


def beep(freq: float, enabled: bool = True, duration: float = 0.08) -> None:
    if not enabled:
        return
    try:
        import sounddevice as sd

        t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
        tone = 0.2 * np.sin(2 * np.pi * freq * t) * np.hanning(len(t))
        sd.play(tone.astype(np.float32), SAMPLE_RATE)
    except Exception:
        pass


def parse_key(name: str):
    """'ctrl_r', 'alt_r', 'f9', 'scroll_lock' ou um caractere."""
    from pynput.keyboard import Key, KeyCode

    name = name.strip().lower()
    if hasattr(Key, name):
        return getattr(Key, name)
    if len(name) == 1:
        return KeyCode.from_char(name)
    raise ValueError(f"Tecla desconhecida: {name}. Exemplos: ctrl_r, alt_r, f8, f9, scroll_lock")


def list_microphones() -> str:
    import sounddevice as sd

    lines = []
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            mark = "*" if i == sd.default.device[0] else " "
            lines.append(f"{mark} {i:2d}  {dev['name']}")
    return "\n".join(lines) or "Nenhum microfone encontrado."

