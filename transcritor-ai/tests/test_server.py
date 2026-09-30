import io
import time

from fastapi.testclient import TestClient
from helpers import seg, transcript

import transcritor.engine as engine
import transcritor.server as server


class FakeTranscriber:
    def __init__(self, opts):
        self.opts = opts

    def transcribe(self, src, progress=None):
        progress("transcrevendo", 0.5)
        return transcript(seg("olá do teste", 0, prob=0.3))


def _wait(client, job_id, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("concluido", "erro"):
            return job
        time.sleep(0.05)
    raise AssertionError("job não terminou")


def _app(tmp_path, monkeypatch, token=None):
    monkeypatch.setattr(engine, "Transcriber", FakeTranscriber)
    monkeypatch.setattr(server.audio, "preprocess", lambda src, dst=None, **kw: open(dst, "wb").close())
    if token:
        monkeypatch.setenv("TRANSCRITOR_TOKEN", token)
    else:
        monkeypatch.delenv("TRANSCRITOR_TOKEN", raising=False)
    return TestClient(server.create_app(tmp_path))


def test_fluxo_completo(tmp_path, monkeypatch):
    client = _app(tmp_path, monkeypatch)
    r = client.post("/api/jobs", files={"file": ("reuniao.ogg", io.BytesIO(b"fake"), "audio/ogg")},
                    data={"glossary": "leed => Lead", "preset": "rapido"})
    assert r.status_code == 200, r.text
    job = _wait(client, r.json()["id"])
    assert job["status"] == "concluido", job
    assert job["transcript"]["text"] == "olá do teste"
    assert job["summary"]["low_confidence"] == 3
    srt = client.get(f"/api/jobs/{job['id']}/download/srt")
    assert srt.status_code == 200 and "olá do teste" in srt.text
    assert 'filename="reuniao.srt"' in srt.headers["content-disposition"]
    assert client.delete(f"/api/jobs/{job['id']}").json() == {"ok": True}
    assert client.get("/api/jobs").json() == []


def test_preset_invalido(tmp_path, monkeypatch):
    client = _app(tmp_path, monkeypatch)
    r = client.post("/api/jobs", files={"file": ("a.mp3", b"x")}, data={"preset": "xyz"})
    assert r.status_code == 400


def test_token_obrigatorio_quando_configurado(tmp_path, monkeypatch):
    client = _app(tmp_path, monkeypatch, token="segredo")
    assert client.get("/api/jobs").status_code == 401
    assert client.get("/api/jobs", headers={"Authorization": "Bearer segredo"}).status_code == 200
    assert client.get("/api/jobs?token=segredo").status_code == 200
    assert client.get("/").status_code == 200  # a página em si é pública
