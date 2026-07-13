from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InternetSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    base_url: str = Field(min_length=1, max_length=1024)
    source_kind: str = "TENDER_PORTAL"
    access_mode: str = "PUBLIC"
    fetch_strategy: str = "HTML"
    fetch_config: dict = Field(default_factory=dict)
    regions: list[str] = Field(default_factory=list)
    product_tags: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    description: str | None = None
    search_hints: str | None = None
    is_active: bool = True
    is_test: bool = False
    priority: int = Field(default=50, ge=0, le=100)


class InternetSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    base_url: str | None = Field(default=None, min_length=1, max_length=1024)
    source_kind: str | None = None
    access_mode: str | None = None
    fetch_config: dict | None = None
    regions: list[str] | None = None
    product_tags: list[str] | None = None
    languages: list[str] | None = None
    description: str | None = None
    search_hints: str | None = None
    is_active: bool | None = None
    is_test: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    last_verified_at: datetime | None = None


class InternetSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID | None
    name: str
    base_url: str
    source_kind: str
    access_mode: str
    fetch_strategy: str = "HTML"
    fetch_config: dict = Field(default_factory=dict)
    regions: list
    product_tags: list
    languages: list
    description: str | None
    search_hints: str | None
    is_active: bool
    is_test: bool = False
    priority: int
    last_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime
    is_system: bool = False

    @classmethod
    def from_model(cls, source) -> "InternetSourceResponse":
        data = cls.model_validate(source)
        return data.model_copy(update={"is_system": source.owner_id is None})


class InternetSourceMatchResponse(BaseModel):
    sources: list[InternetSourceResponse]
    matched_count: int
    product_keywords: list[str]
    regions: list[str]
    sources_discovered: int = 0
    discovery_notes: str | None = None


class InternetSourceDiscoverRequest(BaseModel):
    product_keywords: list[str] = Field(min_length=1)
    regions: list[str] = Field(default_factory=list)
    access_mode: str = "PUBLIC"
    force: bool = False


class InternetSourceDiscoverResponse(BaseModel):
    added_sources: list[InternetSourceResponse]
    added_count: int
    skipped_existing: int
    skipped_discovery: bool
    discovery_notes: str | None = None
    product_keywords: list[str]
    regions: list[str]


class InternetSourceSearchRequest(BaseModel):
    product_keywords: list[str] = Field(min_length=1)
    regions: list[str] = Field(default_factory=list)
    search_date: datetime | None = None
    access_mode: str = "PUBLIC"
    max_sources: int = Field(default=6, ge=1, le=12)
    verify_real: bool = True
    auto_discover_sources: bool = True


class InternetSourceSearchRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    product_id: UUID | None = None
    product_keywords: list
    regions: list
    search_date: datetime
    access_mode: str | None
    status: str
    sources_matched: int
    sources_scanned: int
    hits_found: int
    hits_new: int
    opportunities_created: int
    ai_calls: int
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
    sources_discovered: int = 0


class TenderMonitoringRow(BaseModel):
    buyer_name: str | None = None
    product_name: str | None = None
    volume: str | None = None
    estimated_value: str | None = None
    destination: str | None = None
    submission_deadline: str | None = None
    delivery_deadline: str | None = None
    submission_expired: bool = False
    product_match: bool = False
    product_match_reason: str | None = None
    display_status: str
    display_status_label: str
    source_url: str | None = None
    feasibility: dict | None = None
    opportunity_id: str | None = None


class TenderHitPromoteResponse(BaseModel):
    hit: "InternetSourceSearchHitResponse"
    opportunity_id: UUID
    opportunity_title: str
    feasibility_summary: str
    supplier_hint: str | None = None
    economics_preview: str | None = None


class InternetSourceSearchHitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    search_run_id: UUID
    internet_source_id: UUID
    title: str
    canonical_url: str | None
    publication_date: datetime | None
    content_hash: str
    status: str
    confidence: float | None
    evidence_excerpt: str | None
    fetch_status: str | None
    extracted_fields: dict | None
    opportunity_id: UUID | None
    created_at: datetime
    updated_at: datetime
    source_name: str | None = None
    monitoring_row: TenderMonitoringRow | None = None

    @classmethod
    def from_model(cls, hit, *, source_name: str | None = None) -> "InternetSourceSearchHitResponse":
        from app.services.internet_source_search import build_monitoring_row

        data = cls.model_validate(hit)
        confidence = float(hit.confidence) if hit.confidence is not None else None
        return data.model_copy(
            update={
                "source_name": source_name,
                "confidence": confidence,
                "monitoring_row": TenderMonitoringRow(**build_monitoring_row(hit)),
            }
        )

