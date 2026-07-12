import json
from datetime import datetime, timezone
from pathlib import Path

from app.integrations.monitoring.base import MonitoringConnector, MonitoringFeedItem


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


class MockMonitoringConnector:
    def __init__(self, source_url: str) -> None:
        self.source_url = source_url

    def _resolve_path(self) -> Path:
        path = Path(self.source_url)
        if path.is_absolute() and path.exists():
            return path
        candidates = [
            Path(__file__).resolve().parents[2] / "data" / "monitoring" / self.source_url,
            Path.cwd() / "data" / "monitoring" / self.source_url,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Monitoring feed not found: {self.source_url}")

    def healthcheck(self) -> tuple[str, str]:
        try:
            path = self._resolve_path()
            payload = json.loads(path.read_text(encoding="utf-8"))
            items = payload.get("items", [])
            return "HEALTHY", f"Feed readable, {len(items)} item(s)"
        except Exception as exc:
            return "UNHEALTHY", str(exc)

    def fetch_items(self) -> list[MonitoringFeedItem]:
        path = self._resolve_path()
        payload = json.loads(path.read_text(encoding="utf-8"))
        items: list[MonitoringFeedItem] = []
        for raw in payload.get("items", []):
            items.append(
                MonitoringFeedItem(
                    source_item_id=str(raw["source_item_id"]),
                    title=str(raw.get("title") or ""),
                    url=raw.get("url"),
                    publication_date=_parse_datetime(raw.get("publication_date")),
                    product=raw.get("product"),
                    quantity=float(raw["quantity"]) if raw.get("quantity") is not None else None,
                    quantity_unit=raw.get("quantity_unit"),
                    destination=raw.get("destination"),
                    buyer=raw.get("buyer"),
                    deadline=_parse_datetime(raw.get("deadline")),
                    body=str(raw.get("body") or ""),
                    raw=raw,
                )
            )
        return items


def get_monitoring_connector(connector_type: str, source_url: str) -> MonitoringConnector:
    if connector_type == "MOCK":
        return MockMonitoringConnector(source_url)
    raise ValueError(f"Unsupported connector type: {connector_type}")
