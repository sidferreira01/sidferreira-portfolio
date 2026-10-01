import pytest

from ditvvos.textproc import (
    TextOptions, apply_backtrack, apply_commands, apply_scratch, apply_style, is_cancel,
    match_snippet, process, remove_fillers,
)


@pytest.mark.parametrize("raw,expected", [
    ("Hum, eu acho que funciona.", "Eu acho que funciona."),
    ("Então, hã, vamos testar.", "Então, vamos testar."),
    ("Ééé, preciso de ajuda.", "Preciso de ajuda."),
    ("Ah, entendi agora.", "Entendi agora."),
    ("Um, a reunião mudou.", "A reunião mudou."),          # "hum" que o Whisper escreve "Um,"
    ("Um cliente ligou, um fornecedor também.", "Um cliente ligou, um fornecedor também."),
    ("o o código está quebrado", "O código está quebrado"),
    ("eu eu acho que sim", "Eu acho que sim"),
    # não pode estragar palavras reais
    ("É importante revisar um arquivo.", "É importante revisar um arquivo."),
    ("Muito muito bom.", "Muito muito bom."),
    ("A humanidade e o humor.", "A humanidade e o humor."),
])
def test_remove_fillers(raw, expected):
    assert remove_fillers(raw) == expected


def test_apaga_isso_mantem_so_o_final():
    assert apply_scratch("Marque às 3. Apaga isso. Marque às 4 da tarde.") == "Marque às 4 da tarde."
    assert apply_scratch("Texto normal sem comando.") == "Texto normal sem comando."


def test_cancelar():
    assert is_cancel("Isso aqui ficou errado, cancela isso.")
    assert is_cancel("Descartar")
    assert not is_cancel("Precisamos cancelar a assinatura do serviço.")


@pytest.mark.parametrize("raw,expected", [
    ("A reunião é às 2, digo, 3 horas.", "A reunião é às 3 horas."),
    ("Custa 50 reais, ou melhor, 60 reais.", "Custa 60 reais."),
    ("Rode com 4 threads, quer dizer, 8.", "Rode com 8 threads."),
    ("Eu digo que 3 é pouco.", "Eu digo que 3 é pouco."),
    ("Vai ser às 2, quer dizer, às 3 da tarde.", "Vai ser às 3 da tarde."),
    ("Vai ser às duas, quer dizer, às três da tarde.", "Vai ser às três da tarde."),
    ("Compre dois, ou melhor, cinco cafés.", "Compre cinco cafés."),
    ("Ela disse que um dia vai voltar.", "Ela disse que um dia vai voltar."),
])
def test_backtrack(raw, expected):
    assert apply_backtrack(raw) == expected


def test_comandos_de_formatacao():
    assert apply_commands("Oi, Claude. Nova linha. Rode os testes.") == "Oi, Claude.\nRode os testes."
    assert apply_commands("Primeiro ponto, novo parágrafo, segundo ponto") == "Primeiro ponto\n\nSegundo ponto"
    assert apply_commands("Tarefas: novo item revisar código novo item publicar") == \
        "Tarefas:\n- Revisar código\n- Publicar"
    assert apply_commands("Ele disse abre aspas funciona fecha aspas ontem") == 'Ele disse "funciona" ontem'
    assert apply_commands("Use o Docker abre parênteses versão 24 fecha parênteses agora") == \
        "Use o Docker (versão 24) agora"


def test_estilos():
    assert apply_style("Chego em 10 minutos.", "casual") == "Chego em 10 minutos"
    assert apply_style("Chego logo. Pode ir.", "casual") == "Chego logo. Pode ir."
    assert apply_style("prezado cliente, segue o relatório", "formal") == "Prezado cliente, segue o relatório."
    assert apply_style("Abra o arquivo engine.py.", "codigo") == "Abra o arquivo engine.py"
    assert apply_style("Rode os testes.", "codigo") == "Rode os testes."


def test_atalho_fala_inteira():
    snippets = {"minha assinatura": "Atenciosamente,\nSid Ferreira"}
    assert match_snippet("Minha assinatura.", snippets) == "Atenciosamente,\nSid Ferreira"
    assert match_snippet("Coloque minha assinatura no fim", snippets) is None


def test_pipeline_completo():
    opts = TextOptions(replacements={"leed talk": "LeadTalkAI"}, style="casual",
                       snippets={"meu email": "contato@sidferreira.com.br"})
    r = process("Hum, o leed talk sobe às 2, digo, 3 horas.", opts)
    assert r.text == "O LeadTalkAI sobe às 3 horas"
    assert r.steps == ["hesitações", "autocorreção", "dicionário", "estilo"]
    assert process("Meu e-mail.", opts).text == "Meu e-mail"  # não é o gatilho exato
    assert process("Meu email.", opts).snippet
    assert process("Esquece, cancela isso.", opts).cancelled
