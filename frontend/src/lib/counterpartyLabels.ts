export const ORG_TYPE_LABELS: Record<string, string> = {
  PRODUCER: "Производитель",
  TRADER: "Трейдер",
  END_BUYER: "Покупатель",
  FORWARDER: "Экспедитор",
  SUPPLIER: "Поставщик",
  OTHER: "Другое",
};

export const CAPABILITY_TYPE_LABELS: Record<string, string> = {
  PRODUCT: "Товар",
  FREIGHT: "Фрахт",
  TERMINAL: "Терминал",
  INSURANCE: "Страхование",
  INSPECTION: "Инспекция",
  STORAGE: "Хранение",
  CUSTOMS: "Таможня",
  FINANCING: "Финансирование",
  OTHER: "Прочее",
};

export function orgTypeLabel(value: string): string {
  return ORG_TYPE_LABELS[value] ?? value;
}

export function capabilityTypeLabel(value: string): string {
  return CAPABILITY_TYPE_LABELS[value] ?? value;
}
