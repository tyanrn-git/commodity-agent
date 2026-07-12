import Link from "next/link";
import { styles } from "@/lib/styles";

const LINKS = [
  { href: "/opportunities", label: "Возможности" },
  { href: "/products", label: "Товары" },
  { href: "/research", label: "Исследование" },
  { href: "/monitoring", label: "Мониторинг" },
  { href: "/automation", label: "Автоматизация" },
  { href: "/counterparties", label: "Контрагенты" },
  { href: "/inbox", label: "Inbox" },
  { href: "/settings", label: "AI-бюджет" },
] as const;

type AppNavProps = {
  backHref?: string;
  backLabel?: string;
};

export function AppNav({ backHref, backLabel }: AppNavProps) {
  return (
    <div style={styles.nav}>
      {backHref ? (
        <Link href={backHref} style={styles.link}>
          {backLabel}
        </Link>
      ) : null}
      {LINKS.map((link) => (
        <Link key={link.href} href={link.href} style={styles.link}>
          {link.label}
        </Link>
      ))}
    </div>
  );
}
