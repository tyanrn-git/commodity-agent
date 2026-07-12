export const OPPORTUNITY_STATUS_LABELS: Record<string, string> = {
  NEW: "Новая",
  IN_ANALYSIS: "В анализе",
  ANALYSIS_DONE: "Анализ закончен",
  NEEDS_INPUT: "Требует данных",
  ACCEPTED: "Принята",
  REJECTED: "Отклонена",
  CONVERTED: "Конвертирована в сделку",
  ARCHIVED: "В архиве",
  OTHER: "Другое",
};

export const PIPELINE_STATUS_LABELS: Record<string, string> = {
  DEAL_DRAFT: "Сделка в проработке",
  DEAL_AGREED: "Согласована сделка",
  IN_EXECUTION: "В исполнении",
  COMPLETED: "Исполнена",
  CANCELLED: "Сорвана",
};

export function displayStatusLabel(code: string, kind: string): string {
  if (kind === "PIPELINE") {
    return PIPELINE_STATUS_LABELS[code] ?? code;
  }
  return OPPORTUNITY_STATUS_LABELS[code] ?? code;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDeadlineShort(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("ru-RU");
}

export function formatDeadlines(
  quoteDeadline: string | null | undefined,
  deliveryDeadline: string | null | undefined,
  legacyDeadline?: string | null
): string {
  const quote = formatDeadlineShort(quoteDeadline || legacyDeadline);
  const delivery = formatDeadlineShort(deliveryDeadline);
  if (quote === "—" && delivery === "—") return "—";
  return `Оффер: ${quote} · Поставка: ${delivery}`;
}
