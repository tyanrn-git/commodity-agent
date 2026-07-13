"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiClient, OpportunitySpecValue, ProductResolution } from "@/lib/api";
import { styles } from "@/lib/styles";

type Props = {
  opportunityId: string;
  initialRoughName?: string | null;
  onResolved?: () => void;
};

function formatSpecValue(spec: OpportunitySpecValue): string {
  if (spec.value_text) return spec.value_text;
  if (spec.value_min && spec.value_max) {
    const unit = spec.unit ? ` ${spec.unit}` : "";
    return `${spec.value_min}–${spec.value_max}${unit}`;
  }
  if (spec.value_min) return `${spec.value_min}${spec.unit ? ` ${spec.unit}` : ""}`;
  return "—";
}

export function ProductResolutionPanel({ opportunityId, initialRoughName, onResolved }: Props) {
  const [roughName, setRoughName] = useState(initialRoughName || "");
  const [sourceText, setSourceText] = useState("");
  const [resolution, setResolution] = useState<ProductResolution | null>(null);
  const [specValues, setSpecValues] = useState<OpportunitySpecValue[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function loadSpecs() {
    const listed = await apiClient.listSpecValues(opportunityId);
    setSpecValues(listed);
  }

  useEffect(() => {
    loadSpecs().catch(() => {});
  }, [opportunityId]);

  useEffect(() => {
    if (initialRoughName) setRoughName(initialRoughName);
  }, [initialRoughName]);

  async function onResolve(event: FormEvent, createIfMissing = false) {
    event.preventDefault();
    if (!roughName.trim()) return;
    setBusy(true);
    setMessage("");
    try {
      const result = await apiClient.resolveProduct(opportunityId, {
        rough_product_name: roughName.trim(),
        source_text: sourceText.trim() || undefined,
        create_if_missing: createIfMissing,
      });
      setResolution(result);
      setSpecValues(result.spec_values);
      if (result.product_created && result.normalized_product_name) {
        setMessage(`Товар автоматически добавлен в каталог: ${result.normalized_product_name}`);
      } else if (result.matched && result.normalized_product_name) {
        setMessage(`Определён продукт: ${result.normalized_product_name}`);
      } else {
        setMessage(`«${result.rough_product_name}» не найден в каталоге — можно добавить через AI`);
      }
      onResolved?.();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка AI-разрешения");
    } finally {
      setBusy(false);
    }
  }

  async function onCreateInCatalog(event: FormEvent) {
    await onResolve(event, true);
  }

  async function onConfirmSpec(specId: string) {
    setBusy(true);
    setMessage("");
    try {
      const confirmed = await apiClient.confirmSpecValue(specId);
      setSpecValues((prev) => prev.map((s) => (s.id === confirmed.id ? confirmed : s)));
      setMessage(`Подтверждено: ${confirmed.parameter_name}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка подтверждения");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={styles.card}>
      <h2 style={{ marginTop: 0 }}>AI: уточнение продукта</h2>
      <p style={{ fontSize: 13, color: "#64748b" }}>
        Введите примерное описание — система сама сопоставит с каталогом или создаст товар и начнёт
        заполнять спецификацию из контекста.
      </p>
      <form onSubmit={(e) => onResolve(e, false)}>
        <label style={styles.label}>Примерное название</label>
        <input
          style={styles.input}
          value={roughName}
          onChange={(e) => setRoughName(e.target.value)}
          placeholder="base oil group II SN500"
          required
        />
        <label style={styles.label}>Доп. текст (опционально)</label>
        <textarea
          style={{ ...styles.input, minHeight: 72, resize: "vertical" }}
          value={sourceText}
          onChange={(e) => setSourceText(e.target.value)}
          placeholder="Фрагмент RFQ, email или спецификации..."
        />
        <button style={styles.button} type="submit" disabled={busy || !roughName.trim()}>
          {busy ? "Обработка..." : "Разрешить продукт (AI)"}
        </button>
      </form>

      {resolution ? (
        <div style={{ marginTop: 16, fontSize: 14 }}>
          {!resolution.matched && resolution.proposed_new_product ? (
            <div
              style={{
                background: "#eff6ff",
                border: "1px solid #bfdbfe",
                borderRadius: 8,
                padding: 12,
                marginBottom: 12,
              }}
            >
              <strong style={{ color: "#1e40af" }}>AI предлагает добавить в каталог</strong>
              <p style={{ margin: "8px 0 0", color: "#1e3a8a" }}>
                <strong>{resolution.proposed_new_product.normalized_name}</strong> ·{" "}
                {resolution.proposed_new_product.category}
              </p>
              {resolution.proposed_new_product.reasoning ? (
                <p style={{ margin: "8px 0 0", fontSize: 13, color: "#475569" }}>
                  {resolution.proposed_new_product.reasoning}
                </p>
              ) : null}
              {resolution.proposed_new_product.parameters.length > 0 ? (
                <ul style={{ margin: "8px 0 0", fontSize: 13, color: "#334155" }}>
                  {resolution.proposed_new_product.parameters.map((param) => (
                    <li key={param.parameter_name}>
                      {param.parameter_name}
                      {param.unit ? ` (${param.unit})` : ""}
                      {param.is_mandatory ? " *" : ""}
                      {param.minimum_value || param.maximum_value
                        ? ` · ${param.minimum_value ?? "—"} – ${param.maximum_value ?? "—"}`
                        : " · без значений"}
                    </li>
                  ))}
                </ul>
              ) : (
                <p style={{ margin: "8px 0 0", fontSize: 13, color: "#64748b" }}>
                  Спецификация пока пустая — заполнится из RFQ и предложений
                </p>
              )}
              <button
                style={{ ...styles.button, marginTop: 12 }}
                onClick={onCreateInCatalog}
                disabled={busy}
                type="button"
              >
                Добавить в каталог (AI)
              </button>
            </div>
          ) : null}
          {!resolution.matched && !resolution.proposed_new_product ? (
            <div
              style={{
                background: "#fff7ed",
                border: "1px solid #fed7aa",
                borderRadius: 8,
                padding: 12,
                marginBottom: 12,
              }}
            >
              <strong style={{ color: "#9a3412" }}>Совпадение в каталоге не найдено</strong>
              <p style={{ margin: "8px 0 0", color: "#7c2d12" }}>
                Ваше описание: <strong>{resolution.rough_product_name}</strong>
              </p>
              {resolution.catalog_products.length > 0 ? (
                <p style={{ margin: "8px 0 0", color: "#7c2d12", fontSize: 13 }}>
                  В каталоге: {resolution.catalog_products.join(", ")}.
                </p>
              ) : null}
            </div>
          ) : null}
          <p>
            <strong>Нормализованный продукт:</strong>{" "}
            {resolution.matched && resolution.normalized_product_name
              ? resolution.normalized_product_name
              : "не определён"}
            {resolution.confidence > 0
              ? ` · уверенность ${Math.round(resolution.confidence * 100)}%`
              : " · уверенность 0%"}
          </p>
          {resolution.reasoning ? (
            <p style={{ color: "#64748b" }}>{resolution.reasoning}</p>
          ) : null}
          {resolution.missing_mandatory?.length ? (
            <p style={{ color: "#b45309" }}>
              Обязательные параметры не найдены: {resolution.missing_mandatory.join(", ")}
            </p>
          ) : null}
          <p style={{ fontSize: 12, color: "#94a3b8" }}>
            Модель: {resolution.ai_model} · стоимость: ${resolution.ai_cost_usd}
          </p>
        </div>
      ) : null}

      {specValues.length > 0 ? (
        <div style={{ marginTop: 16 }}>
          <h3 style={{ marginTop: 0, fontSize: 15 }}>Характеристики</h3>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {specValues.map((spec) => (
              <li
                key={spec.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "8px 0",
                  borderBottom: "1px solid #e2e8f0",
                  flexWrap: "wrap",
                }}
              >
                <span style={{ minWidth: 180 }}>
                  <strong>{spec.parameter_name}</strong>
                  {spec.is_mandatory ? " *" : ""}
                </span>
                <span>{formatSpecValue(spec)}</span>
                <span
                  style={{
                    fontSize: 12,
                    color: spec.status === "CONFIRMED" ? "#15803d" : "#64748b",
                  }}
                >
                  {spec.status}
                </span>
                {!spec.user_confirmed ? (
                  <button
                    style={styles.secondaryButton}
                    onClick={() => onConfirmSpec(spec.id)}
                    disabled={busy}
                  >
                    Подтвердить
                  </button>
                ) : (
                  <span style={{ fontSize: 12, color: "#15803d" }}>✓ подтверждено</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {message ? <p style={{ marginTop: 12 }}>{message}</p> : null}
    </div>
  );
}
