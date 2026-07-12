from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CompanySettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    legal_name: str | None
    trade_name: str | None
    brand_name: str | None
    registration_number: str | None
    tax_id: str | None
    address: str | None
    default_rfq_language: str
    email_signature_text: str | None
    email_signature_html: str | None
    bank_details: dict | None


class CompanySettingsUpdate(BaseModel):
    legal_name: str | None = None
    trade_name: str | None = None
    brand_name: str | None = None
    registration_number: str | None = None
    tax_id: str | None = None
    address: str | None = None
    default_rfq_language: str | None = None
    email_signature_text: str | None = None
    email_signature_html: str | None = None
    bank_details: dict | None = None


class ContactCreate(BaseModel):
    full_name: str | None = None
    role_title: str | None = None
    department: str | None = None
    email: str | None = None
    phone: str | None = None
    preferred_language: str = "en"
    is_primary: bool = False


class ContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    counterparty_id: UUID
    full_name: str | None
    role_title: str | None
    department: str | None
    email: str | None
    phone: str | None
    preferred_language: str
    verification_status: str
    is_primary: bool
    created_at: datetime
    updated_at: datetime


class CounterpartyCreate(BaseModel):
    legal_name: str = Field(min_length=1, max_length=512)
    trade_name: str | None = None
    organization_type: str = "OTHER"
    incorporation_country: str | None = None
    operating_countries: list[str] | None = None
    registration_number: str | None = None
    tax_id: str | None = None
    website: str | None = None
    primary_domain: str | None = None
    address: str | None = None


class CounterpartyUpdate(BaseModel):
    legal_name: str | None = Field(default=None, min_length=1, max_length=512)
    trade_name: str | None = None
    organization_type: str | None = None
    incorporation_country: str | None = None
    operating_countries: list[str] | None = None
    registration_number: str | None = None
    tax_id: str | None = None
    website: str | None = None
    primary_domain: str | None = None
    address: str | None = None
    compliance_review_status: str | None = None


class CounterpartyListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    legal_name: str
    trade_name: str | None
    organization_type: str
    website: str | None
    primary_domain: str | None
    verification_status: str
    compliance_review_status: str
    contacts_count: int = 0
    capabilities_count: int = 0
    confirmed_capabilities_count: int = 0
    created_at: datetime
    updated_at: datetime


class CounterpartyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    legal_name: str
    trade_name: str | None
    organization_type: str
    incorporation_country: str | None
    operating_countries: list | None
    registration_number: str | None
    tax_id: str | None
    website: str | None
    primary_domain: str | None
    address: str | None
    verification_status: str
    compliance_review_status: str
    compliance_reviewed_at: datetime | None
    risk_flags: list | None
    domain_verification_report: dict | None
    contacts: list[ContactResponse] = []
    created_at: datetime
    updated_at: datetime


class DealPartyCreate(BaseModel):
    counterparty_id: UUID
    role: str
    disclosure_status: str = "HIDDEN"
    selected_for_contact: bool = True


class DealPartyUpdate(BaseModel):
    disclosure_status: str | None = None
    selected_for_contact: bool | None = None
    selected_for_configuration: bool | None = None


class DealPartyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    deal_id: UUID
    counterparty_id: UUID
    role: str
    confidentiality_level: str
    disclosure_status: str
    verification_status: str
    selected_for_contact: bool
    selected_for_configuration: bool
    counterparty: CounterpartyResponse | None = None
    created_at: datetime
    updated_at: datetime


class RFQTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    rfq_type: str
    language: str
    subject_template: str
    body_template: str
    default_requested_fields: list
    is_active: bool


class RFQCreate(BaseModel):
    target_deal_party_id: UUID
    rfq_type: str
    contact_id: UUID | None = None
    template_id: UUID | None = None
    requested_fields: list[str] | None = None
    language: str | None = None


class RFQUpdate(BaseModel):
    contact_id: UUID | None = None
    requested_fields: list[str] | None = None
    language: str | None = None
    subject: str | None = None
    body: str | None = None
    response_deadline: datetime | None = None


class ApprovalRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    rfq_id: UUID
    proposed_action: str
    exact_payload: dict
    recipients: list
    disclosed_information: dict | None
    binding_class: str
    risk_flags: list | None
    compliance_warnings: list | None
    expires_at: datetime | None
    approval_status: str
    approved_snapshot_hash: str | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RFQResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    deal_id: UUID
    target_deal_party_id: UUID
    contact_id: UUID | None
    template_id: UUID | None
    rfq_type: str
    requested_fields: list
    language: str
    subject: str
    body: str
    status: str
    response_deadline: datetime | None
    expires_at: datetime | None
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RFQApproveRequest(BaseModel):
    acknowledge_warnings: bool = False
