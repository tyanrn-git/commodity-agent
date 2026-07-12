"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  apiClient,
  InternetSource,
  InternetSourceSearchHit,
  InternetSourceSearchRun,
  MonitoringRule,
  MonitoringRun,
  MonitoredPublication,
  TenderMonitoringRow,
} from "@/lib/api";
import { formatDateTime } from "@/lib/opportunityStatus";
import { AppNav } from "@/components/AppNav";
import { styles } from "@/lib/styles";

const ACCESS_MODE_LABELS: Record<string, string> = {
  PUBLIC: "Открытый источник",
  CREDENTIALS: "Платформа с доступом",
  MANUAL_IMPORT: "Только ручной импорт",
};

const SOURCE_KIND_LABELS: Record<string, string> = {
  TENDER_PORTAL: "Тендерный портал",
  PROCUREMENT_FEED: "Лента закупок",
  GOV_REGISTRY: "Гос. реестр",
  NEWS: "Новости",
  AGGREGATOR: "Агрегатор",
  OTHER: "Другое",
};

const thStyle = { padding: "8px 6px", fontSize: 12, color: "#64748b", whiteSpace: "nowrap" as const };
const tdStyle = { padding: "10px 6px", fontSize: 13, verticalAlign: "top" as const };

function statusColor(status: string) {
  if (status === "ACTIVE" || status === "FOUND") return "#166534";
  if (status === "EXPIRED") return "#92400e";
  return "#991b1b";
}

function TenderResultRow({
  hit,
  onPromote,
  promoting,
}: {
  hit: InternetSourceSearchHit;
  onPromote: (hitId: string) => Promise<void>;
  promoting: boolean;
}) {
  const row: TenderMonitoringRow =
    hit.monitoring_row ?? {
      buyer_name: null,
      product_name: null,
      volume: null,
      destination: null,
      submission_deadline: null,
      delivery_deadline: null,
      submission_expired: false,
      product_match: false,
      product_match_reason: null,
      display_status: hit.status,
      display_status_label: hit.status,
      source_url: hit.canonical_url,
    };
  const feasibility = (row.feasibility || null) as {
    feasible?: boolean;
    summary?: string;
    supplier_hint?: string;
    gross_margin?: number;
    gross_margin_percent?: number;
    margin_currency?: string;
  } | null;
  const canPromote =
    row.product_match &&
    !row.submission_expired &&
    row.display_status === "ACTIVE" &&
    !hit.opportunity_id &&
    hit.status === "FOUND";

  return (
    <tr style={{ borderBottom: "1px solid #f1f5f9" }}>
      <td style={tdStyle}>
        <div style={{ fontWeight: 600 }}>{hit.title}</div>
        <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4 }}>
          {hit.source_name || "источник"}
          {hit.confidence != null ? ` · ${Math.round(hit.confidence * 100)}%` : ""}
        </div>
      </td>
      <td style={{ ...tdStyle, color: statusColor(row.display_status), fontWeight: 600 }}>
        {row.display_status_label}
      </td>
      <td style={tdStyle}>
        {row.product_match ? "Да" : "Нет"}
        {row.product_match_reason ? (
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>{row.product_match_reason}</div>
        ) : null}
      </td>
      <td style={tdStyle}>{row.buyer_name || "—"}</td>
      <td style={tdStyle}>{row.product_name || "—"}</td>
      <td style={tdStyle}>{row.volume || "—"}</td>
      <td style={tdStyle}>
        {row.submission_deadline ? formatDateTime(row.submission_deadline) : "—"}
        {row.submission_expired ? (
          <div style={{ fontSize: 11, color: "#92400e" }}>истёк</div>
        ) : null}
      </td>
      <td style={tdStyle}>{row.delivery_deadline ? formatDateTime(row.delivery_deadline) : row.destination || "—"}</td>
      <td style={tdStyle}>
        {row.source_url ? (
          <a href={row.source_url} target="_blank" rel="noreferrer" style={styles.link}>
            🔗
          </a>
        ) : (
          "—"
        )}
      </td>
      <td style={tdStyle}>
        {hit.opportunity_id ? (
          <Link href={`/opportunities/${hit.opportunity_id}`} style={styles.link}>
            Открыть
          </Link>
        ) : canPromote ? (
          <button
            type="button"
            style={styles.secondaryButton}
            disabled={promoting}
            onClick={() => onPromote(hit.id)}
          >
            {promoting ? "AI-оценка..." : "В возможности"}
          </button>
        ) : feasibility && feasibility.feasible === false ? (
          <span style={{ fontSize: 12, color: "#991b1b" }}>Нереализуемо</span>
        ) : (
          "—"
        )}
        {feasibility?.summary ? (
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 6 }}>{feasibility.summary}</div>
        ) : null}
        {feasibility?.supplier_hint ? (
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>
            Поставщик: {feasibility.supplier_hint}
          </div>
        ) : null}
        {feasibility?.gross_margin != null ? (
          <div style={{ fontSize: 11, color: "#166534", marginTop: 4 }}>
            Маржа {feasibility.gross_margin} {feasibility.margin_currency || "USD"}
            {feasibility.gross_margin_percent != null ? ` (${feasibility.gross_margin_percent}%)` : ""}
          </div>
        ) : null}
      </td>
    </tr>
  );
}

