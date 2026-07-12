import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Commodity Agent",
  description: "Рабочее место сырьевого трейдера",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
