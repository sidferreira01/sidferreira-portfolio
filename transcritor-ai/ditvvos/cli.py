"""Linha de comando do DitvvOS.

    python -m ditvvos                       # inicia (segure Ctrl direito para falar)
    python -m ditvvos dicionario adicionar "Evolution API"
    python -m ditvvos dicionario corrigir "super base" "Supabase"
    python -m ditvvos atalhos adicionar "minha assinatura" "Atenciosamente,\\nSid Ferreira"
    python -m ditvvos estilos definir whatsapp casual
    python -m ditvvos historico --estatisticas
    python -m ditvvos inicializacao ativar
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from typing import List, Optional

from . import __version__
from .config import Config, home
from .textproc import STYLES


def _save(cfg: Config, msg: str) -> int:
    cfg.save()
    print(msg)
    return 0


def cmd_start(args) -> int:
    from .app import DitvvOS, listen
    from .devices import FileRecorder, Keyboard

    cfg = Config.load()
    for field, value in (("hotkey", args.tecla), ("model", args.modelo), ("output", args.saida)):
        if value:
            setattr(cfg, field, value)
    if args.enviar:
        cfg.submit = True
    if args.sem_som:
        cfg.sounds = False

    overlay = None
    use_overlay = cfg.overlay and not args.sem_overlay
    recorder = FileRecorder(args.audio_teste) if args.audio_teste else None

    def show(r):
        if r.cancelled:
            return
        extras = f" [{', '.join(r.steps)}]" if r.steps else ""
        where = f" → {r.app} ({r.style})" if r.app else ""
        print(f"✓ {r.audio_seconds:.1f}s de fala, {r.latency_seconds:.1f}s{where}{extras}\n  {r.text}",
              file=sys.stderr, flush=True)

    print(f"DitvvOS {__version__} · carregando {cfg.model}…", file=sys.stderr, flush=True)
    if use_overlay:
        try:
            from .overlay import Overlay

            overlay = Overlay()
        except Exception as exc:  # sem interface gráfica: segue sem indicador
            print(f"· indicador visual indisponível ({exc})", file=sys.stderr)
    app = DitvvOS(cfg, keyboard=Keyboard(cfg.output), recorder=recorder, overlay=overlay, on_result=show)
    if overlay is not None:
        overlay.level = lambda: app.recorder.level
    app.warm_up()
    listener = listen(app, cfg.hotkey)
    if app.llm and not app.llm.available():
        print(f"· IA local (Ollama) não respondeu em {cfg.llm.url} — Modo Comando indisponível",
              file=sys.stderr)
    print(f"Pronto! Segure [{cfg.hotkey}] para falar · toque rápido = mãos-livres · "
          f"Shift+[{cfg.hotkey}] = Modo Comando · Ctrl+C aqui para sair.", file=sys.stderr, flush=True)
    try:
        if overlay is not None:
            overlay.run()
        else:
            while listener.is_alive():
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()
        app.close()
    return 0


def cmd_config(args) -> int:
    cfg = Config.load()
    if args.acao == "definir":
        if not args.chave or args.valor is None:
            print("Uso: config definir <chave> <valor>  (ex.: config definir submit true)")
            return 1
        target, key = (cfg.llm, args.chave[4:]) if args.chave.startswith("llm.") else (cfg, args.chave)
        if key == "llm" or key not in type(target).__dataclass_fields__:
            print(f"Chave desconhecida: {args.chave}")
            return 1
        setattr(target, key, _parse_value(args.valor))
        return _save(cfg, f"{args.chave} = {args.valor}")
    print(f"# {home() / 'config.json'}")
    print((home() / "config.json").read_text(encoding="utf-8"))
    return 0


def _parse_value(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def cmd_dictionary(args) -> int:
    cfg = Config.load()
    if args.acao == "adicionar":
        if args.termo not in cfg.vocabulary:
            cfg.vocabulary.append(args.termo)
        return _save(cfg, f"+ {args.termo}")
    if args.acao == "corrigir":
        cfg.replacements[args.errado] = args.certo
        return _save(cfg, f"{args.errado} => {args.certo}")
    if args.acao == "remover":
        cfg.vocabulary = [t for t in cfg.vocabulary if t != args.termo]
        cfg.replacements.pop(args.termo, None)
        return _save(cfg, f"- {args.termo}")
    if args.acao == "importar":
        from transcritor.config import load_glossary

        vocab, repl = load_glossary(args.arquivo)
        cfg.vocabulary = list(dict.fromkeys(cfg.vocabulary + vocab))
        cfg.replacements.update(repl)
        return _save(cfg, f"Importados {len(vocab)} termos e {len(repl)} correções")
    print("Vocabulário:", ", ".join(cfg.vocabulary) or "(vazio)")
    for wrong, right in cfg.replacements.items():
        print(f"  {wrong} => {right}")
    return 0


def cmd_snippets(args) -> int:
    cfg = Config.load()
    if args.acao == "adicionar":
        cfg.snippets[args.gatilho] = args.texto.replace("\\n", "\n")
        return _save(cfg, f"Diga \"{args.gatilho}\" para inserir o texto.")
    if args.acao == "remover":
        cfg.snippets.pop(args.gatilho, None)
        return _save(cfg, f"- {args.gatilho}")
    for trigger, text in cfg.snippets.items():
        print(f"\"{trigger}\" -> {text!r}")
    if not cfg.snippets:
        print("(nenhum atalho)")
    return 0


def cmd_styles(args) -> int:
    cfg = Config.load()
    if args.acao == "definir":
        cfg.app_styles[args.app.lower()] = args.estilo
        return _save(cfg, f"{args.app} -> {args.estilo}")
    if args.acao == "padrao":
        cfg.default_style = args.estilo
        return _save(cfg, f"estilo padrão -> {args.estilo}")
    print(f"Padrão: {cfg.default_style} (estilos por app {'ligados' if cfg.app_styles_enabled else 'desligados'})")
    for app, style in sorted(cfg.app_styles.items()):
        print(f"  {app:<16} {style}")
    return 0


def cmd_history(args) -> int:
    from .history import History

    hist = History(home() / "historico.db")
    if args.limpar:
        hist.clear()
        print("Histórico apagado.")
        return 0
    if args.estatisticas:
        for key, value in hist.stats().items():
            print(f"{key.replace('_', ' '):<22} {value}")
        return 0
    if args.copiar_ultimo:
        last = hist.last()
        if not last:
            print("Histórico vazio.")
            return 1
        import pyperclip

        pyperclip.copy(last.final)
        print("Copiado:", last.final)
        return 0
    for e in reversed(hist.recent(args.n, args.buscar)):
        when = time.strftime("%d/%m %H:%M", time.localtime(e.ts))
        print(f"[{when}] {e.app or '-'} · {e.mode}\n  {e.final}")
    return 0


def cmd_microphones(args) -> int:
    from .devices import list_microphones

    print(list_microphones())
    return 0


def cmd_autostart(args) -> int:
    from . import autostart

    if args.acao == "ativar":
        print("Ativado:", autostart.enable())
    else:
        path = autostart.disable()
        print("Desativado:" if path else "Já estava desativado.", path or "")
    return 0


def cmd_ai(args) -> int:
    from .llm import LLMError, Ollama

    cfg = Config.load()
    llm = Ollama(cfg.llm)
    if not llm.available():
        print(f"Ollama não encontrado em {cfg.llm.url}. Instale em https://ollama.com e rode: "
              f"ollama pull {cfg.llm.model}")
        return 1
    try:
        print("Teste:", llm.polish("hum então a reunião é às duas, quer dizer, às três tá", "normal"))
    except LLMError as exc:
        print("Falhou:", exc)
        return 1
    if not cfg.llm.enabled:
        cfg.llm.enabled = True
        cfg.save()
        print("IA local ativada (Modo Comando disponível). Polimento automático: "
              "python -m ditvvos config definir llm.polish true")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ditvvos", description="DitvvOS — ditado por voz local e preciso.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("iniciar", help="Inicia o ditado (padrão)")
    s.add_argument("--tecla", help="Atalho (padrão ctrl_r). Ex.: alt_r, f8, f9, scroll_lock")
    s.add_argument("--modelo", help="large-v3-turbo (padrão), large-v3, small…")
    s.add_argument("--saida", choices=["colar", "digitar", "copiar"])
    s.add_argument("--enviar", action="store_true", help="Aperta Enter após inserir")
    s.add_argument("--sem-overlay", action="store_true", help="Sem indicador visual")
    s.add_argument("--sem-som", action="store_true")
    s.add_argument("--audio-teste", help=argparse.SUPPRESS)  # usa arquivo no lugar do microfone
    s.set_defaults(func=cmd_start)

    c = sub.add_parser("config", help="Mostra ou altera a configuração")
    c.add_argument("acao", nargs="?", choices=["mostrar", "definir"], default="mostrar")
    c.add_argument("chave", nargs="?")
    c.add_argument("valor", nargs="?")
    c.set_defaults(func=cmd_config)

    d = sub.add_parser("dicionario", help="Dicionário pessoal (nomes, marcas, jargões)")
    dsub = d.add_subparsers(dest="acao")
    dsub.add_parser("listar")
    a = dsub.add_parser("adicionar"); a.add_argument("termo")
    a = dsub.add_parser("corrigir"); a.add_argument("errado"); a.add_argument("certo")
    a = dsub.add_parser("remover"); a.add_argument("termo")
    a = dsub.add_parser("importar"); a.add_argument("arquivo")
    d.set_defaults(func=cmd_dictionary)

    t = sub.add_parser("atalhos", help="Atalhos de texto falados (snippets)")
    tsub = t.add_subparsers(dest="acao")
    tsub.add_parser("listar")
    a = tsub.add_parser("adicionar"); a.add_argument("gatilho"); a.add_argument("texto")
    a = tsub.add_parser("remover"); a.add_argument("gatilho")
    t.set_defaults(func=cmd_snippets)

    e = sub.add_parser("estilos", help="Estilo de escrita por aplicativo")
    esub = e.add_subparsers(dest="acao")
    esub.add_parser("listar")
    a = esub.add_parser("definir"); a.add_argument("app"); a.add_argument("estilo", choices=STYLES)
    a = esub.add_parser("padrao"); a.add_argument("estilo", choices=STYLES)
    e.set_defaults(func=cmd_styles)

    h = sub.add_parser("historico", help="Histórico e estatísticas")
    h.add_argument("-n", type=int, default=20)
    h.add_argument("--buscar")
    h.add_argument("--estatisticas", action="store_true")
    h.add_argument("--copiar-ultimo", action="store_true")
    h.add_argument("--limpar", action="store_true")
    h.set_defaults(func=cmd_history)

    m = sub.add_parser("microfones", help="Lista os microfones")
    m.set_defaults(func=cmd_microphones)

    i = sub.add_parser("inicializacao", help="Iniciar junto com o sistema")
    i.add_argument("acao", choices=["ativar", "desativar"])
    i.set_defaults(func=cmd_autostart)

    ia = sub.add_parser("ia", help="Testa e ativa a IA local (Ollama)")
    ia.set_defaults(func=cmd_ai)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # sem subcomando (ou só com opções do "iniciar") -> iniciar
    if not argv or (argv[0].startswith("-") and argv[0] not in ("-h", "--help", "--version", "-v", "--verbose")):
        argv = ["iniciar"] + argv
    elif argv[0] in ("-v", "--verbose") and (len(argv) == 1 or argv[1].startswith("-")):
        argv = [argv[0], "iniciar"] + argv[1:]
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(message)s")
    if getattr(args, "acao", "x") is None:
        args.acao = "listar"
    return args.func(args)
