"""Mede WER (taxa de erro de palavras) no FLEURS pt-BR, o mesmo conjunto usado
nos rankings públicos (Open ASR Leaderboard, artigos da NVIDIA/OpenAI).

Compara o Whisper "puro" (configuração padrão, como a maioria das ferramentas
pagas usa) com o pipeline completo do Transcritor AI.

    # baixar: huggingface.co/datasets/google/fleurs -> data/pt_br/test.tsv + audio/test.tar.gz
    python bench/fleurs_wer.py --tsv test.tsv --audio fleurs/test -n 100 --modelo large-v3-turbo
    python bench/fleurs_wer.py ... --longo 60   # também testa um áudio longo (60 frases emendadas)
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import jiwer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from transcritor.audio import find_ffmpeg  # noqa: E402
from transcritor.config import get_preset  # noqa: E402
from transcritor.engine import Transcriber, load_model  # noqa: E402


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text.lower())
    text = re.sub(r"[^\w\s%]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_refs(tsv: Path, audio_dir: Path, n: int, seed: int):
    rows = []
    seen = set()
    with tsv.open(encoding="utf-8") as fh:
        for row in csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
            path = audio_dir / row[1]
            if row[0] in seen or not path.exists():  # uma gravação por frase
                continue
            seen.add(row[0])
            rows.append((path, row[2]))
    random.Random(seed).shuffle(rows)
    return rows[:n]


def run_plain(model_name: str, files):
    model = load_model(model_name)
    out = []
    for f in files:
        segs, _ = model.transcribe(str(f), language="pt", beam_size=5)
        out.append(" ".join(s.text for s in segs))
    return out


def run_pipeline(model_name: str, files, revision: bool):
    opts = get_preset("equilibrado").with_overrides(model=model_name, revision_pass=revision)
    tr = Transcriber(opts)
    return [tr.transcribe(f).text for f in files]


def concat(files, dest: Path, gap: float = 1.5) -> Path:
    """Emenda os áudios com silêncio entre eles (simula áudio longo com pausas)."""
    lst = dest.with_suffix(".txt")
    silence = dest.with_name("silence.wav")
    ff = find_ffmpeg()
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=16000:cl=mono", "-t", str(gap), silence], check=True)
    lines = []
    for f in files:
        lines += [f"file '{f.resolve()}'", f"file '{silence.resolve()}'"]
    lst.write_text("\n".join(lines))
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-ar", "16000", "-ac", "1", dest], check=True)
    return dest


def report(name: str, refs, hyps, seconds: float, audio_seconds: float):
    wer = jiwer.wer([normalize(r) for r in refs], [normalize(h) for h in hyps])
    print(f"{name:<34} WER {wer:6.2%}   tempo {seconds:6.0f}s   "
          f"{audio_seconds / seconds:5.1f}x tempo real")
    return wer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tsv", type=Path, required=True)
    ap.add_argument("--audio", type=Path, required=True)
    ap.add_argument("-n", type=int, default=50)
    ap.add_argument("--modelo", default="large-v3-turbo")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--longo", type=int, default=0, help="Nº de frases para o teste de áudio longo")
    args = ap.parse_args()

    data = load_refs(args.tsv, args.audio, args.n, args.seed)
    files, refs = [d[0] for d in data], [d[1] for d in data]
    from faster_whisper import decode_audio
    audio_s = sum(len(decode_audio(str(f))) / 16000 for f in files)
    print(f"{len(files)} frases, {audio_s / 60:.1f} min de áudio, modelo {args.modelo}\n")

    load_model(args.modelo)  # não conta o tempo de carregamento
    t = time.perf_counter(); hyps = run_plain(args.modelo, files)
    report("Whisper puro (padrão de mercado)", refs, hyps, time.perf_counter() - t, audio_s)
    t = time.perf_counter(); hyps = run_pipeline(args.modelo, files, revision=False)
    report("Transcritor AI sem revisão", refs, hyps, time.perf_counter() - t, audio_s)
    t = time.perf_counter(); hyps = run_pipeline(args.modelo, files, revision=True)
    report("Transcritor AI completo", refs, hyps, time.perf_counter() - t, audio_s)

    if args.longo:
        long_data = load_refs(args.tsv, args.audio, args.longo, args.seed + 1)
        long_file = concat([d[0] for d in long_data], Path("/tmp/fleurs_longo.wav"))
        ref = " ".join(d[1] for d in long_data)
        dur = len(decode_audio(str(long_file))) / 16000
        print(f"\nÁudio longo: {dur / 60:.1f} min")
        t = time.perf_counter(); hyp = run_plain(args.modelo, [long_file])
        report("Whisper puro (longo)", [ref], hyp, time.perf_counter() - t, dur)
        t = time.perf_counter(); hyp = run_pipeline(args.modelo, [long_file], revision=True)
        report("Transcritor AI completo (longo)", [ref], hyp, time.perf_counter() - t, dur)


if __name__ == "__main__":
    main()
