import { useMemo, useState } from "react";

import type { IrrigationEvent, LocalVoiceRecord, OperationType } from "../types";
import { StatusBadge } from "./StatusBadge";

const SECTORS = [1, 2, 3, 4, 5, 6, 7] as const;

type OperationFilter = "ALL" | OperationType;

function durationLabel(minutes: number | null): string {
  if (minutes === null) return "duração pendente";
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) return `${rest} min`;
  if (rest === 0) return `${hours} h`;
  return `${hours} h ${rest} min`;
}

function dateLabel(event: IrrigationEvent): string {
  if (event.start_date === null) return "Data pendente";
  const [year, month, day] = event.start_date.split("-");
  return `${day}/${month}/${year} · ${event.start_time ?? "--:--"}`;
}

function productLabel(event: IrrigationEvent): string | null {
  if (event.products.length === 0) return null;
  return event.products.map((product) => {
    const details = [
      product.kg_per_ha === null ? null : `${product.kg_per_ha} kg/ha`,
      product.solution_liters === null ? null : `${product.solution_liters} L`,
    ].filter(Boolean).join(" · ");
    return `${product.name ?? "Produto pendente"}${details ? ` · ${details}` : ""}`;
  }).join(" | ");
}

function queueLabel(record: LocalVoiceRecord): string {
  if (record.status === "UPLOADING") return "Enviando áudio…";
  if (record.status === "PROCESSING") return "Processando registro…";
  if (record.status === "ERROR") return "Falha no processamento. O áudio continua salvo neste dispositivo.";
  if (record.status === "NEEDS_REVIEW") return "O registro precisa ser tentado novamente ou descartado.";
  return "Aguardando processamento/sincronização";
}

export function HistoryScreen({
  events,
  localQueue,
  online,
  onRetry,
  onDiscard,
}: {
  events: IrrigationEvent[];
  localQueue: LocalVoiceRecord[];
  online: boolean;
  onRetry: (record: LocalVoiceRecord) => Promise<void>;
  onDiscard: (record: LocalVoiceRecord) => Promise<void>;
}) {
  const [sector, setSector] = useState<number | "ALL">("ALL");
  const [operation, setOperation] = useState<OperationFilter>("ALL");

  const filtered = useMemo(() => events.filter((event) => {
    if (sector !== "ALL" && event.sector_id !== sector) return false;
    if (operation !== "ALL" && event.operation_type !== operation) return false;
    return true;
  }), [events, sector, operation]);

  const sectorSummary = useMemo(() => SECTORS.map((sectorId) => {
    const sectorEvents = events.filter((event) => event.sector_id === sectorId);
    const totalMinutes = sectorEvents.reduce((sum, event) => sum + (event.duration_minutes ?? 0), 0);
    return {
      sectorId,
      count: sectorEvents.length,
      totalMinutes,
      last: sectorEvents[0] ?? null,
    };
  }), [events]);

  return (
    <>
      <section className="hero compact-hero">
        <p className="eyebrow">Histórico</p>
        <h1>Irrigações registradas</h1>
        <p>Consulte por setor e tipo de operação.</p>
      </section>

      {localQueue.length > 0 && (
        <section className="history-section pending-panel">
          <div className="section-heading">
            <div><p className="eyebrow">Sincronização</p><h2>Registros pendentes</h2></div>
            <span className="pending-count">{localQueue.length}</span>
          </div>
          <div className="history-list">
            {localQueue.map((record) => {
              const busy = record.status === "UPLOADING" || record.status === "PROCESSING";
              return (
                <article className="history-item pending-history-item" key={record.id}>
                  <div className="history-icon leaf" aria-hidden="true">●</div>
                  <div className="history-copy">
                    <strong>{record.quick ? "Registro rápido por voz" : `Setor ${record.sectorId ?? "--"}`}</strong>
                    <span>{queueLabel(record)}</span>
                    {record.lastError && <small className="history-missing">{record.lastError}</small>}
                    <div className="queue-actions">
                      <button
                        type="button"
                        className="queue-action retry"
                        disabled={!online || busy}
                        onClick={() => void onRetry(record)}
                      >
                        {busy ? "Processando…" : "Tentar novamente"}
                      </button>
                      <button
                        type="button"
                        className="queue-action discard"
                        disabled={busy}
                        onClick={() => void onDiscard(record)}
                      >
                        Descartar
                      </button>
                    </div>
                    {!online && <small className="queue-offline-note">Conecte-se à internet para tentar novamente.</small>}
                  </div>
                  <StatusBadge status={record.status} />
                </article>
              );
            })}
          </div>
        </section>
      )}

      <section className="sector-summary-grid" aria-label="Resumo por setor">
        {sectorSummary.map((item) => (
          <button
            key={item.sectorId}
            type="button"
            className={`sector-summary-card${sector === item.sectorId ? " selected" : ""}`}
            onClick={() => setSector(sector === item.sectorId ? "ALL" : item.sectorId)}
          >
            <span>Setor {String(item.sectorId).padStart(2, "0")}</span>
            <strong>{item.count} registro{item.count === 1 ? "" : "s"}</strong>
            <small>{durationLabel(item.totalMinutes)}</small>
          </button>
        ))}
      </section>

      <section className="history-section full-history">
        <div className="history-filters">
          <label className="field">
            <span>Setor</span>
            <select value={sector} onChange={(event) => setSector(event.target.value === "ALL" ? "ALL" : Number(event.target.value))}>
              <option value="ALL">Todos</option>
              {SECTORS.map((item) => <option key={item} value={item}>Setor {String(item).padStart(2, "0")}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Operação</span>
            <select value={operation} onChange={(event) => setOperation(event.target.value as OperationFilter)}>
              <option value="ALL">Todas</option>
              <option value="IRRIGATION">Irrigação</option>
              <option value="FERTIGATION">Fertirrigação</option>
            </select>
          </label>
        </div>

        <div className="section-heading history-total">
          <div><p className="eyebrow">Registros</p><h2>{filtered.length} encontrado{filtered.length === 1 ? "" : "s"}</h2></div>
        </div>

        {filtered.length === 0 ? (
          <div className="empty-state"><strong>Nenhum registro encontrado.</strong><span>Altere os filtros ou faça um novo registro.</span></div>
        ) : (
          <div className="history-list">
            {filtered.map((item) => (
              <article className="history-item" key={item.id}>
                <div className={`history-icon ${item.operation_type === "IRRIGATION" ? "water" : "leaf"}`} aria-hidden="true">{item.operation_type === "IRRIGATION" ? "●" : "◆"}</div>
                <div className="history-copy">
                  <strong>Setor {String(item.sector_id).padStart(2, "0")} · {item.operation_type === "IRRIGATION" ? "Irrigação" : "Fertirrigação"}</strong>
                  <span>{dateLabel(item)} · {durationLabel(item.duration_minutes)}</span>
                  {productLabel(item) && <small className="history-details">{productLabel(item)}</small>}
                  {item.transcript && <small>“{item.transcript}”</small>}
                  {item.missing_fields && item.missing_fields.length > 0 && <small className="history-missing">Faltando: {item.missing_fields.join(", ")}</small>}
                </div>
                <StatusBadge status={item.status} />
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
