from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .schemas import FertigationProduct, OperationType

_NUMBER_WORDS: dict[str, int] = {
    "zero": 0,
    "uma": 1,
    "um": 1,
    "duas": 2,
    "dois": 2,
    "tres": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
    "dez": 10,
    "onze": 11,
    "doze": 12,
    "treze": 13,
    "quatorze": 14,
    "catorze": 14,
    "quinze": 15,
    "dezesseis": 16,
    "dezessete": 17,
    "dezoito": 18,
    "dezenove": 19,
    "vinte": 20,
    "vinte e uma": 21,
    "vinte e um": 21,
    "vinte e duas": 22,
    "vinte e dois": 22,
    "vinte e tres": 23,
}


@dataclass(slots=True)
class ParsedSpeech:
    start_date: str | None = None
    start_time: str | None = None
    duration_minutes: int | None = None
    products: list[FertigationProduct] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.missing_fields


def parse_speech_to_entity(
    transcript: str,
    operation_type: OperationType,
    reference_time: datetime | None = None,
) -> ParsedSpeech:
    reference = reference_time or datetime.now().astimezone()
    normalized = _normalize(transcript)

    parsed_date = _parse_date(normalized, reference.date())
    parsed_time = _parse_start_time(normalized)
    duration = _parse_duration(normalized)
    products = _parse_fertigation(normalized, transcript) if operation_type == "FERTIGATION" else []

    missing: list[str] = []
    if parsed_date is None:
        missing.append("start_date")
    if parsed_time is None:
        missing.append("start_time")
    if duration is None:
        missing.append("duration_minutes")
    if operation_type == "FERTIGATION":
        if not products:
            missing.append("products")
        else:
            for index, product in enumerate(products):
                if not product.name:
                    missing.append(f"products[{index}].name")
                if product.kg_per_ha is None:
                    missing.append(f"products[{index}].kg_per_ha")
                if product.solution_liters is None:
                    missing.append(f"products[{index}].solution_liters")

    return ParsedSpeech(
        start_date=parsed_date.isoformat() if parsed_date else None,
        start_time=parsed_time,
        duration_minutes=duration,
        products=products,
        missing_fields=missing,
    )


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.lower())
    no_accents = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", no_accents).strip()


def _parse_date(text: str, reference: date) -> date | None:
    if "anteontem" in text:
        return reference - timedelta(days=2)
    if "ontem" in text:
        return reference - timedelta(days=1)
    if "hoje" in text:
        return reference

    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", text)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        year_raw = match.group(3)
        year = reference.year if year_raw is None else int(year_raw)
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            return None

    # No caso operacional, se a fala contiver horário/duração mas não disser a data,
    # "hoje" é uma suposição aceitável apenas quando explicitamente habilitada no futuro.
    # Na V0 mantemos null para pedir revisão e nunca inventar o dia.
    return None


