from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import firebase_admin
from firebase_admin import firestore, storage

from .config import get_settings
from .schemas import AudioObject, FertigationProduct, IrrigationEventResponse, ManualEventRequest, OperationType, ProcessingInfo


class FirebasePersistenceError(RuntimeError):
    """Firebase/Firestore/Storage is unavailable or misconfigured."""


def _app() -> firebase_admin.App:
    settings = get_settings()
    if not settings.firebase_configured:
        raise FirebasePersistenceError(
            "Firebase não configurado. Verifique FIREBASE_PROJECT_ID e FIREBASE_STORAGE_BUCKET."
        )
    try:
        return firebase_admin.get_app()
    except ValueError:
        # firebase-admin uses Application Default Credentials. Outside Google Cloud,
        # GOOGLE_APPLICATION_CREDENTIALS must point to the service-account JSON.
        try:
            return firebase_admin.initialize_app(
                options={
                    "projectId": settings.firebase_project_id,
                    "storageBucket": settings.firebase_storage_bucket,
                }
            )
        except Exception as exc:  # pragma: no cover - depends on external credentials
            raise FirebasePersistenceError(f"Falha ao inicializar Firebase Admin SDK: {exc}") from exc


def _db():
    try:
        return firestore.client(app=_app())
    except Exception as exc:  # pragma: no cover
        raise FirebasePersistenceError(f"Falha ao acessar Firestore: {exc}") from exc


def _bucket():
    settings = get_settings()
    try:
        return storage.bucket(name=settings.firebase_storage_bucket, app=_app())
    except Exception as exc:  # pragma: no cover
        raise FirebasePersistenceError(f"Falha ao acessar Firebase Storage: {exc}") from exc


def firebase_health() -> dict[str, str | bool | None]:
    settings = get_settings()
    return {
        "configured": settings.firebase_configured,
        "project_id": settings.firebase_project_id,
        "storage_bucket": settings.firebase_storage_bucket,
        "events_collection": settings.firestore_events_collection,
    }


def _safe_extension(filename: str | None, mime_type: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix and re.fullmatch(r"\.[a-z0-9]{1,8}", suffix):
        return suffix
    return {
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
    }.get(mime_type.split(";", 1)[0].lower(), ".bin")


def store_original_audio(
    *,
    event_id: str,
    content: bytes,
    mime_type: str,
    original_filename: str | None,
    recorded_at: datetime,
) -> AudioObject:
    settings = get_settings()
    reference = recorded_at if recorded_at.tzinfo is not None else recorded_at.replace(tzinfo=UTC)
    extension = _safe_extension(original_filename, mime_type)
    path = (
        f"{settings.firebase_audio_prefix}/{reference.year:04d}/{reference.month:02d}/"
        f"{event_id}/original{extension}"
    )
    digest = hashlib.sha256(content).hexdigest()

    try:
        bucket = _bucket()
        blob = bucket.blob(path)
        blob.metadata = {
            "event_id": event_id,
            "sha256": digest,
            "recorded_at": reference.isoformat(),
            "original_filename": original_filename or "",
        }
        blob.upload_from_string(content, content_type=mime_type or "application/octet-stream")
    except Exception as exc:  # pragma: no cover
        raise FirebasePersistenceError(f"Falha ao salvar áudio original no Storage: {exc}") from exc

    return AudioObject(
        storage_path=path,
        bucket=settings.firebase_storage_bucket or "",
        mime_type=mime_type or "application/octet-stream",
        size_bytes=len(content),
        sha256=digest,
        original_filename=original_filename,
    )


def reserve_voice_event(
    *,
    event_id: str,
    audio: AudioObject,
    recorded_at: datetime,
) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "id": event_id,
        "sector_id": None,
        "operation_type": None,
        "start_date": None,
        "start_time": None,
        "duration_minutes": None,
        "products": [],
        "source": "VOICE",
        "transcript": None,
        "status": "PROCESSING",
        "missing_fields": [],
        "audio": audio.model_dump(),
        "processing": {
            "transcription_model": settings.openai_transcribe_model if settings.stt_provider == "openai" else settings.stt_provider,
            "extraction_model": settings.openai_text_model if settings.entity_extractor == "openai" else settings.entity_extractor,
        },
        "schema_version": 1,
        "recorded_at": recorded_at,
        "created_at": now,
        "processed_at": None,
    }
    try:
        _db().collection(settings.firestore_events_collection).document(event_id).set(payload, merge=True)
    except Exception as exc:  # pragma: no cover
        raise FirebasePersistenceError(f"Falha ao criar registro PROCESSING no Firestore: {exc}") from exc


def mark_voice_error(event_id: str, message: str) -> None:
    settings = get_settings()
    try:
        _db().collection(settings.firestore_events_collection).document(event_id).set(
            {
                "status": "ERROR",
                "processing_error": message[:2000],
                "processed_at": datetime.now(UTC),
            },
            merge=True,
        )
    except Exception:
        # The original processing exception remains the one returned to the caller.
        pass


