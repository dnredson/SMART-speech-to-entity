from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    openai_api_key: str | None
    openai_text_model: str
    openai_transcribe_model: str
    entity_extractor: str
    stt_provider: str
    max_openai_calls_per_month: int
    max_audio_bytes: int
    max_transcript_chars: int

    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        openai_text_model=os.environ.get("OPENAI_TEXT_MODEL", "gpt-6-luna"),
        openai_transcribe_model=os.environ.get("OPENAI_TRANSCRIBE_MODEL", "gpt-transcribe"),
        entity_extractor=os.environ.get("ENTITY_EXTRACTOR", "openai").strip().lower(),
        stt_provider=os.environ.get("STT_PROVIDER", "openai").strip().lower(),
        max_openai_calls_per_month=max(1, int(os.environ.get("OPENAI_MAX_CALLS_PER_MONTH", "100"))),
        max_audio_bytes=max(1024, int(os.environ.get("MAX_AUDIO_BYTES", str(20 * 1024 * 1024)))),
        max_transcript_chars=max(100, int(os.environ.get("MAX_TRANSCRIPT_CHARS", "5000"))),
    )
