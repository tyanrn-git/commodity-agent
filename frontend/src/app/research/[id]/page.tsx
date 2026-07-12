"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  apiClient,
  CommercialFact,
  OutreachDraft,
  ResearchCampaign,
  ResearchLead,
} from "@/lib/api";
import { styles } from "@/lib/styles";

function viabilityLabel(status: string) {
  const map: Record<string, string> = {
    UNKNOWN: "Неизвестно",
    VIABLE_CANDIDATE: "Перспективная цепочка",
    NO_VIABLE_CHAIN_FOUND: "Цепочка не найдена",
  };
  return map[status] || status;
}

function leadTypeLabel(type: string) {
  const map: Record<string, string> = {
    BUYER_NEED: "Покупатель",
    PUBLIC_BUYER_NEED: "Публичный спрос",
    SUPPLIER: "Поставщик",
    LOGISTICS_ROUTE: "Логистика",
  };
  return map[type] || type;
}

export default function ResearchDetailPage() {
  const params = useParams();
  const router = useRouter();
  const campaignId = params.id as string;

  const [campaign, setCampaign] = useState<ResearchCampaign | null>(null);
  const [leads, setLeads] = useState<ResearchLead[]>([]);
  const [drafts, setDrafts] = useState<OutreachDraft[]>([]);
  const [facts, setFacts] = useState<CommercialFact[]>([]);
  const [viability, setViability] = useState<Record<string, unknown>>({});
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [copiedId, setCopiedId] = useState("");

  const load = useCallback(async () => {
    try {
      const [c, l, d, f, v] = await Promise.all([
        apiClient.getResearchCampaign(campaignId),
        apiClient.listResearchLeads(campaignId),
        apiClient.listOutreach(campaignId),
        apiClient.listCampaignFacts(campaignId),
        apiClient.getCampaignViability(campaignId),
      ]);
      setCampaign(c);
      setLeads(l);
      setDrafts(d);
      setFacts(f);
      setViability(v);
    } catch {
      router.replace("/login");
    }
  }, [campaignId, router]);

  useEffect(() => {
    load();
  }, [load]);

  async function runAction(label: string, fn: () => Promise<void>) {
    setBusy(label);
    setError("");
    try {
      await fn();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setBusy("");
    }
  }

  async function onRunSearch() {
    await runAction("search", async () => {
      await apiClient.runResearchCampaign(campaignId);
    });
  }

  async function onGenerateOutreach() {
    await runAction("outreach", async () => {
      await apiClient.generateOutreach(campaignId);
    });
  }

  async function onMarkSent(draftId: string) {
    await runAction("sent", async () => {
      await apiClient.markOutreachSent(draftId);
    });
  }

  async function onImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const input = event.currentTarget.elements.namedItem("file") as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    await runAction("import", async () => {
      await apiClient.importCampaignResponse(campaignId, file);
      input.value = "";
    });
  }

  async function onCreateOpportunity() {
    await runAction("opportunity", async () => {
      const buyer = leads.find((l) => l.lead_type.includes("BUYER"));
      await apiClient.createOpportunityFromCampaign(campaignId, {
        lead_id: buyer?.id,
        opportunity_type: "BUYER_NEED",
      });
    });
  }

  function copyDraft(draft: OutreachDraft) {
    const text = `Subject: ${draft.subject}\n\n${draft.body}`;
    navigator.clipboard.writeText(text);
    setCopiedId(draft.id);
    setTimeout(() => setCopiedId(""), 2000);
  }

  if (!campaign) {
    return (
      <main style={styles.page}>
        <div style={styles.container}>Загрузка...</div>
      </main>
    );
  }

  const buyers = leads.filter((l) => l.lead_type.includes("BUYER"));
  const suppliers = leads.filter((l) => l.lead_type === "SUPPLIER");
  const routes = leads.filter((l) => l.lead_type === "LOGISTICS_ROUTE");
  const counts = (viability.counts as Record<string, number>) || {};
  const missing = (viability.missing_facts as string[]) || [];
  const reasons = (viability.reasons as string[]) || [];

  return (
    <main style={styles.page}>
      <div style={styles.container}>
        <div style={styles.header}>
          <div>
            <Link href="/research" style={styles.link}>
              ← К списку
            </Link>
            <h1 style={{ margin: "8px 0 0" }}>{campaign.name}</h1>
            <div style={{ fontSize: 14, color: "#64748b", marginTop: 4 }}>
              {campaign.status} · {viabilityLabel(campaign.viability_status)}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              style={styles.button}
              disabled={!!busy}
              onClick={onRunSearch}
            >
              {busy === "search" ? "Поиск..." : "Запустить поиск"}
            </button>
            <button
              style={styles.secondaryButton}
              disabled={!!busy || leads.length === 0}
              onClick={onGenerateOutreach}
            >
              Сгенерировать письма
            </button>
          </div>
        </div>

        {error ? <div style={{ ...styles.error, marginBottom: 16 }}>{error}</div> : null}

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Viability dashboard</h2>
          <p style={{ marginTop: 0 }}>{String(viability.summary || "")}</p>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 14 }}>
            <span>Покупатели: {counts.buyers ?? buyers.length}</span>
            <span>Поставщики: {counts.suppliers ?? suppliers.length}</span>
            <span>Маршруты: {counts.routes ?? routes.length}</span>
            <span>Отправлено: {counts.sent_outreach ?? 0}</span>
            <span>Факты: {counts.commercial_facts ?? facts.length}</span>
            <span>Opportunities: {counts.opportunities ?? 0}</span>
          </div>
          {missing.length > 0 ? (
            <div style={{ marginTop: 12 }}>
              <strong>Недостающие сигналы:</strong>
              <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
                {missing.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {reasons.length > 0 ? (
            <div style={{ marginTop: 12, color: "#64748b", fontSize: 14 }}>
              {reasons.map((r) => (
                <div key={r}>• {r}</div>
              ))}
            </div>
          ) : null}
        </div>

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Результаты поиска</h2>
          {leads.length === 0 ? (
            <p style={{ color: "#64748b" }}>Запустите поиск, чтобы получить лиды</p>
          ) : (
            <>
              <Section title={`Покупатели (${buyers.length})`} items={buyers} />
              <Section title={`Поставщики (${suppliers.length})`} items={suppliers} />
              <Section title={`Логистика (${routes.length})`} items={routes} />
            </>
          )}
        </div>

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Outreach (ручная отправка)</h2>
          {drafts.length === 0 ? (
            <p style={{ color: "#64748b" }}>Сгенерируйте черновики писем после поиска</p>
          ) : (
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {drafts.map((draft) => (
                <li
                  key={draft.id}
                  style={{ padding: "16px 0", borderBottom: "1px solid #e2e8f0" }}
                >
                  <div style={{ fontWeight: 600 }}>{draft.subject}</div>
                  <div style={{ fontSize: 13, color: "#64748b", margin: "4px 0 8px" }}>
                    {draft.outreach_type} · {draft.status}
                  </div>
                  <pre
                    style={{
                      whiteSpace: "pre-wrap",
                      background: "#f8fafc",
                      padding: 12,
                      borderRadius: 6,
                      fontSize: 13,
                      margin: "0 0 8px",
                    }}
                  >
                    {draft.body}
                  </pre>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button style={styles.secondaryButton} onClick={() => copyDraft(draft)}>
                      {copiedId === draft.id ? "Скопировано" : "Копировать текст"}
                    </button>
                    {draft.status === "DRAFT" ? (
                      <button
                        style={styles.button}
                        disabled={!!busy}
                        onClick={() => onMarkSent(draft.id)}
                      >
                        Отметить отправленным
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Импорт ответа</h2>
          <form onSubmit={onImport}>
            <input type="file" name="file" accept=".eml,.pdf,.txt" required />
            <button style={{ ...styles.button, marginTop: 12 }} type="submit" disabled={!!busy}>
              {busy === "import" ? "Импорт..." : "Импортировать ответ"}
            </button>
          </form>
          {facts.length > 0 ? (
            <div style={{ marginTop: 16 }}>
              <strong>CommercialFacts:</strong>
              <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
                {facts.map((f) => (
                  <li key={f.id}>
                    {f.field_path}: {f.value}
                    {f.unit ? ` ${f.unit}` : ""}
                    {f.currency ? ` ${f.currency}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Opportunity из кампании</h2>
          {campaign.created_opportunity_ids && campaign.created_opportunity_ids.length > 0 ? (
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {campaign.created_opportunity_ids.map((id) => (
                <li key={id}>
                  <Link href={`/opportunities/${id}`} style={styles.link}>
                    {id}
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <button style={styles.button} disabled={!!busy} onClick={onCreateOpportunity}>
              Создать Opportunity
            </button>
          )}
        </div>
      </div>
    </main>
  );
}

function Section({ title, items }: { title: string; items: ResearchLead[] }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <h3 style={{ margin: "0 0 8px", fontSize: 15 }}>{title}</h3>
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {items.map((lead) => (
          <li
            key={lead.id}
            style={{ padding: "8px 0", borderBottom: "1px solid #f1f5f9", fontSize: 14 }}
          >
            <strong>{lead.organization_name || lead.title}</strong>
            <div style={{ color: "#64748b" }}>
              {leadTypeLabel(lead.lead_type)}
              {lead.region ? ` · ${lead.region}` : ""}
              {lead.relevance_score ? ` · score ${lead.relevance_score}` : ""}
            </div>
            {lead.notes ? <div style={{ marginTop: 4 }}>{lead.notes}</div> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
