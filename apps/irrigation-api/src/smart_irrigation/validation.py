from __future__ import annotations

from datetime import datetime

from .parser import ParsedSpeech
from .schemas import ExtractedEvent, FertigationProduct, OperationType


def validate_extracted(extracted: ExtractedEvent, operation_type: OperationType) -> ParsedSpeech:
    start_date = _valid_iso_date(extracted.start_date)
    start_time = _valid_hhmm(extracted.start_time)
    duration = extracted.duration_minutes if extracted.duration_minutes and 0 < extracted.duration_minutes <= 24 * 60 else None

    products: list[FertigationProduct] = []
    if operation_type == "FERTIGATION":
        for item in extracted.products[:10]:
            name = item.name.strip() if item.name else None
            if name or item.kg_per_ha is not None or item.solution_liters is not None:
                products.append(
                    FertigationProduct(
                        name=name,
                        kg_per_ha=item.kg_per_ha,
                        solution_liters=item.solution_liters,
                    )
                )

    missing: list[str] = []
    if start_date is None:
        missing.append("start_date")
    if start_time is None:
        missing.append("start_time")
    if duration is None:
        missing.append("duration_minutes")

    # A IA interpreta; o SMART decide se o registro está completo.
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
        start_date=start_date,
        start_time=start_time,
        duration_minutes=duration,
        products=products,
        missing_fields=missing,
    )


def _valid_iso_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _valid_hhmm(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%H:%M").strftime("%H:%M")
    except ValueError:
        return None
