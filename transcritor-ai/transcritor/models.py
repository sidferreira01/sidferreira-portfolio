"""Estruturas de dados da transcrição (independentes do motor de ASR)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class Word:
    start: float
    end: float
    text: str
    probability: float = 1.0
    speaker: Optional[str] = None


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: List[Word] = field(default_factory=list)
    speaker: Optional[str] = None
    avg_logprob: float = 0.0
    compression_ratio: float = 0.0
    no_speech_prob: float = 0.0
    revised: bool = False  # True quando passou pela 2ª passada de revisão

    @property
    def confidence(self) -> float:
        """Confiança média das palavras (0–1)."""
        if not self.words:
            return 1.0
        return sum(w.probability for w in self.words) / len(self.words)


@dataclass
class Transcript:
    segments: List[Segment]
    language: str
    language_probability: float
    duration: float
    model: str
    processing_seconds: float = 0.0
    speakers: List[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments if s.text.strip())

    @property
    def realtime_factor(self) -> float:
        """Quantas vezes mais rápido que o tempo real (ex.: 5.0 = 5x)."""
        if not self.processing_seconds:
            return 0.0
        return self.duration / self.processing_seconds

    def to_dict(self) -> dict:
        data = asdict(self)
        data["text"] = self.text
        data["realtime_factor"] = round(self.realtime_factor, 2)
        for seg, raw in zip(self.segments, data["segments"]):
            raw["confidence"] = round(seg.confidence, 4)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Transcript":
        segments = []
        for raw in data["segments"]:
            words = [Word(**w) for w in raw.get("words", [])]
            seg_fields = {k: raw[k] for k in (
                "start", "end", "text", "speaker", "avg_logprob",
                "compression_ratio", "no_speech_prob", "revised",
            ) if k in raw}
            segments.append(Segment(words=words, **seg_fields))
        return cls(
            segments=segments,
            language=data["language"],
            language_probability=data.get("language_probability", 1.0),
            duration=data["duration"],
            model=data["model"],
            processing_seconds=data.get("processing_seconds", 0.0),
            speakers=data.get("speakers", []),
        )
