import contextlib
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import numpy as np
import pytest
from helpers import seg, transcript

from ditvvos import autostart
from ditvvos.app import DitvvOS
from ditvvos.config import Config, LLMConfig
from ditvvos.devices import Keyboard, prepare_audio
from ditvvos.history import History
from ditvvos.hotkey import COMMAND, DICTATE
from ditvvos.llm import LLMError, Ollama

SR = 16000
VOICE = (0.3 * np.sin(np.linspace(0, 3000, SR * 2))).astype(np.float32)


# ------------------------------------------------------------------ fakes
class FakeTranscriber:
    def __init__(self, text):
        self.text = text

    def transcribe_samples(self, samples):
        return transcript(seg(self.text))


class FakeKeyboard:
    def __init__(self, selection=""):
        self.sent, self.selection = [], selection

    def send(self, text, submit=False, restore_clipboard=True):
        self.sent.append((text, submit))

    def selected_text(self):
        return self.selection


class FakeRecorder:
    level = 0.0

    def start(self):
        pass

    def stop(self):
        return VOICE

    def elapsed(self):
        return 1.0


class FakeLLM:
    def polish(self, text, style):
        return text.upper()

    def command(self, instruction, selection):
        return f"[{instruction}] {selection}"


def make(text, tmp_path, cfg=None, keyboard=None, llm=None, app=("WhatsApp.exe", "Conversa")):
    cfg = cfg or Config()
    return DitvvOS(cfg, keyboard=keyboard or FakeKeyboard(), recorder=FakeRecorder(),
                   transcriber=FakeTranscriber(text), llm=llm, history=History(tmp_path / "h.db"),
                   app_detector=lambda: app)


# ------------------------------------------------------------------ fluxo principal
def test_ditado_aplica_regras_e_estilo_do_app(tmp_path):
    kb = FakeKeyboard()
    cfg = Config(replacements={"super base": "Supabase"})
    app = make("Hum, o deploy no super base é às 2, digo, 3 horas.", tmp_path, cfg, kb)
    r = app.process(VOICE, DICTATE, ("WhatsApp.exe", "Conversa"))
    assert r.text == "O deploy no Supabase é às 3 horas"  # casual: sem ponto final
    assert kb.sent == [("O deploy no Supabase é às 3 horas ", False)]
    assert r.style == "casual" and "hesitações" in r.steps
    assert app.history.stats()["palavras"] == 8


def test_enviar_aperta_enter_sem_espaco_extra(tmp_path):
    kb = FakeKeyboard()
    app = make("Rode os testes.", tmp_path, Config(submit=True), kb)
    app.process(VOICE, DICTATE, ("WindowsTerminal.exe", "Claude Code"))
    assert kb.sent == [("Rode os testes.", True)]


def test_cancelar_nao_cola_nem_salva(tmp_path):
    kb = FakeKeyboard()
    app = make("Isso ficou errado, cancela isso.", tmp_path, keyboard=kb)
    r = app.process(VOICE)
    assert r.cancelled and kb.sent == [] and app.history.stats()["ditados"] == 0


def test_silencio_nao_chama_transcricao(tmp_path):
    app = make("não deveria aparecer", tmp_path)
    assert app.process(np.zeros(SR, dtype=np.float32)) is None


def test_polimento_ia_opcional(tmp_path):
    cfg = Config(llm=LLMConfig(enabled=True, polish=True))
    kb = FakeKeyboard()
    app = make("Texto simples.", tmp_path, cfg, kb, llm=FakeLLM())
    assert app.process(VOICE).text == "TEXTO SIMPLES."
    r = app.process(VOICE, DICTATE, ("WhatsApp.exe", ""))
    assert r.text == "TEXTO SIMPLES" and "IA" in r.steps  # estilo casual vale também após a IA


def test_modo_comando_reescreve_selecao(tmp_path):
    kb = FakeKeyboard(selection="texto original")
    r = make("Deixe mais formal", tmp_path, keyboard=kb, llm=FakeLLM()).process(VOICE, COMMAND)
    assert kb.sent == [("[Deixe mais formal] texto original", False)]
    assert r.steps == ["comando na seleção"]


def test_modo_comando_sem_ia_avisa(tmp_path):
    kb = FakeKeyboard(selection="x")
    assert make("Traduza", tmp_path, keyboard=kb).process(VOICE, COMMAND) is None
    assert kb.sent == []


def test_atalho_pelo_hotkey_ponta_a_ponta(tmp_path):
    kb, results = FakeKeyboard(), []
    app = make("Olá, Claude.", tmp_path, keyboard=kb)
    app.on_result = results.append
    app.hotkey.press(); app.hotkey._pressed_at -= 1; app.hotkey.release()  # segurou 1s
    app.close()
    assert kb.sent == [("Olá, Claude ", False)] and results[0].app == "WhatsApp.exe"  # casual


def test_microfone_quebrado_nao_lanca(tmp_path):
    class Broken(FakeRecorder):
        def start(self):
            raise OSError("sem dispositivo")

    app = make("x", tmp_path)
    app.recorder = Broken()
    app.hotkey.press(); app.hotkey.release()  # não pode lançar exceção
    app.close()


