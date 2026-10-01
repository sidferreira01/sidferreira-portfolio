"""Orquestrador do DitvvOS: atalho -> microfone -> Whisper -> regras/IA -> janela ativa."""

from __future__ import annotations

import logging
import queue
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import numpy as np

from transcritor.config import get_preset
from transcritor.engine import Transcriber

from . import textproc
from .apps import active_app
from .config import Config, home
from .devices import SAMPLE_RATE, MAX_SECONDS, Keyboard, Recorder, beep, prepare_audio
from .history import History
from .hotkey import COMMAND, DICTATE, HotkeyStateMachine
from .llm import LLMError, Ollama
from .overlay import NullOverlay

log = logging.getLogger("ditvvos")

# O Whisper imita o estilo do prompt: uma frase bem pontuada faz ele pontuar e usar
# maiúsculas mesmo em falas curtas e sem contexto.
PUNCTUATION_HINT = "Olá, Claude. Tudo bem? Vamos revisar o código, por favor."


def transcriber_for(cfg: Config) -> Transcriber:
    vocabulary = list(dict.fromkeys(cfg.vocabulary + list(cfg.replacements.values())))
    opts = get_preset("equilibrado").with_overrides(
        model=cfg.model,
        language=None if cfg.language == "auto" else cfg.language,
        revision_pass=False,  # frases curtas: a 2ª passada só aumentaria a espera
        context=PUNCTUATION_HINT,
        vocabulary=vocabulary or None,
        replacements=cfg.replacements or None,
    )
    return Transcriber(opts)


@dataclass
class Result:
    mode: str
    raw: str
    text: str
    app: str
    style: str
    audio_seconds: float
    latency_seconds: float
    steps: list
    cancelled: bool = False


