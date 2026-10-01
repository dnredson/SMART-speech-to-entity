from datetime import datetime

from smart_irrigation.parser import parse_speech_to_entity


def test_irrigation_relative_date_time_and_duration() -> None:
    result = parse_speech_to_entity(
        "Ontem comecei às 14:30 e irriguei por uma hora e meia.",
        "IRRIGATION",
        datetime(2026, 9, 30, 17, 0),
    )
    assert result.start_date == "2026-09-29"
    assert result.start_time == "14:30"
    assert result.duration_minutes == 90
    assert result.missing_fields == []


def test_fertigation_fields() -> None:
    result = parse_speech_to_entity(
        "Hoje comecei às oito da manhã, duas horas, com nitrato de cálcio 3 quilos por hectare e 20 litros de solução.",
        "FERTIGATION",
        datetime(2026, 9, 30, 17, 0),
    )
    assert result.start_date == "2026-09-30"
    assert result.start_time == "08:00"
    assert result.duration_minutes == 120
    assert result.products[0].name == "nitrato de calcio"
    assert result.products[0].kg_per_ha == 3
    assert result.products[0].solution_liters == 20
    assert result.missing_fields == []


def test_problem_phrase_no_longer_confuses_half_hour() -> None:
    result = parse_speech_to_entity(
        "Hoje comecei às oito e meia da manhã, irriguei por duas horas, com nitrato de cálcio, três quilos por hectare e vinte litros de solução.",
        "FERTIGATION",
        datetime(2026, 9, 30, 19, 0),
    )
    assert result.start_date == "2026-09-30"
    assert result.start_time == "08:30"
    assert result.duration_minutes == 120
    assert result.products[0].name == "nitrato de calcio"
    assert result.products[0].kg_per_ha == 3
    assert result.products[0].solution_liters == 20
    assert result.missing_fields == []


def test_missing_date_is_not_invented() -> None:
    result = parse_speech_to_entity(
        "Comecei às 9 e irriguei por 45 minutos.",
        "IRRIGATION",
        datetime(2026, 9, 30, 17, 0),
    )
    assert result.start_date is None
    assert "start_date" in result.missing_fields
