const amountFormatter = new Intl.NumberFormat("ru-RU", {
  maximumFractionDigits: 0,
});

const percentFormatter = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function toNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const num = typeof value === "number" ? value : Number(String(value).replace(/\s/g, "").replace(",", "."));
  return Number.isFinite(num) ? num : null;
}

export function formatAmount(value: string | number | null | undefined): string {
  const num = toNumber(value);
  if (num === null) return "—";
  return amountFormatter.format(Math.round(num));
}

export function formatPercent(value: string | number | null | undefined): string {
  const num = toNumber(value);
  if (num === null) return "—";
  return percentFormatter.format(num);
}

const COST_LABELS: Record<string, string> = {
  product_purchase_cost: "Закупка",
  inland_transport: "Внутренняя логистика",
  main_freight: "Основной фрахт",
  port_terminal_handling: "Порт / терминал",
  storage: "Хранение",
  insurance: "Страхование",
  inspection: "Инспекция",
  customs_and_duties: "Таможня и пошлины",
  financing_cost: "Финансирование",
  base_currency: "Валюта расчёта",
};

export function formatCostBreakdownKey(key: string): string {
  return COST_LABELS[key] || key;
}

export function formatCostBreakdownValue(key: string, value: string): string {
  if (key === "base_currency") return value;
  return formatAmount(value);
}
