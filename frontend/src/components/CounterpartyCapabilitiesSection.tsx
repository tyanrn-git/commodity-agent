"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient, CounterpartyCapability } from "@/lib/api";
import { capabilityTypeLabel } from "@/lib/counterpartyLabels";
import { styles } from "@/lib/styles";

type Props = {
  counterpartyId: string;
  refreshKey?: number;
};

function groupCapabilities(items: CounterpartyCapability[]) {
  const products = items.filter((item) => item.capability_type === "PRODUCT");
  const services = items.filter((item) => item.capability_type !== "PRODUCT");
  return { products, services };
}

export function CounterpartyCapabilitiesSection({ counterpartyId, refreshKey = 0 }: Props) {
  const [capabilities, setCapabilities] = useState<CounterpartyCapability[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const caps = await apiClient.listCounterpartyCapabilities(counterpartyId);
    setCapabilities(caps);
  }, [counterpartyId]);

  useEffect(() => {
    load().catch(() => {});
  }, [load, refreshKey]);

  async function onConfirmCapability(capabilityId: string) {
    setBusy(true);
    setMessage("");
    try {
      const confirmed = await apiClient.confirmCounterpartyCapability(capabilityId);
      setCapabilities((prev) => prev.map((item) => (item.id === confirmed.id ? confirmed : item)));
      setMessage(`Подтверждено: ${confirmed.title}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка подтверждения");
    } finally {
      setBusy(false);
    }
  }

  function renderList(items: CounterpartyCapability[], emptyLabel: string) {
    if (items.length === 0) {
      return <p style={{ color: "#64748b", fontSize: 14 }}>{emptyLabel}</p>;
    }
    return (
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {items.map((cap) => (
          <li
            key={cap.id}
            style={{
              padding: "12px 0",
              borderBottom: "1px solid #e2e8f0",
            }}
          >
            <div>
              <strong>{cap.title}</strong>
              <span style={{ fontSize: 13, color: "#64748b", marginLeft: 8 }}>
                {capabilityTypeLabel(cap.capability_type)}
              </span>
              {cap.rough_product_name ? (
                <span style={{ fontSize: 13, color: "#64748b" }}> · {cap.rough_product_name}</span>
              ) : null}
            </div>
            {cap.regions?.length ? (
              <div style={{ fontSize: 13, color: "#64748b" }}>Регионы: {cap.regions.join(", ")}</div>
            ) : null}
            {cap.routes?.length ? (
              <div style={{ fontSize: 13, color: "#64748b" }}>Маршруты: {cap.routes.join(", ")}</div>
            ) : null}
            {cap.incoterms?.length ? (
              <div style={{ fontSize: 13, color: "#64748b" }}>Incoterms: {cap.incoterms.join(", ")}</div>
            ) : null}
            {cap.evidence_excerpt ? (
              <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 4 }}>«{cap.evidence_excerpt}»</div>
            ) : null}
            <div style={{ marginTop: 6 }}>
              {cap.user_confirmed ? (
                <span style={{ fontSize: 12, color: "#15803d" }}>✓ подтверждено</span>
              ) : (
                <button
                  style={styles.secondaryButton}
                  onClick={() => onConfirmCapability(cap.id)}
                  disabled={busy}
                >
                  Подтвердить
                </button>
              )}
              {cap.extracted_by_ai ? (
                <span style={{ fontSize: 12, color: "#64748b", marginLeft: 8 }}>AI</span>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    );
  }

  const { products, services } = groupCapabilities(capabilities);
  const confirmedCount = capabilities.filter((item) => item.user_confirmed).length;

  return (
    <div style={styles.card}>
      <h2 style={{ marginTop: 0 }}>Товары и услуги контрагента</h2>
      <p style={{ fontSize: 13, color: "#64748b" }}>
        Что контрагент предлагает: товары из каталога, фрахт, терминалы и другие услуги.
        Записи добавляются через AI-обогащение или вручную при разработке сделок.
      </p>
      <div style={{ fontSize: 13, color: "#334155", marginBottom: 16 }}>
        Всего: {capabilities.length} · подтверждено: {confirmedCount}
      </div>

      <h3 style={{ fontSize: 15, marginTop: 0 }}>Товары</h3>
      {renderList(products, "Товары не указаны")}

      <h3 style={{ fontSize: 15, marginTop: 24 }}>Услуги</h3>
      {renderList(services, "Услуги не указаны")}

      {message ? <p style={{ marginTop: 12 }}>{message}</p> : null}
    </div>
  );
}
