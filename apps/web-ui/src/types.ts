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
  created_at: string;
}

export interface LocalVoiceRecord {
  id: string;
  sectorId: number;
  operationType: OperationType;
  blob: Blob;
  mimeType: string;
  createdAt: string;
  status: RecordStatus;
  lastError?: string;
}
