"""Indicador flutuante (tkinter): mostra quando está ouvindo, o volume do microfone,
o processamento e o resultado — como a "pílula" do Wispr Flow.

Para nunca roubar o foco da janela onde o texto será colado, a janela é criada uma
única vez e depois só muda de opacidade (nunca é remapeada). No Windows ela também
recebe WS_EX_NOACTIVATE + WS_EX_TRANSPARENT (não ativa e deixa o clique passar).
"""

from __future__ import annotations

import queue
import sys
from typing import Callable, Optional

COLORS = {
    "ouvindo": "#ef4444",
    "maos-livres": "#f59e0b",
    "comando": "#8b5cf6",
    "transcrevendo": "#3b82f6",
    "pronto": "#10b981",
    "aviso": "#9ca3af",
    "erro": "#ef4444",
}
LABELS = {
    "ouvindo": "Ouvindo…",
    "maos-livres": "Mãos-livres · toque para enviar",
    "comando": "Comando…",
    "transcrevendo": "Transcrevendo…",
}
WIDTH, HEIGHT, BARS = 300, 40, 14


class Overlay:
    def __init__(self, level: Callable[[], float] = lambda: 0.0):
        import tkinter as tk

        self._tk = tk
        self.level = level
        self.events: "queue.Queue[tuple]" = queue.Queue()
        self.root = tk.Tk()
        self.root.withdraw()
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="#111827")
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self._visible_geometry = f"{WIDTH}x{HEIGHT}+{(sw - WIDTH) // 2}+{sh - HEIGHT - 90}"
        self._hidden_geometry = f"{WIDTH}x{HEIGHT}+{-WIDTH * 4}+{-HEIGHT * 4}"
        self.win.geometry(self._visible_geometry)
        self.canvas = tk.Canvas(self.win, width=WIDTH, height=HEIGHT, bg="#111827",
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.dot = self.canvas.create_oval(14, 14, 26, 26, fill=COLORS["ouvindo"], outline="")
        self.text = self.canvas.create_text(36, HEIGHT // 2, anchor="w", fill="#f9fafb",
                                            font=("Segoe UI", 10), text="")
        self.bars = [self.canvas.create_rectangle(0, 0, 0, 0, fill="#f9fafb", outline="")
                     for _ in range(BARS)]
        self.state: Optional[str] = None
        self._hide_job = None
        self._set_alpha(0.0)
        self._no_activate()
        self.win.update_idletasks()
        self.root.after(40, self._tick)

    # ------------------------------------------------------------------ plataforma
    def _set_alpha(self, value: float) -> None:
        # Sem compositor (alguns Linux) a opacidade é ignorada: por isso a janela também
        # sai da tela ao esconder. Mover não remapeia a janela, então não rouba o foco.
        self.win.geometry(self._visible_geometry if value > 0 else self._hidden_geometry)
        try:
            self.win.attributes("-alpha", value)
        except Exception:
            pass

    def _no_activate(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes

            hwnd = ctypes.windll.user32.GetParent(self.win.winfo_id())
            GWL_EXSTYLE, NOACTIVATE, TRANSPARENT, LAYERED, TOOLWINDOW = -20, 0x08000000, 0x20, 0x80000, 0x80
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE, style | NOACTIVATE | TRANSPARENT | LAYERED | TOOLWINDOW)
        except Exception:
            pass

    # ------------------------------------------------------------------ API (thread-safe)
    def show(self, state: str, message: str = "", hide_after: Optional[float] = None) -> None:
        self.events.put((state, message, hide_after))

    def hide(self) -> None:
        self.events.put((None, "", None))

    def run(self) -> None:
        self.root.mainloop()

    def quit(self) -> None:
        self.events.put(("__quit__", "", None))

    # ------------------------------------------------------------------ loop da UI
    def _apply(self, state: Optional[str], message: str, hide_after: Optional[float]) -> None:
        if self._hide_job:
            self.root.after_cancel(self._hide_job)
            self._hide_job = None
        self.state = state
        if state is None:
            self._set_alpha(0.0)
            return
        self.canvas.itemconfigure(self.dot, fill=COLORS.get(state, "#9ca3af"))
        label = message or LABELS.get(state, "")
        if len(label) > 38:
            label = label[:37] + "…"
        self.canvas.itemconfigure(self.text, text=label)
        self._set_alpha(0.93)
        if hide_after:
            self._hide_job = self.root.after(int(hide_after * 1000), lambda: self._apply(None, "", None))

    def _tick(self) -> None:
        try:
            while True:
                state, message, hide_after = self.events.get_nowait()
                if state == "__quit__":
                    self.root.quit()
                    return
                self._apply(state, message, hide_after)
        except queue.Empty:
            pass
        recording = self.state in ("ouvindo", "maos-livres", "comando")
        level = self.level() if recording else 0.0
        x0 = WIDTH - 14 - BARS * 6
        for i, bar in enumerate(self.bars):
            # barras centrais mais altas: forma de onda simples
            weight = 1 - abs(i - BARS / 2) / (BARS / 2) * 0.6
            h = max(2, int((HEIGHT - 16) * level * weight)) if recording else 0
            x = x0 + i * 6
            self.canvas.coords(bar, x, (HEIGHT - h) / 2, x + 3, (HEIGHT + h) / 2)
        self.root.after(40, self._tick)


class NullOverlay:
    """Usado com overlay desligado ou sem interface gráfica."""

    def show(self, state: str, message: str = "", hide_after: Optional[float] = None) -> None:
        pass

    def hide(self) -> None:
        pass
