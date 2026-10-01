from smart_irrigation.schemas import ExtractedEvent, ExtractedProduct, QuickVoiceExtractedEvent
from smart_irrigation.validation import validate_extracted, validate_quick_voice


def test_irrigation_does_not_require_product() -> None:
    parsed = validate_extracted(
        ExtractedEvent(
            start_date="2026-09-29",
            start_time="14:00",
            duration_minutes=90,
            products=[],
        ),
        "IRRIGATION",
    )

    assert parsed.complete is True
    assert parsed.missing_fields == []
    assert parsed.products == []


def test_fertigation_requires_product_quantities() -> None:
    parsed = validate_extracted(
        ExtractedEvent(
            start_date="2026-09-30",
            start_time="09:00",
            duration_minutes=60,
            products=[ExtractedProduct(name="nitrato de cálcio")],
        ),
        "FERTIGATION",
    )

    assert parsed.complete is False
    assert parsed.missing_fields == [
        "products[0].kg_per_ha",
        "products[0].solution_liters",
    ]


def test_fertigation_multiple_products_complete() -> None:
    parsed = validate_extracted(
        ExtractedEvent(
            start_date="2026-09-30",
            start_time="08:00",
            duration_minutes=120,
            products=[
                ExtractedProduct(name="nitrato de cálcio", kg_per_ha=3, solution_liters=20),
                ExtractedProduct(name="sulfato de magnésio", kg_per_ha=2, solution_liters=10),
            ],
        ),
        "FERTIGATION",
    )

    assert parsed.complete is True
    assert parsed.missing_fields == []
    assert len(parsed.products) == 2


def test_quick_voice_can_supply_sector_and_operation() -> None:
    parsed = validate_quick_voice(
        QuickVoiceExtractedEvent(
            sector_id=7,
            operation_type="IRRIGATION",
            start_date="2026-09-30",
            start_time="21:00",
            duration_minutes=120,
            products=[],
        ),
        "Hoje irriguei o setor 7 às 21 horas durante duas horas.",
    )

    assert parsed.complete is True
    assert parsed.sector_id == 7
    assert parsed.operation_type == "IRRIGATION"
    assert parsed.missing_fields == []


def test_quick_voice_requires_sector_when_not_spoken() -> None:
    parsed = validate_quick_voice(
        QuickVoiceExtractedEvent(
            sector_id=None,
            operation_type="IRRIGATION",
            start_date="2026-09-30",
            start_time="21:00",
            duration_minutes=120,
            products=[],
        ),
        "Hoje irriguei às 21 horas durante duas horas.",
    )

    assert parsed.complete is False
    assert "sector_id" in parsed.missing_fields
