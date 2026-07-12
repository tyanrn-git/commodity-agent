"use client";

import { useEffect, useState } from "react";
import { apiClient, SupplierLeadDetail, SupplierLeadMatch } from "@/lib/api";
import { styles } from "@/lib/styles";

type Props = {
  opportunityId: string;
};

export function SupplierLeadPanel({ opportunityId }: Props) {
  const [detail, setDetail] = useState<SupplierLeadDetail | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const data = await apiClient.getSupplierLeadDetail(opportunityId);
    setDetail(data);
  }

  useEffect(() => {
    load().catch((err) => setMessage(err instanceof Error ? err.message : "Ошибка загрузки"));
  }, [opportunityId]);

  async function runMatch() {
    setBusy(true);
    setMessage("");
    try {
      const matches = await apiClient.matchBuyerNeeds(opportunityId);
      setDetail((prev) => (prev ? { ...prev, matches } : prev));
      setMessage(`Найдено совпадений: ${matches.length}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка сопоставления");
    } finally {
      setBusy(false);
    }
  }

  async function onBuildRoute(match: SupplierLeadMatch) {
    setBusy(true);
    setMessage("");
    try {
      const updated = await apiClient.buildSupplierLeadRoute(match.id);
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              matches: prev.matches.map((m) => (m.id === updated.id ? updated : m)),
            }
          : prev
      );
      setMessage("Маршрут построен");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка маршрута");
    } finally {
      setBusy(false);
    }
  }

  async function onDraftOutreach(match: SupplierLeadMatch) {
    setBusy(true);
    setMessage("");
    try {
      const updated = await apiClient.draftSupplierLeadOutreach(match.id);
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              matches: prev.matches.map((m) => (m.id === updated.id ? updated : m)),
            }
          : prev
      );
      setMessage("Черновик обращения готов (без отправки)");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка черновика");
    } finally {
      setBusy(false);
    }
  }

  if (!detail) {
    return (
      <div style={styles.card}>
        <p>Загрузка supplier-led…</p>
      </div>
    );
  }

  const ctx = detail.context;
  const market = detail.market_comparison;

  return (
    <div style={styles.card}>
      <h2 style={{ marginTop: 0 }}>Supplier-led: сопоставление и outreach</h2>
      {message ? <p>{message}</p> : null}

      {ctx ? (
        <div style={{ fontSize: 14, marginBottom: 16 }}>
          <strong>Предложение поставщика:</strong>{" "}
          {ctx.unit_price ? `${ctx.unit_price} ${ctx.currency || "USD"}` : "цена не указана"}
          {ctx.incoterm ? ` · ${ctx.incoterm}` : ""}
          {ctx.origin ? ` · ${ctx.origin}` : ""}
          {ctx.supplier_hint ? ` · ${ctx.supplier_hint}` : ""}
        </div>
      ) : null}

      {market ? (
        <div style={{ fontSize: 13, color: "#475569", marginBottom: 16, background: "#f8fafc", padding: 12, borderRadius: 8 }}>
          <strong>Сравнение рынка (оценка):</strong>{" "}
          {market.comparable_count
            ? `${market.comparable_count} сопоставимых предложений в системе`
            : "нет сопоставимых предложений"}
          {market.market_avg ? ` · средняя ${market.market_avg} ${market.currency}` : ""}
          {market.position ? ` · позиция: ${market.position}` : ""}
        </div>
      ) : null}

      <button style={styles.button} onClick={runMatch} disabled={busy}>
        Найти buyer needs
      </button>

      {detail.matches.length === 0 ? (
        <p style={{ marginTop: 16, color: "#64748b" }}>
          Совпадений пока нет. Запустите сопоставление или создайте buyer-led возможность с тем же товаром.
        </p>
      ) : (
        <ul style={{ marginTop: 16, paddingLeft: 0, listStyle: "none" }}>
          {detail.matches.map((match) => (
            <li
              key={match.id}
              style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 12, marginBottom: 12 }}
            >
              <div style={{ fontWeight: 600 }}>{match.match_summary}</div>
              <div style={{ fontSize: 13, color: "#64748b" }}>
                Score {match.score} · {match.status}
              </div>
              {match.match_reasons.length > 0 ? (
                <ul style={{ fontSize: 13, margin: "8px 0" }}>
                  {match.match_reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              ) : null}

              {match.route_proposal ? (
                <div style={{ fontSize: 13, marginTop: 8 }}>
                  <strong>Маршрут:</strong> {match.route_proposal.origin} → {match.route_proposal.destination}
                  {match.route_proposal.suggested_sell_price_per_mt
                    ? ` · продажа ~${match.route_proposal.suggested_sell_price_per_mt} ${match.route_proposal.currency}/MT`
                    : ""}
                </div>
              ) : null}

              {match.outreach_subject ? (
                <div style={{ marginTop: 12, fontSize: 13, background: "#f1f5f9", padding: 10, borderRadius: 6 }}>
                  <div>
                    <strong>Черновик:</strong> {match.outreach_subject}
                  </div>
                  <pre style={{ whiteSpace: "pre-wrap", marginTop: 8, fontFamily: "inherit" }}>
                    {match.outreach_body}
                  </pre>
                </div>
              ) : null}

              <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button
                  style={styles.secondaryButton}
                  onClick={() => onBuildRoute(match)}
                  disabled={busy}
                >
                  Построить маршрут
                </button>
                <button
                  style={styles.secondaryButton}
                  onClick={() => onDraftOutreach(match)}
                  disabled={busy}
                >
                  Черновик покупателю
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
