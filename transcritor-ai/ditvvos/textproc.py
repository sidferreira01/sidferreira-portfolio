"""Pós-processamento do texto ditado (puro, sem hardware — tudo testável).

Ordem: cancelar? -> "apaga isso" -> atalhos de texto -> hesitações -> gaguejos ->
autocorreção de números -> dicionário -> comandos de formatação -> estilo do app.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


# ---------------------------------------------------------------- cancelar / apagar
CANCEL_PHRASES = ["cancela isso", "cancelar ditado", "cancela o ditado", "descarta isso", "descartar"]
SCRATCH_RE = re.compile(
    r"[\s,.;:!?-]*\b(?:apaga isso|apague isso|apaga tudo|esquece isso|esqueça isso)\b[\s,.;:!?-]*",
    re.IGNORECASE,
)


def is_cancel(text: str) -> bool:
    """A fala termina com um comando de descarte ('... cancela isso')."""
    n = _norm(text)
    return any(n == p or n.endswith(" " + p) for p in CANCEL_PHRASES)


def apply_scratch(text: str) -> str:
    """'mande às 3, apaga isso, mande às 4' -> 'mande às 4'."""
    parts = SCRATCH_RE.split(text)
    return parts[-1].strip() if len(parts) > 1 else text


# ---------------------------------------------------------------- hesitações / gaguejos
FILLER_RE = re.compile(
    r"(?<![\w-])(?:h+u+m+|h+m+|hã+|ãh+|ahn+|é{2,}|e{3,}|u+h+m*|ah+(?=\s*,)|u+m+(?=\s*,))(?![\w-])[\s,.…]*",
    re.IGNORECASE,
)
STUTTER_RE = re.compile(r"\b(\w{1,3})(?:[\s,]+\1\b)+", re.IGNORECASE)


def remove_fillers(text: str) -> str:
    out = FILLER_RE.sub("", text)
    out = STUTTER_RE.sub(r"\1", out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    out = re.sub(r"^[,.\s]+", "", out)
    return _fix_sentence_starts(out)


def _fix_sentence_starts(text: str) -> str:
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return re.sub(r"([.!?]\s+)([a-zà-ú])", lambda m: m.group(1) + m.group(2).upper(), text)


# ---------------------------------------------------------------- autocorreção falada
_NUMBER_WORDS = (
    "uma|um|duas|dois|três|tres|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|"
    "quatorze|catorze|quinze|vinte|trinta|quarenta|cinquenta|cem|cento|duzentos|quinhentos|mil|"
    "meio-dia|meia-noite"
)
_NUM = r"(\d+(?:[:h,.]\d+)?|\b(?:" + _NUMBER_WORDS + r")\b)"
_UNIT = r"(\s*%|\s+(?!digo\b|quer\b|ou\b|aliás\b|não\b|na\b)[a-zà-ú]+)?"
BACKTRACK_RE = re.compile(
    _NUM + _UNIT + r"\s*[,.]?\s*(?:digo|quer dizer|ou melhor|aliás|não,? não|na verdade)\s*[,.]?\s*"
    + r"(?:(?:às|as|a|o|os|de|em|por|para|pra)\s+)?" + _NUM + _UNIT,
    re.IGNORECASE,
)


def apply_backtrack(text: str) -> str:
    """'às 2, digo, 3 horas' -> 'às 3 horas'; '4 threads, quer dizer, 8' -> '8 threads'."""
    def fix(m: re.Match) -> str:
        unit = m.group(4) or m.group(2) or ""
        return m.group(3) + unit

    return BACKTRACK_RE.sub(fix, text)


# ---------------------------------------------------------------- comandos de formatação
_P = r"[\s,.;:!?]*"
COMMANDS = [
    (re.compile(_P + r"\bnovo parágrafo\b" + _P, re.I), "\n\n"),
    (re.compile(_P + r"\bnova linha\b" + _P, re.I), "\n"),
    (re.compile(_P + r"\bnovo item\b" + _P, re.I), "\n- "),
    (re.compile(r"\s*\babre aspas\b[\s,]*", re.I), ' "'),
    (re.compile(r"[\s,]*\bfecha aspas\b", re.I), '"'),
    (re.compile(r"\s*\babre parênteses\b[\s,]*", re.I), " ("),
    (re.compile(r"[\s,]*\bfecha parênteses\b", re.I), ")"),
]


def apply_commands(text: str) -> str:
    # pontuação que o Whisper põe antes de "nova linha" pertence à frase anterior
    def keep_period(m: re.Match, repl: str) -> str:
        before = m.group(0).strip()
        end = before[:1] if before[:1] in ".!?:;" else ""
        return end + repl

    for pattern, repl in COMMANDS:
        if repl.startswith("\n"):
            text = pattern.sub(lambda m, r=repl: keep_period(m, r), text)
        else:
            text = pattern.sub(repl, text)
    lines = [_fix_sentence_starts(line.strip(" ")) if not line.startswith("- ") else
             "- " + _fix_sentence_starts(line[2:].strip()) for line in text.split("\n")]
    return "\n".join(lines).strip(" ")


# ---------------------------------------------------------------- dicionário e atalhos
def apply_dictionary(text: str, replacements: Dict[str, str]) -> str:
    for wrong, right in sorted(replacements.items(), key=lambda kv: -len(kv[0])):
        text = re.sub(r"(?<!\w)" + re.escape(wrong) + r"(?!\w)", right, text, flags=re.IGNORECASE)
    return text


def match_snippet(text: str, snippets: Dict[str, str]) -> Optional[str]:
    """A fala inteira é o gatilho de um atalho ('minha assinatura' -> bloco de texto)."""
    n = _norm(text)
    for trigger, expansion in snippets.items():
        if _norm(trigger) == n:
            return expansion
    return None


# ---------------------------------------------------------------- estilos
STYLES = ("normal", "casual", "formal", "codigo")


def apply_style(text: str, style: str) -> str:
    if style == "casual":
        # mensagens: sem ponto final numa frase única (como se digita no WhatsApp)
        if text.count(".") == 1 and text.endswith(".") and "\n" not in text:
            text = text[:-1]
    elif style == "formal":
        text = _fix_sentence_starts(text)
        if text and text[-1] not in ".!?:\"')":
            text += "."
    elif style == "codigo":
        # prompts/terminal: sem ponto final solto depois de nomes de arquivo, comandos etc.
        if re.search(r"[\w/]\.\w+\.$|`$", text):
            text = text[:-1]
    return text


@dataclass
class TextOptions:
    remove_fillers: bool = True
    backtrack: bool = True
    commands: bool = True
    style: str = "normal"
    replacements: Dict[str, str] = field(default_factory=dict)
    snippets: Dict[str, str] = field(default_factory=dict)


@dataclass
class Processed:
    text: str
    cancelled: bool = False
    snippet: bool = False
    steps: List[str] = field(default_factory=list)


def process(raw: str, opts: TextOptions) -> Processed:
    text = " ".join(raw.split())
    if not text:
        return Processed("")
    if is_cancel(text):
        return Processed("", cancelled=True, steps=["cancelado"])
    steps: List[str] = []
    scratched = apply_scratch(text)
    if scratched != text:
        steps.append("apaga isso")
        text = scratched
    snippet = match_snippet(text, opts.snippets)
    if snippet is not None:
        return Processed(snippet, snippet=True, steps=steps + ["atalho"])

    def step(name: str, fn, enabled: bool = True):
        nonlocal text
        if enabled:
            new = fn(text)
            if new != text:
                steps.append(name)
                text = new

    step("hesitações", remove_fillers, opts.remove_fillers)
    step("autocorreção", apply_backtrack, opts.backtrack)
    step("dicionário", lambda t: apply_dictionary(t, opts.replacements), bool(opts.replacements))
    step("comandos", apply_commands, opts.commands)
    step("estilo", lambda t: apply_style(t, opts.style), opts.style != "normal")
    return Processed(text.strip(), steps=steps)
