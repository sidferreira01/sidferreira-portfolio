"""Pré-processamento de áudio com ffmpeg.

Converte qualquer entrada (mp3, m4a, ogg/opus do WhatsApp, mp4, mkv...) para
WAV 16 kHz mono — o formato nativo do Whisper — e aplica uma cadeia leve de
filtros que melhora a precisão em gravações reais:

* highpass 80 Hz  -> remove ronco/ruído de baixa frequência (ar-condicionado, mesa)
* afftdn          -> redução de ruído espectral (opcional, útil em áudio ruim)
* loudnorm        -> normaliza volume (falas baixas deixam de ser "puladas")
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


class AudioError(RuntimeError):
    pass


def find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:  # fallback: binário estático distribuído via pip (imageio-ffmpeg)
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover - depende do ambiente
        raise AudioError(
            "ffmpeg não encontrado. Instale (apt install ffmpeg / brew install ffmpeg) "
            "ou `pip install imageio-ffmpeg`."
        ) from exc


def build_filter_chain(normalize: bool = True, denoise: bool = False) -> str:
    filters = ["highpass=f=80"]
    if denoise:
        filters.append("afftdn=nf=-25")
    if normalize:
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    return ",".join(filters)


def preprocess(
    src: str | Path,
    dst: str | Path | None = None,
    *,
    normalize: bool = True,
    denoise: bool = False,
) -> Path:
    """Converte `src` para WAV 16 kHz mono (pcm_s16le) e retorna o caminho."""
    src = Path(src)
    if not src.exists():
        raise AudioError(f"Arquivo não encontrado: {src}")
    if dst is None:
        tmp = tempfile.NamedTemporaryFile(prefix="transcritor_", suffix=".wav", delete=False)
        tmp.close()
        dst = tmp.name
    dst = Path(dst)

    cmd = [
        find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(src),
        "-vn",  # descarta vídeo
        "-af", build_filter_chain(normalize=normalize, denoise=denoise),
        "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise AudioError(f"ffmpeg falhou ao processar {src.name}: {proc.stderr.strip()}")
    return dst
