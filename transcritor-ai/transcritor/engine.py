"""Motor de transcrição: faster-whisper (CTranslate2) + revisão de baixa confiança.

Pipeline:
  1. ffmpeg: qualquer formato -> WAV 16 kHz mono, normalizado
  2. VAD (Silero) corta silêncios -> menos alucinação, mais velocidade
  3. Whisper com beam search, timestamps por palavra e vocabulário customizado
  4. 2ª passada: trechos com baixa confiança são re-decodificados isoladamente com
     busca mais ampla; fica a versão com maior log-probabilidade
  5. Limpeza: alucinações conhecidas, loops de repetição, glossário
  6. (opcional) Diarização com pyannote -> quem falou o quê
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from . import audio, postprocess
from .config import TranscribeOptions
from .models import Segment, Transcript, Word

log = logging.getLogger("transcritor")

ProgressFn = Callable[[str, float], None]
SAMPLE_RATE = 16000

_model_cache: Dict[Tuple[str, str, str], object] = {}
_model_lock = threading.Lock()


def detect_device() -> Tuple[str, str]:
    """Escolhe GPU (float16) se houver CUDA; senão CPU com int8 (rápido e leve)."""
    forced = os.environ.get("TRANSCRITOR_DEVICE")
    try:
        import ctranslate2

        has_cuda = ctranslate2.get_cuda_device_count() > 0
    except Exception:
        has_cuda = False
    device = forced or ("cuda" if has_cuda else "cpu")
    compute = os.environ.get("TRANSCRITOR_COMPUTE_TYPE") or (
        "float16" if device == "cuda" else "int8"
    )
    return device, compute


def load_model(name: str):
    from faster_whisper import WhisperModel

    device, compute = detect_device()
    key = (name, device, compute)
    with _model_lock:
        if key not in _model_cache:
            log.info("Carregando modelo %s (%s/%s)...", name, device, compute)
            _model_cache[key] = WhisperModel(
                name, device=device, compute_type=compute,
                cpu_threads=int(os.environ.get("TRANSCRITOR_CPU_THREADS", "0")),
                download_root=os.environ.get("TRANSCRITOR_MODELS_DIR"),
            )
        return _model_cache[key]


def build_prompt(opts: TranscribeOptions) -> Optional[str]:
    """Prompt inicial: contexto + vocabulário. O Whisper tende a copiar a grafia e
    a pontuação do prompt, o que melhora nomes próprios, siglas e jargões."""
    parts = []
    if opts.context.strip():
        parts.append(opts.context.strip())
    if opts.vocabulary:
        parts.append("Termos: " + ", ".join(opts.vocabulary) + ".")
    return " ".join(parts) or None


def _convert(fw_segments, offset: float = 0.0) -> List[Segment]:
    out = []
    for s in fw_segments:
        words = [
            Word(start=w.start + offset, end=w.end + offset, text=w.word,
                 probability=float(w.probability))
            for w in (s.words or [])
        ]
        out.append(Segment(
            start=s.start + offset, end=s.end + offset, text=s.text.strip(), words=words,
            avg_logprob=float(s.avg_logprob), compression_ratio=float(s.compression_ratio),
            no_speech_prob=float(s.no_speech_prob),
        ))
    return out


def needs_revision(seg: Segment, opts: TranscribeOptions) -> bool:
    return (
        seg.avg_logprob < opts.revision_logprob_threshold
        or seg.confidence < opts.revision_confidence_threshold
        or seg.compression_ratio > 2.2
    )


def _mean_logprob(segments: List[Segment]) -> float:
    total = sum(max(len(s.words), 1) for s in segments)
    if not total:
        return float("-inf")
    return sum(s.avg_logprob * max(len(s.words), 1) for s in segments) / total


def revise_segments(
    model, samples, segments: List[Segment], opts: TranscribeOptions,
    prompt: Optional[str], progress: Optional[ProgressFn] = None,
) -> List[Segment]:
    targets = [i for i, s in enumerate(segments) if needs_revision(s, opts)]
    if not targets:
        return segments
    log.info("Revisando %d de %d trechos de baixa confiança", len(targets), len(segments))
    replaced: Dict[int, List[Segment]] = {}
    for n, i in enumerate(targets, 1):
        seg = segments[i]
        pad = 0.25
        start = max(0.0, seg.start - pad)
        end = min(len(samples) / SAMPLE_RATE, seg.end + pad)
        clip = samples[int(start * SAMPLE_RATE):int(end * SAMPLE_RATE)]
        if len(clip) < SAMPLE_RATE * 0.3:
            continue
        fw_segs, _ = model.transcribe(
            clip, language=opts.language, beam_size=opts.revision_beam_size,
            best_of=opts.revision_beam_size, patience=2.0,
            temperature=[0.0, 0.2, 0.4], condition_on_previous_text=False,
            initial_prompt=prompt,
            word_timestamps=True, vad_filter=False,
        )
        candidates = _convert(list(fw_segs), offset=start)
        if candidates and _mean_logprob(candidates) > seg.avg_logprob + 0.05:
            for c in candidates:
                c.revised = True
            replaced[i] = candidates
        if progress:
            progress("revisando", n / len(targets))
    if not replaced:
        return segments
    final: List[Segment] = []
    for i, seg in enumerate(segments):
        final.extend(replaced.get(i, [seg]))
    return final


class Transcriber:
    def __init__(self, opts: TranscribeOptions):
        self.opts = opts

    def transcribe(self, src: str | Path, progress: Optional[ProgressFn] = None) -> Transcript:
        from faster_whisper import decode_audio

        opts = self.opts
        report = progress or (lambda stage, frac: None)
        t0 = time.perf_counter()

        report("preparando audio", 0.0)
        wav = audio.preprocess(src, normalize=opts.normalize, denoise=opts.denoise)
        try:
            samples = decode_audio(str(wav), sampling_rate=SAMPLE_RATE)
            duration = len(samples) / SAMPLE_RATE

            report("carregando modelo", 0.0)
            model = load_model(opts.model)
            prompt = build_prompt(opts)

            fw_segments, info = model.transcribe(
                samples,
                language=opts.language,
                beam_size=opts.beam_size,
                best_of=opts.best_of,
                patience=opts.patience,
                condition_on_previous_text=opts.condition_on_previous_text,
                initial_prompt=prompt,
                word_timestamps=True,
                vad_filter=opts.vad,
                vad_parameters={"min_silence_duration_ms": opts.vad_min_silence_ms},
                hallucination_silence_threshold=opts.hallucination_silence_threshold,
            )
            raw = []
            for s in fw_segments:  # gerador: decodifica sob demanda
                raw.append(s)
                report("transcrevendo", min(s.end / duration, 1.0) if duration else 1.0)
            segments = _convert(raw)

            if opts.revision_pass:
                segments = revise_segments(model, samples, segments, opts, prompt, report)

            segments = postprocess.postprocess(segments, opts.replacements)

            speakers: List[str] = []
            if opts.diarize:
                from . import diarization

                report("identificando falantes", 0.0)
                turns = diarization.diarize(
                    str(wav), num_speakers=opts.num_speakers,
                    min_speakers=opts.min_speakers, max_speakers=opts.max_speakers,
                )
                segments = diarization.assign_speakers(segments, turns)
                speakers = list(dict.fromkeys(s.speaker for s in segments if s.speaker))
        finally:
            Path(wav).unlink(missing_ok=True)

        report("concluido", 1.0)
        return Transcript(
            segments=segments,
            language=info.language,
            language_probability=float(info.language_probability),
            duration=duration,
            model=opts.model,
            processing_seconds=time.perf_counter() - t0,
            speakers=speakers,
        )
