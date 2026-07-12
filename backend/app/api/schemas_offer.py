from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OfferCreate(BaseModel):
    configuration_id: UUID
    target_deal_party_id: UUID


class OfferUpdate(BaseModel):
    subject: str | None = None
    body: str | None = None


class OfferApproveRequest(BaseModel):
    acknowledge_warnings: bool = False


class OfferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    deal_id: UUID
    configuration_id: UUID
    target_deal_party_id: UUID
    subject: str
    body: str
    status: str
    configuration_snapshot: dict
    economics_snapshot: dict
    disclosure_snapshot: dict | None
    validity_until: datetime | None
    sent_at: datetime | None
    source_message_id: UUID | None
    created_at: datetime
    updated_at: datetime


class SendOfferResponse(BaseModel):
    offer_id: UUID
    status: str
    message_id: UUID
    mailbox_message_id: str | None
