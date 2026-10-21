import io
from functools import lru_cache


@lru_cache(maxsize=1)
def _model():
    from faster_whisper import WhisperModel
    # "base" is small and fast on a normal laptop CPU; the first run downloads it
    return WhisperModel("base", device="cpu", compute_type="int8")


def transcribe_audio(data: bytes) -> str:
    segments, _info = _model().transcribe(io.BytesIO(data), beam_size=1)
    return " ".join(s.text.strip() for s in segments)