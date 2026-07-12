"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient, Product } from "@/lib/api";
import { AppNav } from "@/components/AppNav";
import { statBoxStyle } from "@/components/SectionTabs";
import { styles } from "@/lib/styles";

export default function ProductsPage() {
  const router = useRouter();
  const [items, setItems] = useState<Product[]>([]);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("other");
  const [aliases, setAliases] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    try {
      setItems(await apiClient.listProductsCatalog());
    } catch {
      router.replace("/login");
    }
  }

  useEffect(() => {
    load();
  }, [router]);

  const categories = useMemo(() => {
    const values = new Set(items.map((item) => item.category).filter(Boolean));
    return Array.from(values).sort();
  }, [items]);

  const filtered = useMemo(
    () => (categoryFilter ? items.filter((item) => item.category === categoryFilter) : items),
    [items, categoryFilter]
  );

  const stats = useMemo(() => {
    const withSpecs = items.filter(
      (item) => item.completeness && item.completeness.filled_parameters > 0
    ).length;
    const complete = items.filter(
      (item) => item.completeness && item.completeness.completeness_percent >= 80
    ).length;
    return { total: items.length, withSpecs, complete };
  }, [items]);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    try {
      await apiClient.createProduct({
        normalized_name: name.trim(),
        category: category.trim() || "other",
        aliases: aliases
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        typical_units: ["MT", "kg"],
        spec_parameters: [],
      });
      setName("");
      setAliases("");
      setMessage("Товар добавлен в каталог (спецификация может быть пустой)");
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка создания");
    }
  }

  return (
    <main style={styles.page}>
      <div style={styles.container}>
        <AppNav backHref="/opportunities" backLabel="← К возможностям" />

        <div style={styles.card}>
          <h1 style={{ marginTop: 0 }}>Управление товарами</h1>
          <p style={{ fontSize: 13, color: "#64748b", marginBottom: 0 }}>
            Открытый каталог: товары добавляются вручную или через AI при разрешении продукта.
            Спецификация может быть пустой, частичной или полной — AI дополняет её из заказов и
            предложений.
          </p>
        </div>

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
          <div style={statBoxStyle}>
            <div style={{ fontSize: 12, color: "#64748b" }}>Товаров</div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{stats.total}</div>
          </div>
          <div style={statBoxStyle}>
            <div style={{ fontSize: 12, color: "#64748b" }}>Со спецификацией</div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{stats.withSpecs}</div>
          </div>
          <div style={statBoxStyle}>
            <div style={{ fontSize: 12, color: "#64748b" }}>Заполнено ≥80%</div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{stats.complete}</div>
          </div>
        </div>

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Добавить товар</h2>
          <form onSubmit={onCreate}>
            <label style={styles.label}>Название</label>
            <input style={styles.input} value={name} onChange={(e) => setName(e.target.value)} required />
            <label style={styles.label}>Категория</label>
            <input
              style={styles.input}
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="polymer, base_oil, vegetable_oil..."
            />
            <label style={styles.label}>Синонимы (через запятую)</label>
            <input
              style={styles.input}
              value={aliases}
              onChange={(e) => setAliases(e.target.value)}
              placeholder="гуар, guar gum"
            />
            <button style={styles.button} type="submit" disabled={!name.trim()}>
              Добавить в каталог
            </button>
          </form>
          {message ? <p style={{ marginTop: 12 }}>{message}</p> : null}
        </div>

        <div style={styles.card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
            <h2 style={{ marginTop: 0, marginBottom: 0 }}>Каталог ({filtered.length})</h2>
            <select
              style={{ ...styles.input, marginBottom: 0, width: "auto", minWidth: 180 }}
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
            >
              <option value="">Все категории</option>
              {categories.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>

          {filtered.length === 0 ? (
            <p style={{ color: "#64748b" }}>Каталог пуст</p>
          ) : (
            <div style={{ overflowX: "auto", marginTop: 12 }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
                <thead>
                  <tr style={{ textAlign: "left", borderBottom: "1px solid #e2e8f0" }}>
                    <th style={{ padding: "8px 4px" }}>Товар</th>
                    <th style={{ padding: "8px 4px" }}>Категория</th>
                    <th style={{ padding: "8px 4px" }}>Спецификация</th>
                    <th style={{ padding: "8px 4px" }}>Синонимы</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((item) => (
                    <tr key={item.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                      <td style={{ padding: "12px 4px" }}>
                        <Link href={`/products/${item.id}`} style={{ ...styles.link, fontWeight: 600 }}>
                          {item.normalized_name}
                        </Link>
                      </td>
                      <td style={{ padding: "12px 4px" }}>{item.category}</td>
                      <td style={{ padding: "12px 4px", fontSize: 13, color: "#64748b" }}>
                        {item.completeness
                          ? `${item.completeness.completeness_percent}% (${item.completeness.filled_parameters}/${item.completeness.total_parameters})`
                          : "—"}
                      </td>
                      <td style={{ padding: "12px 4px", fontSize: 12, color: "#94a3b8" }}>
                        {item.aliases?.length ? item.aliases.join(", ") : "—"}
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
