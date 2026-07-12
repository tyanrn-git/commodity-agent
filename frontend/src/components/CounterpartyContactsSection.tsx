"use client";

import { FormEvent, useState } from "react";
import { apiClient, Contact } from "@/lib/api";
import { styles } from "@/lib/styles";

type Props = {
  counterpartyId: string;
  contacts: Contact[];
  onUpdated: () => Promise<void>;
};

export function CounterpartyContactsSection({ counterpartyId, contacts, onUpdated }: Props) {
  const [fullName, setFullName] = useState("");
  const [roleTitle, setRoleTitle] = useState("");
  const [department, setDepartment] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [isPrimary, setIsPrimary] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onAddContact(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await apiClient.createContact(counterpartyId, {
        full_name: fullName.trim() || null,
        role_title: roleTitle.trim() || null,
        department: department.trim() || null,
        email: email.trim() || null,
        phone: phone.trim() || null,
        is_primary: isPrimary,
      });
      setFullName("");
      setRoleTitle("");
      setDepartment("");
      setEmail("");
      setPhone("");
      setIsPrimary(false);
      setMessage("Менеджер добавлен");
      await onUpdated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div style={styles.card}>
        <h2 style={{ marginTop: 0 }}>Менеджеры и контакты</h2>
        <p style={{ fontSize: 13, color: "#64748b" }}>
          Контактные лица контрагента для RFQ, переговоров и сделок. AI-подсказки из обогащения
          профиля можно добавить вручную из вкладки «Товары и услуги».
        </p>
        {contacts.length === 0 ? (
          <p style={{ color: "#64748b" }}>Контакты не добавлены</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
              <thead>
                <tr style={{ textAlign: "left", borderBottom: "1px solid #e2e8f0" }}>
                  <th style={{ padding: "8px 4px" }}>Имя</th>
                  <th style={{ padding: "8px 4px" }}>Должность</th>
                  <th style={{ padding: "8px 4px" }}>Отдел</th>
                  <th style={{ padding: "8px 4px" }}>Email</th>
                  <th style={{ padding: "8px 4px" }}>Телефон</th>
                  <th style={{ padding: "8px 4px" }}>Статус</th>
                </tr>
              </thead>
              <tbody>
                {contacts.map((contact) => (
                  <tr key={contact.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                    <td style={{ padding: "10px 4px" }}>
                      {contact.full_name || "—"}
                      {contact.is_primary ? (
                        <span style={{ marginLeft: 6, fontSize: 11, color: "#1d4ed8" }}>основной</span>
                      ) : null}
                    </td>
                    <td style={{ padding: "10px 4px" }}>{contact.role_title || "—"}</td>
                    <td style={{ padding: "10px 4px" }}>{contact.department || "—"}</td>
                    <td style={{ padding: "10px 4px" }}>{contact.email || "—"}</td>
                    <td style={{ padding: "10px 4px" }}>{contact.phone || "—"}</td>
                    <td style={{ padding: "10px 4px", fontSize: 12, color: "#64748b" }}>
                      {contact.verification_status}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div style={styles.card}>
        <h3 style={{ marginTop: 0 }}>Добавить менеджера</h3>
        <form onSubmit={onAddContact}>
          <label style={styles.label}>Имя</label>
          <input
            style={styles.input}
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
          />
          <label style={styles.label}>Должность</label>
          <input
            style={styles.input}
            value={roleTitle}
            onChange={(e) => setRoleTitle(e.target.value)}
            placeholder="Sales Manager, Procurement..."
          />
          <label style={styles.label}>Отдел</label>
          <input
            style={styles.input}
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
          />
          <label style={styles.label}>Email</label>
          <input
            style={styles.input}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <label style={styles.label}>Телефон</label>
          <input style={styles.input} value={phone} onChange={(e) => setPhone(e.target.value)} />
          <label style={{ ...styles.label, display: "flex", alignItems: "center", gap: 8 }}>
            <input
              type="checkbox"
              checked={isPrimary}
              onChange={(e) => setIsPrimary(e.target.checked)}
            />
            Основной контакт
          </label>
          <button style={styles.button} type="submit" disabled={busy}>
            {busy ? "Сохранение..." : "Добавить"}
          </button>
        </form>
        {message ? <p style={{ marginTop: 12 }}>{message}</p> : null}
        {error ? <div style={styles.error}>{error}</div> : null}
      </div>
    </div>
  );
}
