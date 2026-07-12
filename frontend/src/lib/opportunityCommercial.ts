export type OpportunityCommercialRow = {
  buyer_name: string | null;
  seller_name: string | null;
  product_name: string | null;
  volume: string | null;
  buy_price_per_unit: number | null;
  buy_currency: string | null;
  buy_incoterm: string | null;
  buy_basis: string | null;
  sell_price_per_unit: number | null;
  sell_currency: string | null;
  sell_incoterm: string | null;
  sell_basis: string | null;
  transport_cost: number | null;
  other_costs: number | null;
  costs_currency: string | null;
  gross_margin: number | null;
  gross_margin_percent: number | null;
  margin_currency: string | null;
  data_completeness: string;
  source: string | null;
};

export function formatPrice(value: number | null | undefined, currency: string | null | undefined): string {
  if (value == null) return "—";
  const rounded = Number.isInteger(value) ? value.toString() : value.toFixed(2);
  return currency ? `${rounded} ${currency}` : rounded;
}

export function formatMoney(value: number | null | undefined, currency: string | null | undefined): string {
  if (value == null) return "—";
  const rounded = Math.round(value).toLocaleString("ru-RU");
  return currency ? `${rounded} ${currency}` : rounded;
}

export function completenessLabel(value: string): string {
  const map: Record<string, string> = {
    EMPTY: "пусто",
    PARTIAL: "частично",
    ESTIMATED: "оценка",
    CONFIRMED: "подтверждено",
  };
  return map[value] ?? value;
}
