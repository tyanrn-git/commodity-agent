"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient, AIBudgetSettings, AIUsageSummary } from "@/lib/api";
import { AppNav } from "@/components/AppNav";
import { styles } from "@/lib/styles";

export default function SettingsPage() {
  const router = useRouter();
  const [budget, setBudget] = useState<AIBudgetSettings | null>(null);
  const [usage, setUsage] = useState<AIUsageSummary | null>(null);
  const [message, setMessage] = useState("");

  async function load() {
    try {
      const [b, u] = await Promise.all([apiClient.getAIBudget(), apiClient.getAIUsage()]);
      setBudget(b);
      setUsage(u);
    } catch {
      router.replace("/login");
    }
  }

  useEffect(() => {
    load();
  }, [router]);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    if (!budget) return;
    setMessage("");
    try {
      await apiClient.updateAIBudget({
        monthly_budget_usd: budget.monthly_budget_usd,
        first_warning_percent: budget.first_warning_percent,
        second_warning_percent: budget.second_warning_percent,
        hard_limit_enabled: budget.hard_limit_enabled,
        allow_manual_override: budget.allow_manual_override,
        budget_reset_day: budget.budget_reset_day,
        preferred_default_model: budget.preferred_default_model,
        fallback_model: budget.fallback_model,
        ai_enabled: budget.ai_enabled,
      });
      setMessage("Настройки сохранены");
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка сохранения");
    }
  }

  if (!budget || !usage) {
    return <main style={{ padding: 24 }}>Загрузка...</main>;
  }

  return (
    <main style={styles.page}>
      <div style={styles.container}>
        <AppNav backHref="/opportunities" backLabel="← К возможностям" />

        <div style={styles.card}>
          <h1 style={{ marginTop: 0 }}>AI-бюджет</h1>
          <p>
            Потрачено: <strong>{usage.spent_usd} USD</strong> из {usage.monthly_budget_usd} USD (
            {usage.percent_used}%)
          </p>
          <p>
            Остаток: {usage.remaining_usd} USD · Прогноз: {usage.forecast_usd} USD
          </p>
          {usage.warning_level ? (
            <p style={{ color: "#b45309" }}>Предупреждение: {usage.warning_level}</p>
          ) : null}
        </div>

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Настройки</h2>
          <form onSubmit={onSave}>
            <label style={styles.label}>Месячный бюджет (USD)</label>
            <input
              style={styles.input}
              value={budget.monthly_budget_usd}
              onChange={(e) => setBudget({ ...budget, monthly_budget_usd: e.target.value })}
            />
            <label style={styles.label}>Первое предупреждение (%)</label>
            <input
              style={styles.input}
              type="number"
              value={budget.first_warning_percent}
              onChange={(e) =>
                setBudget({ ...budget, first_warning_percent: Number(e.target.value) })
              }
            />
            <label style={styles.label}>Второе предупреждение (%)</label>
            <input
              style={styles.input}
              type="number"
              value={budget.second_warning_percent}
              onChange={(e) =>
                setBudget({ ...budget, second_warning_percent: Number(e.target.value) })
              }
            />
            <label style={styles.label}>Модель по умолчанию</label>
            <input
              style={styles.input}
              value={budget.preferred_default_model}
              onChange={(e) =>
                setBudget({ ...budget, preferred_default_model: e.target.value })
              }
            />
            <label style={styles.label}>
              <input
                type="checkbox"
                checked={budget.ai_enabled}
                onChange={(e) => setBudget({ ...budget, ai_enabled: e.target.checked })}
              />{" "}
              AI включён
            </label>
            <br />
            <label style={styles.label}>
              <input
                type="checkbox"
                checked={budget.hard_limit_enabled}
                onChange={(e) =>
                  setBudget({ ...budget, hard_limit_enabled: e.target.checked })
                }
              />{" "}
              Hard limit
            </label>
            <br />
            <label style={styles.label}>
              <input
                type="checkbox"
                checked={budget.allow_manual_override}
                onChange={(e) =>
                  setBudget({ ...budget, allow_manual_override: e.target.checked })
                }
              />{" "}
              Разрешить override
            </label>
            {message ? <p>{message}</p> : null}
            <button style={styles.button} type="submit">
              Сохранить
            </button>
          </form>
        </div>

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Расходы по моделям</h2>
          <ul>
            {usage.by_model.map((row) => (
              <li key={row.model}>
                {row.model}: {row.cost_usd} USD ({row.count} вызовов)
              </li>
            ))}
          </ul>
          <h2>Расходы по операциям</h2>
          <ul>
            {usage.by_operation.map((row) => (
              <li key={row.operation}>
                {row.operation}: {row.cost_usd} USD ({row.count} вызовов)
              </li>
            ))}
          </ul>
        </div>
      </div>
    </main>
  );
}
