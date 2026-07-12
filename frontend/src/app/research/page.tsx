"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient, Product, ResearchCampaign } from "@/lib/api";
import { AppNav } from "@/components/AppNav";
import { SectionTabs } from "@/components/SectionTabs";
import { styles } from "@/lib/styles";

const INTAKE_TABS = [
  { id: "chain", label: "Поиск цепочки" },
  { id: "buyer", label: "Запрос покупателя" },
  { id: "supplier", label: "Оффер поставщика" },
] as const;

type IntakeTab = (typeof INTAKE_TABS)[number]["id"];

export default function ResearchPage() {
  const router = useRouter();
  const [intakeTab, setIntakeTab] = useState<IntakeTab>("chain");
  const [items, setItems] = useState<ResearchCampaign[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState("");

  const [name, setName] = useState("");
  const [productId, setProductId] = useState("");
  const [buyRegions, setBuyRegions] = useState("EU, Rotterdam");
  const [sellRegions, setSellRegions] = useState("Middle East, Asia");
  const [hypothesis, setHypothesis] = useState("");

  const [buyerTitle, setBuyerTitle] = useState("");
  const [buyerProductId, setBuyerProductId] = useState("");
  const [buyerHint, setBuyerHint] = useState("");

  const [supplierTitle, setSupplierTitle] = useState("");
  const [supplierProductId, setSupplierProductId] = useState("");
  const [supplierQty, setSupplierQty] = useState("100");
  const [supplierPrice, setSupplierPrice] = useState("");
  const [supplierOrigin, setSupplierOrigin] = useState("");
  const [supplierHint, setSupplierHint] = useState("");

  async function load() {
    try {
      const [campaigns, prods] = await Promise.all([
        apiClient.listResearchCampaigns(),
        apiClient.listProducts(),
      ]);
      setItems(campaigns);
      setProducts(prods);
      const defaultProduct = prods.find((p) => p.normalized_name === "SN500") || prods[0];
      if (defaultProduct) {
        if (!productId) setProductId(defaultProduct.id);
        if (!buyerProductId) setBuyerProductId(defaultProduct.id);
        if (!supplierProductId) setSupplierProductId(defaultProduct.id);
      }
    } catch {
      router.replace("/login");
    }
  }

  useEffect(() => {
    load();
  }, [router]);

  async function onCreateChain(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const created = await apiClient.createResearchCampaign({
        name,
        product_ids: productId ? [productId] : [],
        target_buy_regions: buyRegions
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        target_sell_regions: sellRegions
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        research_hypothesis: hypothesis || null,
      });
      setName("");
      router.push(`/research/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка создания");
    }
  }

  async function onCreateBuyer(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const created = await apiClient.createOpportunity({
        title: buyerTitle,
        normalized_product_id: buyerProductId || null,
        buyer_or_supplier_hint: buyerHint || null,
        notes: "Intake: buyer-led (исследование)",
      });
      setBuyerTitle("");
      router.push(`/opportunities/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка создания");
    }
  }

  async function onCreateSupplier(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const created = await apiClient.createSupplierLedOpportunity({
        title: supplierTitle,
        normalized_product_id: supplierProductId || null,
        quantity_min: supplierQty || null,
        quantity_max: supplierQty || null,
        quantity_unit: "MT",
        origin_hint: supplierOrigin || null,
        origin: supplierOrigin || null,
        buyer_or_supplier_hint: supplierHint || null,
        unit_price: supplierPrice || null,
        currency: "USD",
        incoterm: "FOB",
        notes: "Intake: supplier-led (исследование)",
      });
      setSupplierTitle("");
      router.push(`/opportunities/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка создания");
    }
  }

  function viabilityLabel(status: string) {
    const map: Record<string, string> = {
      UNKNOWN: "Неизвестно",
      VIABLE_CANDIDATE: "Перспективная цепочка",
      NO_VIABLE_CHAIN_FOUND: "Цепочка не найдена",
    };
    return map[status] || status;
  }

  return (
    <main style={styles.page}>
      <div style={styles.container}>
        <h1 style={{ margin: 0, marginBottom: 8 }}>Исследование</h1>
        <p style={{ margin: "0 0 16px", color: "#64748b", fontSize: 14 }}>
          Ввод сырых сигналов: поиск цепочки, запрос покупателя, оффер поставщика. После заполнения
          коммерции сценарий попадает в{" "}
          <Link href="/opportunities" style={styles.link}>
            Возможности
          </Link>
          .
        </p>
        <AppNav />

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Новое исследование</h2>
          <SectionTabs
            tabs={[...INTAKE_TABS]}
            activeId={intakeTab}
            onChange={(id) => setIntakeTab(id as IntakeTab)}
          />

          {intakeTab === "chain" ? (
            <form onSubmit={onCreateChain}>
              <p style={{ fontSize: 13, color: "#64748b" }}>
                Активный поиск цепочки: регионы, гипотеза, лиды и outreach.
              </p>
              <label style={styles.label}>Название кампании</label>
              <input
                style={styles.input}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="SN500 EU discovery pilot"
                required
              />
              <label style={styles.label}>Товар</label>
              <select
                style={styles.input}
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
                required
              >
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.normalized_name}
                  </option>
                ))}
              </select>
              <label style={styles.label}>Регионы покупателей (через запятую)</label>
              <input style={styles.input} value={buyRegions} onChange={(e) => setBuyRegions(e.target.value)} />
              <label style={styles.label}>Регионы поставщиков (через запятую)</label>
              <input style={styles.input} value={sellRegions} onChange={(e) => setSellRegions(e.target.value)} />
              <label style={styles.label}>Гипотеза</label>
              <textarea
                style={{ ...styles.input, minHeight: 72, resize: "vertical" }}
                value={hypothesis}
                onChange={(e) => setHypothesis(e.target.value)}
                placeholder="Есть ли рабочая цепочка SN500 UAE → EU?"
              />
              <button style={styles.button} type="submit">
                Создать кампанию
              </button>
            </form>
          ) : null}

          {intakeTab === "buyer" ? (
            <form onSubmit={onCreateBuyer}>
              <p style={{ fontSize: 13, color: "#64748b" }}>
                Запрос покупателя: загрузите PDF/email на карточке возможности, AI извлечёт условия.
              </p>
              <label style={styles.label}>Название</label>
              <input
                style={styles.input}
                value={buyerTitle}
                onChange={(e) => setBuyerTitle(e.target.value)}
                placeholder="Запрос покупателя на SN500"
                required
              />
              <label style={styles.label}>Товар</label>
              <select
                style={styles.input}
                value={buyerProductId}
                onChange={(e) => setBuyerProductId(e.target.value)}
              >
                <option value="">Не выбран</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.normalized_name}
                  </option>
                ))}
              </select>
              <label style={styles.label}>Покупатель (подсказка)</label>
              <input
                style={styles.input}
                value={buyerHint}
                onChange={(e) => setBuyerHint(e.target.value)}
                placeholder="Rotterdam Base Oils"
              />
              <button style={styles.button} type="submit">
                Создать и открыть возможность
              </button>
            </form>
          ) : null}

          {intakeTab === "supplier" ? (
            <form onSubmit={onCreateSupplier}>
              <p style={{ fontSize: 13, color: "#64748b" }}>
                Подтверждённый оффер поставщика — система найдёт buyer needs и подготовит outreach.
              </p>
              <label style={styles.label}>Название</label>
              <input
                style={styles.input}
                value={supplierTitle}
                onChange={(e) => setSupplierTitle(e.target.value)}
                placeholder="Gulf SN500 FOB Jebel Ali"
                required
              />
              <label style={styles.label}>Товар</label>
              <select
                style={styles.input}
                value={supplierProductId}
                onChange={(e) => setSupplierProductId(e.target.value)}
              >
                <option value="">Не выбран</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.normalized_name}
                  </option>
                ))}
              </select>
              <label style={styles.label}>Объём (MT)</label>
              <input style={styles.input} value={supplierQty} onChange={(e) => setSupplierQty(e.target.value)} />
              <label style={styles.label}>Цена USD/MT</label>
              <input
                style={styles.input}
                value={supplierPrice}
                onChange={(e) => setSupplierPrice(e.target.value)}
                placeholder="850"
              />
              <label style={styles.label}>Происхождение / порт</label>
              <input
                style={styles.input}
                value={supplierOrigin}
                onChange={(e) => setSupplierOrigin(e.target.value)}
                placeholder="Jebel Ali"
              />
              <label style={styles.label}>Поставщик</label>
              <input
                style={styles.input}
                value={supplierHint}
                onChange={(e) => setSupplierHint(e.target.value)}
                placeholder="Gulf Base Oil"
              />
              <button style={styles.button} type="submit">
                Создать и открыть возможность
              </button>
            </form>
          ) : null}

          {error ? <div style={{ ...styles.error, marginTop: 12 }}>{error}</div> : null}
        </div>

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Кампании поиска цепочки</h2>
          {items.length === 0 ? (
            <p style={{ color: "#64748b" }}>Пока нет кампаний</p>
          ) : (
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {items.map((item) => (
                <li
                  key={item.id}
                  style={{ padding: "12px 0", borderBottom: "1px solid #e2e8f0" }}
                >
                  <Link href={`/research/${item.id}`} style={styles.link}>
                    {item.name}
                  </Link>
                  <div style={{ fontSize: 13, color: "#64748b", marginTop: 4 }}>
                    {item.status} · {viabilityLabel(item.viability_status)}
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
