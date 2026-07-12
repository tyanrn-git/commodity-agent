import uuid

from sqlalchemy.orm import Session

from app.domain.enums import SourceType
from app.domain.models import Opportunity, Source, User
from app.integrations.storage.local import LocalFilesystemStorage


def attach_tender_link(
    db: Session,
    *,
    user: User,
    opportunity: Opportunity,
    url: str | None,
    storage: LocalFilesystemStorage | None = None,
) -> Source | None:
    if not url:
        return None
    opportunity.source_url = url
    storage = storage or LocalFilesystemStorage()
    storage_key = f"opportunities/{opportunity.id}/url-ref-{uuid.uuid4()}.url"
    storage.save(storage_key, url.encode("utf-8"))
    source = Source(
        opportunity_id=opportunity.id,
        source_type=SourceType.URL.value,
        source_url=url,
        content_hash=None,
        original_filename=url,
        mime_type="text/uri-list",
        storage_key=storage_key,
        file_size_bytes=len(url.encode("utf-8")),
        is_immutable=True,
        uploaded_by_id=user.id,
    )
    db.add(source)
    db.flush()
    return source
