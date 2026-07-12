"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiClient, Counterparty } from "@/lib/api";
import { orgTypeLabel } from "@/lib/counterpartyLabels";
import { CounterpartyCapabilitiesSection } from "@/components/CounterpartyCapabilitiesSection";
import { CounterpartyContactsSection } from "@/components/CounterpartyContactsSection";
import { CounterpartyEnrichmentPanel } from "@/components/CounterpartyEnrichmentPanel";
import { SectionTabs } from "@/components/SectionTabs";
import { styles } from "@/lib/styles";

const TABS = [
  { id: "profile", label: "Профиль" },
  { id: "contacts", label: "Менеджеры" },
  { id: "products", label: "Товары и услуги" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function CounterpartyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [item, setItem] = useState<Counterparty | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("profile");
  const [capabilitiesRefreshKey, setCapabilitiesRefreshKey] = useState(0);
  const [domainReport, setDomainReport] = useState<Record<string, unknown> | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setItem(await apiClient.getCounterparty(id));
    } catch {
      router.replace("/login");
    }
  }, [id, router]);

  useEffect(() => {
    load();
  }, [load]);

  async function onVerifyDomain() {
    setError("");
    try {
      const report = await apiClient.verifyCounterpartyDomain(id);
      setDomainReport(report);
      setMessage("Проверка домена выполнена");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    }
  }

  async function onConfirmDomain() {
    setError("");
    try {
      await apiClient.confirmCounterpartyDomain(id);
      setMessage("Домен подтверждён пользователем");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    }
  }

  async function onMarkReviewed() {
    await apiClient.markCounterpartyReviewed(id);
    setMessage("Compliance review отмечен");
    await load();
  }

  function onEnriched() {
    setCapabilitiesRefreshKey((value) => value + 1);
  }

  if (!item) {
    return (
      <main style={styles.page}>
        <div style={styles.container}>Загрузка...</div>
      </main>
    );
  }

  return (
    <main style={styles.page}>
      <div style={styles.container}>
        <Link href="/counterparties" style={styles.link}>
          ← Управление контрагентами
        </Link>

        <div style={{ ...styles.card, marginTop: 12 }}>
          <h1 style={{ marginTop: 0 }}>{item.trade_name || item.legal_name}</h1>
          <p style={{ color: "#64748b", marginBottom: 0 }}>
            {orgTypeLabel(item.organization_type)} · verify: {item.verification_status} · compliance:{" "}
            <strong>{item.compliance_review_status}</strong>
          </p>
          <div style={{ fontSize: 13, color: "#64748b", marginTop: 8 }}>
            Контактов: {item.contacts?.length ?? 0}
          </div>
        </div>

        <SectionTabs tabs={[...TABS]} activeId={activeTab} onChange={(tabId) => setActiveTab(tabId as TabId)} />

        {activeTab === "profile" ? (
          <div style={styles.card}>
            <h2 style={{ marginTop: 0 }}>Профиль контрагента</h2>
            <dl style={{ margin: 0, fontSize: 14, display: "grid", gap: 8 }}>
              <div>
                <dt style={{ color: "#64748b", fontSize: 12 }}>Юридическое название</dt>
                <dd style={{ margin: "4px 0 0" }}>{item.legal_name}</dd>
              </div>
              {item.trade_name ? (
                <div>
                  <dt style={{ color: "#64748b", fontSize: 12 }}>Торговое название</dt>
                  <dd style={{ margin: "4px 0 0" }}>{item.trade_name}</dd>
                </div>
              ) : null}
              {item.website ? (
                <div>
                  <dt style={{ color: "#64748b", fontSize: 12 }}>Сайт</dt>
                  <dd style={{ margin: "4px 0 0" }}>{item.website}</dd>
                </div>
              ) : null}
              {item.primary_domain ? (
                <div>
                  <dt style={{ color: "#64748b", fontSize: 12 }}>Домен</dt>
                  <dd style={{ margin: "4px 0 0" }}>{item.primary_domain}</dd>
                </div>
              ) : null}
              {item.address ? (
                <div>
                  <dt style={{ color: "#64748b", fontSize: 12 }}>Адрес</dt>
                  <dd style={{ margin: "4px 0 0" }}>{item.address}</dd>
                </div>
              ) : null}
            </dl>

            {item.compliance_review_status === "NOT_REVIEWED" ? (
              <div style={{ background: "#fef3c7", padding: 12, borderRadius: 6, marginTop: 16 }}>
                Контрагент не прошёл compliance review
                <button style={{ ...styles.secondaryButton, marginLeft: 8 }} onClick={onMarkReviewed}>
                  Отметить проверенным
                </button>
              </div>
            ) : null}

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 16 }}>
              <button style={styles.button} onClick={onVerifyDomain}>
                Проверить домен (DNS/MX)
              </button>
              <button style={styles.secondaryButton} onClick={onConfirmDomain}>
                Подтвердить домен
              </button>
            </div>
            {domainReport ? (
              <pre style={{ fontSize: 12, background: "#f8fafc", padding: 12, marginTop: 12 }}>
                {JSON.stringify(domainReport, null, 2)}
              </pre>
            ) : null}
          </div>
        ) : null}

        {activeTab === "contacts" ? (
          <CounterpartyContactsSection
            counterpartyId={id}
            contacts={item.contacts ?? []}
            onUpdated={load}
          />
        ) : null}

        {activeTab === "products" ? (
          <>
            <CounterpartyCapabilitiesSection counterpartyId={id} refreshKey={capabilitiesRefreshKey} />
            <CounterpartyEnrichmentPanel counterpartyId={id} onEnriched={onEnriched} />
          </>
        ) : null}

        {message ? <p>{message}</p> : null}
        {error ? <div style={styles.error}>{error}</div> : null}
      </div>
    </main>
  );
}
