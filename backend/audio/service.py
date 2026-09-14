"""Local, on-premise audio transcription using faster-whisper (CTranslate2).

No cloud APIs are used. The model runs entirely on the local machine's
CPU/GPU, consistent with the rest of the workbench's air-gapped design.
The model is loaded lazily and cached in-process so repeated requests
don't reload weights from disk every time.
"""
import os
import tempfile
from typing import Optional

from config import get_settings

settings = get_settings()

_model = None
_model_error: Optional[str] = None
_model_name = os.environ.get("WHISPER_MODEL", "base")


def _get_model():
    """Lazily load the faster-whisper model, caching success or failure."""
    global _model, _model_error

    if _model is not None:
        return _model
    if _model_error is not None:
        return None

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        _model_error = (
            "faster-whisper is not installed in this backend environment. "
            "Install it with: pip install faster-whisper"
        )
        return None

    try:
        # int8 compute type keeps this usable on CPU-only air-gapped hosts.
        _model = WhisperModel(_model_name, device="cpu", compute_type="int8")
        return _model
    except Exception as e:
        _model_error = (
            f"Whisper model '{_model_name}' could not be loaded locally: {e}. "
            "If this host is air-gapped, pre-download the model weights and "
            "place them where faster-whisper/huggingface cache expects them, "
            "or set WHISPER_MODEL to a model already cached locally."
        )
        return None


def transcription_status() -> dict:
    """Report whether local transcription is actually usable right now,
    without pretending it works when the model isn't available."""
    try:
        import faster_whisper  # noqa: F401
        installed = True
    except ImportError:
        installed = False

    if not installed:
        return {
            "available": False,
            "model": _model_name,
            "reason": "faster-whisper package is not installed in the backend environment.",
        }

    model = _get_model()
    if model is None:
        return {"available": False, "model": _model_name, "reason": _model_error}

    return {"available": True, "model": _model_name, "reason": None}


async def transcribe_file(file_bytes: bytes, filename: str, language: Optional[str] = None) -> dict:
    """Transcribe an uploaded audio file entirely locally.

    Returns a dict with 'text', 'segments' (with timestamps), and
    'language'. Raises RuntimeError with a clear message if the local
    model isn't available - callers should surface that to the user
    rather than fabricating a transcript.
    """
    model = _get_model()
    if model is None:
        raise RuntimeError(_model_error or "Local transcription model is not available.")

    suffix = os.path.splitext(filename)[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        segments, info = model.transcribe(tmp_path, language=language, vad_filter=True)
        segments_out = []
        full_text_parts = []
        for seg in segments:
            segments_out.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
            })
            full_text_parts.append(seg.text.strip())

        return {
            "text": " ".join(full_text_parts).strip(),
            "segments": segments_out,
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
        }
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
