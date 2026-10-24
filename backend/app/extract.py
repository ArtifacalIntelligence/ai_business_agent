import io
from pypdf import PdfReader
from docx import Document

AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm")


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if name.endswith(".docx"):
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    if name.endswith(AUDIO_EXTS):
        try:
            from app.transcribe import transcribe_audio  # loaded only when needed
            return transcribe_audio(data)
        except ImportError:
            raise ValueError("Audio transcription is not available here. "
                             "Upload a transcript (TXT, PDF or DOCX) instead.")
    raise ValueError("Unsupported file type. Use TXT, PDF, DOCX or audio (MP3/WAV/M4A).")