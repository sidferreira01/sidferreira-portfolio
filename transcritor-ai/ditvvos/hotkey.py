"""Máquina de estados do atalho (sem hardware — testável).

Igual aos apps líderes (Wispr Flow, Superwhisper):
  * SEGURAR o atalho        -> grava enquanto estiver pressionado (aperte para falar)
  * TOCAR rápido o atalho   -> trava em mãos-livres; toque de novo para encerrar
  * Shift + atalho          -> Modo Comando (a fala vira uma instrução para editar a seleção)
"""

from __future__ import annotations

import time
from typing import Callable

TAP_SECONDS = 0.3

IDLE, HOLDING, LOCKED = "parado", "segurando", "maos-livres"
DICTATE, COMMAND = "ditado", "comando"


class HotkeyStateMachine:
    def __init__(self, on_start: Callable[[str], None], on_stop: Callable[[], None],
                 on_lock: Callable[[], None] = lambda: None, clock: Callable[[], float] = time.monotonic):
        self.on_start, self.on_stop, self.on_lock = on_start, on_stop, on_lock
        self.clock = clock
        self.state = IDLE
        self.mode = DICTATE
        self._key_down = False
        self._pressed_at = 0.0
        self._ignore_release = False

    def press(self, shift: bool = False) -> None:
        if self._key_down:  # auto-repeat do sistema enquanto a tecla está segura
            return
        self._key_down = True
        if self.state == IDLE:
            self.state = HOLDING
            self.mode = COMMAND if shift else DICTATE
            self._pressed_at = self.clock()
            self.on_start(self.mode)
        elif self.state == LOCKED:
            self.state = IDLE
            self._ignore_release = True
            self.on_stop()

    def release(self) -> None:
        self._key_down = False
        if self._ignore_release:
            self._ignore_release = False
            return
        if self.state == HOLDING:
            if self.clock() - self._pressed_at < TAP_SECONDS:
                self.state = LOCKED
                self.on_lock()
            else:
                self.state = IDLE
                self.on_stop()

    def force_stop(self) -> None:
        """Usado pelo limite de duração."""
        if self.state != IDLE:
            self.state = IDLE
            self.on_stop()
