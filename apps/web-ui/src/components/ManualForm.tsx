import { useMemo, useState, type FormEvent } from "react";

import type { OperationType } from "../types";

interface ManualFormProps {
  sectorId: number;
  operationType: OperationType;
  onSubmit: (value: {
    start_date: string;
    start_time: string;
    duration_minutes: number;
    product_name?: string;
    kg_per_ha?: number | null;
    solution_liters?: number | null;
  }) => Promise<void>;
}

function today(): string {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function ManualForm({ sectorId, operationType, onSubmit }: ManualFormProps) {
  const now = useMemo(() => new Date(), []);
  const [date, setDate] = useState(today());
  const [time, setTime] = useState(`${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`);
  const [hours, setHours] = useState("1");
  const [minutes, setMinutes] = useState("0");
  const [product, setProduct] = useState("");
  const [kgHa, setKgHa] = useState("");
  const [solutionLiters, setSolutionLiters] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const duration = Math.max(0, Number(hours) * 60 + Number(minutes));
    if (duration <= 0) {
      setError("Informe uma duração maior que zero.");
      return;
    }
    if (operationType === "FERTIGATION" && product.trim() === "") {
      setError("Informe o produto ou nutriente utilizado.");
      return;
    }
    if (operationType === "FERTIGATION" && kgHa.trim() === "") {
      setError("Informe a dose em kg/ha.");
      return;
    }
    if (operationType === "FERTIGATION" && solutionLiters.trim() === "") {
      setError("Informe os litros de solução.");
      return;
    }

    try {
      setSaving(true);
      await onSubmit({
        start_date: date,
        start_time: time,
        duration_minutes: duration,
        ...(operationType === "FERTIGATION"
          ? {
              product_name: product.trim(),
              kg_per_ha: kgHa === "" ? null : Number(kgHa.replace(",", ".")),
              solution_liters: solutionLiters === "" ? null : Number(solutionLiters.replace(",", ".")),
            }
          : {}),
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível salvar.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="manual-form" onSubmit={(event) => void submit(event)}>
      <div className="form-context">Setor {sectorId} · {operationType === "IRRIGATION" ? "Irrigação" : "Fertirrigação"}</div>
      <div className="form-grid">
        <label className="field">
          <span>Data</span>
          <input type="date" value={date} onChange={(event) => setDate(event.target.value)} required />
        </label>
        <label className="field">
          <span>Hora de início</span>
          <input type="time" value={time} onChange={(event) => setTime(event.target.value)} required />
        </label>
      </div>
      <fieldset className="duration-fieldset">
        <legend>Duração</legend>
        <div className="duration-row">
          <label className="field"><span>Horas</span><input inputMode="numeric" min="0" type="number" value={hours} onChange={(event) => setHours(event.target.value)} /></label>
          <label className="field"><span>Minutos</span><input inputMode="numeric" min="0" max="59" type="number" value={minutes} onChange={(event) => setMinutes(event.target.value)} /></label>
        </div>
      </fieldset>
      {operationType === "FERTIGATION" && (
        <div className="fertigation-fields">
          <label className="field field-wide"><span>Produto / nutriente</span><input type="text" value={product} onChange={(event) => setProduct(event.target.value)} placeholder="Ex.: nitrato de cálcio" /></label>
          <div className="form-grid">
            <label className="field"><span>kg/ha</span><input inputMode="decimal" type="text" value={kgHa} onChange={(event) => setKgHa(event.target.value)} placeholder="Ex.: 3" required /></label>
            <label className="field"><span>Litros de solução</span><input inputMode="decimal" type="text" value={solutionLiters} onChange={(event) => setSolutionLiters(event.target.value)} placeholder="Ex.: 20" required /></label>
          </div>
        </div>
      )}
      {error !== null && <p className="form-error">{error}</p>}
      <button className="btn btn-primary btn-stretch btn-large" type="submit" disabled={saving}>{saving ? "Salvando…" : "Salvar registro"}</button>
    </form>
  );
}
