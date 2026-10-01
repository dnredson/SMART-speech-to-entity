from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

OperationType = Literal["IRRIGATION", "FERTIGATION"]
RecordStatus = Literal["LOCAL", "UPLOADING", "PROCESSING", "NEEDS_REVIEW", "REGISTERED", "ERROR"]


class FertigationProduct(BaseModel):
    name: str | None = None
    kg_per_ha: float | None = None
    solution_liters: float | None = None


class ExtractedProduct(BaseModel):
    name: str | None = Field(default=None, description="Produto ou nutriente exatamente como foi mencionado, sem inventar nomes.")
    kg_per_ha: float | None = Field(default=None, ge=0, description="Dose em kg/ha, se explicitamente informada.")
    solution_liters: float | None = Field(default=None, ge=0, description="Volume de solução em litros, se explicitamente informado.")


class ExtractedEvent(BaseModel):
    start_date: str | None = Field(default=None, description="Data de início em YYYY-MM-DD.")
    start_time: str | None = Field(default=None, description="Hora de início em HH:MM, 24 horas.")
    duration_minutes: int | None = Field(default=None, ge=1, le=24 * 60)
    products: list[ExtractedProduct] = Field(default_factory=list)


class QuickVoiceExtractedEvent(BaseModel):
    sector_id: int | None = Field(default=None, ge=1, le=7, description="Setor explicitamente mencionado na fala, entre 1 e 7.")
    operation_type: OperationType | None = Field(default=None, description="IRRIGATION ou FERTIGATION, conforme a operação descrita na fala.")
    start_date: str | None = Field(default=None, description="Data de início em YYYY-MM-DD.")
    start_time: str | None = Field(default=None, description="Hora de início em HH:MM, 24 horas.")
    duration_minutes: int | None = Field(default=None, ge=1, le=24 * 60)
    products: list[ExtractedProduct] = Field(default_factory=list)


class IrrigationEventResponse(BaseModel):
    id: str
    sector_id: int
    operation_type: OperationType
    start_date: str | None
    start_time: str | None
    duration_minutes: int | None
    products: list[FertigationProduct] = Field(default_factory=list)
    source: Literal["VOICE", "MANUAL"]
    transcript: str | None = None
    status: RecordStatus
    missing_fields: list[str] = Field(default_factory=list)
    created_at: str


class ExtractionPreviewResponse(BaseModel):
    sector_id: int
    operation_type: OperationType
    start_date: str | None
    start_time: str | None
    duration_minutes: int | None
    products: list[FertigationProduct] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    complete: bool


class VoicePreviewResponse(ExtractionPreviewResponse):
    transcript: str


class QuickVoicePreviewResponse(BaseModel):
    sector_id: int | None
    operation_type: OperationType | None
    transcript: str
    start_date: str | None
    start_time: str | None
    duration_minutes: int | None
    products: list[FertigationProduct] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    complete: bool


class ManualEventRequest(BaseModel):
    sector_id: int = Field(ge=1, le=7)
    operation_type: OperationType
    start_date: str
    start_time: str
    duration_minutes: int = Field(gt=0, le=24 * 60)
    product_name: str | None = None
    kg_per_ha: float | None = Field(default=None, ge=0)
    solution_liters: float | None = Field(default=None, ge=0)

    @field_validator("product_name")
    @classmethod
    def normalize_product(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class TranscriptProcessRequest(BaseModel):
    sector_id: int = Field(ge=1, le=7)
    operation_type: OperationType
    transcript: str = Field(min_length=1, max_length=5000)
    recorded_at: datetime | None = None
    client_record_id: str | None = None
