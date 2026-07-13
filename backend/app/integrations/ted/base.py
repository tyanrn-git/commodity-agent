from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.ai.schemas import TenderSearchHitOutput


@dataclass(frozen=True)
class TedSearchResult:
    hits: list[TenderSearchHitOutput]
    status: str
    error: str | None = None


class TedSearchProvider(ABC):
    @abstractmethod
    def search_notices(
        self,
        *,
        keywords: list[str],
        search_date: datetime,
        limit: int = 10,
    ) -> TedSearchResult:
        raise NotImplementedError

    def enrich_notice_documents(
        self,
        hit: TenderSearchHitOutput,
    ) -> TenderSearchHitOutput:
        """Optional fallback: fetch public notice HTML for extra fields only."""
        return hit
