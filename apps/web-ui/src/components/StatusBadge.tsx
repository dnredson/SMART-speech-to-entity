import type { RecordStatus } from "../types";

const LABELS: Record<RecordStatus, string> = {
  LOCAL: "Aguardando envio",
  UPLOADING: "Enviando",
  PROCESSING: "Processando",
  NEEDS_REVIEW: "Precisa revisar",
  REGISTERED: "Registrado",
  ERROR: "Erro",
};

export function StatusBadge({ status }: { status: RecordStatus }) {
  return <span className={`status-badge status-${status.toLowerCase()}`}>{LABELS[status]}</span>;
}
