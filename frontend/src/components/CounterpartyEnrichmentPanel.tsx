"use client";

import { FormEvent, useState } from "react";
import { apiClient, ContactHint, CounterpartyEnrichment } from "@/lib/api";
import { styles } from "@/lib/styles";

type Props = {
  counterpartyId: string;
  onEnriched?: () => void;
};

export function CounterpartyEnrichmentPanel({ counterpartyId, onEnriched }: Props) {
  const [sourceText, setSourceText] = useState("");
  const [contactHints, setContactHints] = useState<ContactHint[]>([]);
  const [summary, setSummary] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function onEnrich(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const result: CounterpartyEnrichment = await apiClient.enrichCounterparty(counterpartyId, {
        source_text: sourceText.trim() || undefined,
      });
      setSummary(result.summary);
      setContactHints(result.contact_hints);
      setMessage(
        `AI обогатил профиль: ${result.capabilities.length} товаров/услуг, ${result.contact_hints.length} контактных подсказок`
      );
      onEnriched?.();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка AI-обогащения");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={styles.card}>
      <h2 style={{ marginTop: 0 }}>AI-обогащение профиля</h2>
      <p style={{ fontSize: 13, color: "#64748b" }}>
        AI извлекает из сайта, email или презентации товары и услуги контрагента, а также
        подсказки по контактным лицам. Результаты появятся во вкладках выше после обработки.
      </p>
      <form onSubmit={onEnrich}>
        <label style={styles.label}>Текст для анализа (опционально)</label>
        <textarea
          style={{ ...styles.input, minHeight: 72, resize: "vertical" }}
          value={sourceText}
          onChange={(e) => setSourceText(e.target.value)}
          placeholder="Описание с сайта, email, презентации..."
        />
        <button style={styles.button} type="submit" disabled={busy}>
          {busy ? "Обработка..." : "Обогатить профиль (AI)"}
        </button>
      </form>

      {summary ? (
        <p style={{ marginTop: 16, fontSize: 14, color: "#334155" }}>{summary}</p>
      ) : null}

      {contactHints.length > 0 ? (
        <div style={{ marginTop: 16 }}>
          <h3 style={{ marginTop: 0, fontSize: 15 }}>Контактные подсказки (добавьте вручную во вкладке «Менеджеры»)</h3>
          <ul>
            {contactHints.map((hint, idx) => (
              <li key={idx} style={{ fontSize: 14 }}>
                {hint.full_name || "—"} · {hint.role_title || "—"} · {hint.email || "—"}
                {hint.evidence_excerpt ? (
                  <span style={{ color: "#94a3b8", fontSize: 12 }}> — «{hint.evidence_excerpt}»</span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {message ? <p style={{ marginTop: 12 }}>{message}</p> : null}
    </div>
  );
}
