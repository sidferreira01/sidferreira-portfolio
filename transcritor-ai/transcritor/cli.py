"""Linha de comando.

    python -m transcritor transcrever reuniao.mp3 audios/ -f txt srt md --falantes 2
    python -m transcritor servidor --porta 8000
    python -m transcritor ditado --tecla ctrl_r --enviar
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Iterable, List

from . import __version__
from .config import PRESETS, get_preset, load_glossary
from .exporters import EXPORTERS, write_all

MEDIA_EXT = {
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".flac", ".wma", ".amr",
    ".webm", ".mp4", ".mkv", ".mov", ".avi", ".3gp",
}


def iter_inputs(paths: Iterable[str]) -> List[Path]:
    files: List[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.suffix.lower() in MEDIA_EXT)
        elif p.exists():
            files.append(p)
        else:
            print(f"! ignorado (não existe): {p}", file=sys.stderr)
    return files


def _progress_printer(name: str):
    last = {"stage": None, "pct": -1}

    def report(stage: str, frac: float) -> None:
        pct = int(frac * 100)
        if stage != last["stage"] or pct >= last["pct"] + 5:
            last.update(stage=stage, pct=pct)
            print(f"\r  {name}: {stage} {pct:3d}%   ", end="", file=sys.stderr, flush=True)

    return report


def cmd_transcribe(args: argparse.Namespace) -> int:
    from .engine import Transcriber

    opts = get_preset(args.preset)
    vocab, repl = [], {}
    if args.glossario:
        vocab, repl = load_glossary(args.glossario)
    vocab += args.termo or []
    opts = opts.with_overrides(
        model=args.modelo,
        language=None if args.idioma == "auto" else args.idioma,
        denoise=args.reduzir_ruido or None,
        revision_pass=False if args.sem_revisao else None,
        diarize=bool(args.falantes or args.diarizar) or None,
        num_speakers=args.falantes,
        context=args.contexto,
        vocabulary=vocab or None,
        replacements=repl or None,
    )
    files = iter_inputs(args.entradas)
    if not files:
        print("Nenhum arquivo de áudio/vídeo encontrado.", file=sys.stderr)
        return 1

    out_dir = Path(args.saida) if args.saida else None
    transcriber = Transcriber(opts)
    failures = 0
    for f in files:
        target_dir = out_dir or f.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        base = target_dir / f.stem
        if args.pular_existentes and base.with_suffix(f".{args.formatos[0]}").exists():
            print(f"= {f.name} (já transcrito)", file=sys.stderr)
            continue
        try:
            t = transcriber.transcribe(f, progress=_progress_printer(f.name))
        except Exception as exc:  # continua o lote mesmo se um arquivo falhar
            failures += 1
            print(f"\n✗ {f.name}: {exc}", file=sys.stderr)
            continue
        written = write_all(t, base, args.formatos)
        print(
            f"\n✓ {f.name}: {t.duration / 60:.1f} min em {t.processing_seconds:.0f}s "
            f"({t.realtime_factor:.1f}x) -> {', '.join(p.name for p in written)}",
            file=sys.stderr,
        )
        if args.imprimir:
            print(t.text)
    return 1 if failures else 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .server import create_app

    uvicorn.run(create_app(data_dir=args.dados), host=args.host, port=args.porta)
    return 0


def cmd_dictate(args: argparse.Namespace) -> int:
    from . import dictation

    if args.listar_microfones:
        print(dictation.list_microphones())
        return 0
    vocab, repl = [], {}
    if args.glossario:
        vocab, repl = load_glossary(args.glossario)
    vocab += args.termo or []
    opts = dictation.dictation_options(
        model=args.modelo,
        language=None if args.idioma == "auto" else args.idioma,
        vocabulary=vocab or None,
        replacements=repl or None,
    )
    output = dictation.Output(args.saida, submit=args.enviar)
    mode = "toggle" if args.modo == "alternar" else "hold"

    def show(r):
        print(f"✓ ({r.audio_seconds:.1f}s de fala, {r.latency_seconds:.1f}s) {r.text}",
              file=sys.stderr, flush=True)

    app = dictation.Dictation(
        opts, output, recorder=dictation.Recorder(args.microfone),
        sounds=not args.sem_som, on_result=show,
    )
    print(f"Carregando {opts.model}…", file=sys.stderr, flush=True)
    app.warm_up()
    how = "Segure" if mode == "hold" else "Toque 1x para gravar e 1x para enviar com"
    print(f"Pronto. {how} [{args.tecla}] para falar. Ctrl+C neste terminal para sair.",
          file=sys.stderr, flush=True)
    try:
        dictation.run(app, args.tecla, mode)
    except KeyboardInterrupt:
        pass
    finally:
        app.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="transcritor", description="Áudio -> texto de alta precisão, 100% local.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("transcrever", help="Transcreve arquivos ou pastas")
    t.add_argument("entradas", nargs="+", help="Arquivos de áudio/vídeo ou pastas")
    t.add_argument("-p", "--preset", choices=list(PRESETS), default="equilibrado")
    t.add_argument("-m", "--modelo", help="Sobrescreve o modelo (ex.: large-v3, large-v3-turbo, medium)")
    t.add_argument("-i", "--idioma", default="pt", help="Código do idioma ou 'auto' (padrão: pt)")
    t.add_argument("-f", "--formatos", nargs="+", choices=list(EXPORTERS), default=["txt", "srt"])
    t.add_argument("-o", "--saida", help="Pasta de saída (padrão: ao lado do arquivo)")
    t.add_argument("-g", "--glossario", help="Arquivo de glossário (termos e correções 'errado => certo')")
    t.add_argument("-t", "--termo", action="append", help="Termo extra do vocabulário (repetível)")
    t.add_argument("-c", "--contexto", help="Frase de contexto (ex.: 'Reunião de vendas da LeadTalkAI.')")
    t.add_argument("--falantes", type=int, help="Nº de falantes (ativa diarização)")
    t.add_argument("--diarizar", action="store_true", help="Identifica falantes (nº automático)")
    t.add_argument("--reduzir-ruido", action="store_true", help="Filtro de redução de ruído")
    t.add_argument("--sem-revisao", action="store_true", help="Desliga a 2ª passada de revisão")
    t.add_argument("--pular-existentes", action="store_true", help="Não refaz arquivos já transcritos")
    t.add_argument("--imprimir", action="store_true", help="Também imprime o texto no terminal")
    t.set_defaults(func=cmd_transcribe)

    d = sub.add_parser("ditado", help="Ditado por voz em qualquer janela (aperte e fale)")
    d.add_argument("--tecla", default="ctrl_r",
                   help="Atalho: ctrl_r (Ctrl direito, padrão), alt_r, f8, f9, scroll_lock…")
    d.add_argument("--modo", choices=["segurar", "alternar"], default="segurar")
    d.add_argument("--saida", choices=["colar", "digitar", "copiar"],
                   default="digitar" if sys.platform.startswith("linux") else "colar",
                   help="Como entregar o texto (padrão: colar; no Linux, digitar)")
    d.add_argument("--enviar", action="store_true", help="Aperta Enter depois de inserir o texto")
    d.add_argument("-m", "--modelo", help="Modelo (padrão large-v3-turbo; 'small' = mais rápido)")
    d.add_argument("-i", "--idioma", default="pt")
    d.add_argument("-g", "--glossario", help="Arquivo de glossário")
    d.add_argument("-t", "--termo", action="append", help="Termo extra do vocabulário (repetível)")
    d.add_argument("--microfone", type=int, help="Índice do microfone (veja --listar-microfones)")
    d.add_argument("--listar-microfones", action="store_true")
    d.add_argument("--sem-som", action="store_true", help="Desliga os bipes de início/fim")
    d.set_defaults(func=cmd_dictate)

    s = sub.add_parser("servidor", help="Sobe a interface web")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--porta", type=int, default=8000)
    s.add_argument("--dados", default="./dados", help="Pasta onde ficam uploads e resultados")
    s.set_defaults(func=cmd_serve)
    return p


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
