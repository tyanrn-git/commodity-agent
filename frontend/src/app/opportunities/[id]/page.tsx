"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { apiClient, Deal, ExtractionResult, openSourceContent, Opportunity, Source } from "@/lib/api";
import { AppNav } from "@/components/AppNav";
import { AgentActivityPanel } from "@/components/AgentActivityPanel";
import { OpportunityStatusPanel } from "@/components/OpportunityStatusPanel";
import { ProductResolutionPanel } from "@/components/ProductResolutionPanel";
import { SupplierLeadPanel } from "@/components/SupplierLeadPanel";
import { styles } from "@/lib/styles";

const APPLY_FIELDS = [
  "raw_product_name",
  "buyer_or_supplier_hint",
  "quantity_min",
  "quantity_max",
  "quantity_unit",
  "origin_hint",
  "destination_hint",
  "notes",
];

export default function OpportunityDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [opportunity, setOpportunity] = useState<Opportunity | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [deal, setDeal] = useState<Deal | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [emlFile, setEmlFile] = useState<File | null>(null);
  const [importUrl, setImportUrl] = useState("");
  const [selectedSourceId, setSelectedSourceId] = useState<string>("");
  const [extraction, setExtraction] = useState<ExtractionResult | null>(null);
  const [message, setMessage] = useState("");

  async function load() {
    try {
      const opp = await apiClient.getOpportunity(params.id);
      const srcs = await apiClient.listSources(params.id);
      setOpportunity(opp);
      setSources(srcs);
      if (srcs.length && !selectedSourceId) {
        setSelectedSourceId(srcs[0].id);
        const ext = await apiClient.getExtraction(srcs[0].id);
        setExtraction(ext);
      }
      if (opp.status === "CONVERTED") {
        const converted = await apiClient.convertOpportunity(params.id);
        setDeal(converted);
      }
    } catch {
      router.replace("/login");
    }
  }

  useEffect(() => {
    if (params.id) load();
  }, [params.id, router]);

  async function onUpload(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setMessage("");
    try {
      await apiClient.uploadSource(params.id, file);
      setFile(null);
      setMessage("Документ сохранён как Source");
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка загрузки");
    }
  }

  async function onImportEml(event: FormEvent) {
    event.preventDefault();
    if (!emlFile) return;
    try {
      await apiClient.importEml(params.id, emlFile);
      setEmlFile(null);
      setMessage("EML импортирован");
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка импорта EML");
    }
  }

  async function onImportUrl(event: FormEvent) {
    event.preventDefault();
    if (!importUrl) return;
    try {
      await apiClient.importUrl(params.id, importUrl);
      setImportUrl("");
      setMessage("URL импортирован");
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка импорта URL");
    }
  }

  async function onExtract(force = false) {
    if (!selectedSourceId) return;
    setMessage("");
    try {
      const result = await apiClient.extractSource(selectedSourceId, force);
      setExtraction(result);
      setMessage(`Извлечение: ${result.status}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка извлечения");
    }
  }

  async function onApplyExtraction() {
    if (!extraction) return;
    try {
      await apiClient.applyExtraction(params.id, extraction.id, APPLY_FIELDS);
      setMessage("Данные применены к возможности (требуют проверки)");
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка применения");
    }
  }

  async function onConvert() {
    setMessage("");
    try {
      const created = await apiClient.convertOpportunity(params.id);
      setDeal(created);
      setMessage(`Создана сделка ${created.deal_number}`);
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка конвертации");
    }
  }

  if (!opportunity) {
    return <main style={{ padding: 24 }}>Загрузка...</main>;
  }

  const extracted = extraction?.extracted_data || {};

  return (
    <main style={styles.page}>
      <div style={styles.container}>
        <AppNav backHref="/opportunities" backLabel="← К списку" />

        <div style={styles.card}>
          <h1 style={{ marginTop: 0 }}>{opportunity.title}</h1>
          <p style={{ color: "#64748b" }}>
            Статус: {opportunity.status} · Тип: {opportunity.type}
          </p>
          {opportunity.raw_product_name ? <p>Товар: {opportunity.raw_product_name}</p> : null}
          {opportunity.destination_hint ? (
            <p>Назначение: {opportunity.destination_hint}</p>
          ) : null}
          {opportunity.source_url ? (
            <p>
              Ссылка на тендер:{" "}
              <button
                type="button"
                style={{ ...styles.link, border: "none", background: "none", padding: 0, cursor: "pointer" }}
                onClick={() => window.open(opportunity.source_url!, "_blank", "noopener,noreferrer")}
              >
                🔗 {opportunity.source_url}
              </button>
            </p>
          ) : null}
          {message ? <p>{message}</p> : null}
          {opportunity.status !== "CONVERTED" ? (
            <button style={styles.button} onClick={onConvert}>
              Создать сделку
            </button>
          ) : deal ? (
            <Link href={`/deals/${deal.id}`} style={styles.link}>
              Открыть сделку {deal.deal_number}
            </Link>
          ) : null}
        </div>

        <OpportunityStatusPanel opportunity={opportunity} onUpdated={load} />

        {opportunity.type === "SUPPLIER_OFFER" ? (
          <SupplierLeadPanel opportunityId={params.id} />
        ) : null}

        <ProductResolutionPanel
          opportunityId={params.id}
          initialRoughName={opportunity.raw_product_name}
        />

        <AgentActivityPanel opportunityId={params.id} />

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Импорт документов</h2>
          <p style={{ fontSize: 13, color: "#64748b" }}>PDF, DOCX, XLSX</p>
          <form onSubmit={onUpload}>
            <input
              type="file"
              accept=".pdf,.docx,.xlsx,application/pdf"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            <div style={{ marginTop: 12 }}>
              <button style={styles.button} type="submit" disabled={!file}>
                Загрузить документ
              </button>
            </div>
          </form>
          <form onSubmit={onImportEml} style={{ marginTop: 16 }}>
            <p style={{ fontSize: 13 }}>Импорт .eml</p>
            <input type="file" accept=".eml" onChange={(e) => setEmlFile(e.target.files?.[0] || null)} />
            <button style={{ ...styles.secondaryButton, marginTop: 8 }} type="submit" disabled={!emlFile}>
              Импорт EML
            </button>
          </form>
          <form onSubmit={onImportUrl} style={{ marginTop: 16 }}>
            <p style={{ fontSize: 13 }}>Импорт публичной HTML-страницы</p>
            <input
              style={styles.input}
              placeholder="https://..."
              value={importUrl}
              onChange={(e) => setImportUrl(e.target.value)}
            />
            <button style={styles.secondaryButton} type="submit" disabled={!importUrl}>
              Импорт URL
            </button>
          </form>
        </div>

        <div style={styles.card} id="documents">
          <h2 style={{ marginTop: 0 }}>Документы и источники</h2>
          {sources.length === 0 ? (
            <p style={{ color: "#64748b", fontSize: 14 }}>Документы пока не прикреплены</p>
          ) : (
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {sources.map((source) => (
                <li
                  key={source.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "8px 0",
                    borderBottom: "1px solid #f1f5f9",
                  }}
                >
                  <button
                    type="button"
                    title="Открыть"
                    style={{ border: "none", background: "none", cursor: "pointer", fontSize: 18 }}
                    onClick={() => openSourceContent(source.id, source.source_url)}
                  >
                    {source.source_type === "URL" ? "🔗" : "📄"}
                  </button>
                  <button
                    style={{ ...styles.secondaryButton, flex: 1, textAlign: "left" }}
                    onClick={async () => {
                      setSelectedSourceId(source.id);
                      const ext = await apiClient.getExtraction(source.id);
                      setExtraction(ext);
                    }}
                  >
                    {source.original_filename} ({source.source_type})
                  </button>
                </li>
              ))}
            </ul>
          )}
          {selectedSourceId ? (
            <div style={{ marginTop: 12 }}>
              <button style={styles.button} onClick={() => onExtract(false)}>
                Извлечь AI (с кешем)
              </button>{" "}
              <button style={styles.secondaryButton} onClick={() => onExtract(true)}>
                Принудительно
              </button>
            </div>
          ) : null}
        </div>

        {extraction ? (
          <div style={styles.card}>
            <h2 style={{ marginTop: 0 }}>Результат извлечения</h2>
            <p>
              Статус: {extraction.status}
              {extraction.model ? ` · ${extraction.model}` : ""}
            </p>
            {extraction.missing_fields && extraction.missing_fields.length > 0 ? (
              <p style={{ color: "#b45309" }}>
                Не найдено: {extraction.missing_fields.join(", ")}
              </p>
            ) : null}
            <ul>
              {APPLY_FIELDS.map((field) => (
                <li key={field}>
                  <strong>{field}:</strong> {String(extracted[field] ?? "—")}
                </li>
              ))}
            </ul>
            {extraction.status !== "FAILED" ? (
              <button style={styles.button} onClick={onApplyExtraction}>
                Применить к возможности
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </main>
  );
}
