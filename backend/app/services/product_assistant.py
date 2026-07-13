import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.factory import get_ai_provider
from app.ai.schemas import ProductAssistantOutput, ProductAutoFillOutput, ProductSpecChangeOutput
from app.config import settings
from app.domain.enums import AIUsageOperation, AuditAction, SpecParameterKind, SpecVariationMateriality, AgentResultType, AgentType
from app.domain.models import Product, ProductSpecificationProfile, User
from app.services.ai_budget import enforce_budget_or_raise, ensure_ai_budget_settings
from app.services.audit import log_audit
from app.services.product_catalog import get_product_detail, merge_discovered_specs
from app.services.agent_runtime import AgentExecutionContext, tracked_agent_run

PRODUCT_SPEC_SCAFFOLD_PROMPT = """You suggest a specification parameter SCHEMA for a commodity trading catalog product.
Rules:
- IDENTITY parameters define WHAT the product is (grade, botanical origin, polymer type).
- VARIANT parameters are physico-chemical indicators that may differ between lots.
- Do NOT invent numeric values or ranges — leave value_min/value_max/value_text empty.
- Suggest 5-15 typical parameters traders use for this commodity.
- Mark is_mandatory=true only for parameters essential to identify the product grade.
"""

PRODUCT_AUTO_FILL_PROMPT = """You enrich commodity product catalog specifications from trade documents.
Classify each parameter:
- IDENTITY: defines WHAT the product is (grade, botanical origin, polymer type, SN grade).
- VARIANT: physico-chemical indicators that may differ between lots (flash point, colour, moisture).

For VARIANT parameters, set variation_materiality:
- MATERIAL: difference is commercially/practically significant (out-of-spec changes deal).
- IMMATERIAL: minor lab variation, usually not deal-breaking.
- UNKNOWN: not enough context.

Only extract parameters explicitly stated or strongly implied. Do not invent values.
Return parameters with value_min/value_max only when numeric ranges are stated.
"""

PRODUCT_ASSISTANT_PROMPT = """You are a catalog assistant for a commodity trading platform.
Help the user refine products and their specifications.
Rules:
- IDENTITY parameters define what the product IS.
- VARIANT parameters are physico-chemical indicators that may vary between batches.
- Explain whether VARIANT differences are MATERIAL or IMMATERIAL when relevant.
- Propose concrete spec_changes (action upsert) when the user asks to add/update parameters.
- Never invent commercial prices. Be concise and practical.
"""


def _product_context(product: Product, profiles: list[ProductSpecificationProfile]) -> str:
    lines = [
        f"Product: {product.normalized_name}",
        f"Category: {product.category}",
        f"Aliases: {', '.join(product.aliases or [])}",
        "Specifications:",
    ]
    if not profiles:
        lines.append("(none yet)")
    for profile in profiles:
        lines.append(
            f"- {profile.parameter_name} [{profile.parameter_kind}] "
            f"materiality={profile.variation_materiality} "
            f"unit={profile.unit or 'n/a'} "
            f"range={profile.minimum_value}..{profile.maximum_value} "
            f"mandatory={profile.is_mandatory}"
        )
    return "\n".join(lines)


def auto_enrich_product_from_text(
    db: Session,
    *,
    user: User,
    product: Product,
    source_text: str,
    rough_product_name: str | None = None,
) -> dict:
    if not source_text.strip():
        return {"parameters_added": 0, "reasoning": None}

    budget_settings = ensure_ai_budget_settings(db, user)
    enforce_budget_or_raise(db, user)

    profiles = list(
        db.scalars(
            select(ProductSpecificationProfile).where(ProductSpecificationProfile.product_id == product.id)
        )
    )
    user_prompt = (
        f"Product catalog entry:\n{_product_context(product, profiles)}\n\n"
        f"Rough name from deal: {rough_product_name or product.normalized_name}\n\n"
        f"Source text:\n{source_text}"
    )
    provider = get_ai_provider()
    model = budget_settings.preferred_default_model or settings.openai_default_model
    with tracked_agent_run(
        db,
        user=user,
        context=AgentExecutionContext(
            agent_type=AgentType.CATALOG_ASSISTANT.value,
            task_type="auto_fill",
            input_payload={"product_id": str(product.id), "rough_product_name": rough_product_name},
        ),
    ) as agent:
        output, usage = provider.structured_completion(
            model=model,
            system_prompt=PRODUCT_AUTO_FILL_PROMPT,
            user_prompt=user_prompt,
            output_schema=ProductAutoFillOutput,
        )
        agent.attach_ai_usage(
            model=usage.model,
            operation=AIUsageOperation.CATALOG.value,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=usage.cost_usd,
        )
        agent.record_result(
            result_type=AgentResultType.CATALOG_ASSISTANT.value,
            structured_payload=output.model_dump(mode="json"),
            summary=output.reasoning,
            applied=False,
        )
    merged = merge_discovered_specs(db, product.id, output.parameters)
    for profile in merged:
        profile.evidence_count = (profile.evidence_count or 0) + 1
    db.commit()
    return {
        "parameters_added": len(merged),
        "reasoning": output.reasoning,
        "parameters": output.parameters,
    }


