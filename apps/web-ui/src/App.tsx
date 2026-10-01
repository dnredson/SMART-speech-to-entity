import { useCallback, useEffect, useMemo, useState } from "react";

import { HistoryScreen } from "./components/HistoryScreen";
import { ManualForm } from "./components/ManualForm";
import { StatusBadge } from "./components/StatusBadge";
import { VoiceRecorder } from "./components/VoiceRecorder";
import { createManualEvent, listEvents, processVoice } from "./lib/api";
import { deleteVoiceRecord, listVoiceRecords, putVoiceRecord } from "./lib/idb";
import type { IrrigationEvent, LocalVoiceRecord, OperationType, RecordStatus } from "./types";

const SECTORS = [1, 2, 3, 4, 5, 6, 7] as const;

type Mode = "voice" | "manual";
type View = "register" | "history";

function localIsoWithOffset(date = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absoluteOffset = Math.abs(offsetMinutes);
  const offsetHours = Math.floor(absoluteOffset / 60);
  const offsetRemainder = absoluteOffset % 60;
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
    + `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
    + `${sign}${pad(offsetHours)}:${pad(offsetRemainder)}`;
}

function formatEventDate(event: IrrigationEvent): string {
  if (event.start_date === null) return "Data pendente";
  const [year, month, day] = event.start_date.split("-");
  return `${day}/${month}/${year} · ${event.start_time ?? "--:--"}`;
}

function durationLabel(minutes: number | null): string {
  if (minutes === null) return "duração pendente";
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) return `${rest} min`;
  if (rest === 0) return `${hours} h`;
  return `${hours} h ${rest} min`;
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

export function App() {
  const [view, setView] = useState<View>("register");
  const [guidedOpen, setGuidedOpen] = useState(false);
  const [operation, setOperation] = useState<OperationType | null>(null);
  const [sector, setSector] = useState<number | null>(null);
  const [mode, setMode] = useState<Mode>("voice");
  const [online, setOnline] = useState(navigator.onLine);
  const [events, setEvents] = useState<IrrigationEvent[]>([]);
  const [localQueue, setLocalQueue] = useState<LocalVoiceRecord[]>([]);
  const [notice, setNotice] = useState<string | null>(null);

  const contextReady = operation !== null && sector !== null;
  const pendingCount = localQueue.length;

  const refreshQueue = useCallback(async () => {
    setLocalQueue(await listVoiceRecords());
  }, []);

  const refreshEvents = useCallback(async () => {
    if (!navigator.onLine) return;
    try {
      setEvents(await listEvents(200));
    } catch {
      // Offline-first: histórico remoto indisponível não bloqueia o registro.
    }
  }, []);

  const uploadRecord = useCallback(async (record: LocalVoiceRecord) => {
    if (!navigator.onLine) return;
    const uploading = { ...record, status: "UPLOADING" as RecordStatus, lastError: undefined };
    await putVoiceRecord(uploading);
    await refreshQueue();

    try {
      const processing = { ...uploading, status: "PROCESSING" as RecordStatus };
      await putVoiceRecord(processing);
      await refreshQueue();
      const parsed = await processVoice({
        id: record.id,
        quick: record.quick,
        sectorId: record.sectorId,
        operationType: record.operationType,
        blob: record.blob,
        mimeType: record.mimeType,
        createdAt: record.createdAt,
      });
      await deleteVoiceRecord(record.id);
      setEvents((current) => [parsed, ...current.filter((item) => item.id !== parsed.id)]);
      await refreshQueue();
      setNotice(parsed.status === "NEEDS_REVIEW" ? "Registro salvo, mas falta revisar uma informação." : `Registrado: Setor ${String(parsed.sector_id).padStart(2, "0")} · ${parsed.operation_type === "IRRIGATION" ? "Irrigação" : "Fertirrigação"}.`);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Falha ao enviar.";
      await putVoiceRecord({
        ...record,
        status: message.includes("identificar setor") ? "NEEDS_REVIEW" : "ERROR",
        lastError: message,
      });
      await refreshQueue();
      setNotice(message);
    }
  }, [refreshQueue]);

  const syncQueue = useCallback(async () => {
    if (!navigator.onLine) return;
    const queued = await listVoiceRecords();
    for (const record of queued.filter((item) => item.status === "LOCAL" || item.status === "ERROR")) {
      await uploadRecord(record);
    }
  }, [uploadRecord]);

  useEffect(() => {
    void refreshQueue();
    void refreshEvents();

    const handleOnline = () => {
      setOnline(true);
      void refreshEvents();
      void syncQueue();
    };
    const handleOffline = () => setOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [refreshEvents, refreshQueue, syncQueue]);

  const recentItems = useMemo(
    () => [...events].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 3),
    [events],
  );

  async function saveVoiceRecord(blob: Blob, mimeType: string, quick: boolean) {
    const record: LocalVoiceRecord = {
      id: crypto.randomUUID(),
      quick,
      sectorId: quick ? undefined : sector ?? undefined,
      operationType: quick ? undefined : operation ?? undefined,
      blob,
      mimeType,
      createdAt: localIsoWithOffset(),
      status: "LOCAL",
    };
    await putVoiceRecord(record);
    await refreshQueue();
    setNotice(online ? "Áudio salvo. Processando…" : "Áudio salvo no dispositivo. Será enviado quando a conexão voltar.");
    if (online) await uploadRecord(record);
  }

  async function handleQuickRecorded(blob: Blob, mimeType: string) {
    await saveVoiceRecord(blob, mimeType, true);
  }

  async function handleGuidedRecorded(blob: Blob, mimeType: string) {
    if (!contextReady) return;
    await saveVoiceRecord(blob, mimeType, false);
  }

  async function handleManual(input: {
    start_date: string;
    start_time: string;
    duration_minutes: number;
    product_name?: string;
    kg_per_ha?: number | null;
    solution_liters?: number | null;
  }) {
    if (sector === null || operation === null) return;
    if (!navigator.onLine) throw new Error("O formulário manual desta versão exige conexão.");
    const created = await createManualEvent({
      sector_id: sector,
      operation_type: operation,
      ...input,
    });
    setEvents((current) => [created, ...current]);
    setNotice("Registro salvo.");
  }

  function resetContext() {
    setSector(null);
    setOperation(null);
    setMode("voice");
    setNotice(null);
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark"><img src="/bot.svg" alt="" /></span>
          <span><strong>SMART</strong><small>Irrigação e fertirrigação</small></span>
        </div>
        <div className="topbar-actions">
          <span className={`connectivity ${online ? "online" : "offline"}`}>{online ? "Online" : "Sem internet"}</span>
        </div>
      </header>

      <nav className="app-nav" aria-label="Navegação principal">
        <button type="button" className={view === "register" ? "active" : ""} onClick={() => setView("register")}>Registrar</button>
        <button type="button" className={view === "history" ? "active" : ""} onClick={() => { setView("history"); void refreshEvents(); }}>Histórico{pendingCount > 0 ? ` (${pendingCount})` : ""}</button>
      </nav>

      <main className="page">
        {view === "history" ? (
          <HistoryScreen events={events} localQueue={localQueue} />
        ) : (
          <>
            <section className="hero">
              <p className="eyebrow">Registro rápido em campo</p>
              <h1>É só falar.</h1>
              <p>Diga o setor, o que foi feito, o horário e a duração. O SMART organiza o registro para você.</p>
            </section>

            <section className="quick-voice-card">
              <div className="quick-badge">Mais rápido</div>
              <h2>Registro completo por voz</h2>
              <p className="quick-example">Exemplo: “Hoje irriguei o setor 7 às 21 horas durante duas horas.”</p>
              <VoiceRecorder
                onRecorded={handleQuickRecorded}
                hint="Inclua o setor e diga se foi irrigação ou fertirrigação. Na fertirrigação, fale também produto, kg/ha e litros de solução."
              />
              {notice !== null && <div className="notice" role="status">{notice}</div>}
            </section>

            <button className="btn btn-stretch guided-toggle" type="button" onClick={() => setGuidedOpen((value) => !value)}>
              {guidedOpen ? "Ocultar preenchimento guiado" : "Prefiro selecionar setor e operação"}
            </button>

            {guidedOpen && (
              <div className="guided-flow">
                <section className="step-card" aria-labelledby="step-operation">
                  <div className="step-heading"><span>1</span><div><h2 id="step-operation">Operação</h2><p>Escolha uma opção</p></div></div>
                  <div className="operation-grid">
                    <button type="button" className={`operation-card${operation === "IRRIGATION" ? " selected" : ""}`} onClick={() => setOperation("IRRIGATION")}>
                      <span className="operation-icon water" aria-hidden="true">●</span><span><strong>Irrigação</strong><small>Somente aplicação de água</small></span>
                    </button>
                    <button type="button" className={`operation-card${operation === "FERTIGATION" ? " selected" : ""}`} onClick={() => setOperation("FERTIGATION")}>
                      <span className="operation-icon leaf" aria-hidden="true">◆</span><span><strong>Fertirrigação</strong><small>Água + nutrientes</small></span>
                    </button>
                  </div>
                </section>

                <section className={`step-card${operation === null ? " muted-step" : ""}`} aria-labelledby="step-sector">
                  <div className="step-heading"><span>2</span><div><h2 id="step-sector">Setor</h2><p>Qual setor recebeu a operação?</p></div></div>
                  <div className="sector-grid">
                    {SECTORS.map((item) => (
                      <button key={item} type="button" disabled={operation === null} className={`sector-button${sector === item ? " selected" : ""}`} onClick={() => setSector(item)}>
                        <span>Setor</span><strong>{String(item).padStart(2, "0")}</strong>
                      </button>
                    ))}
                  </div>
                </section>

                <section className={`step-card register-card${!contextReady ? " muted-step" : ""}`} aria-labelledby="step-register">
                  <div className="step-heading"><span>3</span><div><h2 id="step-register">Registrar</h2><p>{contextReady ? `Setor ${sector} · ${operation === "IRRIGATION" ? "Irrigação" : "Fertirrigação"}` : "Escolha operação e setor primeiro"}</p></div></div>
                  <div className="mode-switch" role="tablist" aria-label="Forma de registro">
                    <button type="button" role="tab" aria-selected={mode === "voice"} disabled={!contextReady} onClick={() => setMode("voice")}>Por voz</button>
                    <button type="button" role="tab" aria-selected={mode === "manual"} disabled={!contextReady} onClick={() => setMode("manual")}>Preencher</button>
                  </div>
                  {mode === "voice"
                    ? <VoiceRecorder disabled={!contextReady} onRecorded={handleGuidedRecorded} />
                    : sector !== null && operation !== null && <ManualForm sectorId={sector} operationType={operation} onSubmit={handleManual} />}
                  {contextReady && <button className="btn btn-tertiary reset-button" type="button" onClick={resetContext}>Trocar operação ou setor</button>}
                </section>
              </div>
            )}

            <section className="history-section compact-history">
              <div className="section-heading">
                <div><p className="eyebrow">Acompanhamento</p><h2>Últimos registros</h2></div>
                <button className="text-button" type="button" onClick={() => setView("history")}>Ver histórico</button>
              </div>
              {recentItems.length === 0 ? (
                <div className="empty-state"><strong>Nenhum registro ainda.</strong><span>Os registros aparecerão aqui depois do primeiro envio.</span></div>
              ) : (
                <div className="history-list">
                  {recentItems.map((item) => (
                    <article className="history-item" key={item.id}>
                      <div className={`history-icon ${item.operation_type === "IRRIGATION" ? "water" : "leaf"}`} aria-hidden="true">{item.operation_type === "IRRIGATION" ? "●" : "◆"}</div>
                      <div className="history-copy">
                        <strong>Setor {String(item.sector_id).padStart(2, "0")} · {item.operation_type === "IRRIGATION" ? "Irrigação" : "Fertirrigação"}</strong>
                        <span>{formatEventDate(item)} · {durationLabel(item.duration_minutes)}</span>
                        {productLabel(item) && <small className="history-details">{productLabel(item)}</small>}
                        {item.transcript && <small>“{item.transcript}”</small>}
                      </div>
                      <StatusBadge status={item.status} />
                    </article>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </main>

      <footer className="app-footer">SMART · Agricultura sustentável e tecnologia</footer>
    </div>
  );
}
