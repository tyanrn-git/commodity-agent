import uuid
from datetime import datetime, timezone

from app.integrations.email.base import EmailProvider, InboundEmail, OutboundEmail


class MockEmailProvider(EmailProvider):
    """Simulates mailbox send/receive. Inbound messages are injected via import/sync APIs."""

    _pending_inbound: list[InboundEmail] = []

    @classmethod
    def queue_inbound(cls, email: InboundEmail) -> None:
        cls._pending_inbound.append(email)

    @classmethod
    def clear_queue(cls) -> None:
        cls._pending_inbound.clear()

    def send_message(self, *, message: OutboundEmail) -> str:
        return f"mock-msg-{uuid.uuid4()}"

    def fetch_new_messages(self, *, since_cursor: str | None = None) -> tuple[list[InboundEmail], str | None]:
        items = list(self._pending_inbound)
        self._pending_inbound.clear()
        cursor = datetime.now(timezone.utc).isoformat() if items else since_cursor
        return items, cursor


def get_email_provider(provider_name: str = "mock") -> EmailProvider:
    name = (provider_name or "mock").lower()
    if name == "mock":
        return MockEmailProvider()
    raise NotImplementedError(f"Email provider '{provider_name}' is not configured yet")
