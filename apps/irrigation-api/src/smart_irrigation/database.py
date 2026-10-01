from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .config import get_settings
from .schemas import AudioObject, FertigationProduct, IrrigationEventResponse, ManualEventRequest, OperationType

settings = get_settings()


def _using_firebase() -> bool:
    return settings.persistence_provider == "firebase"


def _firebase():
    from . import firebase_store

    return firebase_store


def _default_database_url() -> str:
    data_dir = Path(os.environ.get("SMART_IRRIGATION_DATA_DIR", "./data")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_dir / 'smart-irrigation.db'}"


DATABASE_URL = os.environ.get("DATABASE_URL", _default_database_url()) if not _using_firebase() else None
engine = (
    create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False} if DATABASE_URL and DATABASE_URL.startswith("sqlite") else {},
    )
    if DATABASE_URL
    else None
)


class Base(DeclarativeBase):
    pass


class IrrigationEventModel(Base):
    __tablename__ = "irrigation_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sector_id: Mapped[int] = mapped_column(Integer, nullable=False)
    operation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    start_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    start_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    products_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    missing_fields_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OpenAIUsageModel(Base):
    __tablename__ = "openai_usage"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


if engine is not None:
    Base.metadata.create_all(engine)


def persistence_health() -> dict[str, object]:
    if _using_firebase():
        return {"provider": "firebase", **_firebase().firebase_health()}
    return {"provider": "sqlite", "database_url": DATABASE_URL}


def store_original_audio(
    *,
    event_id: str,
    content: bytes,
    mime_type: str,
    original_filename: str | None,
    recorded_at: datetime,
) -> AudioObject | None:
    if not _using_firebase():
        return None
    return _firebase().store_original_audio(
        event_id=event_id,
        content=content,
        mime_type=mime_type,
        original_filename=original_filename,
        recorded_at=recorded_at,
    )


def reserve_voice_event(*, event_id: str, audio: AudioObject, recorded_at: datetime) -> None:
    if not _using_firebase():
        return
    _firebase().reserve_voice_event(event_id=event_id, audio=audio, recorded_at=recorded_at)


def mark_voice_error(event_id: str, message: str) -> None:
    if not _using_firebase():
        return
    _firebase().mark_voice_error(event_id, message)


def create_manual_event(request: ManualEventRequest) -> IrrigationEventResponse:
    if _using_firebase():
        return _firebase().create_manual_event(request)
    assert engine is not None

    products: list[FertigationProduct] = []
    if request.operation_type == "FERTIGATION" and request.product_name:
        products.append(
            FertigationProduct(
                name=request.product_name,
                kg_per_ha=request.kg_per_ha,
                solution_liters=request.solution_liters,
            )
        )
    model = IrrigationEventModel(
        id=str(uuid4()),
        sector_id=request.sector_id,
        operation_type=request.operation_type,
        start_date=request.start_date,
        start_time=request.start_time,
        duration_minutes=request.duration_minutes,
        products_json=json.dumps([item.model_dump() for item in products], ensure_ascii=False),
        source="MANUAL",
        transcript=None,
        status="REGISTERED",
        missing_fields_json="[]",
        created_at=datetime.now(UTC),
    )
    with Session(engine) as session:
        session.add(model)
        session.commit()
        session.refresh(model)
    return _response(model)


def create_voice_event(
    *,
    event_id: str | None,
    sector_id: int,
    operation_type: OperationType,
    start_date: str | None,
    start_time: str | None,
    duration_minutes: int | None,
    products: list[FertigationProduct],
    transcript: str,
    missing_fields: list[str],
    audio: AudioObject | None = None,
) -> IrrigationEventResponse:
    if _using_firebase():
        return _firebase().create_voice_event(
            event_id=event_id,
            sector_id=sector_id,
            operation_type=operation_type,
            start_date=start_date,
            start_time=start_time,
            duration_minutes=duration_minutes,
            products=products,
            transcript=transcript,
            missing_fields=missing_fields,
            audio=audio,
        )
    assert engine is not None

    model = IrrigationEventModel(
        id=event_id or str(uuid4()),
        sector_id=sector_id,
        operation_type=operation_type,
        start_date=start_date,
        start_time=start_time,
        duration_minutes=duration_minutes,
        products_json=json.dumps([item.model_dump() for item in products], ensure_ascii=False),
        source="VOICE",
        transcript=transcript,
        status="NEEDS_REVIEW" if missing_fields else "REGISTERED",
        missing_fields_json=json.dumps(missing_fields),
        created_at=datetime.now(UTC),
    )
    with Session(engine) as session:
        session.merge(model)
        session.commit()
        stored = session.get(IrrigationEventModel, model.id)
        assert stored is not None
        return _response(stored)


def list_events(limit: int = 50) -> list[IrrigationEventResponse]:
    if _using_firebase():
        return _firebase().list_events(limit)
    assert engine is not None

    with Session(engine) as session:
        rows = session.scalars(
            select(IrrigationEventModel).order_by(IrrigationEventModel.created_at.desc()).limit(limit)
        ).all()
        return [_response(row) for row in rows]


def count_openai_calls_this_month(now: datetime | None = None) -> int:
    if _using_firebase():
        return _firebase().count_openai_calls_this_month(now)
    assert engine is not None

    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    month_start = current.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    with Session(engine) as session:
        return int(
            session.scalar(
                select(func.count()).select_from(OpenAIUsageModel).where(OpenAIUsageModel.created_at >= month_start)
            )
            or 0
        )


def record_openai_usage(
    *,
    kind: str,
    model: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
) -> None:
    if _using_firebase():
        _firebase().record_openai_usage(
            kind=kind,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
        return
    assert engine is not None

    row = OpenAIUsageModel(
        id=str(uuid4()),
        kind=kind,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        created_at=datetime.now(UTC),
    )
    with Session(engine) as session:
        session.add(row)
        session.commit()


def usage_summary() -> dict[str, int | None]:
    if _using_firebase():
        return _firebase().usage_summary()
    assert engine is not None

    current = datetime.now(UTC)
    month_start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    with Session(engine) as session:
        row = session.execute(
            select(
                func.count(OpenAIUsageModel.id),
                func.sum(OpenAIUsageModel.input_tokens),
                func.sum(OpenAIUsageModel.output_tokens),
                func.sum(OpenAIUsageModel.total_tokens),
            ).where(OpenAIUsageModel.created_at >= month_start)
        ).one()
        return {
            "calls": int(row[0] or 0),
            "input_tokens": int(row[1]) if row[1] is not None else None,
            "output_tokens": int(row[2]) if row[2] is not None else None,
            "total_tokens": int(row[3]) if row[3] is not None else None,
        }


def _response(model: IrrigationEventModel) -> IrrigationEventResponse:
    products = [FertigationProduct.model_validate(item) for item in json.loads(model.products_json)]
    missing = list(json.loads(model.missing_fields_json))
    created_at = model.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return IrrigationEventResponse(
        id=model.id,
        sector_id=model.sector_id,
        operation_type=model.operation_type,  # type: ignore[arg-type]
        start_date=model.start_date,
        start_time=model.start_time,
        duration_minutes=model.duration_minutes,
        products=products,
        source=model.source,  # type: ignore[arg-type]
        transcript=model.transcript,
        status=model.status,  # type: ignore[arg-type]
        missing_fields=missing,
        audio=None,
        processing=None,
        schema_version=1,
        created_at=created_at.isoformat(),
        processed_at=None,
    )