def create_manual_event(request: ManualEventRequest) -> IrrigationEventResponse:
    settings = get_settings()
    event_id = str(uuid4())
    products: list[FertigationProduct] = []
    if request.operation_type == "FERTIGATION" and request.product_name:
        products.append(
            FertigationProduct(
                name=request.product_name,
                kg_per_ha=request.kg_per_ha,
                solution_liters=request.solution_liters,
            )
        )

    now = datetime.now(UTC)
    payload = {
        "id": event_id,
        "sector_id": request.sector_id,
        "operation_type": request.operation_type,
        "start_date": request.start_date,
        "start_time": request.start_time,
        "duration_minutes": request.duration_minutes,
        "products": [item.model_dump() for item in products],
        "source": "MANUAL",
        "transcript": None,
        "status": "REGISTERED",
        "missing_fields": [],
        "audio": None,
        "processing": None,
        "schema_version": 1,
        "created_at": now,
        "processed_at": now,
    }
    try:
        _db().collection(settings.firestore_events_collection).document(event_id).set(payload)
    except Exception as exc:  # pragma: no cover
        raise FirebasePersistenceError(f"Falha ao salvar registro manual no Firestore: {exc}") from exc
    return _response(payload)


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
    settings = get_settings()
    resolved_id = event_id or str(uuid4())
    now = datetime.now(UTC)
    doc_ref = _db().collection(settings.firestore_events_collection).document(resolved_id)

    try:
        existing = doc_ref.get()
        previous = existing.to_dict() if existing.exists else {}
        created_at = previous.get("created_at") or now
        stored_audio = audio.model_dump() if audio is not None else previous.get("audio")
        processing = previous.get("processing") or {
            "transcription_model": settings.openai_transcribe_model if settings.stt_provider == "openai" else settings.stt_provider,
            "extraction_model": settings.openai_text_model if settings.entity_extractor == "openai" else settings.entity_extractor,
        }
        payload = {
            "id": resolved_id,
            "sector_id": sector_id,
            "operation_type": operation_type,
            "start_date": start_date,
            "start_time": start_time,
            "duration_minutes": duration_minutes,
            "products": [item.model_dump() for item in products],
            "source": "VOICE",
            "transcript": transcript,
            "status": "NEEDS_REVIEW" if missing_fields else "REGISTERED",
            "missing_fields": missing_fields,
            "audio": stored_audio,
            "processing": processing,
            "schema_version": 1,
            "created_at": created_at,
            "processed_at": now,
            "processing_error": None,
        }
        doc_ref.set(payload, merge=True)
    except Exception as exc:  # pragma: no cover
        raise FirebasePersistenceError(f"Falha ao salvar evento no Firestore: {exc}") from exc

    return _response(payload)


def list_events(limit: int = 50) -> list[IrrigationEventResponse]:
    settings = get_settings()
    try:
        query = (
            _db()
            .collection(settings.firestore_events_collection)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        result: list[IrrigationEventResponse] = []
        for snapshot in query.stream():
            payload = snapshot.to_dict() or {}
            # PROCESSING/ERROR documents can exist before sector/type extraction.
            # They stay in Firestore for auditability but cannot satisfy the public event schema yet.
            if payload.get("sector_id") is None or payload.get("operation_type") is None:
                continue
            result.append(_response(payload))
        return result
    except Exception as exc:  # pragma: no cover
        raise FirebasePersistenceError(f"Falha ao consultar histórico no Firestore: {exc}") from exc


def _usage_documents(month_start: datetime) -> list[dict[str, Any]]:
    settings = get_settings()
    try:
        query = _db().collection(settings.firestore_usage_collection).where("created_at", ">=", month_start)
        return [snapshot.to_dict() or {} for snapshot in query.stream()]
    except Exception as exc:  # pragma: no cover
        raise FirebasePersistenceError(f"Falha ao consultar uso da OpenAI no Firestore: {exc}") from exc


def count_openai_calls_this_month(now: datetime | None = None) -> int:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    month_start = current.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return len(_usage_documents(month_start))


def record_openai_usage(
    *,
    kind: str,
    model: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
) -> None:
    settings = get_settings()
    payload = {
        "id": str(uuid4()),
        "kind": kind,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "created_at": datetime.now(UTC),
    }
    try:
        _db().collection(settings.firestore_usage_collection).document(payload["id"]).set(payload)
    except Exception as exc:  # pragma: no cover
        raise FirebasePersistenceError(f"Falha ao registrar uso da OpenAI no Firestore: {exc}") from exc


def usage_summary() -> dict[str, int | None]:
    current = datetime.now(UTC)
    month_start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = _usage_documents(month_start)

    def _sum(key: str) -> int | None:
        values = [row.get(key) for row in rows if isinstance(row.get(key), int)]
        return sum(values) if values else None

    return {
        "calls": len(rows),
        "input_tokens": _sum("input_tokens"),
        "output_tokens": _sum("output_tokens"),
        "total_tokens": _sum("total_tokens"),
    }


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()
    return str(value)


def _response(payload: dict[str, Any]) -> IrrigationEventResponse:
    return IrrigationEventResponse(
        id=str(payload["id"]),
        sector_id=int(payload["sector_id"]),
        operation_type=payload["operation_type"],
        start_date=payload.get("start_date"),
        start_time=payload.get("start_time"),
        duration_minutes=payload.get("duration_minutes"),
        products=[FertigationProduct.model_validate(item) for item in payload.get("products", [])],
        source=payload.get("source", "VOICE"),
        transcript=payload.get("transcript"),
        status=payload.get("status", "ERROR"),
        missing_fields=list(payload.get("missing_fields", [])),
        audio=AudioObject.model_validate(payload["audio"]) if payload.get("audio") else None,
        processing=ProcessingInfo.model_validate(payload["processing"]) if payload.get("processing") else None,
        schema_version=int(payload.get("schema_version", 1)),
        created_at=_iso(payload.get("created_at")) or datetime.now(UTC).isoformat(),
        processed_at=_iso(payload.get("processed_at")),
    )
