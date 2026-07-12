from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_serializer


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    thread_id: UUID
    rfq_id: UUID | None
    source_id: UUID | None
    direction: str
    link_status: str
    subject: str
    body_text: str
    from_address: str | None
    to_addresses: list | None
    binding_class: str
    mailbox_message_id: str | None
    sent_at: datetime
    created_at: datetime


class SupplyOfferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    deal_id: UUID
    rfq_id: UUID | None
    supplier_counterparty_id: UUID | None
    source_message_id: UUID | None
    product_name: str | None
    available_quantity: Decimal | None
    quantity_unit: str | None
    price: Decimal | None
    currency: str | None
    incoterm: str | None
    origin: str | None
    payment_terms: dict | None
    extracted_fields: dict | None
    missing_fields: list | None
    status: str
    user_confirmed: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("available_quantity", "price")
    def serialize_decimal(self, value: Decimal | float | str | None) -> str | None:
        if value is None:
            return None
        return str(value)


class LinkMessageRequest(BaseModel):
    rfq_id: UUID


class ImportInboundRequest(BaseModel):
    deal_id: UUID | None = None
    rfq_id: UUID | None = None


class SendRfqResponse(BaseModel):
    rfq_id: UUID
    status: str
    message_id: UUID
    mailbox_message_id: str | None
