"""Interface web + API REST (FastAPI).

Fila com um único worker: o modelo é pesado e processar um arquivo por vez usa
melhor a CPU/GPU do que vários em paralelo. Resultados ficam em disco e
sobrevivem a reinícios.

Segurança: por padrão escuta só em 127.0.0.1. Para expor na rede/VPS, defina
TRANSCRITOR_TOKEN e envie `Authorization: Bearer <token>`.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import re
import secrets
import shutil
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

from . import __version__, audio
from .config import PRESETS, get_preset, parse_glossary
from .exporters import EXPORTERS, export
from .models import Transcript

log = logging.getLogger("transcritor.server")
STATIC = Path(__file__).parent / "static"
MAX_UPLOAD_MB = int(os.environ.get("TRANSCRITOR_MAX_UPLOAD_MB", "2048"))
MEDIA_TYPES = {"txt": "text/plain", "srt": "application/x-subrip", "vtt": "text/vtt",
               "json": "application/json", "md": "text/markdown"}


@dataclass
class Job:
    id: str
    filename: str
    created: float
    options: dict
    status: str = "na fila"      # na fila | processando | concluido | erro
    stage: str = ""
    progress: float = 0.0
    error: Optional[str] = None
    duration: Optional[float] = None
    finished: Optional[float] = None
    summary: dict = field(default_factory=dict)


class JobStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.jobs: Dict[str, Job] = {}
        self.lock = threading.Lock()
        self._load()

    def dir(self, job_id: str) -> Path:
        return self.root / job_id

    def _load(self) -> None:
        for meta in self.root.glob("*/job.json"):
            try:
                job = Job(**json.loads(meta.read_text(encoding="utf-8")))
            except Exception:
                continue
            if job.status in ("na fila", "processando"):
                job.status, job.error = "erro", "Servidor reiniciado durante o processamento"
            self.jobs[job.id] = job

    def save(self, job: Job) -> None:
        with self.lock:
            self.jobs[job.id] = job
            path = self.dir(job.id) / "job.json"
            path.write_text(json.dumps(asdict(job), ensure_ascii=False), encoding="utf-8")

    def transcript(self, job_id: str) -> Transcript:
        path = self.dir(job_id) / "transcript.json"
        if not path.exists():
            raise HTTPException(404, "Transcrição ainda não disponível")
        return Transcript.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def delete(self, job_id: str) -> None:
        with self.lock:
            self.jobs.pop(job_id, None)
        shutil.rmtree(self.dir(job_id), ignore_errors=True)


class Worker(threading.Thread):
    def __init__(self, store: JobStore):
        super().__init__(daemon=True, name="transcritor-worker")
        self.store = store
        self.queue: "queue.Queue[str]" = queue.Queue()

    def run(self) -> None:
        while True:
            job_id = self.queue.get()
            job = self.store.jobs.get(job_id)
            if job is None:  # removido enquanto estava na fila
                continue
            try:
                self._process(job)
            except Exception as exc:
                log.exception("Falha no job %s", job_id)
                job.status, job.error = "erro", str(exc)
                self.store.save(job)

    def _process(self, job: Job) -> None:
        from .engine import Transcriber

        job_dir = self.store.dir(job.id)
        src = next(job_dir.glob("original.*"))
        job.status = "processando"
        self.store.save(job)
        last_save = [0.0]

        def report(stage: str, frac: float) -> None:
            job.stage, job.progress = stage, round(frac, 3)
            if time.time() - last_save[0] > 1.0:
                last_save[0] = time.time()
                self.store.save(job)

        o = job.options
        opts = get_preset(o.get("preset", "equilibrado"))
        vocab, repl = parse_glossary(o.get("glossary", ""))
        opts = opts.with_overrides(
            language=None if o.get("language") == "auto" else o.get("language"),
            denoise=bool(o.get("denoise")),
            diarize=bool(o.get("diarize")),
            num_speakers=o.get("num_speakers") or None,
            context=o.get("context") or None,
            vocabulary=vocab or None,
            replacements=repl or None,
        )
        # áudio normalizado para o player (toca em qualquer navegador)
        audio.preprocess(src, job_dir / "audio.wav", normalize=True)

        t = Transcriber(opts).transcribe(src, progress=report)
        (job_dir / "transcript.json").write_text(
            json.dumps(t.to_dict(), ensure_ascii=False), encoding="utf-8")
        low = sum(1 for s in t.segments for w in s.words if w.probability < 0.5)
        job.summary = {
            "words": sum(len(s.words) or len(s.text.split()) for s in t.segments),
            "low_confidence": low,
            "speakers": t.speakers,
            "processing_seconds": round(t.processing_seconds, 1),
            "realtime_factor": round(t.realtime_factor, 2),
            "model": t.model,
        }
        job.duration = t.duration
        job.status, job.stage, job.progress = "concluido", "concluido", 1.0
        job.finished = time.time()
        self.store.save(job)


def _safe_name(name: str) -> str:
    stem = Path(name or "audio").stem
    return re.sub(r"[^\w.-]+", "_", stem)[:80] or "audio"


def create_app(data_dir: str | Path = "./dados") -> FastAPI:
    app = FastAPI(title="Transcritor AI", version=__version__)
    store = JobStore(Path(data_dir))
    worker = Worker(store)
    worker.start()
    token = os.environ.get("TRANSCRITOR_TOKEN")

    def auth(request: Request) -> None:
        if not token:
            return
        header = request.headers.get("authorization", "")
        supplied = header[7:] if header.lower().startswith("bearer ") else request.query_params.get("token", "")
        if not secrets.compare_digest(supplied, token):
            raise HTTPException(401, "Token inválido")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (STATIC / "index.html").read_text(encoding="utf-8")

    @app.get("/api/config", dependencies=[Depends(auth)])
    def config():
        from . import diarization
        from .engine import detect_device

        device, compute = detect_device()
        return {
            "version": __version__,
            "presets": {k: {"model": v.model, "revision": v.revision_pass} for k, v in PRESETS.items()},
            "formats": list(EXPORTERS),
            "diarization": diarization.is_available() and bool(os.environ.get("HF_TOKEN")),
            "device": device, "compute_type": compute,
            "auth": bool(token),
        }

    @app.post("/api/jobs", dependencies=[Depends(auth)])
    async def create_job(
        file: UploadFile = File(...),
        preset: str = Form("equilibrado"),
        language: str = Form("pt"),
        diarize: bool = Form(False),
        num_speakers: int = Form(0),
        denoise: bool = Form(False),
        glossary: str = Form(""),
        context: str = Form(""),
    ):
        if preset not in PRESETS:
            raise HTTPException(400, f"Preset inválido: {preset}")
        job_id = uuid.uuid4().hex[:12]
        job_dir = store.dir(job_id)
        job_dir.mkdir(parents=True)
        ext = (Path(file.filename or "").suffix or ".bin").lower()[:8]
        dest = job_dir / f"original{ext}"
        size, limit = 0, MAX_UPLOAD_MB * 1024 * 1024
        with dest.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    out.close()
                    store.delete(job_id)
                    raise HTTPException(413, f"Arquivo maior que {MAX_UPLOAD_MB} MB")
                out.write(chunk)
        job = Job(
            id=job_id, filename=file.filename or "audio", created=time.time(),
            options=dict(preset=preset, language=language, diarize=diarize,
                         num_speakers=num_speakers, denoise=denoise,
                         glossary=glossary, context=context),
        )
        store.save(job)
        worker.queue.put(job_id)
        return asdict(job)

    @app.get("/api/jobs", dependencies=[Depends(auth)])
    def list_jobs():
        return sorted((asdict(j) for j in store.jobs.values()), key=lambda j: -j["created"])

    def get_job(job_id: str) -> Job:
        job = store.jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Job não encontrado")
        return job

    @app.get("/api/jobs/{job_id}", dependencies=[Depends(auth)])
    def job_detail(job_id: str):
        job = get_job(job_id)
        data = asdict(job)
        if job.status == "concluido":
            data["transcript"] = store.transcript(job_id).to_dict()
        return data

    @app.delete("/api/jobs/{job_id}", dependencies=[Depends(auth)])
    def delete_job(job_id: str):
        job = get_job(job_id)
        if job.status == "processando":
            raise HTTPException(409, "Aguarde o fim do processamento para excluir")
        store.delete(job_id)
        return {"ok": True}

    @app.get("/api/jobs/{job_id}/audio", dependencies=[Depends(auth)])
    def job_audio(job_id: str):
        get_job(job_id)
        path = store.dir(job_id) / "audio.wav"
        if not path.exists():
            raise HTTPException(404, "Áudio indisponível")
        return FileResponse(path, media_type="audio/wav")

    @app.get("/api/jobs/{job_id}/download/{fmt}", dependencies=[Depends(auth)])
    def download(job_id: str, fmt: str):
        job = get_job(job_id)
        if fmt not in EXPORTERS:
            raise HTTPException(400, "Formato inválido")
        content = export(store.transcript(job_id), fmt)
        filename = f"{_safe_name(job.filename)}.{fmt}"
        return PlainTextResponse(
            content, media_type=f"{MEDIA_TYPES[fmt]}; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return app
