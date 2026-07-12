import type { CSSProperties } from "react";

export const styles = {
  page: {
    minHeight: "100vh",
    background: "#f4f6f8",
    color: "#1a1a1a",
    fontFamily: "system-ui, -apple-system, sans-serif",
  } as CSSProperties,
  container: {
    maxWidth: 960,
    margin: "0 auto",
    padding: "24px 16px",
  } as CSSProperties,
  card: {
    background: "#fff",
    border: "1px solid #e2e8f0",
    borderRadius: 8,
    padding: 20,
    marginBottom: 16,
  } as CSSProperties,
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 24,
  } as CSSProperties,
  button: {
    background: "#1d4ed8",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    padding: "10px 16px",
    cursor: "pointer",
    fontSize: 14,
  } as CSSProperties,
  secondaryButton: {
    background: "#fff",
    color: "#1d4ed8",
    border: "1px solid #1d4ed8",
    borderRadius: 6,
    padding: "10px 16px",
    cursor: "pointer",
    fontSize: 14,
  } as CSSProperties,
  input: {
    width: "100%",
    padding: "10px 12px",
    border: "1px solid #cbd5e1",
    borderRadius: 6,
    marginBottom: 12,
    fontSize: 14,
  } as CSSProperties,
  label: {
    display: "block",
    marginBottom: 6,
    fontSize: 13,
    fontWeight: 600,
  } as CSSProperties,
  error: {
    color: "#b91c1c",
    marginBottom: 12,
    fontSize: 14,
  } as CSSProperties,
  nav: {
    display: "flex",
    gap: 16,
    marginBottom: 16,
  } as CSSProperties,
  link: {
    color: "#1d4ed8",
    textDecoration: "none",
    fontSize: 14,
  } as CSSProperties,
};
