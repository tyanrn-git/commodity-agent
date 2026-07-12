"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiClient, ProductDetail, ProductSpecProfile } from "@/lib/api";
import { AppNav } from "@/components/AppNav";
import { ProductAssistantPanel } from "@/components/ProductAssistantPanel";
import { styles } from "@/lib/styles";

function materialityLabel(value: string) {
  if (value === "MATERIAL") return "принципиально";
  if (value === "IMMATERIAL") return "несущественно";
  return "не определено";
}

function SpecList({ specs, title }: { specs: ProductSpecProfile[]; title: string }) {
  if (specs.length === 0) {
    return <p style={{ color: "#64748b", fontSize: 13 }}>Пока нет параметров</p>;
  }
  return (
    <>
      <h3 style={{ fontSize: 15 }}>{title}</h3>
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {specs.map((spec) => (
          <li key={spec.id} style={{ padding: "10px 0", borderBottom: "1px solid #e2e8f0" }}>
            <strong>{spec.parameter_name}</strong>
            {spec.is_mandatory ? " *" : ""}
            {spec.unit ? ` · ${spec.unit}` : ""}
            <div style={{ fontSize: 13, color: "#64748b", marginTop: 4 }}>
              {spec.minimum_value || spec.maximum_value
                ? `Диапазон: ${spec.minimum_value ?? "—"} – ${spec.maximum_value ?? "—"}`
                : "Значения не заполнены — AI дополнит из RFQ/оферт"}
            </div>
            {spec.parameter_kind === "VARIANT" ? (
              <div style={{ fontSize: 12, color: "#475569", marginTop: 4 }}>
                Отличие: {materialityLabel(spec.variation_materiality)}
              </div>
            ) : null}
            {spec.description ? (
              <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 4 }}>{spec.description}</div>
            ) : null}
            <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4 }}>
              Источников: {spec.evidence_count}
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}

export default function ProductDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [item, setItem] = useState<ProductDetail | null>(null);

  const load = useCallback(async () => {
    try {
      setItem(await apiClient.getProduct(params.id));
    } catch {
      router.replace("/login");
    }
  }, [params.id, router]);

  useEffect(() => {
    load();
  }, [load]);

  if (!item) {
    return (
      <main style={styles.page}>
        <div style={styles.container}>Загрузка...</div>
      </main>
    );
  }

  const identitySpecs = item.specification_profiles.filter((s) => s.parameter_kind === "IDENTITY");
  const variantSpecs = item.specification_profiles.filter((s) => s.parameter_kind !== "IDENTITY");

  return (
    <main style={styles.page}>
      <div style={styles.container}>
        <AppNav backHref="/products" backLabel="← К каталогу" />
        <div style={styles.card}>
          <h1 style={{ marginTop: 0 }}>{item.normalized_name}</h1>
          <p style={{ color: "#64748b" }}>
            {item.category} · заполнено {item.completeness.completeness_percent}% · ключевых{" "}
            {item.completeness.identity_parameters} · вариативных {item.completeness.variant_parameters}
          </p>
          <p style={{ fontSize: 13, color: "#64748b" }}>
            Система автоматически дополняет карточку из заказов, предложений и AI-разрешения продукта.
          </p>
          {item.aliases?.length ? <p>Синонимы: {item.aliases.join(", ")}</p> : null}
        </div>

        <ProductAssistantPanel productId={params.id} onUpdated={load} />

        <div style={styles.card}>
          <h2 style={{ marginTop: 0 }}>Спецификация</h2>
          <SpecList
            specs={identitySpecs}
            title="Ключевые (IDENTITY) — определяют ЧТО это за товар"
          />
          <div style={{ marginTop: 20 }}>
            <SpecList
              specs={variantSpecs}
              title="Вариативные (VARIANT) — физико-химия, может отличаться"
            />
          </div>
        </div>
      </div>
    </main>
  );
}
