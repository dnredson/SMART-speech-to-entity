from datetime import datetime

from smart_irrigation.date_policy import mentions_date_reference, resolve_start_date


def test_uses_recording_date_when_no_date_is_spoken() -> None:
    reference = datetime.fromisoformat("2026-10-01T16:30:00-03:00")

    result = resolve_start_date(
        extracted_date=None,
        transcript="Irriguei o setor 5 às quatro da tarde durante duas horas.",
        recorded_at=reference,
    )

    assert result == "2026-10-01"


def test_preserves_resolved_explicit_date() -> None:
    reference = datetime.fromisoformat("2026-10-01T08:30:00-03:00")

    result = resolve_start_date(
        extracted_date="2026-09-30",
        transcript="Ontem irriguei o setor 2 às nove da manhã durante 45 minutos.",
        recorded_at=reference,
    )

    assert result == "2026-09-30"


def test_does_not_guess_when_date_reference_was_spoken_but_unresolved() -> None:
    reference = datetime.fromisoformat("2026-10-01T08:30:00-03:00")

    result = resolve_start_date(
        extracted_date=None,
        transcript="Na terça-feira irriguei o setor 2 durante uma hora.",
        recorded_at=reference,
    )

    assert result is None
    assert mentions_date_reference("Na terça-feira irriguei o setor 2.") is True