def _parse_start_time(text: str) -> str | None:
    # 14:30, 14h30, 14h
    patterns = [
        r"\b(?:as|a partir das|comecei as|inicio as|iniciou as)?\s*(\d{1,2})[:h](\d{2})\b",
        r"\b(?:as|a partir das|comecei as|inicio as|iniciou as)\s+(\d{1,2})\s*h?\b",
    ]
    for index, pattern in enumerate(patterns):
        match = re.search(pattern, text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if index == 0 else 0
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return f"{hour:02d}:{minute:02d}"

    # "duas e meia da tarde", "oito da manha", "sete horas e quinze"
    word_pattern = "|".join(sorted((re.escape(word) for word in _NUMBER_WORDS), key=len, reverse=True))
    match = re.search(
        rf"\b(?:as|comecei as|inicio as|iniciou as)\s+({word_pattern})(?:\s+horas?)?(?:\s+e\s+(meia|quinze|trinta|quarenta e cinco))?(?:\s+da\s+(manha|tarde|noite))?",
        text,
    )
    if match:
        hour = _NUMBER_WORDS[match.group(1)]
        minute_word = match.group(2)
        period = match.group(3)
        minute = {None: 0, "meia": 30, "quinze": 15, "trinta": 30, "quarenta e cinco": 45}[minute_word]
        if period in {"tarde", "noite"} and 1 <= hour <= 11:
            hour += 12
        if period == "manha" and hour == 12:
            hour = 0
        if 0 <= hour <= 23:
            return f"{hour:02d}:{minute:02d}"
    return None


def _parse_duration(text: str) -> int | None:
    # Duração compacta: 1h30, 2h, 45min
    match = re.search(r"\b(\d{1,2})\s*h(?:\s*(\d{1,2})\s*(?:m|min)?)?\b", text)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2) or 0)
        total = hours * 60 + minutes
        if 0 < total <= 24 * 60:
            return total

    match = re.search(r"\b(\d{1,4})\s*(?:min|minutos?|mins)\b", text)
    if match:
        minutes = int(match.group(1))
        if 0 < minutes <= 24 * 60:
            return minutes

    # "por uma hora e meia", "durou duas horas e vinte minutos"
    hours = _extract_quantity_before_unit(text, r"horas?")
    minutes = _extract_quantity_before_unit(text, r"minutos?")
    if hours is not None or minutes is not None:
        total = (hours or 0) * 60 + (minutes or 0)
        # A meia hora só pertence à duração quando aparece junto da expressão de duração.
        half_match = re.search(
            r"\b(?:uma|um|duas|dois|tres|quatro|cinco|seis|sete|oito|nove|dez|\d+)\s+horas?\s+e\s+meia\b",
            text,
        )
        if half_match is not None and minutes is None:
            total += 30
        if 0 < total <= 24 * 60:
            return total
    return None


def _extract_quantity_before_unit(text: str, unit_pattern: str) -> int | None:
    numeric = re.search(rf"\b(\d{{1,4}})\s*{unit_pattern}\b", text)
    if numeric:
        return int(numeric.group(1))
    word_pattern = "|".join(sorted((re.escape(word) for word in _NUMBER_WORDS), key=len, reverse=True))
    words = re.search(rf"\b({word_pattern})\s+{unit_pattern}\b", text)
    if words:
        return _NUMBER_WORDS[words.group(1)]
    return None


def _parse_fertigation(normalized: str, original: str) -> list[FertigationProduct]:
    kg_value = _extract_decimal_quantity(normalized, r"(?:kg|quilos?)", suffix=r"(?:/\s*ha|por hectare)?")
    liters_value = _extract_decimal_quantity(normalized, r"(?:l|litros?)", suffix=r"(?:de\s+solucao)?")

    name = _extract_product_name(normalized, original)
    if not name and kg_value is None and liters_value is None:
        return []
    return [
        FertigationProduct(
            name=name or None,
            kg_per_ha=kg_value,
            solution_liters=liters_value,
        )
    ]


def _extract_decimal_quantity(text: str, unit_pattern: str, *, suffix: str = "") -> float | None:
    numeric = re.search(rf"\b(\d+(?:[.,]\d+)?)\s*{unit_pattern}\s*{suffix}\b", text)
    if numeric:
        return _decimal(numeric.group(1))

    word_pattern = "|".join(sorted((re.escape(word) for word in _NUMBER_WORDS), key=len, reverse=True))
    words = re.search(rf"\b({word_pattern})\s+{unit_pattern}\s*{suffix}\b", text)
    if words:
        return float(_NUMBER_WORDS[words.group(1)])
    return None


def _extract_product_name(normalized: str, original: str) -> str:
    # Faixa iniciada por verbos/preposições típicos e encerrada antes de dose/volume.
    word_pattern = "|".join(sorted((re.escape(word) for word in _NUMBER_WORDS), key=len, reverse=True))
    pattern = re.search(
        rf"\b(?:com|coloquei|apliquei|usei)\s+(.+?)(?=\s+(?:(?:\d+(?:[.,]\d+)?|{word_pattern})\s*(?:kg|quilos?|l|litros?)|por\s+(?:\d+|{word_pattern})|$))",
        normalized,
    )
    if pattern is None:
        return ""
    normalized_name = pattern.group(1).strip(" ,.;")
    # A transcrição original é preservada separadamente. Para entidade, o nome normalizado
    # é preferível e facilita catálogo/correlação futura.
    return normalized_name


def _decimal(raw: str) -> float:
    return float(raw.replace(",", "."))
