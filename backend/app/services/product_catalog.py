import re
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.schemas import ProposedProductOutput, SpecParameterOutput
from app.domain.enums import SpecParameterKind, SpecVariationMateriality
from app.domain.models import Product, ProductSpecificationProfile
from app.services.audit import log_audit
from app.domain.enums import AuditAction
from app.domain.models import User


def _slug_name(value: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", value.strip(), flags=re.UNICODE)
    cleaned = re.sub(r"[\s_-]+", "_", cleaned)
    return cleaned[:255] or "product"


def spec_profile_completeness(profiles: list[ProductSpecificationProfile]) -> dict:
    if not profiles:
        return {
            "total_parameters": 0,
            "filled_parameters": 0,
            "completeness_percent": 0,
            "identity_parameters": 0,
            "variant_parameters": 0,
        }
    filled = sum(
        1
        for profile in profiles
        if profile.minimum_value is not None or profile.maximum_value is not None
    )
    total = len(profiles)
    identity = sum(1 for p in profiles if p.parameter_kind == SpecParameterKind.IDENTITY.value)
    return {
        "total_parameters": total,
        "filled_parameters": filled,
        "completeness_percent": round(100 * filled / total) if total else 0,
        "identity_parameters": identity,
        "variant_parameters": total - identity,
    }


def list_products_with_specs(db: Session) -> list[dict]:
    products = list(db.scalars(select(Product).order_by(Product.normalized_name)))
    result: list[dict] = []
    for product in products:
        profiles = list(
            db.scalars(
                select(ProductSpecificationProfile)
                .where(ProductSpecificationProfile.product_id == product.id)
                .order_by(ProductSpecificationProfile.parameter_name)
            )
        )
        result.append(
            {
                "product": product,
                "specification_profiles": profiles,
                "completeness": spec_profile_completeness(profiles),
            }
        )
    return result


def get_product_detail(db: Session, *, product_id: uuid.UUID) -> dict:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    profiles = list(
        db.scalars(
            select(ProductSpecificationProfile)
            .where(ProductSpecificationProfile.product_id == product.id)
            .order_by(ProductSpecificationProfile.parameter_name)
        )
    )
    return {
        "product": product,
        "specification_profiles": profiles,
        "completeness": spec_profile_completeness(profiles),
    }


def create_product(
    db: Session,
    *,
    user: User,
    normalized_name: str,
    category: str,
    aliases: list[str] | None = None,
    typical_units: list[str] | None = None,
    spec_parameters: list[SpecParameterOutput] | None = None,
    auto_bootstrap_specs: bool = True,
) -> Product:
    name = normalized_name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product name is required")

    existing = db.scalar(select(Product).where(Product.normalized_name.ilike(name)))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product already exists")

    product = Product(
        normalized_name=name,
        category=category.strip() or "other",
        aliases=aliases or [],
        typical_units=typical_units or ["MT", "kg"],
    )
    db.add(product)
    db.flush()

    if spec_parameters:
        merge_discovered_specs(db, product.id, spec_parameters)

    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="Product",
        entity_id=product.id,
        new_value={"normalized_name": product.normalized_name, "category": product.category},
    )
    db.commit()
    db.refresh(product)
    if auto_bootstrap_specs and not spec_parameters:
        from app.services.product_assistant import bootstrap_product_spec_scaffold

        bootstrap_product_spec_scaffold(db, user=user, product=product)
        db.refresh(product)
    return product


def create_product_from_proposal(
    db: Session,
    *,
    user: User,
    proposal: ProposedProductOutput,
) -> Product:
    return create_product(
        db,
        user=user,
        normalized_name=proposal.normalized_name,
        category=proposal.category,
        aliases=proposal.aliases,
        typical_units=proposal.typical_units or ["MT", "kg"],
        spec_parameters=proposal.parameters,
    )


def add_spec_parameter(
    db: Session,
    *,
    user: User,
    product_id: uuid.UUID,
    parameter_name: str,
    unit: str | None = None,
    is_mandatory: bool = False,
    minimum_value: float | None = None,
    maximum_value: float | None = None,
) -> ProductSpecificationProfile:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    existing = db.scalar(
        select(ProductSpecificationProfile).where(
            ProductSpecificationProfile.product_id == product_id,
            ProductSpecificationProfile.parameter_name == parameter_name,
        )
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parameter already exists")

    profile = ProductSpecificationProfile(
        product_id=product_id,
        parameter_name=parameter_name.strip(),
        unit=unit,
        is_mandatory=is_mandatory,
        minimum_value=minimum_value,
        maximum_value=maximum_value,
    )
    db.add(profile)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="ProductSpecificationProfile",
        entity_id=profile.id,
        new_value={"parameter_name": profile.parameter_name, "product_id": str(product_id)},
    )
    db.commit()
    db.refresh(profile)
    return profile


def merge_discovered_specs(
    db: Session,
    product_id: uuid.UUID,
    parameters: list[SpecParameterOutput],
) -> list[ProductSpecificationProfile]:
    updated: list[ProductSpecificationProfile] = []
    allowed_kinds = {item.value for item in SpecParameterKind}
    allowed_materiality = {item.value for item in SpecVariationMateriality}

    for param in parameters:
        if not param.parameter_name:
            continue
        kind = param.parameter_kind if param.parameter_kind in allowed_kinds else SpecParameterKind.VARIANT.value
        materiality = (
            param.variation_materiality
            if param.variation_materiality in allowed_materiality
            else SpecVariationMateriality.UNKNOWN.value
        )
        existing = db.scalar(
            select(ProductSpecificationProfile).where(
                ProductSpecificationProfile.product_id == product_id,
                ProductSpecificationProfile.parameter_name == param.parameter_name,
            )
        )
        if existing:
            if param.unit and not existing.unit:
                existing.unit = param.unit
            if param.is_mandatory:
                existing.is_mandatory = True
            if param.description and not existing.description:
                existing.description = param.description
            if kind == SpecParameterKind.IDENTITY.value:
                existing.parameter_kind = kind
            if materiality != SpecVariationMateriality.UNKNOWN.value:
                existing.variation_materiality = materiality
            if param.value_min is not None:
                value = float(param.value_min)
                existing.minimum_value = (
                    value if existing.minimum_value is None else min(float(existing.minimum_value), value)
                )
            if param.value_max is not None:
                value = float(param.value_max)
                existing.maximum_value = (
                    value if existing.maximum_value is None else max(float(existing.maximum_value), value)
                )
            existing.evidence_count = (existing.evidence_count or 0) + 1
            updated.append(existing)
            continue

        profile = ProductSpecificationProfile(
            product_id=product_id,
            parameter_name=param.parameter_name,
            unit=param.unit,
            is_mandatory=param.is_mandatory,
            minimum_value=float(param.value_min) if param.value_min is not None else None,
            maximum_value=float(param.value_max) if param.value_max is not None else None,
            parameter_kind=kind,
            variation_materiality=materiality,
            description=param.description,
            evidence_count=1,
        )
        db.add(profile)
        updated.append(profile)

    db.flush()
    return updated


def suggest_normalized_name(rough_name: str) -> str:
    return _slug_name(rough_name)
