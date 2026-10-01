"""Ditado por voz em qualquer janela (Claude Code, navegador, WhatsApp Web...).

Segure a tecla de atalho, fale, solte: o áudio é transcrito localmente pelo mesmo
motor do Transcritor e o texto é colado onde o cursor estiver.

    python -m transcritor ditado                    # segure Ctrl direito para falar
    python -m transcritor ditado --modo alternar     # toque 1x para gravar, 1x para enviar
    python -m transcritor ditado --enviar            # aperta Enter depois de colar

Dependências extras: requirements-ditado.txt (sounddevice, pynput, pyperclip).
"""

from __future__ import annotations

import logging
import queue
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

import numpy as np

from .config import TranscribeOptions, get_preset
from .engine import SAMPLE_RATE, Transcriber

log = logging.getLogger("transcritor.ditado")

MIN_SECONDS = 0.4        # toques acidentais
MAX_SECONDS = 120.0      # trava de segurança
SILENCE_PEAK = 0.002     # abaixo disso o microfone só captou silêncio
# O Whisper imita o estilo do prompt: uma frase bem pontuada faz ele pontuar e
# usar maiúsculas mesmo em falas curtas e sem contexto.
PUNCTUATION_HINT = "Olá, Claude. Tudo bem? Vamos revisar o código, por favor."


def dictation_options(base: Optional[TranscribeOptions] = None, **overrides) -> TranscribeOptions:
    """Preset do ditado: mesma precisão do 'equilibrado', sem a 2ª passada
    (frases curtas raramente precisam e ela aumentaria a espera)."""
    opts = base or get_preset("equilibrado")
    overrides.setdefault("context", PUNCTUATION_HINT)
    return opts.with_overrides(revision_pass=False, **overrides)


def prepare_audio(samples: np.ndarray) -> Optional[np.ndarray]:
    """Mono float32, nível normalizado. None se for curto demais ou só silêncio."""
    if samples is None or len(samples) < MIN_SECONDS * SAMPLE_RATE:
        return None
    samples = np.asarray(samples, dtype=np.float32).reshape(-1)
    samples = samples - float(np.mean(samples))  # remove offset DC de alguns microfones
    peak = float(np.max(np.abs(samples)))
    if peak < SILENCE_PEAK:
        return None
    return samples * min(0.9 / peak, 100.0)  # microfone baixo vira voz audível; o VAD descarta ruído


def format_text(text: str, submit: bool) -> str:
    text = " ".join(text.split())
    if not text:
        return ""
    # sem Enter, deixa um espaço para o próximo ditado não grudar no anterior
    return text if submit else text + " "


# --------------------------------------------------------------------------- tecla
class PushToTalk:
    """Máquina de estados do atalho, sem dependência de hardware (testável).

    hold:   pressionar = gravar, soltar = transcrever
    toggle: 1º toque = gravar, 2º toque = transcrever
    """

    def __init__(self, mode: str, start: Callable[[], None], stop: Callable[[], None]):
        if mode not in ("hold", "toggle"):
            raise ValueError("modo deve ser 'hold' ou 'toggle'")
        self.mode = mode
        self._start, self._stop = start, stop
        self.recording = False
        self._key_down = False

    def press(self) -> None:
        if self._key_down:  # auto-repeat do sistema enquanto a tecla está segura
            return
        self._key_down = True
        if self.mode == "hold":
            if not self.recording:
                self.recording = True
                self._start()
        else:
            self.recording = not self.recording
            (self._start if self.recording else self._stop)()

    def release(self) -> None:
        self._key_down = False
        if self.mode == "hold" and self.recording:
            self.recording = False
            self._stop()


# --------------------------------------------------------------------------- saída
class Output:
    """Entrega o texto na janela ativa.

    colar   -> área de transferência + Ctrl/Cmd+V (rápido, preserva acentos)
    digitar -> simula digitação (funciona em qualquer terminal Linux)
    copiar  -> só copia; você cola quando quiser
    """

    def __init__(self, method: str = "colar", submit: bool = False, restore_clipboard: bool = True,
                 keyboard=None, clipboard=None, keys=None, platform: str = sys.platform):
        if method not in ("colar", "digitar", "copiar"):
            raise ValueError("saída deve ser colar, digitar ou copiar")
        self.method, self.submit, self.restore = method, submit, restore_clipboard
        self.platform = platform
        self._kb = keyboard
        self._clip = clipboard
        self._key_names = keys

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

    def _keys(self):
        if self._key_names is None:
            from pynput.keyboard import Key

            self._key_names = Key
        return self._key_names

    def send(self, text: str) -> None:
        if not text:
            return
        if self.method == "digitar":
            self.kb.type(text)
        else:
            previous = None
            if self.method == "colar" and self.restore:
                try:
                    previous = self.clip.paste()
                except Exception:
                    previous = None
            self.clip.copy(text)
            if self.method == "copiar":
                return
            Key = self._keys()
            mod = Key.cmd if self.platform == "darwin" else Key.ctrl
            time.sleep(0.05)
            with self.kb.pressed(mod):
                self.kb.press("v")
                self.kb.release("v")
            if previous is not None:
                # espera o app ler a área de transferência antes de restaurar
                threading.Timer(0.6, self.clip.copy, args=(previous,)).start()
        if self.submit:
            Key = self._keys()
            time.sleep(0.15)
            self.kb.press(Key.enter)
            self.kb.release(Key.enter)


