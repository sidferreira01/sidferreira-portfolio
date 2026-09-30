import json

from helpers import seg, transcript

from transcritor.exporters import captions, export, fmt_ts, to_md, to_srt, to_txt, to_vtt
from transcritor.models import Transcript


def test_fmt_ts():
    assert fmt_ts(3661.5) == "01:01:01,500"
    assert fmt_ts(0.0015, ".") == "00:00:00.002"


def test_srt_e_vtt_basicos():
    t = transcript(seg("Olá, mundo.", 0), seg("Tudo certo?", 2))
    srt = to_srt(t)
    assert srt.startswith("1\n00:00:00,000 --> 00:00:00,800\nOlá, mundo.")
    assert "2\n00:00:02,000" in srt
    vtt = to_vtt(t)
    assert vtt.startswith("WEBVTT") and "00:00:02.000 --> 00:00:02.800" in vtt


def test_legendas_longas_sao_quebradas():
    long = seg(" ".join(["palavra"] * 60), step=0.3)
    caps = captions(transcript(long))
    assert len(caps) > 1
    assert all(len(c.text) <= 84 for c in caps)
    assert all(c.end - c.start <= 6.3 for c in caps)
    for line in to_srt(transcript(long)).split("\n"):
        assert len(line) <= 42 or "-->" in line


def test_txt_agrupa_por_falante():
    t = transcript(seg("oi", 0, speaker="Falante 1"), seg("tudo bem", 1, speaker="Falante 1"),
                   seg("sim", 2, speaker="Falante 2"), speakers=["Falante 1", "Falante 2"])
    assert to_txt(t) == "Falante 1: oi tudo bem\n\nFalante 2: sim\n"


def test_md_marca_palavras_incertas():
    t = transcript(seg("certo", 0, prob=0.9), seg("duvidoso", 1, prob=0.2))
    md = to_md(t)
    assert "==duvidoso==" in md and "==certo==" not in md
    assert "Palavras incertas:** 1 de 2" in md


def test_json_ida_e_volta():
    t = transcript(seg("ida e volta", 0, speaker="Falante 1"))
    data = json.loads(export(t, "json"))
    assert data["text"] == "ida e volta"
    back = Transcript.from_dict(data)
    assert back.segments[0].words[2].text == " volta"
    assert back.segments[0].speaker == "Falante 1"
