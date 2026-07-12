from dataclasses import dataclass


@dataclass
class OutboundEmail:
    subject: str
    body: str
    to_addresses: list[str]
    cc_addresses: list[str] | None = None


@dataclass
class InboundEmail:
    subject: str
    body: str
    from_address: str
    to_addresses: list[str]
    mailbox_message_id: str
    in_reply_to: str | None = None
    sent_at_iso: str | None = None


class EmailProvider:
    def send_message(self, *, message: OutboundEmail) -> str:
        raise NotImplementedError

    def fetch_new_messages(self, *, since_cursor: str | None = None) -> tuple[list[InboundEmail], str | None]:
        raise NotImplementedError
