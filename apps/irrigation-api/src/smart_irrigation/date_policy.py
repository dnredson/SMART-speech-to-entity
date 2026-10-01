from __future__ import annotations

import re
import unicodedata
from datetime import datetime

_DATE_REFERENCE_RE = re.compile(
    r"(?:"
    r"\b(?:hoje|ontem|anteontem|amanha)\b|"
    r"\b(?:segunda|terca|quarta|quinta|sexta)(?:-feira)?\b|"
    r"\b(?:sabado|domingo)\b|"
    r"\bdia\s+\d{1,2}\b|"
    r"\b\d{1,2}\s*[/.-]\s*\d{1,2}(?:\s*[/.-]\s*\d{2,4})?\b|"
    r"\b\d{1,2}\s+de\s+(?:janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b|"
    r"\b(?:semana|mes|ano)\s+(?:passad[oa]|anterior)\b"
    r")",
    re.IGNORECASE,
)


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def mentions_date_reference(transcript: str) -> bool:
    """Return True when the speaker explicitly refers to a calendar date/day.

    The policy is intentionally conservative: when a date reference is present but
    the extractor cannot resolve it, the event must remain NEEDS_REVIEW instead of
    silently falling back to the recording date.
    """

    return bool(_DATE_REFERENCE_RE.search(_normalize(transcript)))


def resolve_start_date(
    *,
    extracted_date: str | None,
    transcript: str,
    recorded_at: datetime,
) -> str | None:
    """Use recorded_at's local date only when the user did not mention any date."""

    if extracted_date is not None:
        return extracted_date
    if mentions_date_reference(transcript):
        return None
    return recorded_at.date().isoformat()
