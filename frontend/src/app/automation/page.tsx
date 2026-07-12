"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  apiClient,
  AutomatedActionLog,
  AutomationRun,
  AutomationSettings,
} from "@/lib/api";
import { AppNav } from "@/components/AppNav";
import { styles } from "@/lib/styles";

export default function AutomationPage() {
  const router = useRouter();
  const [settings, setSettings] = useState<AutomationSettings | null>(null);
  const [runs, setRuns] = useState<AutomationRun[]>([]);
  const [actions, setActions] = useState<AutomatedActionLog[]>([]);
  const [message, setMessage] = useState("");

  async function load() {
    try {
      const [s, r, a] = await Promise.all([
        apiClient.getAutomationSettings(),
        apiClient.listAutomationRuns(),
        apiClient.listAutomationActions(),
      ]);
      setSettings(s);
      setRuns(r);
      setActions(a);
    } catch {
      router.replace("/login");
    }
  }

  useEffect(() => {
    load();
  }, [router]);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    if (!settings) return;
    setMessage("");
    try {
      const updated = await apiClient.updateAutomationSettings({
        auto_follow_up_enabled: settings.auto_follow_up_enabled,
        follow_up_after_days: settings.follow_up_after_days,
        max_follow_ups_per_rfq: settings.max_follow_ups_per_rfq,
        min_days_between_follow_ups: settings.min_days_between_follow_ups,
        max_auto_actions_per_day: settings.max_auto_actions_per_day,
      });
      setSettings(updated);
      setMessage("Настройки сохранены");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка сохранения");
    }
  }

  async function onRun() {
    setMessage("");
    try {
      const run = await apiClient.runAutomation();
      setMessage(
        `Запуск: ${run.status} · отправлено ${run.actions_sent}, пропущено ${run.actions_skipped}, заблокировано ${run.actions_blocked}, лимит ${run.actions_rate_limited}`
      );
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка запуска");
    }
  }

  if (!settings) {
    return <main style={{ padding: 24 }}>Загрузка...</main>;
  }

  return (
    <main style={styles.page}>
      <div style={styles.container}>
        <h1 style={{ margin: 0, marginBottom: 16 }}>Контролируемая автоматизация</h1>
        <AppNav />

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Auto follow-up RFQ</h2>
          <p style={{ fontSize: 13, color: "#64748b" }}>
            Автоматически отправляются только NON_BINDING напоминания (INFORMATIONAL) по отправленным RFQ без ответа.
            COMMERCIAL_SENSITIVE, POTENTIALLY_BINDING и BINDING всегда требуют ручного approval.
          </p>
          <form onSubmit={onSave}>
            <label style={styles.label}>
              <input
                type="checkbox"
                checked={settings.auto_follow_up_enabled}
                onChange={(e) =>
                  setSettings({ ...settings, auto_follow_up_enabled: e.target.checked })
                }
              />{" "}
              Включить auto follow-up
            </label>
            <label style={styles.label}>Дней до первого follow-up</label>
            <input
              style={styles.input}
              type="number"
              min={1}
              max={30}
              value={settings.follow_up_after_days}
              onChange={(e) =>
                setSettings({ ...settings, follow_up_after_days: Number(e.target.value) })
              }
            />
            <label style={styles.label}>Макс. follow-up на RFQ</label>
            <input
              style={styles.input}
              type="number"
              min={0}
              max={10}
              value={settings.max_follow_ups_per_rfq}
              onChange={(e) =>
                setSettings({ ...settings, max_follow_ups_per_rfq: Number(e.target.value) })
              }
            />
            <label style={styles.label}>Мин. дней между follow-up</label>
            <input
              style={styles.input}
              type="number"
              min={1}
              max={30}
              value={settings.min_days_between_follow_ups}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  min_days_between_follow_ups: Number(e.target.value),
                })
              }
            />
            <label style={styles.label}>Лимит авто-действий в день</label>
            <input
              style={styles.input}
              type="number"
              min={1}
              max={100}
              value={settings.max_auto_actions_per_day}
              onChange={(e) =>
                setSettings({ ...settings, max_auto_actions_per_day: Number(e.target.value) })
              }
            />
            <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button style={styles.button} type="submit">
                Сохранить
              </button>
              <button style={styles.secondaryButton} type="button" onClick={onRun}>
                Запустить сейчас
              </button>
            </div>
          </form>
          {message ? <p style={{ marginTop: 12 }}>{message}</p> : null}
        </div>

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Последние запуски</h2>
          {runs.length === 0 ? (
            <p style={{ color: "#64748b" }}>Запусков пока нет</p>
          ) : (
            <ul style={{ paddingLeft: 20 }}>
              {runs.slice(0, 10).map((run) => (
                <li key={run.id} style={{ marginBottom: 8 }}>
                  {new Date(run.started_at).toLocaleString("ru-RU")} · {run.status} · sent{" "}
                  {run.actions_sent} / eval {run.actions_evaluated}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Журнал авто-действий</h2>
          {actions.length === 0 ? (
            <p style={{ color: "#64748b" }}>Действий пока нет</p>
          ) : (
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {actions.slice(0, 20).map((action) => (
                <li
                  key={action.id}
                  style={{ padding: "10px 0", borderBottom: "1px solid #e2e8f0", fontSize: 13 }}
                >
                  <strong>{action.status}</strong> · {action.action_type} · {action.entity_type}{" "}
                  {action.entity_id.slice(0, 8)}…
                  <div style={{ color: "#64748b" }}>
                    {action.action_category} · {action.binding_class}
                    {action.reason ? ` · ${action.reason}` : ""}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </main>
  );
}
