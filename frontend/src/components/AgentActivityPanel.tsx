"use client";

import { useEffect, useState } from "react";
import { AgentActivityItem, apiClient } from "@/lib/api";
import { styles } from "@/lib/styles";

const AGENT_LABELS: Record<string, string> = {
  TENDER_DISCOVERY: "Поиск тендеров",
  TENDER_QUALIFICATION: "Квалификация тендера",
  SUPPLY_DISCOVERY: "Поиск поставщиков",
  LOGISTICS_DISCOVERY: "Логистика",
  DEAL_COORDINATOR: "Координатор сделки",
  PRODUCT_MATCHING: "Сопоставление товара",
  CATALOG_ASSISTANT: "Каталог",
  COUNTERPARTY_RESEARCH: "Контрагенты",
  COMMUNICATION: "Коммуникации",
  LEGACY_TENDER_PROMOTION: "Продвижение тендера (legacy)",
};

type AgentActivityPanelProps = {
  opportunityId: string;
};

export function AgentActivityPanel({ opportunityId }: AgentActivityPanelProps) {
  const [items, setItems] = useState<AgentActivityItem[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient
      .getOpportunityAgentActivity(opportunityId)
      .then(setItems)
      .catch((err) => setError(err instanceof Error ? err.message : "Ошибка загрузки"));
  }, [opportunityId]);

  return (
    <div style={styles.card}>
      <h2 style={{ marginTop: 0 }}>Agent Activity</h2>
      <p style={{ fontSize: 13, color: "#64748b", marginTop: 0 }}>
        Журнал специализированных агентов: задачи, AI-вызовы и структурированные результаты.
      </p>
      {error ? <p style={{ color: "#b91c1c" }}>{error}</p> : null}
      {items.length === 0 && !error ? (
        <p style={{ color: "#64748b", fontSize: 14 }}>Пока нет записей агентов для этой возможности.</p>
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          {items.map((item) => {
            const run = item.runs[0];
            const result = item.results[0];
            return (
              <div
                key={item.id}
                style={{
                  border: "1px solid #e2e8f0",
                  borderRadius: 8,
                  padding: 12,
                  background: "#f8fafc",
                }}
              >
                <div style={{ fontWeight: 600 }}>
                  {AGENT_LABELS[item.agent_type] || item.agent_type} · {item.task_type}
                </div>
                <div style={{ fontSize: 13, color: "#64748b", marginTop: 4 }}>
                  Статус: {item.status}
                  {run ? ` · модель ${run.model || run.provider}` : ""}
                  {run?.estimated_cost != null ? ` · $${Number(run.estimated_cost).toFixed(4)}` : ""}
                </div>
                {result?.summary ? (
                  <div style={{ fontSize: 14, marginTop: 8 }}>{result.summary}</div>
                ) : null}
                {result?.requires_review ? (
                  <div style={{ fontSize: 12, color: "#b45309", marginTop: 6 }}>Требует проверки</div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
