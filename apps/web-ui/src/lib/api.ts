import type { IrrigationEvent, OperationType } from "../types";

function detailMessage(body: unknown, fallback: string): string {
  if (typeof body !== "object" || body === null || !("detail" in body)) return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (typeof detail === "object" && detail !== null && "message" in detail) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  return fallback;
}

export async function listEvents(): Promise<IrrigationEvent[]> {
  const response = await fetch("/api/v1/events?limit=50");
  if (!response.ok) {
    throw new Error(`Falha ao carregar histórico (${response.status}).`);
  }
  return (await response.json()) as IrrigationEvent[];
}

export async function createManualEvent(input: {
  sector_id: number;
  operation_type: OperationType;
  start_date: string;
  start_time: string;
  duration_minutes: number;
  product_name?: string;
  kg_per_ha?: number | null;
  solution_liters?: number | null;
}): Promise<IrrigationEvent> {
  const response = await fetch("/api/v1/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as unknown;
    throw new Error(detailMessage(body, `Falha ao salvar registro (${response.status}).`));
  }
  return (await response.json()) as IrrigationEvent;
}

export async function processVoice(input: {
  id: string;
  sectorId: number;
  operationType: OperationType;
  blob: Blob;
  mimeType: string;
  createdAt: string;
}): Promise<IrrigationEvent> {
  const extension = input.mimeType.includes("ogg") ? "ogg" : input.mimeType.includes("mp4") ? "m4a" : "webm";
  const form = new FormData();
  form.append("sector_id", String(input.sectorId));
  form.append("operation_type", input.operationType);
  form.append("recorded_at", input.createdAt);
  form.append("client_record_id", input.id);
  form.append("audio", input.blob, `${input.id}.${extension}`);

  const response = await fetch("/api/v1/voice/process", { method: "POST", body: form });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as unknown;
    throw new Error(detailMessage(body, `Falha no processamento (${response.status}).`));
  }
  return (await response.json()) as IrrigationEvent;
}
