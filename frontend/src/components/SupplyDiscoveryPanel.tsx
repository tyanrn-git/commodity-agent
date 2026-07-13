"use client";

import { useState } from "react";
import { apiClient, Opportunity } from "@/lib/api";
import { styles } from "@/lib/styles";

type Props = {
  opportunity: Opportunity;
  onUpdated: () => void;
  onAgentActivity?: () => void;
};

export function SupplyDiscoveryPanel({ opportunity, onUpdated, onAgentActivity }: Props) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const economics = opportunity.indicative_economics || {};
  const hasSupplyEstimate = economics.source === "supply_discovery_ai";

  async function onDiscover() {
    setBusy(true);
    setMessage("");
    try {
      const result = await apiClient.runSupplyDiscovery(opportunity.id);
      setMessage(
        `${result.summary}` +
          (result.economics_preview ? ` · ${result.economics_preview}` : "") +
          (result.supplier_hint ? ` · ${result.supplier_hint}` : "")
      );
      onUpdated();
      onAgentActivity?.();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка поиска поставщика");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={styles.card}>
      <h2 style={{ marginTop: 0 }}>Supply Discovery</h2>
      <p style={{ fontSize: 13, color: "#64748b", marginTop: 0 }}>
        Отдельный AI-агент оценивает поставщика и предварительную экономику (ESTIMATED). Не влияет на
        квалификацию тендера.
      </p>
      {hasSupplyEstimate ? (
        <div style={{ fontSize: 14, marginBottom: 12 }}>
          <div>
            Поставщик: <strong>{String(economics.seller_name || "—")}</strong>
          </div>
          {economics.gross_margin != null ? (
            <div style={{ color: "#166534", marginTop: 4 }}>
              Маржа {String(economics.gross_margin)}{" "}
              {String(economics.margin_currency || economics.costs_currency || "USD")}
              {economics.gross_margin_percent != null ? ` (${economics.gross_margin_percent}%)` : ""}
            </div>
          ) : null}
          {economics.feasibility_summary ? (
            <div style={{ color: "#64748b", marginTop: 6, fontSize: 13 }}>{String(economics.feasibility_summary)}</div>
          ) : null}
        </div>
      ) : economics.source === "tender_qualification" ? (
        <p style={{ fontSize: 13, color: "#64748b" }}>Экономика ещё не оценена — запустите Supply Discovery.</p>
      ) : null}
      <button style={styles.button} onClick={onDiscover} disabled={busy}>
        {busy ? "AI ищет поставщика..." : hasSupplyEstimate ? "Обновить оценку" : "Найти поставщика (AI)"}
      </button>
      {message ? <p style={{ marginTop: 12, fontSize: 14 }}>{message}</p> : null}
    </div>
  );
}
