"""Limpeza pós-transcrição: alucinações conhecidas, loops de repetição e glossário."""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List

from .models import Segment, Word

# Frases que o Whisper "inventa" em silêncio/música porque apareciam em legendas
# de treino. As da primeira lista nunca são fala real e sempre são removidas.
ALWAYS_HALLUCINATION = [
    "legendas pela comunidade amara.org",
    "legenda adriana zanotto",
    "legendado por",
    "subtitles by the amara.org community",
    "transcrição e legendas",
]
# Estas podem ser ditas de verdade: só removemos se o trecho tiver baixa confiança
# ou alta probabilidade de "não-fala".
SUSPECT_HALLUCINATION = [
    "obrigado por assistir",
    "obrigada por assistir",
    "obrigado por assistirem",
    "inscreva-se no canal",
    "se inscreva no canal",
    "ative o sininho",
    "thanks for watching",
    "thank you for watching",
    "tchau, tchau",
]


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^\w.\s-]", "", text).strip(" .!?-")


_ALWAYS = [_norm(p) for p in ALWAYS_HALLUCINATION]
_SUSPECT = [_norm(p) for p in SUSPECT_HALLUCINATION]


def is_hallucination(seg: Segment) -> bool:
    text = _norm(seg.text)
    if not text:
        return True
    if any(p in text for p in _ALWAYS):
        return True
    if any(text == p or text.startswith(p) for p in _SUSPECT):
        return seg.no_speech_prob > 0.3 or seg.confidence < 0.6
    return False


_REPEAT_RE = re.compile(r"(\b.{2,60}?)(?:[\s,.]+\1){3,}", re.IGNORECASE)


def collapse_repetitions(text: str) -> str:
    """'eu acho eu acho eu acho eu acho' -> 'eu acho' (loop típico de decodificação)."""
    return _REPEAT_RE.sub(r"\1", text)


def _align_words(words: List[Word], text: str) -> List[Word]:
    """Mantém, em ordem, só as palavras que sobraram no texto (descarta as repetidas)."""
    tokens = [_norm(t) for t in text.split()]
    kept, j = [], 0
    for w in words:
        if j < len(tokens) and _norm(w.text) == tokens[j]:
            kept.append(w)
            j += 1
    return kept


def remove_hallucinations(segments: List[Segment]) -> List[Segment]:
    cleaned: List[Segment] = []
    repeat_run = 0
    for seg in segments:
        if is_hallucination(seg):
            continue
        new_text = collapse_repetitions(seg.text)
        if new_text != seg.text:
            seg.text = new_text
            seg.words = _align_words(seg.words, new_text)
        if cleaned and _norm(cleaned[-1].text) == _norm(seg.text):
            repeat_run += 1
            if repeat_run >= 2:  # 3ª cópia idêntica seguida = loop, descarta
                continue
        else:
            repeat_run = 0
        cleaned.append(seg)
    return cleaned


def _replacement_pattern(wrong: str) -> re.Pattern:
    return re.compile(r"(?<!\w)" + re.escape(wrong) + r"(?!\w)", re.IGNORECASE)


def apply_replacements(segments: List[Segment], replacements: Dict[str, str]) -> List[Segment]:
    """Aplica correções do glossário ('leed talk' => 'LeadTalkAI') no texto e nas palavras."""
    if not replacements:
        return segments
    # termos mais longos primeiro, para 'evolution api' vencer 'api'
    rules = sorted(replacements.items(), key=lambda kv: -len(kv[0]))
    compiled = [(_replacement_pattern(w), r, len(w.split())) for w, r in rules]
    for seg in segments:
        for pattern, right, _ in compiled:
            seg.text = pattern.sub(right, seg.text)
        _replace_in_words(seg, compiled)
    return segments


def _replace_in_words(seg: Segment, compiled) -> None:
    """Correções de várias palavras fundem os Word correspondentes em um só."""
    for pattern, right, n in compiled:
        i = 0
        words = seg.words
        while i <= len(words) - n:
            window = words[i:i + n]
            joined = " ".join(w.text.strip() for w in window)
            stripped = joined.strip(".,!?;:")
            if pattern.fullmatch(stripped):
                trailing = joined[len(stripped):] if joined.startswith(stripped) else ""
                lead = " " if window[0].text.startswith(" ") else ""
                merged = Word(
                    start=window[0].start,
                    end=window[-1].end,
                    text=f"{lead}{right}{trailing}",
                    probability=min(w.probability for w in window),
                    speaker=window[0].speaker,
                )
                words[i:i + n] = [merged]
            i += 1


def postprocess(segments: List[Segment], replacements: Dict[str, str] | None = None) -> List[Segment]:
    segments = remove_hallucinations(segments)
    segments = apply_replacements(segments, replacements or {})
    return [s for s in segments if s.text.strip()]
