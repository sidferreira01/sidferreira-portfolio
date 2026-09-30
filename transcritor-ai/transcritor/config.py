"""Opções de transcrição e presets de qualidade."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class TranscribeOptions:
    model: str = "large-v3-turbo"
    language: Optional[str] = "pt"  # None = detecção automática
    beam_size: int = 5
    best_of: int = 5
    patience: float = 1.0
    # Desligar reduz "loops" de repetição e alucinações em áudios longos.
    condition_on_previous_text: bool = False
    vad: bool = True
    vad_min_silence_ms: int = 500
    # Descarta trechos alucinados em silêncios longos (requer timestamps por palavra).
    hallucination_silence_threshold: Optional[float] = 2.0
    # 2ª passada: re-decodifica com busca mais ampla os trechos de baixa confiança.
    revision_pass: bool = True
    revision_beam_size: int = 10
    revision_logprob_threshold: float = -0.6
    revision_confidence_threshold: float = 0.65
    # Pré-processamento
    normalize: bool = True
    denoise: bool = False
    # Vocabulário / contexto
    vocabulary: List[str] = field(default_factory=list)
    replacements: Dict[str, str] = field(default_factory=dict)
    context: str = ""
    # Diarização (quem falou)
    diarize: bool = False
    num_speakers: Optional[int] = None
    min_speakers: Optional[int] = None
    max_speakers: Optional[int] = None

    def with_overrides(self, **kwargs) -> "TranscribeOptions":
        clean = {k: v for k, v in kwargs.items() if v is not None}
        return replace(self, **clean)


PRESETS: Dict[str, TranscribeOptions] = {
    # Máxima precisão: modelo completo + busca ampla + revisão. Mais lento.
    "maxima": TranscribeOptions(
        model="large-v3", beam_size=8, best_of=5, patience=1.5,
        revision_pass=True, revision_beam_size=12,
    ),
    # Padrão: large-v3-turbo tem precisão muito próxima do large-v3
    # e é várias vezes mais rápido (decoder de 4 camadas). Melhor custo/benefício.
    "equilibrado": TranscribeOptions(),
    # Rascunho rápido (triagem, áudios de WhatsApp curtos, CPUs fracas).
    "rapido": TranscribeOptions(
        model="small", beam_size=1, best_of=1, revision_pass=False,
    ),
}


def get_preset(name: str) -> TranscribeOptions:
    try:
        return replace(PRESETS[name])
    except KeyError:
        raise ValueError(f"Preset desconhecido '{name}'. Opções: {', '.join(PRESETS)}") from None


def parse_glossary(text: str) -> tuple[List[str], Dict[str, str]]:
    """Lê um glossário no formato:

        # comentário
        Evolution API            -> termo do vocabulário (ajuda o modelo a acertar)
        leed talk => LeadTalkAI  -> correção forçada após a transcrição
    """
    vocabulary: List[str] = []
    replacements: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=>" in line:
            wrong, right = (p.strip() for p in line.split("=>", 1))
            if wrong and right:
                replacements[wrong] = right
                if right not in vocabulary:
                    vocabulary.append(right)
        elif line not in vocabulary:
            vocabulary.append(line)
    return vocabulary, replacements


def load_glossary(path: str | Path) -> tuple[List[str], Dict[str, str]]:
    return parse_glossary(Path(path).read_text(encoding="utf-8"))
