from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path

from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI, RateLimitError

from .ai import AILimitError, AIUnavailableError, ensure_openai_capacity
from .config import get_settings
from .database import record_openai_usage


class SpeechUnavailableError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _load_local_model():
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise SpeechUnavailableError(
            "faster-whisper não está instalado. Instale o extra local-stt ou use STT_PROVIDER=openai."
        ) from exc

    model_name = os.environ.get("WHISPER_MODEL", "base")
    device = os.environ.get("WHISPER_DEVICE", "cpu")
    compute_type = os.environ.get("WHISPER_COMPUTE_TYPE", "int8" if device == "cpu" else "float16")
    return WhisperModel(model_name, device=device, compute_type=compute_type)


def transcribe_audio(content: bytes, suffix: str = ".webm", filename: str | None = None) -> str:
    settings = get_settings()
    if settings.stt_provider == "openai":
        return _transcribe_openai(content, suffix=suffix, filename=filename)
    if settings.stt_provider == "local":
        return _transcribe_local(content, suffix=suffix)
    raise SpeechUnavailableError(f"STT_PROVIDER desconhecido: {settings.stt_provider}")


def _transcribe_openai(content: bytes, *, suffix: str, filename: str | None) -> str:
    settings = get_settings()
    if not settings.openai_configured:
        raise AIUnavailableError("OPENAI_API_KEY não está configurada no backend.")
    ensure_openai_capacity(1)

    safe_name = filename or f"recording{suffix}"
    if Path(safe_name).suffix == "":
        safe_name = f"{safe_name}{suffix}"

    client = OpenAI(api_key=settings.openai_api_key)
    try:
        transcription = client.audio.transcriptions.create(
            model=settings.openai_transcribe_model,
            file=(safe_name, content),
            prompt=(
                "Registro agrícola em português brasileiro sobre irrigação ou fertirrigação. "
                "Pode conter horários, duração, nomes de fertilizantes, kg por hectare e litros de solução."
            ),
            extra_body={
                "keywords": ["irrigação", "fertirrigação", "kg por hectare", "litros de solução"],
                "languages": ["pt"],
            },
        )
    except RateLimitError as exc:
        raise AILimitError("A OpenAI recusou a transcrição por limite de uso/rate limit.") from exc
    except AuthenticationError as exc:
        raise AIUnavailableError("A chave da OpenAI foi rejeitada. Verifique OPENAI_API_KEY.") from exc
    except APIConnectionError as exc:
        raise AIUnavailableError("Não foi possível conectar à OpenAI para transcrever o áudio.") from exc
    except APIStatusError as exc:
        raise AIUnavailableError(f"A OpenAI respondeu com erro HTTP {exc.status_code} na transcrição.") from exc

    text = transcription.text.strip()
    if not text:
        raise SpeechUnavailableError("O áudio não gerou transcrição.")

    usage = getattr(transcription, "usage", None)
    record_openai_usage(
        kind="TRANSCRIPTION",
        model=settings.openai_transcribe_model,
        input_tokens=getattr(usage, "input_tokens", None) if usage else None,
        output_tokens=getattr(usage, "output_tokens", None) if usage else None,
        total_tokens=getattr(usage, "total_tokens", None) if usage else None,
    )
    return text


def _transcribe_local(content: bytes, *, suffix: str) -> str:
    model = _load_local_model()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(content)
        path = Path(handle.name)

    try:
        segments, _info = model.transcribe(
            str(path),
            language="pt",
            vad_filter=True,
            beam_size=5,
        )
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        if not text:
            raise SpeechUnavailableError("O áudio não gerou transcrição.")
        return text.strip()
    finally:
        path.unlink(missing_ok=True)
