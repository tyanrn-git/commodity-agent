"use client";

import type { CSSProperties } from "react";
import { styles } from "@/lib/styles";

type Tab = {
  id: string;
  label: string;
};

type Props = {
  tabs: Tab[];
  activeId: string;
  onChange: (id: string) => void;
};

const tabButton: CSSProperties = {
  background: "transparent",
  border: "none",
  borderBottom: "2px solid transparent",
  padding: "10px 4px",
  marginRight: 20,
  cursor: "pointer",
  fontSize: 14,
  color: "#64748b",
};

const tabButtonActive: CSSProperties = {
  ...tabButton,
  color: "#1d4ed8",
  borderBottomColor: "#1d4ed8",
  fontWeight: 600,
};

export function SectionTabs({ tabs, activeId, onChange }: Props) {
  return (
    <div
      style={{
        display: "flex",
        borderBottom: "1px solid #e2e8f0",
        marginBottom: 16,
        flexWrap: "wrap",
      }}
    >
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          style={tab.id === activeId ? tabButtonActive : tabButton}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export const statBoxStyle: CSSProperties = {
  ...styles.card,
  marginBottom: 0,
  flex: "1 1 140px",
  minWidth: 140,
};
