from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas import SourceResponse
from app.api.schemas_ai import (
    ApplyExtractionRequest,
    ExtractSourceRequest,
    ExtractionResultResponse,
    ImportUrlRequest,
)
from app.db.session import get_db
from app.domain.enums import SourceType
from app.domain.models import ExtractionResult, Opportunity, Source, User
from app.integrations.storage.local import LocalFilesystemStorage
from app.services.extraction import (
    apply_extraction_to_opportunity,
    extract_opportunity_from_source,
    import_eml_source,
    import_url_source,
)

router = APIRouter(tags=["extraction"])


@router.get("/sources/{source_id}/open")
def open_source(
    source_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = db.get(Source, source_id)
    if source is None or source.opportunity is None or source.opportunity.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    if source.source_type == SourceType.URL.value and source.source_url:
        return RedirectResponse(url=source.source_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    storage = LocalFilesystemStorage()
    content = storage.read(source.storage_key)
    filename = source.original_filename or "document.bin"
    media_type = source.mime_type or "application/octet-stream"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/sources/{source_id}/extract", response_model=ExtractionResultResponse)
def extract_source(
    source_id: UUID,
    payload: ExtractSourceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = db.get(Source, source_id)
    if source is None or source.opportunity is None or source.opportunity.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    storage = LocalFilesystemStorage()
    return extract_opportunity_from_source(
        db,
        user=current_user,
        source=source,
        storage=storage,
        force=payload.force,
        allow_budget_override=payload.allow_budget_override,
    )


@router.get("/sources/{source_id}/extraction", response_model=ExtractionResultResponse | None)
def get_latest_extraction(
    source_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = db.get(Source, source_id)
    if source is None or source.opportunity is None or source.opportunity.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    if not source.extractions:
        return None
    latest = sorted(source.extractions, key=lambda x: x.created_at, reverse=True)[0]
    return latest


@router.post("/opportunities/{opportunity_id}/apply-extraction", response_model=dict)
def apply_extraction(
    opportunity_id: UUID,
    payload: ApplyExtractionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or opportunity.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    extraction = db.get(ExtractionResult, payload.extraction_id)
    if extraction is None or extraction.source.opportunity_id != opportunity.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extraction not found")
    updated = apply_extraction_to_opportunity(
        db,
        user=current_user,
        opportunity=opportunity,
        extraction=extraction,
        fields=payload.fields,
    )
    return {"status": "applied", "opportunity_id": str(updated.id), "opportunity_status": updated.status}


@router.post(
    "/opportunities/{opportunity_id}/import-url",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_url(
    opportunity_id: UUID,
    payload: ImportUrlRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or opportunity.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    storage = LocalFilesystemStorage()
    return import_url_source(
        db,
        user=current_user,
        opportunity=opportunity,
        url=str(payload.url),
        storage=storage,
    )


@router.post(
    "/opportunities/{opportunity_id}/import-eml",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_eml(
    opportunity_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or opportunity.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    storage = LocalFilesystemStorage()
    return import_eml_source(
        db,
        user=current_user,
        opportunity=opportunity,
        file=file,
        storage=storage,
    )
