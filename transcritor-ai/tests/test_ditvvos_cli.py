import json

from ditvvos.cli import main


def test_cli_dicionario_atalhos_estilos_config(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DITVVOS_HOME", str(tmp_path))
    assert main(["dicionario", "adicionar", "Evolution API"]) == 0
    assert main(["dicionario", "corrigir", "super base", "Supabase"]) == 0
    assert main(["atalhos", "adicionar", "minha assinatura", "Abraços,\\nSid"]) == 0
    assert main(["estilos", "definir", "Slack", "formal"]) == 0
    assert main(["config", "definir", "submit", "true"]) == 0
    assert main(["config", "definir", "llm.model", "llama3.2"]) == 0
    assert main(["config", "definir", "inexistente", "1"]) == 1
    cfg = json.loads((tmp_path / "config.json").read_text())
    assert "Supabase" in cfg["replacements"].values() and "Evolution API" in cfg["vocabulary"]
    assert cfg["snippets"]["minha assinatura"] == "Abraços,\nSid"
    assert cfg["app_styles"]["slack"] == "formal" and cfg["submit"] is True
    assert cfg["llm"]["model"] == "llama3.2"
    capsys.readouterr()
    assert main(["dicionario"]) == 0
    assert "super base => Supabase" in capsys.readouterr().out


def test_cli_historico_vazio(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DITVVOS_HOME", str(tmp_path))
    assert main(["historico", "--estatisticas"]) == 0
    assert "palavras" in capsys.readouterr().out
