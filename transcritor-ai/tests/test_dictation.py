import contextlib
from types import SimpleNamespace

import numpy as np
from helpers import seg, transcript

from transcritor.dictation import Dictation, Output, PushToTalk, format_text, prepare_audio

SR = 16000


def _ptt(mode):
    log = []
    return PushToTalk(mode, lambda: log.append("start"), lambda: log.append("stop")), log


def test_segurar_ignora_autorepeat():
    ptt, log = _ptt("hold")
    ptt.press(); ptt.press(); ptt.press()  # sistema repete o evento enquanto a tecla está segura
    ptt.release()
    assert log == ["start", "stop"]


def test_alternar_um_toque_inicia_outro_para():
    ptt, log = _ptt("toggle")
    ptt.press(); ptt.release(); ptt.press(); ptt.press(); ptt.release()
    assert log == ["start", "stop"]


def test_prepare_audio_descarta_curto_e_silencio_e_normaliza():
    assert prepare_audio(np.zeros(SR // 10, dtype=np.float32)) is None
    assert prepare_audio(np.full(SR, 0.001, dtype=np.float32)) is None
    quiet = (0.05 * np.sin(np.linspace(0, 500, SR))).astype(np.float32)
    out = prepare_audio(quiet)
    assert abs(float(np.max(np.abs(out))) - 0.9) < 0.01


def test_format_text():
    assert format_text("  olá   mundo ", submit=False) == "olá mundo "
    assert format_text("olá mundo", submit=True) == "olá mundo"
    assert format_text("   ", submit=False) == ""


class FakeKeyboard:
    def __init__(self):
        self.events = []

    def type(self, text):
        self.events.append(("type", text))

    def press(self, k):
        self.events.append(("press", k))

    def release(self, k):
        self.events.append(("release", k))

    @contextlib.contextmanager
    def pressed(self, k):
        self.events.append(("hold", k))
        yield
        self.events.append(("unhold", k))


class FakeClipboard:
    def __init__(self, value="antigo"):
        self.value = value

    def copy(self, v):
        self.value = v

    def paste(self):
        return self.value


KEYS = SimpleNamespace(ctrl="CTRL", cmd="CMD", enter="ENTER")


def test_colar_usa_ctrl_v_e_restaura_area_de_transferencia():
    kb, clip = FakeKeyboard(), FakeClipboard()
    Output("colar", submit=True, keyboard=kb, clipboard=clip, keys=KEYS, platform="win32").send("oi Claude")
    assert kb.events == [("hold", "CTRL"), ("press", "v"), ("release", "v"), ("unhold", "CTRL"),
                         ("press", "ENTER"), ("release", "ENTER")]
    assert clip.value == "oi Claude"
    import time; time.sleep(0.8)
    assert clip.value == "antigo"


def test_colar_no_mac_usa_cmd():
    kb = FakeKeyboard()
    Output("colar", keyboard=kb, clipboard=FakeClipboard(), keys=KEYS, platform="darwin",
           restore_clipboard=False).send("x")
    assert kb.events[0] == ("hold", "CMD")


def test_digitar_e_copiar():
    kb, clip = FakeKeyboard(), FakeClipboard()
    Output("digitar", keyboard=kb, clipboard=clip, keys=KEYS).send("ação")
    assert kb.events == [("type", "ação")] and clip.value == "antigo"
    kb2 = FakeKeyboard()
    Output("copiar", keyboard=kb2, clipboard=clip, keys=KEYS).send("só copia")
    assert kb2.events == [] and clip.value == "só copia"


def test_fluxo_do_ditado_com_transcritor_falso(monkeypatch):
    sent = []

    class FakeOutput:
        submit = False

        def send(self, text):
            sent.append(text)

    class FakeRecorder:
        def start(self):
            pass

        def stop(self):
            return (0.3 * np.sin(np.linspace(0, 3000, SR * 2))).astype(np.float32)

    import transcritor.dictation as d

    class FakeTranscriber:
        def __init__(self, opts):
            pass

        def transcribe_samples(self, samples):
            assert len(samples) == SR * 2
            return transcript(seg("Claude, rode os testes."))

    monkeypatch.setattr(d, "Transcriber", FakeTranscriber)
    results = []
    app = Dictation(d.dictation_options(), FakeOutput(), recorder=FakeRecorder(), sounds=False,
                    on_result=results.append)
    app.start(); app.stop(); app.close()
    assert sent == ["Claude, rode os testes. "]
    assert results[0].text == "Claude, rode os testes." and results[0].audio_seconds == 2.0


def test_microfone_quebrado_nao_derruba_o_ditado(monkeypatch, capsys):
    import transcritor.dictation as d

    class BrokenRecorder:
        def start(self):
            raise OSError("sem dispositivo")

        def stop(self):
            return np.zeros(0, dtype=np.float32)

    monkeypatch.setattr(d, "Transcriber", lambda opts: None)
    app = Dictation(d.dictation_options(), object(), recorder=BrokenRecorder(), sounds=False)
    app.start()
    app.stop()
    app.close()
    assert "microfone indisponível" in capsys.readouterr().err
