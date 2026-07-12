"use client";

import { useEffect, useState } from "react";
import { apiClient, Opportunity, OpportunityDisplayStatus, OpportunityStatusEvent } from "@/lib/api";
import {
  displayStatusLabel,
  formatDateTime,
  formatDeadlines,
  OPPORTUNITY_STATUS_LABELS,
} from "@/lib/opportunityStatus";
import { styles } from "@/lib/styles";

type Props = {
  opportunity: Opportunity;
  onUpdated: () => Promise<void>;
};

const ACTION_STATUSES = [
  { code: "IN_ANALYSIS", label: "В анализе" },
  { code: "ANALYSIS_DONE", label: "Анализ закончен" },
  { code: "NEEDS_INPUT", label: "Требует данных" },
  { code: "ACCEPTED", label: "Принята" },
  { code: "REJECTED", label: "Отклонена" },
] as const;

export function OpportunityStatusPanel({ opportunity, onUpdated }: Props) {
  const [displayStatus, setDisplayStatus] = useState<OpportunityDisplayStatus | null>(null);
  const [history, setHistory] = useState<OpportunityStatusEvent[]>([]);
  const [otherNote, setOtherNote] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const [status, events] = await Promise.all([
      apiClient.getOpportunityDisplayStatus(opportunity.id),
      apiClient.getOpportunityStatusHistory(opportunity.id),
    ]);
    setDisplayStatus(status);
    setHistory(events);
  }

  useEffect(() => {
    load().catch(() => {});
  }, [opportunity.id, opportunity.status, opportunity.status_changed_at]);

  async function changeStatus(status: string, note?: string) {
    setBusy(true);
    setMessage("");
    try {
      await apiClient.changeOpportunityStatus(opportunity.id, { status, note });
      setMessage(`Статус: ${OPPORTUNITY_STATUS_LABELS[status] ?? status}`);
      await onUpdated();
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка смены статуса");
    } finally {
      setBusy(false);
    }
  }

  const isConverted = opportunity.status === "CONVERTED";
  const status = displayStatus ?? {
    code: opportunity.status,
    label: displayStatusLabel(opportunity.status, "OPPORTUNITY"),
    kind: "OPPORTUNITY",
    changed_at: opportunity.status_changed_at,
  };

  return (
    <div style={styles.card}>
      <h2 style={{ marginTop: 0 }}>Статус и сроки</h2>
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>{status.label}</div>
        <div style={{ fontSize: 13, color: "#64748b", marginTop: 4 }}>
          Обновлено: {formatDateTime(status.changed_at)}
          {opportunity.status_note ? ` · ${opportunity.status_note}` : ""}
        </div>
        <div style={{ fontSize: 13, color: "#334155", marginTop: 8 }}>
          {formatDeadlines(opportunity.quote_deadline, opportunity.delivery_deadline, opportunity.deadline)}
        </div>
      </div>

      {!isConverted ? (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          {ACTION_STATUSES.map((item) => (
            <button
              key={item.code}
              style={opportunity.status === item.code ? styles.button : styles.secondaryButton}
              disabled={busy}
              onClick={() => changeStatus(item.code)}
            >
              {item.label}
            </button>
          ))}
        </div>
      ) : (
        <p style={{ fontSize: 13, color: "#64748b" }}>
          После конвертации в сделку статус pipeline определяется стадией сделки.
        </p>
      )}

      {!isConverted ? (
        <div style={{ marginBottom: 12 }}>
          <label style={styles.label}>Другое (комментарий)</label>
          <input
            style={styles.input}
            value={otherNote}
            onChange={(e) => setOtherNote(e.target.value)}
            placeholder="Причина или уточнение"
          />
          <button
            style={styles.secondaryButton}
            disabled={busy || !otherNote.trim()}
            onClick={() => changeStatus("OTHER", otherNote.trim())}
          >
            Установить «Другое»
          </button>
        </div>
      ) : null}

      {history.length > 0 ? (
        <div>
          <h3 style={{ fontSize: 15, marginTop: 0 }}>История статусов</h3>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {history.slice(0, 8).map((event) => (
              <li
                key={event.id}
                style={{ padding: "8px 0", borderBottom: "1px solid #f1f5f9", fontSize: 13 }}
              >
                <strong>
                  {event.status_kind === "PIPELINE"
                    ? displayStatusLabel(event.status_code, "PIPELINE")
                    : displayStatusLabel(event.status_code, "OPPORTUNITY")}
                </strong>
                {" · "}
                {formatDateTime(event.changed_at)}
                {event.note ? ` · ${event.note}` : ""}
                <span style={{ color: "#94a3b8" }}> ({event.actor_type})</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {message ? <p style={{ marginTop: 12 }}>{message}</p> : null}
    </div>
  );
}
