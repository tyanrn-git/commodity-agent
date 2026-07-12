from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass
class MonitoringFeedItem:
    source_item_id: str
    title: str
    url: str | None
    publication_date: datetime | None
    product: str | None
    quantity: float | None
    quantity_unit: str | None
    destination: str | None
    buyer: str | None
    deadline: datetime | None
    body: str
    raw: dict


class MonitoringConnector(Protocol):
    def healthcheck(self) -> tuple[str, str]:
        """Return (health_status, message)."""

    def fetch_items(self) -> list[MonitoringFeedItem]:
        """Fetch current publications from the source."""
