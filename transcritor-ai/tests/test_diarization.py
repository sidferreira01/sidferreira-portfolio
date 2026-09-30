from helpers import seg

from transcritor.diarization import Turn, assign_speakers


def test_quebra_segmento_quando_falante_muda():
    s = seg("oi tudo bem sim e você", step=1.0)  # palavras em 0-1, 1-2, ... 5-6
    turns = [Turn(0.0, 3.1, "SPEAKER_01"), Turn(3.1, 6.0, "SPEAKER_00")]
    out = assign_speakers([s], turns)
    assert [(o.speaker, o.text) for o in out] == [("Falante 1", "oi tudo bem"), ("Falante 2", "sim e você")]
    assert out[1].start == 3.0


def test_palavra_sem_sobreposicao_usa_turno_mais_proximo():
    s = seg("olá", start=10.0)
    out = assign_speakers([s], [Turn(0, 9.5, "A"), Turn(20, 30, "B")])
    assert out[0].speaker == "Falante 1"


def test_sem_turnos_nao_altera():
    s = seg("teste")
    assert assign_speakers([s], []) == [s]
