"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient, InboxMessage } from "@/lib/api";
import { AppNav } from "@/components/AppNav";
import { styles } from "@/lib/styles";

export default function InboxPage() {
  const router = useRouter();
  const [tab, setTab] = useState<"linked" | "unlinked">("linked");
  const [linked, setLinked] = useState<InboxMessage[]>([]);
  const [unlinked, setUnlinked] = useState<InboxMessage[]>([]);
  const [linkRfqId, setLinkRfqId] = useState("");
  const [linkMessageId, setLinkMessageId] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    try {
      const [l, u] = await Promise.all([
        apiClient.listInbox(),
        apiClient.listUnlinkedInbox(),
      ]);
      setLinked(l);
      setUnlinked(u);
    } catch {
      router.replace("/login");
    }
  }

  useEffect(() => {
    load();
  }, [router]);

  async function onImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const input = event.currentTarget.elements.namedItem("file") as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    const result = await apiClient.importInboxEml(file);
    setMessage(
      result.supply_offer
        ? "Ответ импортирован, SupplyOffer создан"
        : "Письмо добавлено в Unlinked Inbox"
    );
    input.value = "";
    await load();
  }

  async function onLink() {
    if (!linkMessageId || !linkRfqId) return;
    await apiClient.linkMessage(linkMessageId, linkRfqId);
    setMessage("Письмо привязано к RFQ");
    setLinkMessageId("");
    await load();
  }

  const items = tab === "linked" ? linked : unlinked;

  return (
    <main style={styles.page}>
      <div style={styles.container}>
        <h1 style={{ margin: 0, marginBottom: 16 }}>Inbox</h1>
        <AppNav />

        <div style={styles.card}>
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <button
              style={tab === "linked" ? styles.button : styles.secondaryButton}
              onClick={() => setTab("linked")}
            >
              Привязанные ({linked.length})
            </button>
            <button
              style={tab === "unlinked" ? styles.button : styles.secondaryButton}
              onClick={() => setTab("unlinked")}
            >
              Unlinked ({unlinked.length})
            </button>
          </div>

          {items.length === 0 ? (
            <p style={{ color: "#64748b" }}>Нет писем</p>
          ) : (
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {items.map((m) => (
                <li key={m.id} style={{ padding: "12px 0", borderBottom: "1px solid #e2e8f0" }}>
                  <strong>{m.subject}</strong>
                  <div style={{ fontSize: 13, color: "#64748b" }}>
                    {m.direction} · {m.from_address} · {m.link_status}
                  </div>
                  <pre style={{ fontSize: 12, whiteSpace: "pre-wrap", marginTop: 8 }}>{m.body_text}</pre>
                  {tab === "unlinked" ? (
                    <button
                      style={styles.secondaryButton}
                      onClick={() => setLinkMessageId(m.id)}
                    >
                      Выбрать для привязки
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Импорт .eml</h2>
          <form onSubmit={onImport}>
            <input type="file" name="file" accept=".eml" required />
            <button style={{ ...styles.button, marginTop: 12 }} type="submit">
              Импортировать
            </button>
          </form>
        </div>

        {linkMessageId ? (
          <div style={styles.card}>
            <h2 style={{ marginTop: 0 }}>Привязать к RFQ</h2>
            <label style={styles.label}>RFQ ID</label>
            <input
              style={styles.input}
              value={linkRfqId}
              onChange={(e) => setLinkRfqId(e.target.value)}
              placeholder="uuid RFQ"
            />
            <button style={styles.button} onClick={onLink}>Привязать</button>
          </div>
        ) : null}

        {message ? <p>{message}</p> : null}
      </div>
    </main>
  );
}
