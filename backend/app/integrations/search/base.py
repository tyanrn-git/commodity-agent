from dataclasses import dataclass


@dataclass
class SearchLeadResult:
    lead_type: str
    title: str
    organization_name: str | None
    region: str | None
    country: str | None
    url: str | None
    notes: str | None
    relevance_score: float
    source_type: str
    metadata: dict | None = None


class SearchProvider:
    def search_chain_leads(
        self,
        *,
        product_names: list[str],
        target_buy_regions: list[str] | None,
        target_sell_regions: list[str] | None,
        quantity_range: dict | None,
    ) -> list[SearchLeadResult]:
        raise NotImplementedError