def bootstrap_product_spec_scaffold(
    db: Session,
    *,
    user: User,
    product: Product,
) -> dict:
    profiles = list(
        db.scalars(
            select(ProductSpecificationProfile).where(ProductSpecificationProfile.product_id == product.id)
        )
    )
    if profiles:
        return {"parameters_added": 0, "reasoning": "Product already has specification profiles"}

    budget_settings = ensure_ai_budget_settings(db, user)
    enforce_budget_or_raise(db, user)

    user_prompt = (
        f"Task: suggest specification schema only (no values).\n"
        f"Product: {product.normalized_name}\n"
        f"Category: {product.category}\n"
        f"Aliases: {', '.join(product.aliases or []) or 'n/a'}"
    )
    provider = get_ai_provider()
    model = budget_settings.preferred_default_model or settings.openai_default_model
    with tracked_agent_run(
        db,
        user=user,
        context=AgentExecutionContext(
            agent_type=AgentType.CATALOG_ASSISTANT.value,
            task_type="spec_scaffold",
            input_payload={"product_id": str(product.id)},
        ),
    ) as agent:
        output, usage = provider.structured_completion(
            model=model,
            system_prompt=PRODUCT_SPEC_SCAFFOLD_PROMPT,
            user_prompt=user_prompt,
            output_schema=ProductAutoFillOutput,
        )
        agent.attach_ai_usage(
            model=usage.model,
            operation=AIUsageOperation.CATALOG.value,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=usage.cost_usd,
        )
        agent.record_result(
            result_type=AgentResultType.CATALOG_ASSISTANT.value,
            structured_payload=output.model_dump(mode="json"),
            summary=output.reasoning,
            applied=False,
        )

    merged = merge_discovered_specs(db, product.id, output.parameters)
    db.commit()
    return {
        "parameters_added": len(merged),
        "reasoning": output.reasoning,
        "parameters": output.parameters,
    }


def chat_product_assistant(
    db: Session,
    *,
    user: User,
    product_id: uuid.UUID,
    message: str,
    apply_changes: bool = False,
) -> dict:
    detail = get_product_detail(db, product_id=product_id)
    product = detail["product"]
    profiles = detail["specification_profiles"]

    budget_settings = ensure_ai_budget_settings(db, user)
    enforce_budget_or_raise(db, user)

    user_prompt = (
        f"{_product_context(product, profiles)}\n\n"
        f"User message:\n{message.strip()}"
    )
    provider = get_ai_provider()
    model = budget_settings.preferred_default_model or settings.openai_default_model
    with tracked_agent_run(
        db,
        user=user,
        context=AgentExecutionContext(
            agent_type=AgentType.CATALOG_ASSISTANT.value,
            task_type="catalog_assist",
            input_payload={"product_id": str(product_id), "apply_changes": apply_changes},
        ),
    ) as agent:
        output, usage = provider.structured_completion(
            model=model,
            system_prompt=PRODUCT_ASSISTANT_PROMPT,
            user_prompt=user_prompt,
            output_schema=ProductAssistantOutput,
        )
        agent.attach_ai_usage(
            model=usage.model,
            operation=AIUsageOperation.CATALOG.value,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=usage.cost_usd,
        )
        agent.record_result(
            result_type=AgentResultType.CATALOG_ASSISTANT.value,
            structured_payload=output.model_dump(mode="json"),
            summary=output.reply[:500] if output.reply else None,
            applied=False,
        )

    applied: list[str] = []
    if apply_changes:
        applied = _apply_assistant_changes(db, user=user, product=product, changes=output.spec_changes)
        if output.category:
            product.category = output.category
        if output.aliases:
            existing = set(product.aliases or [])
            product.aliases = list(existing | set(output.aliases))
        db.commit()

    log_audit(
        db,
        actor=user,
        action=AuditAction.AI_CALL,
        entity_type="Product",
        entity_id=product.id,
        new_value={"assistant_message": message[:200], "applied": applied, "apply_changes": apply_changes},
    )
    db.commit()

    return {
        "reply": output.reply,
        "spec_changes": output.spec_changes,
        "applied_changes": applied,
        "ai_model": usage.model,
        "ai_cost_usd": usage.cost_usd,
    }


def _apply_assistant_changes(
    db: Session,
    *,
    user: User,
    product: Product,
    changes: list[ProductSpecChangeOutput],
) -> list[str]:
    from app.ai.schemas import SpecParameterOutput

    applied: list[str] = []
    allowed_kinds = {item.value for item in SpecParameterKind}
    allowed_materiality = {item.value for item in SpecVariationMateriality}

    for change in changes:
        if change.action == "remove":
            existing = db.scalar(
                select(ProductSpecificationProfile).where(
                    ProductSpecificationProfile.product_id == product.id,
                    ProductSpecificationProfile.parameter_name == change.parameter_name,
                )
            )
            if existing:
                db.delete(existing)
                applied.append(f"removed:{change.parameter_name}")
            continue

        param = SpecParameterOutput(
            parameter_name=change.parameter_name,
            unit=change.unit,
            value_min=change.value_min,
            value_max=change.value_max,
            is_mandatory=change.is_mandatory,
            parameter_kind=change.parameter_kind if change.parameter_kind in allowed_kinds else SpecParameterKind.VARIANT.value,
            variation_materiality=(
                change.variation_materiality
                if change.variation_materiality in allowed_materiality
                else SpecVariationMateriality.UNKNOWN.value
            ),
            description=change.description,
        )
        merge_discovered_specs(db, product.id, [param])
        existing = db.scalar(
            select(ProductSpecificationProfile).where(
                ProductSpecificationProfile.product_id == product.id,
                ProductSpecificationProfile.parameter_name == change.parameter_name,
            )
        )
        if existing and change.description:
            existing.description = change.description
        applied.append(f"upsert:{change.parameter_name}")

    if applied:
        log_audit(
            db,
            actor=user,
            action=AuditAction.UPDATE,
            entity_type="Product",
            entity_id=product.id,
            new_value={"assistant_applied": applied},
        )
    return applied
