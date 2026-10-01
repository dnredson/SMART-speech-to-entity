export type OperationType = "IRRIGATION" | "FERTIGATION";

export type RecordStatus =
  | "LOCAL"
  | "UPLOADING"
  | "PROCESSING"
  | "NEEDS_REVIEW"
  | "REGISTERED"
  | "ERROR";

export interface FertigationProduct {
  name: string | null;
  kg_per_ha: number | null;
  solution_liters: number | null;
}

export interface StoredAudio {
  storage_path: string;
  bucket: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  original_filename?: string | null;
}

export interface ProcessingInfo {
  transcription_model?: string | null;
  extraction_model?: string | null;
}

export interface IrrigationEvent {
  id: string;
  sector_id: number;
  operation_type: OperationType;
  start_date: string | null;
  start_time: string | null;
  duration_minutes: number | null;
  products: FertigationProduct[];
  source: "VOICE" | "MANUAL";
  transcript?: string | null;
  status: RecordStatus;
  missing_fields?: string[];
  audio?: StoredAudio | null;
  processing?: ProcessingInfo | null;
  schema_version?: number;
  created_at: string;
  processed_at?: string | null;
}

export interface LocalVoiceRecord {
  id: string;
  quick: boolean;
  sectorId?: number;
  operationType?: OperationType;
  blob: Blob;
  mimeType: string;
  createdAt: string;
  status: RecordStatus;
  lastError?: string;
}
