"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  REGION_GROUPS,
  WORLD_REGION,
  formatRegionsSummary,
} from "@/lib/regions";
import { styles } from "@/lib/styles";

type RegionPickerProps = {
  value: string[];
  onChange: (regions: string[]) => void;
  label?: string;
};

function groupCountryValues(groupId: string): string[] {
  const group = REGION_GROUPS.find((item) => item.id === groupId);
  if (!group) return [];
  return group.countries.map((country) => country.value);
}

export function RegionPicker({ value, onChange, label = "Регион" }: RegionPickerProps) {
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(REGION_GROUPS.map((group) => [group.id, true]))
  );
  const rootRef = useRef<HTMLDivElement>(null);

  const selected = useMemo(() => new Set(value), [value]);
  const worldSelected = selected.has(WORLD_REGION.value);

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function emit(next: Set<string>) {
    if (next.has(WORLD_REGION.value)) {
      onChange([WORLD_REGION.value]);
      return;
    }
    onChange(Array.from(next));
  }

  function toggleWorld() {
    if (worldSelected) {
      onChange([]);
      return;
    }
    emit(new Set([WORLD_REGION.value]));
  }

  function toggleGroup(groupId: string) {
    const countries = groupCountryValues(groupId);
    const group = REGION_GROUPS.find((item) => item.id === groupId);
    if (!group) return;

    const next = new Set(selected);
    next.delete(WORLD_REGION.value);
    const allSelected = countries.every((country) => next.has(country));

    if (allSelected) {
      countries.forEach((country) => next.delete(country));
      next.delete(group.value);
    } else {
      countries.forEach((country) => next.add(country));
      next.add(group.value);
    }
    emit(next);
  }

  function toggleCountry(countryValue: string, groupValue: string) {
    const next = new Set(selected);
    next.delete(WORLD_REGION.value);

    const group = REGION_GROUPS.find((item) => item.value === groupValue);
    if (group && next.has(groupValue)) {
      next.delete(groupValue);
      group.countries.forEach((country) => next.add(country.value));
    }

    if (next.has(countryValue)) {
      next.delete(countryValue);
    } else {
      next.add(countryValue);
    }
    if (group) {
      const allCountriesSelected = group.countries.every((country) => next.has(country.value));
      if (allCountriesSelected) {
        next.add(groupValue);
      } else {
        next.delete(groupValue);
      }
    }
    emit(next);
  }

  function isGroupChecked(groupId: string): boolean {
    const group = REGION_GROUPS.find((item) => item.id === groupId);
    if (!group) return false;
    if (selected.has(group.value)) return true;
    const countries = groupCountryValues(groupId);
    return countries.length > 0 && countries.every((country) => selected.has(country));
  }

  function isGroupIndeterminate(groupId: string): boolean {
    const group = REGION_GROUPS.find((item) => item.id === groupId);
    if (!group || selected.has(group.value)) return false;
    const countries = groupCountryValues(groupId);
    const selectedCount = countries.filter((country) => selected.has(country)).length;
    return selectedCount > 0 && selectedCount < countries.length;
  }

  function isCountryChecked(countryValue: string, groupValue: string): boolean {
    return selected.has(countryValue) || selected.has(groupValue);
  }

  return (
    <div ref={rootRef} style={{ position: "relative" }}>
      <label style={styles.label}>{label}</label>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        style={{
          ...styles.input,
          width: "100%",
          textAlign: "left",
          cursor: "pointer",
          background: "#fff",
        }}
      >
        {formatRegionsSummary(value)}
      </button>

      {open ? (
        <div
          style={{
            position: "absolute",
            zIndex: 20,
            top: "calc(100% + 4px)",
            left: 0,
            right: 0,
            maxHeight: 360,
            overflowY: "auto",
            background: "#fff",
            border: "1px solid #e2e8f0",
            borderRadius: 8,
            boxShadow: "0 8px 24px rgba(15, 23, 42, 0.12)",
            padding: 12,
          }}
        >
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 600, marginBottom: 10 }}>
            <input type="checkbox" checked={worldSelected} onChange={toggleWorld} />
            {WORLD_REGION.label}
          </label>

          {REGION_GROUPS.map((group) => {
            const isExpanded = expanded[group.id] ?? true;
            const groupChecked = isGroupChecked(group.id);
            const groupIndeterminate = isGroupIndeterminate(group.id);
            return (
              <div key={group.id} style={{ marginBottom: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <button
                    type="button"
                    onClick={() =>
                      setExpanded((current) => ({ ...current, [group.id]: !isExpanded }))
                    }
                    style={{
                      border: "none",
                      background: "transparent",
                      cursor: "pointer",
                      padding: "0 4px",
                      color: "#64748b",
                    }}
                    aria-label={isExpanded ? "Свернуть" : "Развернуть"}
                  >
                    {isExpanded ? "▾" : "▸"}
                  </button>
                  <label style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 600 }}>
                    <input
                      type="checkbox"
                      checked={groupChecked}
                      ref={(node) => {
                        if (node) node.indeterminate = groupIndeterminate;
                      }}
                      onChange={() => toggleGroup(group.id)}
                    />
                    {group.label}
                  </label>
                </div>

                {isExpanded ? (
                  <div style={{ marginLeft: 28, marginTop: 6, display: "grid", gap: 6 }}>
                    {group.countries.map((country) => (
                      <label
                        key={country.id}
                        style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}
                      >
                        <input
                          type="checkbox"
                          checked={isCountryChecked(country.value, group.value)}
                          onChange={() => toggleCountry(country.value, group.value)}
                        />
                        {country.label}
                      </label>
                    ))}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : null}

      <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>
        Уровни: весь мир → регионы → страны. Список источников обновляется автоматически.
      </div>
    </div>
  );
}
