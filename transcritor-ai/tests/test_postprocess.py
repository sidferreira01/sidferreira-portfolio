from helpers import seg

from transcritor.config import parse_glossary
from transcritor.postprocess import apply_replacements, collapse_repetitions, postprocess


def test_remove_alucinacao_amara_sempre():
    out = postprocess([seg("Bom dia a todos."), seg("Legendas pela comunidade Amara.org", 3)])
    assert [s.text for s in out] == ["Bom dia a todos."]


def test_obrigado_por_assistir_real_eh_mantido():
    real = seg("Obrigado por assistir, até a próxima.", prob=0.95)
    fake = seg("Obrigado por assistir", 10, prob=0.3, no_speech=0.7)
    out = postprocess([real, fake])
    assert out == [real]


def test_colapsa_loop_de_repeticao():
    assert collapse_repetitions("eu acho eu acho eu acho eu acho eu acho que sim") == "eu acho que sim"
    assert collapse_repetitions("não, não, está certo") == "não, não, está certo"


def test_colapso_mantem_palavras_alinhadas():
    s = seg("eu acho eu acho eu acho eu acho que sim")
    out = postprocess([s])[0]
    assert out.text == "eu acho que sim"
    assert [w.text.strip() for w in out.words] == ["eu", "acho", "que", "sim"]
    assert out.words[2].start == 3.2  # timestamp real do "que", não do 3º "eu"


def test_descarta_terceira_copia_identica():
    segs = [seg("vamos lá", i) for i in range(4)]
    assert len(postprocess(segs)) == 2


def test_glossario_corrige_texto_e_funde_palavras():
    s = seg("o leed talk usa evolution api")
    apply_replacements([s], {"leed talk": "LeadTalkAI", "evolution api": "Evolution API"})
    assert s.text == "o LeadTalkAI usa Evolution API"
    assert [w.text.strip() for w in s.words] == ["o", "LeadTalkAI", "usa", "Evolution API"]
    assert s.words[1].start == 0.4 and s.words[1].end == 1.2


def test_glossario_respeita_limite_de_palavra():
    s = seg("rapidamente a api respondeu")
    apply_replacements([s], {"api": "API"})
    assert s.text == "rapidamente a API respondeu"


def test_parse_glossary():
    vocab, repl = parse_glossary("# comentário\nSupabase\nleed talk => LeadTalkAI\n\nSupabase\n")
    assert vocab == ["Supabase", "LeadTalkAI"]
    assert repl == {"leed talk": "LeadTalkAI"}
