"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient, ApiError, openSourceContent, OpportunityBoardDocument, OpportunityBoardItem, SkippedMonitoringItem } from "@/lib/api";
import { AppNav } from "@/components/AppNav";
import {
  completenessLabel,
  formatMoney,
  formatPrice,
} from "@/lib/opportunityCommercial";
import { formatDateTime, formatDeadlines } from "@/lib/opportunityStatus";
import { styles } from "@/lib/styles";

const thStyle = { padding: "8px 6px", fontSize: 12, color: "#64748b", whiteSpace: "nowrap" as const };
const tdStyle = { padding: "10px 6px", fontSize: 13, verticalAlign: "top" as const };
const iconButtonStyle = {
  border: "none",
  background: "none",
  cursor: "pointer",
  fontSize: 18,
  lineHeight: 1,
  padding: 2,
};

function openDocument(doc: OpportunityBoardDocument) {
  openSourceContent(doc.id, doc.source_url).catch(() => undefined);
}

function SkippedCard({ item }: { item: SkippedMonitoringItem }) {
  const qty =
    item.quantity != null
      ? `${Math.round(item.quantity)} ${item.quantity_unit || ""}`.trim()
      : null;
  const commercial = [item.product, qty, item.destination ? `→ ${item.destination}` : null, item.buyer]
    .filter(Boolean)
    .join(" · ");

  return (
    <li style={{ padding: "14px 0", borderBottom: "1px solid #fee2e2" }}>
      <div style={{ fontWeight: 600, color: "#991b1b" }}>{item.title}</div>
      <div style={{ fontSize: 13, color: "#64748b", marginTop: 4 }}>
        {commercial || "Без коммерческих полей"}
      </div>
      <div style={{ marginTop: 8, fontSize: 13, color: "#7f1d1d" }}>
        <strong>Не стала возможностью:</strong> {item.filter_explanation}
      </div>
      <div style={{ marginTop: 4, fontSize: 12, color: "#94a3b8" }}>
        Правило: {item.monitoring_rule_name} ·{" "}
        <Link href="/monitoring" style={styles.link}>
          мониторинг
        </Link>
      </div>
    </li>
  );
}

