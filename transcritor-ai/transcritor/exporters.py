"""Exportação: txt, srt, vtt, json e md (com marcação de palavras incertas)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Callable, Dict, List

from .models import Segment, Transcript, Word

MAX_LINE_CHARS = 42      # padrão de legendagem (Netflix/BBC usam 42)
MAX_CAPTION_LINES = 2
MAX_CAPTION_SECONDS = 6.0
LOW_CONFIDENCE = 0.5


def fmt_ts(seconds: float, sep: str = ",") -> str:
    ms = int(round(max(seconds, 0.0) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def fmt_clock(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _wrap(text: str, width: int = MAX_LINE_CHARS) -> str:
    """Quebra em até 2 linhas equilibradas."""
    if len(text) <= width:
        return text
    words = text.split()
    best, best_diff = None, None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        diff = abs(len(a) - len(b))
        if len(a) <= width and len(b) <= width and (best_diff is None or diff < best_diff):
            best, best_diff = f"{a}\n{b}", diff
    return best or text


def _sentences(words: List[Word]) -> List[List[Word]]:
    groups: List[List[Word]] = [[]]
    for w in words:
        groups[-1].append(w)
        if w.text.strip().endswith((".", "?", "!")):
            groups.append([])
    return [g for g in groups if g]


def _balanced_chunks(words: List[Word], n: int) -> List[List[Word]]:
    """Divide em n partes de tamanho parecido (evita legenda com 1 palavra órfã)."""
    total = sum(len(w.text) for w in words)
    chunks: List[List[Word]] = [[]]
    acc = 0.0
    for w in words:
        if acc >= total * len(chunks) / n and len(chunks) < n and chunks[-1]:
            chunks.append([])
        chunks[-1].append(w)
        acc += len(w.text)
    return chunks


def captions(transcript: Transcript) -> List[Segment]:
    """Re-segmenta em legendas legíveis: frase a frase, e frases longas são divididas
    em partes equilibradas que respeitam o limite de caracteres e de duração."""
    limit = MAX_LINE_CHARS * MAX_CAPTION_LINES
    out: List[Segment] = []
    for seg in transcript.segments:
        if not seg.words:
            out.append(seg)
            continue
        for sentence in _sentences(seg.words):
            chars = len("".join(w.text for w in sentence).strip())
            secs = sentence[-1].end - sentence[0].start
            n = max(math.ceil(chars / (limit * 0.9)), math.ceil(secs / MAX_CAPTION_SECONDS), 1)
            n = min(n, len(sentence))
            for chunk in _balanced_chunks(sentence, n):
                out.append(_caption_from(chunk, seg.speaker))
    return out


def _caption_from(words: List[Word], speaker) -> Segment:
    return Segment(start=words[0].start, end=words[-1].end,
                   text="".join(w.text for w in words).strip(), words=words, speaker=speaker)


def _speaker_prefix(seg: Segment) -> str:
    return f"[{seg.speaker}] " if seg.speaker else ""


def to_srt(t: Transcript) -> str:
    blocks = []
    for i, c in enumerate(captions(t), 1):
        text = _wrap(_speaker_prefix(c) + c.text)
        blocks.append(f"{i}\n{fmt_ts(c.start)} --> {fmt_ts(c.end)}\n{text}\n")
    return "\n".join(blocks)


def to_vtt(t: Transcript) -> str:
    lines = ["WEBVTT", ""]
    for c in captions(t):
        text = _wrap(c.text)
        if c.speaker:
            text = f"<v {c.speaker}>{text}"
        lines += [f"{fmt_ts(c.start, '.')} --> {fmt_ts(c.end, '.')}", text, ""]
    return "\n".join(lines)


def _paragraphs(t: Transcript) -> List[tuple]:
    """Agrupa segmentos em parágrafos: por falante, ou por pausas > 2s."""
    paras: List[list] = []
    for seg in t.segments:
        if not paras:
            paras.append([seg])
            continue
        prev = paras[-1][-1]
        new_speaker = seg.speaker != prev.speaker
        long_pause = seg.start - prev.end > 2.0
        too_big = sum(len(s.text) for s in paras[-1]) > 900
        if new_speaker or long_pause or too_big:
            paras.append([seg])
        else:
            paras[-1].append(seg)
    return [(p[0].start, p[0].speaker, p) for p in paras]


def to_txt(t: Transcript, timestamps: bool = False) -> str:
    out = []
    for start, speaker, segs in _paragraphs(t):
        text = " ".join(s.text.strip() for s in segs)
        head = ""
        if timestamps:
            head += f"[{fmt_clock(start)}] "
        if speaker:
            head += f"{speaker}: "
        out.append(head + text)
    return "\n\n".join(out) + "\n"


def _md_words(segs: List[Segment]) -> str:
    parts = []
    for s in segs:
        if not s.words:
            parts.append(" " + s.text)
            continue
        for w in s.words:
            txt = w.text
            if w.probability < LOW_CONFIDENCE and txt.strip():
                lead = " " if txt.startswith(" ") else ""
                txt = f"{lead}=={txt.strip()}=="
            parts.append(txt)
    return "".join(parts).strip()


def to_md(t: Transcript) -> str:
    low = sum(1 for s in t.segments for w in s.words if w.probability < LOW_CONFIDENCE)
    total = sum(len(s.words) for s in t.segments) or 1
    lines = [
        "# Transcrição",
        "",
        f"- **Duração:** {fmt_clock(t.duration)}",
        f"- **Idioma:** {t.language} ({t.language_probability:.0%})",
        f"- **Modelo:** {t.model}",
        f"- **Processamento:** {t.processing_seconds:.1f}s ({t.realtime_factor:.1f}x tempo real)",
        f"- **Palavras incertas:** {low} de {total} ({low / total:.1%}) — marcadas como ==assim==",
    ]
    if t.speakers:
        lines.append(f"- **Falantes:** {', '.join(t.speakers)}")
    lines.append("")
    for start, speaker, segs in _paragraphs(t):
        head = f"**[{fmt_clock(start)}]"
        head += f" {speaker}:**" if speaker else "**"
        lines += [f"{head} {_md_words(segs)}", ""]
    return "\n".join(lines)


def to_json(t: Transcript) -> str:
    return json.dumps(t.to_dict(), ensure_ascii=False, indent=2)


EXPORTERS: Dict[str, Callable[[Transcript], str]] = {
    "txt": to_txt,
    "srt": to_srt,
    "vtt": to_vtt,
    "json": to_json,
    "md": to_md,
}


def export(t: Transcript, fmt: str) -> str:
    try:
        return EXPORTERS[fmt](t)
    except KeyError:
        raise ValueError(f"Formato desconhecido '{fmt}'. Opções: {', '.join(EXPORTERS)}") from None


def write_all(t: Transcript, base: Path, formats: List[str]) -> List[Path]:
    written = []
    for fmt in formats:
        path = base.with_suffix(f".{fmt}")
        path.write_text(export(t, fmt), encoding="utf-8")
        written.append(path)
    return written
