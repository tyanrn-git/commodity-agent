from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas import ProductResponse
from app.api.schemas_products import (
    ProductCreate,
    ProductDetailResponse,
    ProductListItemResponse,
    ProductSpecProfileResponse,
    SpecParameterCreate,
)
from app.api.schemas_product_assistant import ProductAssistantRequest, ProductAssistantResponse, ProductSpecChangeResponse
from app.db.session import get_db
from app.domain.models import User
from app.services.product_assistant import chat_product_assistant
from app.services.product_catalog import (
    add_spec_parameter,
    create_product,
    get_product_detail,
    list_products_with_specs,
)

router = APIRouter(tags=["products"])


def _to_list_item(item: dict) -> ProductListItemResponse:
    product = item["product"]
    return ProductListItemResponse(
        id=product.id,
        normalized_name=product.normalized_name,
        category=product.category,
        aliases=product.aliases,
        typical_units=product.typical_units,
        completeness=item["completeness"],
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def _to_detail(item: dict) -> ProductDetailResponse:
    product = item["product"]
    return ProductDetailResponse(
        id=product.id,
        normalized_name=product.normalized_name,
        category=product.category,
        aliases=product.aliases,
        typical_units=product.typical_units,
        specification_profiles=[
            ProductSpecProfileResponse.model_validate(profile) for profile in item["specification_profiles"]
        ],
        completeness=item["completeness"],
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.get("/products", response_model=list[ProductListItemResponse])
def list_products_catalog(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ProductListItemResponse]:
    return [_to_list_item(item) for item in list_products_with_specs(db)]


@router.get("/products/summary", response_model=list[ProductResponse])
def list_products_summary(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ProductResponse]:
    return [item["product"] for item in list_products_with_specs(db)]


@router.get("/products/{product_id}", response_model=ProductDetailResponse)
def get_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ProductDetailResponse:
    return _to_detail(get_product_detail(db, product_id=product_id))


@router.post("/products", response_model=ProductDetailResponse, status_code=201)
def create_product_route(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductDetailResponse:
    from app.ai.schemas import SpecParameterOutput

    spec_parameters = [
        SpecParameterOutput(
            parameter_name=item.parameter_name,
            unit=item.unit,
            value_min=item.minimum_value,
            value_max=item.maximum_value,
            is_mandatory=item.is_mandatory,
        )
        for item in payload.spec_parameters
    ]
    product = create_product(
        db,
        user=current_user,
        normalized_name=payload.normalized_name,
        category=payload.category,
        aliases=payload.aliases,
        typical_units=payload.typical_units,
        spec_parameters=spec_parameters,
    )
    return _to_detail(get_product_detail(db, product_id=product.id))


@router.post("/products/{product_id}/spec-parameters", response_model=ProductSpecProfileResponse, status_code=201)
def add_product_spec_parameter(
    product_id: UUID,
    payload: SpecParameterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductSpecProfileResponse:
    profile = add_spec_parameter(
        db,
        user=current_user,
        product_id=product_id,
        parameter_name=payload.parameter_name,
        unit=payload.unit,
        is_mandatory=payload.is_mandatory,
        minimum_value=float(payload.minimum_value) if payload.minimum_value is not None else None,
        maximum_value=float(payload.maximum_value) if payload.maximum_value is not None else None,
    )
    return ProductSpecProfileResponse.model_validate(profile)


@router.post("/products/{product_id}/assistant", response_model=ProductAssistantResponse)
def product_assistant_route(
    product_id: UUID,
    payload: ProductAssistantRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductAssistantResponse:
    result = chat_product_assistant(
        db,
        user=current_user,
        product_id=product_id,
        message=payload.message,
        apply_changes=payload.apply_changes,
    )
    return ProductAssistantResponse(
        reply=result["reply"],
        spec_changes=[
            ProductSpecChangeResponse(
                action=change.action,
                parameter_name=change.parameter_name,
                parameter_kind=change.parameter_kind,
                variation_materiality=change.variation_materiality,
                unit=change.unit,
                value_min=str(change.value_min) if change.value_min is not None else None,
                value_max=str(change.value_max) if change.value_max is not None else None,
                is_mandatory=change.is_mandatory,
                description=change.description,
                reasoning=change.reasoning,
            )
            for change in result["spec_changes"]
        ],
        applied_changes=result["applied_changes"],
        ai_model=result["ai_model"],
        ai_cost_usd=str(result["ai_cost_usd"]),
    )