export default function MonitoringPage() {
  const router = useRouter();
  const [rules, setRules] = useState<MonitoringRule[]>([]);
  const [sources, setSources] = useState<InternetSource[]>([]);
  const [searchRun, setSearchRun] = useState<InternetSourceSearchRun | null>(null);
  const [searchHits, setSearchHits] = useState<InternetSourceSearchHit[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [promotingHitId, setPromotingHitId] = useState<string | null>(null);
  const [activeRule, setActiveRule] = useState<MonitoringRule | null>(null);
  const [publications, setPublications] = useState<MonitoredPublication[]>([]);
  const [lastRun, setLastRun] = useState<MonitoringRun | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [catalogProductFilter, setCatalogProductFilter] = useState("urea, карбамид");
  const [catalogRegionFilter, setCatalogRegionFilter] = useState("India, EU, Global");
  const [catalogAccessFilter, setCatalogAccessFilter] = useState("PUBLIC");
  const [showInactiveSources, setShowInactiveSources] = useState(false);
  const [togglingSourceId, setTogglingSourceId] = useState<string | null>(null);

  const [newSourceName, setNewSourceName] = useState("");
  const [newSourceUrl, setNewSourceUrl] = useState("");
  const [newSourceTags, setNewSourceTags] = useState("urea, карбамид");
  const [newSourceRegions, setNewSourceRegions] = useState("India");
  const [newSourceHints, setNewSourceHints] = useState("");
  const [newSourceIsTest, setNewSourceIsTest] = useState(false);

  const [ruleName, setRuleName] = useState("");
  const [ruleSourceUrl, setRuleSourceUrl] = useState("");
  const [productKeywords, setProductKeywords] = useState("SN500, Base Oil");
  const [accessMode, setAccessMode] = useState("PUBLIC");
  const [platformName, setPlatformName] = useState("");
  const [loginHint, setLoginHint] = useState("");
  const [accessNotes, setAccessNotes] = useState("");

  async function loadCatalog() {
    const match = await apiClient.matchInternetSources({
      product_keywords: catalogProductFilter,
      regions: catalogRegionFilter,
      access_mode: catalogAccessFilter || undefined,
      include_inactive: showInactiveSources,
    });
    setSources(match.sources);
    if (match.sources_discovered && match.sources_discovered > 0) {
      setMessage(`AI добавил ${match.sources_discovered} новых площадок в каталог`);
    }
  }

  async function onToggleSourceActive(source: InternetSource) {
    setTogglingSourceId(source.id);
    setError("");
    try {
      await apiClient.patchInternetSource(source.id, { is_active: !source.is_active });
      await loadCatalog();
      setMessage(`Источник «${source.name}» ${source.is_active ? "отключён" : "подключён"}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка переключения источника");
    } finally {
      setTogglingSourceId(null);
    }
  }

  async function loadLastSearchResults() {
    const runs = await apiClient.listInternetSourceSearchRuns();
    if (runs.length === 0) return;
    const lastRun = runs[0];
    setSearchRun(lastRun);
    const hits = await apiClient.listInternetSourceSearchHits(lastRun.id);
    setSearchHits(hits);
    if (lastRun.product_keywords?.length) {
      setCatalogProductFilter(lastRun.product_keywords.join(", "));
    }
    if (lastRun.regions?.length) {
      setCatalogRegionFilter(lastRun.regions.join(", "));
    }
    if (lastRun.access_mode) {
      setCatalogAccessFilter(lastRun.access_mode);
    }
  }

  async function load() {
    try {
      const items = await apiClient.listMonitoringRules();
      setRules(items);
      await loadCatalog();
      await loadLastSearchResults();
      if (!activeRule && items.length > 0) {
        await selectRule(items[0]);
      } else if (activeRule) {
        const refreshed = items.find((r) => r.id === activeRule.id);
        if (refreshed) setActiveRule(refreshed);
      }
    } catch {
      router.replace("/login");
    }
  }

  async function selectRule(rule: MonitoringRule) {
    setActiveRule(rule);
    setLastRun(null);
    const pubs = await apiClient.listMonitoringPublications(rule.id);
    setPublications(pubs);
  }

  useEffect(() => {
    load();
  }, [router]);

  useEffect(() => {
    loadCatalog().catch(() => setError("Ошибка загрузки каталога"));
  }, [showInactiveSources]);

  async function onRunAiSearch() {
    setSearchLoading(true);
    setError("");
    setMessage("");
    try {
      const run = await apiClient.runInternetSourceSearch({
        product_keywords: catalogProductFilter
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        regions: catalogRegionFilter
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        access_mode: catalogAccessFilter || "PUBLIC",
        verify_real: true,
      });
      setSearchRun(run);
      const hits = await apiClient.listInternetSourceSearchHits(run.id);
      setSearchHits(hits);
      setMessage(
        `Поиск: ${run.status} · источников ${run.sources_scanned}/${run.sources_matched} · ` +
          `найдено ${run.hits_found} · перенесено в возможности ${run.opportunities_created}` +
          (run.sources_discovered ? ` · AI добавил площадок ${run.sources_discovered}` : "")
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка AI-поиска");
    } finally {
      setSearchLoading(false);
    }
  }

  async function onPromoteHit(hitId: string) {
    setPromotingHitId(hitId);
    setError("");
    try {
      const result = await apiClient.promoteSearchHit(hitId);
      setSearchHits((current) =>
        current.map((item) => (item.id === hitId ? result.hit : item))
      );
      setMessage(
        `Создана возможность «${result.opportunity_title}»` +
          (result.economics_preview ? ` · ${result.economics_preview}` : "")
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI не подтвердил реализуемость сделки");
      if (searchRun) {
        const hits = await apiClient.listInternetSourceSearchHits(searchRun.id);
        setSearchHits(hits);
      }
    } finally {
      setPromotingHitId(null);
    }
  }

  async function onCreateSource(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      const created = await apiClient.createInternetSource({
        name: newSourceName.trim(),
        base_url: newSourceUrl.trim(),
        source_kind: "TENDER_PORTAL",
        access_mode: "PUBLIC",
        product_tags: newSourceTags
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        regions: newSourceRegions
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        search_hints: newSourceHints.trim() || null,
        is_test: newSourceIsTest,
        is_active: !newSourceIsTest,
      });
      setNewSourceName("");
      setNewSourceUrl("");
      setNewSourceIsTest(false);
      setMessage(`Источник «${created.name}» добавлен в каталог`);
      await loadCatalog();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка добавления источника");
    }
  }

  async function onCreateRule(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      const connectorConfig: Record<string, string> = {};
      if (accessMode === "CREDENTIALS") {
        if (platformName.trim()) connectorConfig.platform_name = platformName.trim();
        if (loginHint.trim()) connectorConfig.login_hint = loginHint.trim();
        if (accessNotes.trim()) connectorConfig.access_notes = accessNotes.trim();
        connectorConfig.has_credentials = accessNotes.trim() ? "true" : "false";
      }
      const created = await apiClient.createMonitoringRule({
        name: ruleName.trim(),
        connector_type: "MOCK",
        source_url: ruleSourceUrl.trim(),
        poll_interval_hours: 24,
        access_mode: accessMode,
        connector_config: connectorConfig,
        filters: {
          product_keywords: productKeywords
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean),
        },
      });
      setRuleName("");
      setMessage(`Правило «${created.name}» создано`);
      await load();
      await selectRule(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка создания правила");
    }
  }

  async function onHealthcheck() {
    if (!activeRule) return;
    const health = await apiClient.getMonitoringHealth(activeRule.id);
    setMessage(`Health: ${health.health_status} — ${health.message}`);
    await load();
  }

  async function onRun() {
    if (!activeRule) return;
    const run = await apiClient.runMonitoringRule(activeRule.id);
    setLastRun(run);
    setMessage(
      `Запуск: ${run.status}, найдено ${run.items_found}, новых ${run.items_new}, возможностей ${run.opportunities_created}`
    );
    await load();
    await selectRule(activeRule);
  }

  return (
    <main style={styles.page}>
      <div style={styles.container}>
        <h1 style={{ margin: 0, marginBottom: 8 }}>Мониторинг источников</h1>
        <p style={{ margin: "0 0 16px", color: "#64748b", fontSize: 14 }}>
          Каталог известных интернет-источников хранится в базе — AI не тратит токены на поиск
          площадок, а сразу знает, куда смотреть. Запустите AI-поиск по подобранным источникам.
        </p>
        <AppNav />

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Каталог источников</h2>
          <p style={{ fontSize: 13, color: "#64748b", marginTop: 0 }}>
            AI сам ищет новые площадки под ваш товар, добавляет их в каталог и запоминает для
            следующих поисков. Уже известные источники повторно не анализируются. Результаты
            тендеров сохраняются здесь; перенос в «Возможности» — вручную после AI-оценки
            реализуемости.
          </p>
          <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
            <div>
              <label style={styles.label}>Товар (ключевые слова)</label>
              <input
                style={styles.input}
                value={catalogProductFilter}
                onChange={(e) => setCatalogProductFilter(e.target.value)}
                placeholder="urea, карбамид"
              />
            </div>
            <div>
              <label style={styles.label}>Регион</label>
              <input
                style={styles.input}
                value={catalogRegionFilter}
                onChange={(e) => setCatalogRegionFilter(e.target.value)}
                placeholder="India, EU"
              />
            </div>
            <div>
              <label style={styles.label}>Доступ</label>
              <select
                style={styles.input}
                value={catalogAccessFilter}
                onChange={(e) => setCatalogAccessFilter(e.target.value)}
              >
                <option value="">Любой</option>
                <option value="PUBLIC">Открытый</option>
                <option value="CREDENTIALS">С доступом</option>
                <option value="MANUAL_IMPORT">Ручной импорт</option>
              </select>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
            <button
              style={styles.secondaryButton}
              onClick={() => loadCatalog().catch(() => setError("Ошибка загрузки каталога"))}
            >
              Подобрать источники
            </button>
            <button style={styles.button} onClick={onRunAiSearch} disabled={searchLoading}>
              {searchLoading ? "Поиск реальных тендеров..." : "Проверить реальные тендеры"}
            </button>
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
              <input
                type="checkbox"
                checked={showInactiveSources}
                onChange={(e) => setShowInactiveSources(e.target.checked)}
              />
              Показать неактивные
            </label>
          </div>
          {sources.length > 0 ? (
            <div style={{ marginTop: 16, overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
                <thead>
                  <tr style={{ textAlign: "left", borderBottom: "1px solid #e2e8f0" }}>
                    <th style={{ padding: "8px 6px" }}>Источник</th>
                    <th style={{ padding: "8px 6px" }}>Тип</th>
                    <th style={{ padding: "8px 6px" }}>Товары</th>
                    <th style={{ padding: "8px 6px" }}>Регионы</th>
                    <th style={{ padding: "8px 6px" }}>Статус</th>
                    <th style={{ padding: "8px 6px" }}>Подсказка для AI</th>
                  </tr>
                </thead>
                <tbody>
                  {sources.map((source) => (
                    <tr
                      key={source.id}
                      style={{
                        borderBottom: "1px solid #f1f5f9",
                        opacity: source.is_active ? 1 : 0.65,
                      }}
                    >
                      <td style={{ padding: "10px 6px", verticalAlign: "top" }}>
                        <a href={source.base_url} target="_blank" rel="noreferrer" style={styles.link}>
                          {source.name}
                        </a>
                        <div style={{ fontSize: 12, color: "#64748b" }}>
                          {source.is_system ? "системный" : "мой"} · приоритет {source.priority}
                          {source.is_test ? (
                            <span
                              style={{
                                marginLeft: 8,
                                padding: "1px 6px",
                                borderRadius: 4,
                                background: "#fef3c7",
                                color: "#92400e",
                              }}
                            >
                              тестовый
                            </span>
                          ) : null}
                        </div>
                      </td>
                      <td style={{ padding: "10px 6px", verticalAlign: "top" }}>
                        {SOURCE_KIND_LABELS[source.source_kind] || source.source_kind}
                        <div style={{ fontSize: 12, color: "#64748b" }}>
                          {ACCESS_MODE_LABELS[source.access_mode] || source.access_mode}
                          {source.fetch_strategy && source.fetch_strategy !== "HTML"
                            ? ` · ${source.fetch_strategy}`
                            : ""}
                        </div>
                      </td>
                      <td style={{ padding: "10px 6px", verticalAlign: "top" }}>
                        {source.product_tags.join(", ")}
                      </td>
                      <td style={{ padding: "10px 6px", verticalAlign: "top" }}>
                        {source.regions.join(", ")}
                      </td>
                      <td style={{ padding: "10px 6px", verticalAlign: "top" }}>
                        <button
                          type="button"
                          style={styles.secondaryButton}
                          disabled={togglingSourceId === source.id}
                          onClick={() => onToggleSourceActive(source)}
                        >
                          {source.is_active ? "Отключить" : "Подключить"}
                        </button>
                        <div style={{ fontSize: 12, color: "#64748b", marginTop: 6 }}>
                          {source.is_active ? "активен" : "неактивен"}
                        </div>
                      </td>
                      <td style={{ padding: "10px 6px", verticalAlign: "top", fontSize: 13, color: "#475569" }}>
                        {source.search_hints || source.description || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p style={{ marginTop: 12, color: "#64748b" }}>
              Нет источников по точному совпадению тегов. Можно всё равно запустить поиск —
              будут проверены общие ленты TED и World Bank.
            </p>
          )}
          {searchRun ? (
            <div style={{ marginTop: 16, fontSize: 14, color: "#475569" }}>
              Последний поиск: {searchRun.status} · AI-вызовов {searchRun.ai_calls} · найдено{" "}
              {searchRun.hits_found} · перенесено в возможности {searchRun.opportunities_created}
              {searchRun.error_message ? ` · ошибка: ${searchRun.error_message}` : ""}
            </div>
          ) : null}
          {searchHits.filter((hit) => hit.status !== "SKIPPED" && hit.status !== "FILTERED_OUT").length > 0 ? (
            <div style={{ marginTop: 16 }}>
              <h3 style={{ marginTop: 0, fontSize: 16 }}>Результаты поиска тендеров</h3>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", minWidth: 1100, borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ textAlign: "left", borderBottom: "2px solid #e2e8f0" }}>
                      <th style={thStyle}>Тендер</th>
                      <th style={thStyle}>Статус</th>
                      <th style={thStyle}>Соответствие</th>
                      <th style={thStyle}>Покупатель</th>
                      <th style={thStyle}>Товар</th>
                      <th style={thStyle}>Объём</th>
                      <th style={thStyle}>Подача заявки</th>
                      <th style={thStyle}>Поставка</th>
                      <th style={thStyle}>Ссылка</th>
                      <th style={thStyle}>Действие</th>
                    </tr>
                  </thead>
                  <tbody>
                    {searchHits
                      .filter((hit) => hit.status !== "SKIPPED" && hit.status !== "FILTERED_OUT")
                      .map((hit) => (
                        <TenderResultRow
                          key={hit.id}
                          hit={hit}
                          promoting={promotingHitId === hit.id}
                          onPromote={onPromoteHit}
                        />
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : searchRun ? (
            <p style={{ marginTop: 12, color: "#64748b" }}>
              По запросу актуальных тендеров не найдено. Попробуйте расширить регион или
              уточнить товар (например, «gum arabic», «guar gum»).
            </p>
          ) : null}
        </div>

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Добавить источник</h2>
          <form onSubmit={onCreateSource}>
            <label style={styles.label}>Название</label>
            <input
              style={styles.input}
              value={newSourceName}
              onChange={(e) => setNewSourceName(e.target.value)}
              placeholder="Портал тендеров Турции"
              required
            />
            <label style={styles.label}>URL</label>
            <input
              style={styles.input}
              value={newSourceUrl}
              onChange={(e) => setNewSourceUrl(e.target.value)}
              placeholder="https://..."
              required
            />
            <label style={styles.label}>Товары (через запятую)</label>
            <input style={styles.input} value={newSourceTags} onChange={(e) => setNewSourceTags(e.target.value)} />
            <label style={styles.label}>Регионы (через запятую)</label>
            <input style={styles.input} value={newSourceRegions} onChange={(e) => setNewSourceRegions(e.target.value)} />
            <label style={styles.label}>Подсказка для AI-поиска</label>
            <textarea
              style={{ ...styles.input, minHeight: 64, resize: "vertical" }}
              value={newSourceHints}
              onChange={(e) => setNewSourceHints(e.target.value)}
              placeholder="Где на сайте искать тендеры, какие разделы, язык..."
            />
            <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12, fontSize: 14 }}>
              <input
                type="checkbox"
                checked={newSourceIsTest}
                onChange={(e) => setNewSourceIsTest(e.target.checked)}
              />
              Тестовый источник (не реальный, по умолчанию неактивен)
            </label>
            <button style={styles.button} type="submit">
              Добавить в каталог
            </button>
          </form>
        </div>

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Правило мониторинга (legacy)</h2>
          <p style={{ fontSize: 13, color: "#64748b", marginTop: 0 }}>
            Старый режим с коннектором на один URL. Новый поток — AI-поиск по каталогу источников
            (следующий шаг).
          </p>
          <form onSubmit={onCreateRule}>
            <label style={styles.label}>Название</label>
            <input
              style={styles.input}
              value={ruleName}
              onChange={(e) => setRuleName(e.target.value)}
              placeholder="SN500 EU tenders"
              required
            />
            <label style={styles.label}>URL источника</label>
            <input
              style={styles.input}
              value={ruleSourceUrl}
              onChange={(e) => setRuleSourceUrl(e.target.value)}
              placeholder="https://example.com/feed или путь к demo-feed"
              required
            />
            <label style={styles.label}>Ключевые слова товара (через запятую)</label>
            <input
              style={styles.input}
              value={productKeywords}
              onChange={(e) => setProductKeywords(e.target.value)}
            />
            <label style={styles.label}>Режим доступа</label>
            <select style={styles.input} value={accessMode} onChange={(e) => setAccessMode(e.target.value)}>
              <option value="PUBLIC">Открытый — AI/система опрашивает сама</option>
              <option value="CREDENTIALS">Платформа с логином — доступ настраивает пользователь</option>
              <option value="MANUAL_IMPORT">Только ручной импорт (CSV, email, PDF)</option>
            </select>
            {accessMode === "CREDENTIALS" ? (
              <>
                <label style={styles.label}>Платформа</label>
                <input
                  style={styles.input}
                  value={platformName}
                  onChange={(e) => setPlatformName(e.target.value)}
                  placeholder="Platts, биржа, B2B-портал..."
                />
                <label style={styles.label}>Логин / аккаунт (подсказка)</label>
                <input
                  style={styles.input}
                  value={loginHint}
                  onChange={(e) => setLoginHint(e.target.value)}
                  placeholder="company@example.com"
                />
                <label style={styles.label}>Заметка по доступу</label>
                <textarea
                  style={{ ...styles.input, minHeight: 64, resize: "vertical" }}
                  value={accessNotes}
                  onChange={(e) => setAccessNotes(e.target.value)}
                  placeholder="API-ключ в vault, VPN, экспорт раз в день..."
                />
              </>
            ) : null}
            <button style={styles.button} type="submit">
              Создать правило
            </button>
          </form>
          {error ? <div style={{ ...styles.error, marginTop: 12 }}>{error}</div> : null}
        </div>

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Правила</h2>
          {rules.length === 0 ? (
            <p style={{ color: "#64748b" }}>Нет правил мониторинга</p>
          ) : (
            <ul style={{ paddingLeft: 20 }}>
              {rules.map((rule) => (
                <li key={rule.id} style={{ marginBottom: 8 }}>
                  <button
                    type="button"
                    style={{
                      ...styles.link,
                      border: "none",
                      background: "none",
                      padding: 0,
                      cursor: "pointer",
                      fontWeight: activeRule?.id === rule.id ? 700 : 400,
                    }}
                    onClick={() => selectRule(rule)}
                  >
                    {rule.name}
                  </button>
                  {" · "}
                  {ACCESS_MODE_LABELS[rule.access_mode] || rule.access_mode} · {rule.health_status}
                  {rule.last_run_at
                    ? ` · последний запуск ${new Date(rule.last_run_at).toLocaleString("ru-RU")}`
                    : ""}
                </li>
              ))}
            </ul>
          )}
        </div>

        {activeRule ? (
          <div style={styles.card}>
            <h2 style={{ marginTop: 0 }}>{activeRule.name}</h2>
            <div style={{ fontSize: 14, marginBottom: 12 }}>
              <div>Источник: {activeRule.source_url}</div>
              <div>Доступ: {ACCESS_MODE_LABELS[activeRule.access_mode] || activeRule.access_mode}</div>
              {activeRule.access_mode === "CREDENTIALS" && activeRule.connector_config ? (
                <div style={{ marginTop: 8, fontSize: 13, color: "#64748b" }}>
                  {activeRule.connector_config.platform_name
                    ? `Платформа: ${String(activeRule.connector_config.platform_name)}`
                    : null}
                  {activeRule.connector_config.login_hint
                    ? ` · логин: ${String(activeRule.connector_config.login_hint)}`
                    : null}
                  {activeRule.connector_config.access_notes
                    ? ` · ${String(activeRule.connector_config.access_notes)}`
                    : null}
                </div>
              ) : null}
              <div>Фильтр: {JSON.stringify(activeRule.filters)}</div>
              <div>
                Health: {activeRule.health_status}
                {activeRule.health_message ? ` — ${activeRule.health_message}` : ""}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button style={styles.secondaryButton} onClick={onHealthcheck}>
                Healthcheck
              </button>
              <button style={styles.button} onClick={onRun}>
                Запустить сейчас
              </button>
            </div>
            {lastRun ? (
              <div style={{ marginTop: 12, fontSize: 14 }}>
                Последний run: {lastRun.status} · items {lastRun.items_found} / new {lastRun.items_new} / opps{" "}
                {lastRun.opportunities_created}
                {lastRun.error_message ? ` · error: ${lastRun.error_message}` : ""}
              </div>
            ) : null}
          </div>
        ) : null}

        {publications.length > 0 ? (
          <div style={styles.card}>
            <h2 style={{ marginTop: 0 }}>Публикации</h2>
            <ul style={{ paddingLeft: 20 }}>
              {publications.map((pub) => (
                <li key={pub.id} style={{ marginBottom: 10 }}>
                  <strong>{pub.title}</strong> · {pub.status}
                  {pub.opportunity_id ? (
                    <>
                      {" · "}
                      <Link href={`/opportunities/${pub.opportunity_id}`} style={styles.link}>
                        открыть возможность
                      </Link>
                    </>
                  ) : null}
                  <div style={{ fontSize: 13, color: "#64748b" }}>
                    {pub.source_item_id} · first seen {new Date(pub.first_seen_at).toLocaleString("ru-RU")}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {message ? (
          <p style={{ padding: 12, background: "#f1f5f9", borderRadius: 6 }}>{message}</p>
        ) : null}
      </div>
    </main>
  );
}