# --------------------------------------------------------------------------- microfone
class Recorder:
    """Captura do microfone com sounddevice (PortAudio)."""

    def __init__(self, device: Optional[int] = None):
        self.device = device
        self._chunks: List[np.ndarray] = []
        self._stream = None
        self._lock = threading.Lock()

    def _callback(self, data, frames, time_info, status):  # thread de áudio
        with self._lock:
            if len(self._chunks) * 1024 < MAX_SECONDS * SAMPLE_RATE:
                self._chunks.append(data[:, 0].copy())

    def start(self) -> None:
        import sounddevice as sd

        with self._lock:
            self._chunks = []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=1024,
            device=self.device, callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            chunks, self._chunks = self._chunks, []
        return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)


def beep(freq: float, enabled: bool = True) -> None:
    if not enabled:
        return
    try:
        import sounddevice as sd

        t = np.linspace(0, 0.08, int(SAMPLE_RATE * 0.08), endpoint=False)
        tone = 0.2 * np.sin(2 * np.pi * freq * t) * np.hanning(len(t))
        sd.play(tone.astype(np.float32), SAMPLE_RATE)
    except Exception:
        pass


# --------------------------------------------------------------------------- app
@dataclass
class DictationResult:
    text: str
    audio_seconds: float
    latency_seconds: float


class Dictation:
    """Liga microfone -> transcrição -> saída. Transcrições rodam numa fila própria,
    então dá para começar a próxima fala enquanto a anterior ainda está processando."""

    def __init__(self, opts: TranscribeOptions, output: Output, recorder=None,
                 sounds: bool = True, on_result: Optional[Callable[[DictationResult], None]] = None):
        self.transcriber = Transcriber(opts)
        self.output = output
        self.recorder = recorder or Recorder()
        self.sounds = sounds
        self.on_result = on_result or (lambda r: None)
        self._jobs: "queue.Queue[Optional[np.ndarray]]" = queue.Queue()
        self._worker = threading.Thread(target=self._run, daemon=True, name="ditado")
        self._worker.start()

    def warm_up(self) -> None:
        """Carrega o modelo antes do primeiro uso (a 1ª fala não fica lenta)."""
        self.transcriber.transcribe_samples(np.zeros(SAMPLE_RATE, dtype=np.float32))

    def start(self) -> None:
        # erros aqui não podem escapar: derrubariam o ouvinte global do teclado
        try:
            self.recorder.start()
        except Exception as exc:
            print(f"✗ microfone indisponível: {exc} (veja --listar-microfones)", file=sys.stderr, flush=True)
            return
        beep(880, self.sounds)
        print("🎙️  gravando…", file=sys.stderr, flush=True)

    def stop(self) -> None:
        try:
            samples = self.recorder.stop()
        except Exception as exc:
            print(f"✗ falha ao parar a gravação: {exc}", file=sys.stderr, flush=True)
            return
        beep(660, self.sounds)
        self._jobs.put(samples)

    def process(self, samples: np.ndarray) -> Optional[DictationResult]:
        t0 = time.perf_counter()
        audio = prepare_audio(samples)
        if audio is None:
            print("… nada para transcrever (muito curto ou silêncio)", file=sys.stderr, flush=True)
            return None
        transcript = self.transcriber.transcribe_samples(audio)
        text = format_text(transcript.text, self.output.submit)
        if not text:
            print("… não entendi nada", file=sys.stderr, flush=True)
            return None
        self.output.send(text)
        result = DictationResult(text.strip(), len(audio) / SAMPLE_RATE, time.perf_counter() - t0)
        self.on_result(result)
        return result

    def _run(self) -> None:
        while True:
            samples = self._jobs.get()
            if samples is None:
                return
            try:
                self.process(samples)
            except Exception as exc:  # o ditado continua funcionando
                log.exception("Falha no ditado")
                print(f"✗ erro: {exc}", file=sys.stderr, flush=True)

    def close(self) -> None:
        self._jobs.put(None)
        self._worker.join(timeout=60)


# --------------------------------------------------------------------------- atalho global
def parse_key(name: str):
    """'ctrl_r', 'alt_r', 'f9', 'scroll_lock' ou um caractere ('§')."""
    from pynput.keyboard import Key, KeyCode

    name = name.strip().lower()
    if hasattr(Key, name):
        return getattr(Key, name)
    if len(name) == 1:
        return KeyCode.from_char(name)
    raise ValueError(f"Tecla desconhecida: {name}. Exemplos: ctrl_r, alt_r, f9, f8, scroll_lock")


def run(dictation: Dictation, key_name: str, mode: str) -> None:
    from pynput import keyboard

    hotkey = parse_key(key_name)
    ptt = PushToTalk(mode, dictation.start, dictation.stop)

    def same(key) -> bool:
        return key == hotkey or (hasattr(key, "char") and getattr(hotkey, "char", None)
                                 and key.char == hotkey.char)

    def on_press(key):
        if same(key):
            ptt.press()

    def on_release(key):
        if same(key):
            ptt.release()

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


def list_microphones() -> str:
    import sounddevice as sd

    lines = []
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            mark = "*" if i == sd.default.device[0] else " "
            lines.append(f"{mark} {i:2d}  {dev['name']}")
    return "\n".join(lines)
