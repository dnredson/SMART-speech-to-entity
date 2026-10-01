from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .ai import AILimitError, AIUnavailableError, ensure_openai_capacity, extract_with_openai
from .config import get_settings
from .database import create_manual_event, create_voice_event, list_events, usage_summary
from .schemas import ExtractionPreviewResponse, IrrigationEventResponse, ManualEventRequest, OperationType, TranscriptProcessRequest, VoicePreviewResponse
from .speech import SpeechUnavailableError, transcribe_audio

settings = get_settings()

app = FastAPI(
    title="SMART Irrigação API",
    version="0.3.0",
    description="Serviço independente para registro de irrigação/fertirrigação e speech-to-entity.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

allowed_origins = [
    item.strip()
    for item in os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:8503,http://127.0.0.1:8503",
    ).split(",")
    if item.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "smart-irrigation-api",
        "version": "0.3.0",
        "openai_configured": settings.openai_configured,
        "entity_extractor": settings.entity_extractor,
        "stt_provider": settings.stt_provider,
        "text_model": settings.openai_text_model if settings.entity_extractor == "openai" else None,
        "transcribe_model": settings.openai_transcribe_model if settings.stt_provider == "openai" else None,
    }


@app.get("/api/v1/usage")
def get_usage() -> dict[str, object]:
    return {
        "month": usage_summary(),
        "local_call_limit": settings.max_openai_calls_per_month,
        "note": "Contador local de chamadas concluídas; o hard spend limit continua sendo configurado na plataforma OpenAI.",
    }


@app.get("/api/v1/sectors")
def sectors() -> list[dict[str, int | str]]:
    return [{"id": sector, "name": f"Setor {sector:02d}"} for sector in range(1, 8)]


@app.get("/api/v1/events", response_model=list[IrrigationEventResponse])
def events(limit: int = 50) -> list[IrrigationEventResponse]:
    return list_events(max(1, min(limit, 200)))


@app.post("/api/v1/events", response_model=IrrigationEventResponse, status_code=201)
def create_event(request: ManualEventRequest) -> IrrigationEventResponse:
    if request.operation_type == "FERTIGATION":
        missing: list[str] = []
        if not request.product_name:
            missing.append("product_name")
        if request.kg_per_ha is None:
            missing.append("kg_per_ha")
        if request.solution_liters is None:
            missing.append("solution_liters")
        if missing:
            raise HTTPException(
                status_code=422,
                detail={"message": "Fertirrigação incompleta.", "missing_fields": missing},
            )
    return create_manual_event(request)


@app.post("/api/v1/transcript/preview", response_model=ExtractionPreviewResponse)
def preview_transcript(request: TranscriptProcessRequest) -> ExtractionPreviewResponse:
    if len(request.transcript) > settings.max_transcript_chars:
        raise HTTPException(status_code=413, detail="Transcrição excede o limite local.")
    try:
        parsed = extract_with_openai(
            request.transcript,
            request.operation_type,
            request.recorded_at,
        )
    except AILimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except AIUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ExtractionPreviewResponse(
        sector_id=request.sector_id,
        operation_type=request.operation_type,
        start_date=parsed.start_date,
        start_time=parsed.start_time,
        duration_minutes=parsed.duration_minutes,
        products=parsed.products,
        missing_fields=parsed.missing_fields,
        complete=parsed.complete,
    )


@app.post("/api/v1/transcript/process", response_model=IrrigationEventResponse, status_code=201)
def process_transcript(request: TranscriptProcessRequest) -> IrrigationEventResponse:
    if len(request.transcript) > settings.max_transcript_chars:
        raise HTTPException(status_code=413, detail="Transcrição excede o limite local.")
    try:
        parsed = extract_with_openai(
            request.transcript,
            request.operation_type,
            request.recorded_at,
        )
    except AILimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except AIUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return create_voice_event(
        event_id=request.client_record_id,
        sector_id=request.sector_id,
        operation_type=request.operation_type,
        start_date=parsed.start_date,
        start_time=parsed.start_time,
        duration_minutes=parsed.duration_minutes,
        products=parsed.products,
        transcript=request.transcript,
        missing_fields=parsed.missing_fields,
    )


@app.post("/api/v1/voice/preview", response_model=VoicePreviewResponse)
async def preview_voice(
    sector_id: Annotated[int, Form(ge=1, le=7)],
    operation_type: Annotated[OperationType, Form()],
    recorded_at: Annotated[str, Form()],
    audio: Annotated[UploadFile, File()],
) -> VoicePreviewResponse:
    """Transcreve e extrai entidades sem gravar o evento no banco."""
    content = await audio.read()
    if not content:
        raise HTTPException(status_code=422, detail="Áudio vazio.")
    if len(content) > settings.max_audio_bytes:
        raise HTTPException(status_code=413, detail="Áudio excede o limite local de tamanho.")

    try:
        if settings.stt_provider == "openai" and settings.entity_extractor == "openai":
            ensure_openai_capacity(2)
    except AILimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    try:
        transcript = transcribe_audio(content, suffix=suffix, filename=audio.filename)
    except AILimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except AIUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SpeechUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Falha ao transcrever áudio: {exc}") from exc

    try:
        reference = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    except ValueError:
        reference = datetime.now().astimezone()

    try:
        parsed = extract_with_openai(transcript, operation_type, reference)
    except AILimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except AIUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return VoicePreviewResponse(
        sector_id=sector_id,
        operation_type=operation_type,
        transcript=transcript,
        start_date=parsed.start_date,
        start_time=parsed.start_time,
        duration_minutes=parsed.duration_minutes,
        products=parsed.products,
        missing_fields=parsed.missing_fields,
        complete=parsed.complete,
    )


@app.post("/api/v1/voice/process", response_model=IrrigationEventResponse, status_code=201)
async def process_voice(
    sector_id: Annotated[int, Form(ge=1, le=7)],
    operation_type: Annotated[OperationType, Form()],
    recorded_at: Annotated[str, Form()],
    audio: Annotated[UploadFile, File()],
    client_record_id: Annotated[str | None, Form()] = None,
) -> IrrigationEventResponse:
    content = await audio.read()
    if not content:
        raise HTTPException(status_code=422, detail="Áudio vazio.")
    if len(content) > settings.max_audio_bytes:
        raise HTTPException(status_code=413, detail="Áudio excede o limite local de tamanho.")

    # Voz com OpenAI usa 2 chamadas: transcrição + extração semântica.
    try:
        if settings.stt_provider == "openai" and settings.entity_extractor == "openai":
            ensure_openai_capacity(2)
    except AILimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    try:
        transcript = transcribe_audio(content, suffix=suffix, filename=audio.filename)
    except AILimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except AIUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SpeechUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Falha ao transcrever áudio: {exc}") from exc

    try:
        reference = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    except ValueError:
        reference = datetime.now().astimezone()

    try:
        parsed = extract_with_openai(transcript, operation_type, reference)
    except AILimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except AIUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return create_voice_event(
        event_id=client_record_id,
        sector_id=sector_id,
        operation_type=operation_type,
        start_date=parsed.start_date,
        start_time=parsed.start_time,
        duration_minutes=parsed.duration_minutes,
        products=parsed.products,
        transcript=transcript,
        missing_fields=parsed.missing_fields,
    )


def run() -> None:
    import uvicorn

    uvicorn.run(
        "smart_irrigation.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8030")),
        reload=False,
    )
