from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.factory import get_ai_provider
from app.ai.schemas import ProductResolutionOutput
from app.config import settings
from app.domain.enums import AIUsageOperation, AgentResultType, AgentType
from app.domain.models import InternetSourceSearchHit, Product, User
from app.services.agent_runtime import AgentExecutionContext, tracked_agent_run
from app.services.ai_budget import enforce_budget_or_raise, ensure_ai_budget_settings
from app.services.product_assistant import auto_enrich_product_from_text
from app.services.product_catalog import create_product_from_proposal
from app.services.product_keyword_localization import expand_product_keywords
from app.services.product_resolution import (
    PRODUCT_MATCH_CONFIDENCE_THRESHOLD,
    PRODUCT_RESOLUTION_SYSTEM_PROMPT,
    _product_catalog_context,
    _resolve_product_id,
)


def find_catalog_product_by_keywords(db: Session, keywords: list[str]) -> Product | None:
    terms = expand_product_keywords(db, [keyword.strip() for keyword in keywords if keyword and keyword.strip()])
    if not terms:
        return None

    lowered = {term.lower() for term in terms}
    for term in terms:
        product = db.scalar(select(Product).where(Product.normalized_name.ilike(term.strip())))
        if product:
            return product

    for product in db.scalars(select(Product).order_by(Product.normalized_name)):
        if product.normalized_name.lower() in lowered:
            return product
        for alias in product.aliases or []:
            if alias.lower() in lowered:
                return product
    return None


def ensure_catalog_product_for_keywords(
    db: Session,
    *,
    user: User,
    keywords: list[str],
) -> tuple[Product, bool]:
    normalized = [keyword.strip() for keyword in keywords if keyword and keyword.strip()]
    if not normalized:
        raise ValueError("product_keywords required")

    existing = find_catalog_product_by_keywords(db, normalized)
    if existing:
        return existing, False

    budget_settings = ensure_ai_budget_settings(db, user)
    enforce_budget_or_raise(db, user)

    rough_name = ", ".join(normalized)
    user_prompt = (
        f"Rough product description: {rough_name}\n\n"
        f"Product catalog:\n{_product_catalog_context(db)}\n\n"
        "Source text:\n(no tender document — infer catalog entry from search keywords only)"
    )

    provider = get_ai_provider()
    model = budget_settings.preferred_default_model or settings.openai_default_model
    with tracked_agent_run(
        db,
        user=user,
        context=AgentExecutionContext(
            agent_type=AgentType.PRODUCT_MATCHING.value,
            task_type="catalog_keyword_resolution",
            input_payload={"product_keywords": normalized},
        ),
    ) as agent:
        output, usage = provider.structured_completion(
            model=model,
            system_prompt=PRODUCT_RESOLUTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            output_schema=ProductResolutionOutput,
        )
        agent.attach_ai_usage(
            model=usage.model,
            operation=AIUsageOperation.MATCHING.value,
            cost_usd=usage.cost_usd,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
        agent.record_result(
            result_type=AgentResultType.PRODUCT_RESOLUTION.value,
            structured_payload=output.model_dump(mode="json"),
            summary=output.reasoning,
            confidence=float(output.confidence),
            requires_review=output.confidence < PRODUCT_MATCH_CONFIDENCE_THRESHOLD,
            applied=False,
        )

    product_id = _resolve_product_id(db, output)
    if product_id is not None:
        product = db.get(Product, product_id)
        if product:
            return product, False

    if output.proposed_new_product:
        proposal = output.proposed_new_product
        duplicate = db.scalar(
            select(Product).where(Product.normalized_name.ilike(proposal.normalized_name.strip()))
        )
        if duplicate:
            return duplicate, False
        created = create_product_from_proposal(db, user=user, proposal=proposal)
        return created, True

    fallback_name = normalized[0]
    from app.services.product_catalog import create_product

    created = create_product(
        db,
        user=user,
        normalized_name=fallback_name,
        category="other",
        aliases=normalized[1:],
        auto_bootstrap_specs=True,
    )
    return created, True


def enrich_product_from_search_hits(
    db: Session,
    *,
    user: User,
    product_id: uuid.UUID,
    hits: list[InternetSourceSearchHit],
) -> int:
    product = db.get(Product, product_id)
    if product is None:
        return 0

    parameters_added = 0
    for hit in hits:
        fields = hit.extracted_fields or {}
        if not fields.get("product_match", True):
            continue
        parts = [
            fields.get("product"),
            fields.get("body"),
            hit.title,
            hit.evidence_excerpt,
        ]
        source_text = "\n".join(part for part in parts if part and str(part).strip())
        if len(source_text.strip()) < 30:
            continue
        result = auto_enrich_product_from_text(
            db,
            user=user,
            product=product,
            source_text=source_text,
            rough_product_name=fields.get("product") or product.normalized_name,
        )
        added = int(result.get("parameters_added") or 0)
        if added > 0:
            updated_fields = dict(fields)
            updated_fields["catalog_params_added"] = added
            hit.extracted_fields = updated_fields
            db.flush()
        parameters_added += added
    db.commit()
    return parameters_added
