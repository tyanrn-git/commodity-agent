export type RegionOption = {
  id: string;
  label: string;
  value: string;
};

export type RegionGroup = {
  id: string;
  label: string;
  value: string;
  countries: RegionOption[];
};

export const WORLD_REGION: RegionOption = {
  id: "world",
  label: "Весь мир",
  value: "Global",
};

export const REGION_GROUPS: RegionGroup[] = [
  {
    id: "cis",
    label: "СНГ / ЕАЭС",
    value: "CIS",
    countries: [
      { id: "ru", label: "Россия", value: "Russia" },
      { id: "by", label: "Беларусь", value: "Belarus" },
      { id: "kz", label: "Казахстан", value: "Kazakhstan" },
      { id: "uz", label: "Узбекистан", value: "Uzbekistan" },
      { id: "am", label: "Армения", value: "Armenia" },
      { id: "az", label: "Азербайджан", value: "Azerbaijan" },
      { id: "kg", label: "Кыргызстан", value: "Kyrgyzstan" },
      { id: "ge", label: "Грузия", value: "Georgia" },
    ],
  },
  {
    id: "europe",
    label: "Европа",
    value: "Europe",
    countries: [
      { id: "eu", label: "Европейский союз", value: "EU" },
      { id: "uk", label: "Великобритания", value: "UK" },
      { id: "tr", label: "Турция", value: "Turkey" },
      { id: "no", label: "Норвегия", value: "Norway" },
      { id: "ch", label: "Швейцария", value: "Switzerland" },
      { id: "ua", label: "Украина", value: "Ukraine" },
    ],
  },
  {
    id: "middle-east",
    label: "Ближний Восток",
    value: "Middle East",
    countries: [
      { id: "ae", label: "ОАЭ", value: "UAE" },
      { id: "sa", label: "Саудовская Аравия", value: "Saudi Arabia" },
      { id: "qa", label: "Катар", value: "Qatar" },
      { id: "kw", label: "Кувейт", value: "Kuwait" },
      { id: "om", label: "Оман", value: "Oman" },
      { id: "ir", label: "Иран", value: "Iran" },
      { id: "il", label: "Израиль", value: "Israel" },
    ],
  },
  {
    id: "south-asia",
    label: "Южная Азия",
    value: "South Asia",
    countries: [
      { id: "in", label: "Индия", value: "India" },
      { id: "pk", label: "Пакистан", value: "Pakistan" },
      { id: "bd", label: "Бангладеш", value: "Bangladesh" },
      { id: "lk", label: "Шри-Ланка", value: "Sri Lanka" },
    ],
  },
  {
    id: "east-asia",
    label: "Восточная Азия",
    value: "East Asia",
    countries: [
      { id: "cn", label: "Китай", value: "China" },
      { id: "jp", label: "Япония", value: "Japan" },
      { id: "kr", label: "Южная Корея", value: "South Korea" },
    ],
  },
  {
    id: "southeast-asia",
    label: "Юго-Восточная Азия",
    value: "Southeast Asia",
    countries: [
      { id: "vn", label: "Вьетнам", value: "Vietnam" },
      { id: "id", label: "Индонезия", value: "Indonesia" },
      { id: "th", label: "Таиланд", value: "Thailand" },
      { id: "my", label: "Малайзия", value: "Malaysia" },
      { id: "sg", label: "Сингапур", value: "Singapore" },
    ],
  },
  {
    id: "africa",
    label: "Африка",
    value: "Africa",
    countries: [
      { id: "ng", label: "Нигерия", value: "Nigeria" },
      { id: "za", label: "ЮАР", value: "South Africa" },
      { id: "eg", label: "Египет", value: "Egypt" },
      { id: "ke", label: "Кения", value: "Kenya" },
      { id: "ma", label: "Марокко", value: "Morocco" },
      { id: "et", label: "Эфиопия", value: "Ethiopia" },
    ],
  },
  {
    id: "north-america",
    label: "Северная Америка",
    value: "North America",
    countries: [
      { id: "us", label: "США", value: "USA" },
      { id: "ca", label: "Канада", value: "Canada" },
      { id: "mx", label: "Мексика", value: "Mexico" },
    ],
  },
  {
    id: "latin-america",
    label: "Латинская Америка",
    value: "Latin America",
    countries: [
      { id: "br", label: "Бразилия", value: "Brazil" },
      { id: "ar", label: "Аргентина", value: "Argentina" },
      { id: "cl", label: "Чили", value: "Chile" },
      { id: "co", label: "Колумбия", value: "Colombia" },
      { id: "pe", label: "Перу", value: "Peru" },
    ],
  },
  {
    id: "oceania",
    label: "Океания",
    value: "Oceania",
    countries: [
      { id: "au", label: "Австралия", value: "Australia" },
      { id: "nz", label: "Новая Зеландия", value: "New Zealand" },
    ],
  },
];

export const ALL_REGION_VALUES = [
  WORLD_REGION.value,
  ...REGION_GROUPS.flatMap((group) => [group.value, ...group.countries.map((c) => c.value)]),
];

const VALUE_ALIASES: Record<string, string[]> = {
  Global: ["Global", "World"],
  Russia: ["Russia", "Россия"],
  EU: ["EU", "Europe"],
  India: ["India"],
  UK: ["UK", "United Kingdom"],
  USA: ["USA", "US", "United States"],
  UAE: ["UAE"],
};

export function parseRegionsInput(input: string | string[] | null | undefined): string[] {
  if (!input) return [WORLD_REGION.value];
  const parts = Array.isArray(input)
    ? input
    : input.split(",").map((item) => item.trim()).filter(Boolean);
  if (parts.length === 0) return [WORLD_REGION.value];
  const normalized: string[] = [];
  for (const part of parts) {
    const canonical = ALL_REGION_VALUES.find(
      (value) => value.toLowerCase() === part.toLowerCase()
    );
    normalized.push(canonical || part);
  }
  return Array.from(new Set(normalized));
}

export function regionsToQuery(regions: string[]): string {
  if (regions.length === 0) return "";
  return regions.join(", ");
}

export function formatRegionsSummary(regions: string[]): string {
  if (regions.length === 0) return "Выберите регионы";
  if (regions.includes(WORLD_REGION.value)) return WORLD_REGION.label;
  if (regions.length <= 3) return regions.join(", ");
  return `${regions.slice(0, 3).join(", ")} +${regions.length - 3}`;
}

export function matchStoredRegion(value: string, stored: string): boolean {
  if (value.toLowerCase() === stored.toLowerCase()) return true;
  const aliases = VALUE_ALIASES[value] || [value];
  return aliases.some((alias) => alias.toLowerCase() === stored.toLowerCase());
}