# ------------------------------------------------------------------ teclado
class FakeController:
    def __init__(self, clip, selection):
        self.events, self.clip, self.selection = [], clip, selection

    def type(self, text):
        self.events.append(("type", text))

    def press(self, k):
        self.events.append(("press", k))
        if k == "c" and self.selection is not None:  # o app copia a seleção
            self.clip.value = self.selection

    def release(self, k):
        self.events.append(("release", k))

    @contextlib.contextmanager
    def pressed(self, k):
        self.events.append(("hold", k))
        yield


class FakeClipboard:
    def __init__(self, value="antigo"):
        self.value = value

    def copy(self, v):
        self.value = v

    def paste(self):
        return self.value


KEYS = SimpleNamespace(ctrl="CTRL", cmd="CMD", enter="ENTER")


def test_keyboard_le_selecao_e_restaura_area_de_transferencia():
    clip = FakeClipboard("antigo")
    kb = Keyboard("colar", FakeController(clip, "selecionado"), clip, KEYS, platform="win32")
    assert kb.selected_text() == "selecionado" and clip.value == "antigo"
    kb_vazio = Keyboard("colar", FakeController(clip, None), clip, KEYS)
    assert kb_vazio.selected_text(wait=0.05) == "" and clip.value == "antigo"


def test_keyboard_colar_enter_e_mac():
    clip = FakeClipboard()
    ctl = FakeController(clip, None)
    Keyboard("colar", ctl, clip, KEYS, platform="darwin").send("oi", submit=True, restore_clipboard=False)
    assert ctl.events[0] == ("hold", "CMD") and ctl.events[-2:] == [("press", "ENTER"), ("release", "ENTER")]


def test_prepare_audio():
    assert prepare_audio(np.zeros(SR // 10, dtype=np.float32)) is None
    assert prepare_audio(np.full(SR, 0.0005, dtype=np.float32)) is None
    out = prepare_audio((0.01 * np.sin(np.linspace(0, 500, SR))).astype(np.float32))
    assert abs(float(np.max(np.abs(out))) - 0.9) < 0.01


# ------------------------------------------------------------------ config / histórico / autostart
def test_config_persistencia_e_estilos(tmp_path):
    path = tmp_path / "c.json"
    cfg = Config.load(path)
    cfg.snippets["oi"] = "Olá!"
    cfg.llm.model = "llama3.2"
    cfg.save(path)
    again = Config.load(path)
    assert again.snippets == {"oi": "Olá!"} and again.llm.model == "llama3.2"
    assert again.style_for("chrome.exe", "Caixa de entrada - Gmail") == "formal"
    assert again.style_for("Code.exe", "engine.py") == "codigo"
    assert again.style_for("app.exe", "Qualquer") == "normal"


def test_historico_busca_e_estatisticas(tmp_path):
    h = History(tmp_path / "h.db")
    h.add(app="a", style="normal", mode="ditado", raw="r", final="um dois três quatro",
          audio_seconds=3, latency_seconds=1)
    h.add(app="b", style="normal", mode="ditado", raw="r", final="cinco seis", audio_seconds=3,
          latency_seconds=2)
    assert [e.final for e in h.recent(search="cinco")] == ["cinco seis"]
    st = h.stats()
    assert st["palavras"] == 6 and st["palavras_por_minuto"] == 60 and st["espera_media_s"] == 1.5


@pytest.mark.parametrize("platform,name", [("win32", "DitvvOS.vbs"), ("darwin", "com.ditvvos.agent.plist"),
                                           ("linux", "ditvvos.desktop")])
def test_autostart(tmp_path, monkeypatch, platform, name):
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    path = autostart.enable(platform, tmp_path)
    assert path.name == name and "ditvvos" in path.read_text()
    assert autostart.disable(platform, tmp_path) == path and not path.exists()


# ------------------------------------------------------------------ Ollama (servidor falso)
@pytest.fixture
def fake_ollama():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"models": []}')

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(body)
            reply = {"message": {"content": '"Texto corrigido."'}}
            self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(reply).encode())

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", calls
    server.shutdown()


def test_ollama_polimento_e_comando(fake_ollama):
    url, calls = fake_ollama
    llm = Ollama(LLMConfig(url=url, model="qwen2.5:3b"))
    assert llm.available()
    assert llm.polish("texto", "formal") == "Texto corrigido."  # aspas removidas
    assert llm.command("resuma", "texto longo") == "Texto corrigido."
    assert calls[0]["model"] == "qwen2.5:3b" and "profissional" in calls[0]["messages"][0]["content"]
    assert "texto longo" in calls[1]["messages"][1]["content"]


def test_ollama_fora_do_ar():
    llm = Ollama(LLMConfig(url="http://127.0.0.1:9", timeout=1))
    assert not llm.available()
    with pytest.raises(LLMError):
        llm.polish("x", "normal")


def test_travas_da_ia():
    from ditvvos.llm import foreign_script, overlap
    assert overlap("qual é a capital da frança", "Paris é a capital da França.") < 0.7
    assert overlap("hum me manda o arquivo amanhã", "Me manda o arquivo amanhã.") == 1.0
    assert foreign_script("deixe formal", "preciso对其进行于明天")
    assert not foreign_script("traduza para chinês", "谢谢")
    assert not foreign_script("deixe formal", "Prezado, envie o relatório.")
