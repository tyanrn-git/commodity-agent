from app.domain.enums import ResearchLeadType
from app.integrations.search.base import SearchLeadResult, SearchProvider


class MockSearchProvider(SearchProvider):
    def search_chain_leads(
        self,
        *,
        product_names: list[str],
        target_buy_regions: list[str] | None,
        target_sell_regions: list[str] | None,
        quantity_range: dict | None,
    ) -> list[SearchLeadResult]:
        product = product_names[0] if product_names else "Base Oil"
        buy_regions = target_buy_regions or ["EU"]
        sell_regions = target_sell_regions or ["Middle East", "Asia"]

        buyers = [
            SearchLeadResult(
                lead_type=ResearchLeadType.PUBLIC_BUYER_NEED.value,
                title=f"{product} tender - Rotterdam intake",
                organization_name="EU Lubricants Buyer A",
                region="Rotterdam",
                country="Netherlands",
                url="https://example.com/tender-rotterdam",
                notes="Public buyer need discovered via mock search",
                relevance_score=0.91,
                source_type="mock_web_search",
            ),
            SearchLeadResult(
                lead_type=ResearchLeadType.BUYER_NEED.value,
                title=f"{product} monthly requirement",
                organization_name="Nordic Blending Co",
                region="Hamburg",
                country="Germany",
                url=None,
                notes="Potential end buyer in EU",
                relevance_score=0.84,
                source_type="mock_web_search",
            ),
            SearchLeadResult(
                lead_type=ResearchLeadType.PUBLIC_BUYER_NEED.value,
                title=f"{product} spot inquiry",
                organization_name="Mediterranean Trader",
                region="Barcelona",
                country="Spain",
                url="https://example.com/spot-barcelona",
                notes="Public RFQ mention",
                relevance_score=0.79,
                source_type="mock_web_search",
            ),
        ]

        suppliers = [
            SearchLeadResult(
                lead_type=ResearchLeadType.SUPPLIER.value,
                title=f"{product} producer offer",
                organization_name="Gulf Base Oil Refinery",
                region=sell_regions[0] if sell_regions else "UAE",
                country="UAE",
                url="https://example.com/supplier-uae",
                notes="Producer with flexitank exports",
                relevance_score=0.88,
                source_type="mock_web_search",
            ),
            SearchLeadResult(
                lead_type=ResearchLeadType.SUPPLIER.value,
                title=f"{product} trader availability",
                organization_name="Singapore Oil Trading",
                region="Singapore",
                country="Singapore",
                url=None,
                notes="Trader with ISO tank lots",
                relevance_score=0.82,
                source_type="mock_web_search",
            ),
            SearchLeadResult(
                lead_type=ResearchLeadType.SUPPLIER.value,
                title=f"{product} export offer",
                organization_name="India Base Oil Exporter",
                region="Mumbai",
                country="India",
                url="https://example.com/supplier-india",
                notes="Export FOB India",
                relevance_score=0.8,
                source_type="mock_web_search",
            ),
        ]

        routes = [
            SearchLeadResult(
                lead_type=ResearchLeadType.LOGISTICS_ROUTE.value,
                title="Jebel Ali → Rotterdam flexitank",
                organization_name="Mock Forwarder EU-Gulf",
                region=f"{sell_regions[0] if sell_regions else 'UAE'} → {buy_regions[0] if buy_regions else 'EU'}",
                country=None,
                url=None,
                notes="Container/feeder + main ocean leg",
                relevance_score=0.86,
                source_type="mock_route_catalog",
                metadata={
                    "origin": sell_regions[0] if sell_regions else "UAE",
                    "destination": buy_regions[0] if buy_regions else "EU",
                    "mode": "container_feeder_plus_ocean",
                    "transit_days": 28,
                },
            ),
        ]

        _ = quantity_range
        return buyers + suppliers + routes


def get_search_provider() -> SearchProvider:
    return MockSearchProvider()
