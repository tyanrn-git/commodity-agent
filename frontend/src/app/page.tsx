"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    apiClient
      .me()
      .then(() => router.replace("/opportunities"))
      .catch(() => router.replace("/login"));
  }, [router]);

  return <main style={{ padding: 24 }}>Загрузка...</main>;
}