class DitvvOS:
    def __init__(self, cfg: Config, *, keyboard: Optional[Keyboard] = None, recorder=None,
                 transcriber=None, llm=None, history: Optional[History] = None, overlay=None,
                 app_detector: Callable[[], Tuple[str, str]] = active_app,
                 on_result: Callable[[Result], None] = lambda r: None):
        self.cfg = cfg
        self.keyboard = keyboard or Keyboard(cfg.output)
        self.recorder = recorder or Recorder(cfg.microphone)
        self.transcriber = transcriber or transcriber_for(cfg)
        self.llm = llm if llm is not None else (Ollama(cfg.llm) if cfg.llm.enabled else None)
        self.history = history if history is not None else (
            History(home() / "historico.db") if cfg.history else None)
        self.overlay = overlay or NullOverlay()
        self.app_detector = app_detector
        self.on_result = on_result
        self.hotkey = HotkeyStateMachine(self._start, self._stop, self._lock)
        self._target: Tuple[str, str] = ("", "")
        self._recording = False
        self._jobs: "queue.Queue[Optional[tuple]]" = queue.Queue()
        self._worker = threading.Thread(target=self._run, daemon=True, name="ditvvos-worker")
        self._worker.start()
        threading.Thread(target=self._watchdog, daemon=True, name="ditvvos-watchdog").start()

    # ------------------------------------------------------------------ eventos do atalho
    # Nada aqui pode lançar exceção: derrubaria o ouvinte global do teclado.
    def _start(self, mode: str) -> None:
        try:
            self.recorder.start()  # primeiro o microfone: não perder o início da fala
            self._recording = True
        except Exception as exc:
            self._recording = False
            self._notify("erro", f"Microfone indisponível: {exc}", 4)
            return
        try:
            self._target = self.app_detector()  # no macOS leva ~0,2 s
        except Exception:
            self._target = ("", "")
        beep(880 if mode == DICTATE else 990, self.cfg.sounds)
        self._notify("comando" if mode == COMMAND else "ouvindo")

    def _lock(self) -> None:
        if self._recording and self.hotkey.mode == DICTATE:
            self._notify("maos-livres")

    def _stop(self) -> None:
        if not self._recording:
            return
        self._recording = False
        try:
            samples = self.recorder.stop()
        except Exception as exc:
            self._notify("erro", f"Falha na gravação: {exc}", 4)
            return
        beep(660, self.cfg.sounds)
        self._notify("transcrevendo")
        self._jobs.put((samples, self.hotkey.mode, self._target))

    def _watchdog(self) -> None:
        while True:
            time.sleep(1)
            try:
                if self._recording and self.recorder.elapsed() >= MAX_SECONDS:
                    self.hotkey.force_stop()
            except Exception:
                pass

    # ------------------------------------------------------------------ processamento
    def _notify(self, state: str, message: str = "", hide_after: Optional[float] = None) -> None:
        try:
            self.overlay.show(state, message, hide_after)
        except Exception:
            pass
        if message and state in ("erro", "aviso"):  # resultados já são exibidos pelo on_result
            print(("✗ " if state == "erro" else "· ") + message, file=sys.stderr, flush=True)

    def _run(self) -> None:
        while True:
            job = self._jobs.get()
            if job is None:
                return
            try:
                self.process(*job)
            except Exception as exc:
                log.exception("Falha ao processar ditado")
                self._notify("erro", f"Erro: {exc}", 5)

    def text_options(self, style: str) -> textproc.TextOptions:
        return textproc.TextOptions(
            remove_fillers=self.cfg.remove_fillers, backtrack=self.cfg.backtrack,
            commands=self.cfg.voice_commands, style=style,
            replacements=self.cfg.replacements, snippets=self.cfg.snippets,
        )

    def process(self, samples: np.ndarray, mode: str = DICTATE,
                target: Tuple[str, str] = ("", "")) -> Optional[Result]:
        t0 = time.perf_counter()
        audio = prepare_audio(samples)
        if audio is None:
            self._notify("aviso", "Nada para transcrever", 1.5)
            return None
        raw = self.transcriber.transcribe_samples(audio).text.strip()
        if not raw:
            self._notify("aviso", "Não entendi — tente de novo", 2)
            return None
        process_name, title = target
        app = process_name or title
        style = self.cfg.style_for(process_name, title)

        if mode == COMMAND:
            text, steps = self._command(raw)
            if text is None:
                return None
            cancelled = False
        else:
            done = textproc.process(raw, self.text_options(style))
            text, steps, cancelled = done.text, done.steps, done.cancelled
            if cancelled:
                self._notify("aviso", "Ditado descartado", 1.5)
            elif self.llm and self.cfg.llm.polish and not done.snippet:
                try:
                    # o estilo é reaplicado: a IA tende a recolocar o ponto final etc.
                    text = textproc.apply_style(self.llm.polish(text, style), style)
                    steps.append("IA")
                except LLMError as exc:
                    log.warning("Polimento por IA indisponível: %s", exc)
            if not cancelled and text:
                ends_line = text.endswith("\n")
                self.keyboard.send(text if (self.cfg.submit or ends_line) else text + " ",
                                   submit=self.cfg.submit)

        result = Result(mode, raw, text, app, style, len(audio) / SAMPLE_RATE,
                        time.perf_counter() - t0, steps, cancelled)
        if not cancelled:
            if self.history is not None:
                self.history.add(app=app, style=style, mode=mode, raw=raw, final=text,
                                 audio_seconds=result.audio_seconds,
                                 latency_seconds=result.latency_seconds)
            self._notify("pronto", text.replace("\n", " ⏎ "), 1.8)
        self.on_result(result)
        return result

    def _command(self, instruction: str):
        if not self.llm:
            self._notify("erro", "Modo Comando requer o Ollama (veja o README)", 4)
            return None, []
        selection = self.keyboard.selected_text()
        try:
            output = self.llm.command(instruction, selection)
        except LLMError as exc:
            self._notify("erro", str(exc), 5)
            return None, []
        self.keyboard.send(output)  # substitui a seleção
        return output, ["comando" + (" na seleção" if selection else "")]

    # ------------------------------------------------------------------ ciclo de vida
    def warm_up(self) -> None:
        """Carrega o modelo antes da 1ª fala (senão a primeira demora bem mais)."""
        self.transcriber.transcribe_samples(np.zeros(SAMPLE_RATE, dtype=np.float32))

    def close(self) -> None:
        self._jobs.put(None)
        self._worker.join(timeout=120)


def listen(app: DitvvOS, key_name: str):
    """Registra o atalho global. Retorna o Listener (thread) do pynput já iniciado."""
    from pynput import keyboard

    from .devices import parse_key

    hotkey = parse_key(key_name)
    shift_keys = {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r}
    shift_down = set()

    def is_hotkey(key) -> bool:
        if key == hotkey:
            return True
        char = getattr(hotkey, "char", None)
        return bool(char) and getattr(key, "char", None) == char

    def on_press(key):
        if key in shift_keys:
            shift_down.add(key)
        elif is_hotkey(key):
            app.hotkey.press(shift=bool(shift_down))

    def on_release(key):
        if key in shift_keys:
            shift_down.discard(key)
        elif is_hotkey(key):
            app.hotkey.release()

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    return listener
