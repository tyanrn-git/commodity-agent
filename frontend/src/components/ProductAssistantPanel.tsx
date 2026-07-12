"use client";

import { FormEvent, useState } from "react";
import { apiClient, ProductAssistantReply } from "@/lib/api";
import { styles } from "@/lib/styles";

type Props = {
  productId: string;
  onUpdated?: () => void;
};

type ChatMessage = {
  role: "user" | "assistant";
  text: string;
};

export function ProductAssistantPanel({ productId, onUpdated }: Props) {
  const [input, setInput] = useState("");
  const [apply, setApply] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [lastReply, setLastReply] = useState<ProductAssistantReply | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!input.trim()) return;
    const userMessage = input.trim();
    setMessages((prev) => [...prev, { role: "user", text: userMessage }]);
    setInput("");
    setBusy(true);
    try {
      const reply = await apiClient.productAssistant(productId, {
        message: userMessage,
        apply_changes: apply,
      });
      setLastReply(reply);
      setMessages((prev) => [...prev, { role: "assistant", text: reply.reply }]);
      if (apply && reply.applied_changes.length > 0 && onUpdated) {
        onUpdated();
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: err instanceof Error ? err.message : "Ошибка AI" },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={styles.card}>
      <h2 style={{ marginTop: 0 }}>AI-помощник каталога</h2>
      <p style={{ fontSize: 13, color: "#64748b" }}>
        Спросите про товар, ключевые (IDENTITY) и вариативные (VARIANT) характеристики. Можно попросить
        добавить или изменить параметры — с галочкой изменения применятся сразу.
      </p>

      <div
        style={{
          minHeight: 140,
          maxHeight: 280,
          overflowY: "auto",
          background: "#f8fafc",
          borderRadius: 8,
          padding: 12,
          marginBottom: 12,
        }}
      >
        {messages.length === 0 ? (
          <p style={{ color: "#94a3b8", fontSize: 13, margin: 0 }}>
            Пример: «Добавь moisture как VARIANT с materiality IMMATERIAL» или «Какие параметры ключевые
            для гуара?»
          </p>
        ) : (
          messages.map((msg, idx) => (
            <div key={idx} style={{ marginBottom: 10, fontSize: 14 }}>
              <strong>{msg.role === "user" ? "Вы" : "AI"}:</strong> {msg.text}
            </div>
          ))
        )}
      </div>

      <form onSubmit={onSubmit}>
        <textarea
          style={{ ...styles.input, minHeight: 72, resize: "vertical" }}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Опишите, что изменить в товаре или спецификации..."
        />
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, marginBottom: 12 }}>
          <input type="checkbox" checked={apply} onChange={(e) => setApply(e.target.checked)} />
          Применить предложенные изменения сразу
        </label>
        <button style={styles.button} type="submit" disabled={busy || !input.trim()}>
          {busy ? "Думаю..." : "Спросить AI"}
        </button>
      </form>

      {lastReply?.applied_changes?.length ? (
        <p style={{ marginTop: 12, color: "#15803d", fontSize: 13 }}>
          Применено: {lastReply.applied_changes.join(", ")}
        </p>
      ) : null}
      {lastReply ? (
        <p style={{ fontSize: 12, color: "#94a3b8", marginTop: 8 }}>
          {lastReply.ai_model} · ${lastReply.ai_cost_usd}
        </p>
      ) : null}
    </div>
  );
}
