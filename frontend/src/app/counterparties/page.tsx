"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient, CounterpartyListItem } from "@/lib/api";
import { orgTypeLabel } from "@/lib/counterpartyLabels";
import { AppNav } from "@/components/AppNav";
import { statBoxStyle } from "@/components/SectionTabs";
import { styles } from "@/lib/styles";

const ORG_FILTER_OPTIONS = [
  { value: "", label: "Все типы" },
  { value: "PRODUCER", label: "Производитель" },
  { value: "TRADER", label: "Трейдер" },
  { value: "END_BUYER", label: "Покупатель" },
  { value: "FORWARDER", label: "Экспедитор" },
  { value: "OTHER", label: "Другое" },
];

export default function CounterpartiesPage() {
  const router = useRouter();
  const [items, setItems] = useState<CounterpartyListItem[]>([]);
  const [orgFilter, setOrgFilter] = useState("");
  const [legalName, setLegalName] = useState("");
  const [tradeName, setTradeName] = useState("");
  const [orgType, setOrgType] = useState("SUPPLIER");
  const [website, setWebsite] = useState("");
  const [domain, setDomain] = useState("");
  const [error, setError] = useState("");

  async function load() {
    try {
      setItems(await apiClient.listCounterparties());
    } catch {
      router.replace("/login");
    }
  }

  useEffect(() => {
    load();
  }, [router]);

  const filtered = useMemo(
    () => (orgFilter ? items.filter((item) => item.organization_type === orgFilter) : items),
    [items, orgFilter]
  );

  const stats = useMemo(() => {
    const withContacts = items.filter((item) => item.contacts_count > 0).length;
    const withCapabilities = items.filter((item) => item.capabilities_count > 0).length;
    return { total: items.length, withContacts, withCapabilities };
  }, [items]);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const created = await apiClient.createCounterparty({
        legal_name: legalName,
        trade_name: tradeName || null,
        organization_type: orgType,
        website: website || null,
        primary_domain: domain || null,
      });
      setLegalName("");
      router.push(`/counterparties/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    }
  }

  return (
    <main style={styles.page}>
      <div style={styles.container}>
        <h1 style={{ margin: 0, marginBottom: 8 }}>Управление контрагентами</h1>
        <p style={{ margin: "0 0 16px", color: "#64748b", fontSize: 14 }}>
          Контрагенты, их менеджеры и каталог товаров/услуг каждого партнёра.
        </p>
        <AppNav />

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
          <div style={statBoxStyle}>
            <div style={{ fontSize: 12, color: "#64748b" }}>Контрагентов</div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{stats.total}</div>
          </div>
          <div style={statBoxStyle}>
            <div style={{ fontSize: 12, color: "#64748b" }}>С контактами</div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{stats.withContacts}</div>
          </div>
          <div style={statBoxStyle}>
            <div style={{ fontSize: 12, color: "#64748b" }}>С товарами/услугами</div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{stats.withCapabilities}</div>
          </div>
        </div>

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Новый контрагент</h2>
          <form onSubmit={onCreate}>
            <label style={styles.label}>Юридическое название</label>
            <input
              style={styles.input}
              value={legalName}
              onChange={(e) => setLegalName(e.target.value)}
              required
            />
            <label style={styles.label}>Торговое название</label>
            <input style={styles.input} value={tradeName} onChange={(e) => setTradeName(e.target.value)} />
            <label style={styles.label}>Тип</label>
            <select style={styles.input} value={orgType} onChange={(e) => setOrgType(e.target.value)}>
              {ORG_FILTER_OPTIONS.filter((option) => option.value).map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <label style={styles.label}>Сайт</label>
            <input style={styles.input} value={website} onChange={(e) => setWebsite(e.target.value)} />
            <label style={styles.label}>Домен</label>
            <input
              style={styles.input}
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="example.com"
            />
            {error ? <div style={styles.error}>{error}</div> : null}
            <button style={styles.button} type="submit">
              Создать
            </button>
          </form>
        </div>

        <div style={styles.card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
            <h2 style={{ marginTop: 0, marginBottom: 0 }}>Контрагенты ({filtered.length})</h2>
            <select
              style={{ ...styles.input, marginBottom: 0, width: "auto", minWidth: 180 }}
              value={orgFilter}
              onChange={(e) => setOrgFilter(e.target.value)}
            >
              {ORG_FILTER_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          {filtered.length === 0 ? (
            <p style={{ color: "#64748b" }}>Пока нет контрагентов</p>
          ) : (
            <div style={{ overflowX: "auto", marginTop: 12 }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
                <thead>
                  <tr style={{ textAlign: "left", borderBottom: "1px solid #e2e8f0" }}>
                    <th style={{ padding: "8px 4px" }}>Название</th>
                    <th style={{ padding: "8px 4px" }}>Тип</th>
                    <th style={{ padding: "8px 4px" }}>Менеджеры</th>
                    <th style={{ padding: "8px 4px" }}>Товары/услуги</th>
                    <th style={{ padding: "8px 4px" }}>Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((item) => (
                    <tr key={item.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                      <td style={{ padding: "12px 4px" }}>
                        <Link href={`/counterparties/${item.id}`} style={{ ...styles.link, fontWeight: 600 }}>
                          {item.trade_name || item.legal_name}
                        </Link>
                        {item.primary_domain ? (
                          <div style={{ fontSize: 12, color: "#94a3b8" }}>{item.primary_domain}</div>
                        ) : null}
                      </td>
                      <td style={{ padding: "12px 4px" }}>{orgTypeLabel(item.organization_type)}</td>
                      <td style={{ padding: "12px 4px" }}>{item.contacts_count}</td>
                      <td style={{ padding: "12px 4px" }}>
                        {item.capabilities_count}
                        {item.confirmed_capabilities_count > 0
                          ? ` (${item.confirmed_capabilities_count} ✓)`
                          : ""}
                      </td>
                      <td style={{ padding: "12px 4px", fontSize: 12, color: "#64748b" }}>
                        {item.verification_status}
                        <br />
                        compliance: {item.compliance_review_status}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
