from transcritor.models import Segment, Transcript, Word


def seg(text, start=0.0, end=None, prob=0.9, no_speech=0.0, speaker=None, step=0.4):
    tokens = text.split()
    words, t = [], start
    for tok in tokens:
        words.append(Word(start=round(t, 2), end=round(t + step, 2), text=" " + tok, probability=prob))
        t += step
    return Segment(start=start, end=end if end is not None else round(t, 2), text=text,
                   words=words, no_speech_prob=no_speech, speaker=speaker, avg_logprob=-0.2)


def transcript(*segments, speakers=None):
    return Transcript(segments=list(segments), language="pt", language_probability=0.99,
                      duration=segments[-1].end if segments else 0.0, model="teste",
                      processing_seconds=2.0, speakers=speakers or [])
