from ditvvos.hotkey import COMMAND, DICTATE, IDLE, LOCKED, HotkeyStateMachine


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


def make():
    clock, log = Clock(), []
    sm = HotkeyStateMachine(lambda m: log.append(("start", m)), lambda: log.append("stop"),
                            lambda: log.append("lock"), clock=clock)
    return sm, clock, log


def test_segurar_grava_ate_soltar_e_ignora_autorepeat():
    sm, clock, log = make()
    sm.press(); clock.t = 0.5; sm.press(); sm.press(); clock.t = 2.0; sm.release()
    assert log == [("start", DICTATE), "stop"] and sm.state == IDLE


def test_toque_rapido_trava_maos_livres_e_proximo_toque_encerra():
    sm, clock, log = make()
    sm.press(); clock.t = 0.1; sm.release()
    assert sm.state == LOCKED
    clock.t = 30; sm.press(); clock.t = 30.1; sm.release()
    assert log == [("start", DICTATE), "lock", "stop"] and sm.state == IDLE


def test_shift_ativa_modo_comando():
    sm, clock, log = make()
    sm.press(shift=True); clock.t = 1; sm.release()
    assert log == [("start", COMMAND), "stop"]


def test_force_stop():
    sm, clock, log = make()
    sm.press(); clock.t = 0.1; sm.release(); sm.force_stop(); sm.force_stop()
    assert log == [("start", DICTATE), "lock", "stop"]