export default function OpportunitiesPage() {
  const router = useRouter();
  const [items, setItems] = useState<OpportunityBoardItem[]>([]);
  const [skipped, setSkipped] = useState<SkippedMonitoringItem[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      const board = await apiClient.getOpportunitiesBoard();
      setItems(board.opportunities);
      setSkipped(board.skipped_monitoring);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Не удалось загрузить возможности");
    }
  }

  useEffect(() => {
    load();
  }, [router]);

  async function onLogout() {
    await apiClient.logout();
    router.push("/login");
  }

  return (
    <main style={styles.page}>
      <div style={styles.container}>
        <div style={styles.header}>
          <div>
            <h1 style={{ margin: 0 }}>Возможности</h1>
            <p style={{ margin: "6px 0 0", color: "#64748b", fontSize: 14 }}>
              Коммерческий pipeline: сравнение сценариев по сторонам, ценам, базисам и марже.
              Новые сигналы вводятся в разделе{" "}
              <Link href="/research" style={styles.link}>
                Исследование
              </Link>
              .
            </p>
          </div>
          <button style={styles.secondaryButton} onClick={onLogout}>
            Выйти
          </button>
        </div>

        <AppNav />

        {error ? <div style={styles.error}>{error}</div> : null}

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Коммерческая таблица ({items.length})</h2>
          {items.length === 0 ? (
            <p style={{ color: "#64748b" }}>
              Пока нет возможностей. Создайте intake в{" "}
              <Link href="/research" style={styles.link}>
                Исследовании
              </Link>{" "}
              или запустите{" "}
              <Link href="/monitoring" style={styles.link}>
                мониторинг
              </Link>
              .
            </p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", minWidth: 1200, borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ textAlign: "left", borderBottom: "2px solid #e2e8f0" }}>
                    <th style={thStyle}>Сценарий</th>
                    <th style={thStyle}>Статус</th>
                    <th style={thStyle}>Сроки</th>
                    <th style={thStyle}>Покупатель</th>
                    <th style={thStyle}>Продавец</th>
                    <th style={thStyle}>Товар</th>
                    <th style={thStyle}>Объём</th>
                    <th style={thStyle}>Цена покупки</th>
                    <th style={thStyle}>Базис покупки</th>
                    <th style={thStyle}>Цена продажи</th>
                    <th style={thStyle}>Базис продажи</th>
                    <th style={thStyle}>Транспорт</th>
                    <th style={thStyle}>Прочие</th>
                    <th style={thStyle}>Маржа</th>
                    <th style={thStyle}>Ссылка</th>
                    <th style={thStyle}>Документы</th>
                    <th style={thStyle}>Данные</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => {
                    const row = item.commercial_row ?? {
                      buyer_name: null,
                      seller_name: null,
                      product_name: item.normalized_product_name,
                      volume: null,
                      buy_price_per_unit: null,
                      buy_currency: null,
                      buy_incoterm: null,
                      buy_basis: null,
                      sell_price_per_unit: null,
                      sell_currency: null,
                      sell_incoterm: null,
                      sell_basis: null,
                      transport_cost: null,
                      other_costs: null,
                      costs_currency: null,
                      gross_margin: null,
                      gross_margin_percent: null,
                      margin_currency: null,
                      data_completeness: "EMPTY",
                      source: null,
                    };
                    return (
                      <tr key={item.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                        <td style={tdStyle}>
                          <Link href={`/opportunities/${item.id}`} style={{ ...styles.link, fontWeight: 600 }}>
                            {item.title}
                          </Link>
                          <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4 }}>
                            {item.type_label} · {item.origin_label}
                            {item.deal_id ? (
                              <>
                                {" · "}
                                <Link href={`/deals/${item.deal_id}`} style={styles.link}>
                                  сделка
                                </Link>
                              </>
                            ) : null}
                          </div>
                        </td>
                        <td style={tdStyle}>
                          <div style={{ fontWeight: 600 }}>
                            {item.display_status?.label ?? item.status}
                          </div>
                          <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4 }}>
                            {formatDateTime(item.display_status?.changed_at ?? item.status_changed_at)}
                          </div>
                        </td>
                        <td style={{ ...tdStyle, fontSize: 12, color: "#64748b" }}>
                          {formatDeadlines(item.quote_deadline, item.delivery_deadline, item.deadline)}
                        </td>
                        <td style={tdStyle}>{row.buyer_name || "—"}</td>
                        <td style={tdStyle}>{row.seller_name || "—"}</td>
                        <td style={tdStyle}>{row.product_name || item.normalized_product_name || "—"}</td>
                        <td style={tdStyle}>{row.volume || "—"}</td>
                        <td style={tdStyle}>
                          {formatPrice(row.buy_price_per_unit, row.buy_currency)}
                        </td>
                        <td style={tdStyle}>{row.buy_basis || row.buy_incoterm || "—"}</td>
                        <td style={tdStyle}>
                          {formatPrice(row.sell_price_per_unit, row.sell_currency)}
                        </td>
                        <td style={tdStyle}>{row.sell_basis || row.sell_incoterm || "—"}</td>
                        <td style={tdStyle}>
                          {formatMoney(row.transport_cost, row.costs_currency)}
                        </td>
                        <td style={tdStyle}>
                          {formatMoney(row.other_costs, row.costs_currency)}
                        </td>
                        <td style={tdStyle}>
                          {row.gross_margin != null ? (
                            <>
                              {formatMoney(row.gross_margin, row.margin_currency)}
                              {row.gross_margin_percent != null
                                ? ` (${row.gross_margin_percent.toFixed(1)}%)`
                                : ""}
                            </>
                          ) : (
                            item.economics_preview || "—"
                          )}
                        </td>
                        <td style={tdStyle}>
                          {item.source_url ? (
                            <button
                              type="button"
                              title={item.source_url}
                              style={iconButtonStyle}
                              onClick={() => window.open(item.source_url!, "_blank", "noopener,noreferrer")}
                            >
                              🔗
                            </button>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td style={tdStyle}>
                          {item.documents?.length ? (
                            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                              {item.documents.map((doc) => (
                                <button
                                  key={doc.id}
                                  type="button"
                                  title={doc.label}
                                  style={iconButtonStyle}
                                  onClick={() => openDocument(doc)}
                                >
                                  📄
                                </button>
                              ))}
                            </div>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td style={{ ...tdStyle, fontSize: 11, color: "#64748b" }}>
                          {completenessLabel(row.data_completeness)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {skipped.length > 0 ? (
          <div style={{ ...styles.card, borderColor: "#fecaca" }}>
            <h2 style={{ marginTop: 0 }}>Пропущено мониторингом</h2>
            <p style={{ color: "#64748b", fontSize: 14, marginTop: 0 }}>
              Объявления, которые система увидела, но не превратила в возможность из‑за фильтра товара.
            </p>
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {skipped.map((item) => (
                <SkippedCard key={item.id} item={item} />
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </main>
  );
}
