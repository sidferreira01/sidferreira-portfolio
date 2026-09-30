"""Diarização (identificação de quem falou) com pyannote.audio — opcional.

Modelo padrão: `pyannote/speaker-diarization-community-1` (pyannote.audio 4.x),
o melhor modelo aberto de diarização atualmente. Roda local; só é preciso um
token gratuito do Hugging Face para baixar os pesos na primeira vez
(aceite os termos em huggingface.co/pyannote/speaker-diarization-community-1).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Sequence

from .models import Segment

DEFAULT_PIPELINE = "pyannote/speaker-diarization-community-1"


@dataclass
class Turn:
    start: float
    end: float
    speaker: str


def is_available() -> bool:
    try:
        import pyannote.audio  # noqa: F401
    except Exception:
        return False
    return True


_pipeline_cache = {}


def _load_pipeline(name: str, token: Optional[str]):
    if name in _pipeline_cache:
        return _pipeline_cache[name]
    from pyannote.audio import Pipeline

    try:
        pipeline = Pipeline.from_pretrained(name, token=token)
    except TypeError:  # pyannote 3.x usa use_auth_token
        pipeline = Pipeline.from_pretrained(name, use_auth_token=token)
    if pipeline is None:
        raise RuntimeError(
            f"Não foi possível carregar {name}. Defina HF_TOKEN e aceite os termos do modelo."
        )
    try:
        import torch

        if torch.cuda.is_available():
            pipeline.to(torch.device("cuda"))
    except Exception:
        pass
    _pipeline_cache[name] = pipeline
    return pipeline


def diarize(
    wav_path: str,
    *,
    num_speakers: Optional[int] = None,
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None,
    pipeline_name: str = DEFAULT_PIPELINE,
) -> List[Turn]:
    pipeline = _load_pipeline(pipeline_name, os.environ.get("HF_TOKEN"))
    kwargs = {k: v for k, v in dict(
        num_speakers=num_speakers, min_speakers=min_speakers, max_speakers=max_speakers,
    ).items() if v}
    output = pipeline(wav_path, **kwargs)

    # pyannote 4.x: modo "exclusive" (um falante por vez) casa melhor com STT
    annotation = getattr(output, "exclusive_speaker_diarization", None) \
        or getattr(output, "speaker_diarization", None) or output
    turns = [
        Turn(turn.start, turn.end, str(label))
        for turn, _, label in annotation.itertracks(yield_label=True)
    ]
    return turns


def friendly_labels(turns: Sequence[Turn]) -> dict:
    """SPEAKER_00 -> 'Falante 1', na ordem em que aparecem."""
    mapping: dict = {}
    for t in sorted(turns, key=lambda t: t.start):
        if t.speaker not in mapping:
            mapping[t.speaker] = f"Falante {len(mapping) + 1}"
    return mapping


def _speaker_at(start: float, end: float, turns: Sequence[Turn]) -> Optional[str]:
    best, best_overlap = None, 0.0
    for t in turns:
        overlap = min(end, t.end) - max(start, t.start)
        if overlap > best_overlap:
            best, best_overlap = t.speaker, overlap
    if best is not None:
        return best
    # sem sobreposição (palavra caiu num "buraco"): usa o turno mais próximo
    mid = (start + end) / 2
    nearest = min(turns, key=lambda t: min(abs(mid - t.start), abs(mid - t.end)), default=None)
    return nearest.speaker if nearest else None


def assign_speakers(segments: List[Segment], turns: Sequence[Turn]) -> List[Segment]:
    """Atribui falante a cada palavra e quebra segmentos onde o falante muda."""
    if not turns:
        return segments
    labels = friendly_labels(turns)
    result: List[Segment] = []
    for seg in segments:
        if not seg.words:
            spk = _speaker_at(seg.start, seg.end, turns)
            seg.speaker = labels.get(spk, spk)
            result.append(seg)
            continue
        for w in seg.words:
            spk = _speaker_at(w.start, w.end, turns)
            w.speaker = labels.get(spk, spk)
        # agrupa palavras consecutivas do mesmo falante
        groups = [[seg.words[0]]]
        for w in seg.words[1:]:
            if w.speaker == groups[-1][-1].speaker:
                groups[-1].append(w)
            else:
                groups.append([w])
        if len(groups) == 1:
            seg.speaker = groups[0][0].speaker
            result.append(seg)
            continue
        for g in groups:
            result.append(Segment(
                start=g[0].start, end=g[-1].end,
                text="".join(w.text for w in g).strip(),
                words=g, speaker=g[0].speaker,
                avg_logprob=seg.avg_logprob, compression_ratio=seg.compression_ratio,
                no_speech_prob=seg.no_speech_prob, revised=seg.revised,
            ))
    return result
