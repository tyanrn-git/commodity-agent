"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api";
import { styles } from "@/lib/styles";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@localhost");
  const [password, setPassword] = useState("changeme");
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await apiClient.login(email, password);
      router.push("/opportunities");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка входа");
    }
  }

  return (
    <main style={styles.page}>
      <div style={{ ...styles.container, maxWidth: 420 }}>
        <div style={styles.card}>
          <h1 style={{ marginTop: 0 }}>Commodity Agent</h1>
          <p style={{ color: "#64748b" }}>Вход в рабочее место трейдера</p>
          <form onSubmit={onSubmit}>
            <label style={styles.label}>Email</label>
            <input
              style={styles.input}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              required
            />
            <label style={styles.label}>Пароль</label>
            <input
              style={styles.input}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              required
            />
            {error ? <div style={styles.error}>{error}</div> : null}
            <button style={styles.button} type="submit">
              Войти
            </button>
          </form>
        </div>
      </div>
    </main>
  );
}
