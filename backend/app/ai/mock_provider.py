import json
import re
from decimal import Decimal
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.ai.base import AIProvider
from app.ai.pricing import estimate_cost_usd
from app.ai.schemas import (
    AICompletionUsage,
    CounterpartyEnrichmentOutput,
    OpportunityExtractionOutput,
    ProductAssistantOutput,
    ProductAutoFillOutput,
    ProductResolutionOutput,
    RFQDraftOutput,
    TenderFeasibilityOutput,
    TenderSearchOutput,
)

T = TypeVar("T", bound=BaseModel)

_EXTRACTION_FIXTURES: list[dict] = [
    {
        "pattern": r"SN500|sn\s*500",
        "data": {
            "raw_product_name": "Base Oil SN500",
            "buyer_or_supplier_hint": "Buyer from document",
            "quantity_min": "100",
            "quantity_max": "200",
            "quantity_unit": "MT",
            "destination_hint": "Rotterdam",
            "requested_incoterm": "CIF",
            "packaging": "flexitank",
            "deadline": "2026-08-31",
            "missing_fields": ["origin_hint"],
            "evidence_hints": [
                {"field_path": "quantity_min", "excerpt": "100 MT", "page_number": 1},
                {"field_path": "destination_hint", "excerpt": "Rotterdam", "page_number": 1},
            ],
        },
    },
    {
        "pattern": r".+",
        "data": {
            "raw_product_name": None,
            "buyer_or_supplier_hint": None,
            "quantity_min": None,
            "quantity_max": None,
            "quantity_unit": None,
            "origin_hint": None,
            "destination_hint": None,
            "requested_incoterm": None,
            "packaging": None,
            "deadline": None,
            "missing_fields": [
                "raw_product_name",
                "quantity_min",
                "destination_hint",
                "requested_incoterm",
            ],
            "evidence_hints": [],
        },
    },
]


class MockAIProvider(AIProvider):
    def structured_completion(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[T],
        temperature: float = 0.0,
    ) -> tuple[T, AICompletionUsage]:
        payload: dict
        if output_schema is OpportunityExtractionOutput:
            payload = _match_fixture(user_prompt)
        elif output_schema is RFQDraftOutput:
            payload = _match_rfq_fixture(user_prompt)
        elif output_schema is ProductResolutionOutput:
            payload = _match_product_resolution_fixture(user_prompt)
        elif output_schema is CounterpartyEnrichmentOutput:
            payload = _match_counterparty_enrichment_fixture(user_prompt)
        elif output_schema is ProductAutoFillOutput:
            payload = _match_product_auto_fill_fixture(user_prompt)
        elif output_schema is ProductAssistantOutput:
            payload = _match_product_assistant_fixture(user_prompt)
        elif output_schema is TenderSearchOutput:
            payload = _match_tender_search_fixture(user_prompt)
        elif output_schema is TenderFeasibilityOutput:
            payload = _match_tender_feasibility_fixture(user_prompt)
        else:
            payload = {}

        try:
            parsed = output_schema.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(f"Mock provider validation failed: {exc}") from exc

        input_tokens = max(len(system_prompt) // 4, 1)
        output_tokens = max(len(json.dumps(payload)) // 4, 1)
        usage = AICompletionUsage(
            model=model or "mock-model",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=estimate_cost_usd(model or "mock-model", input_tokens, output_tokens),
            raw_response={"mock": True, "payload": payload},
        )
        return parsed, usage


def _match_fixture(text: str) -> dict:
    for fixture in _EXTRACTION_FIXTURES:
        if re.search(fixture["pattern"], text, re.IGNORECASE):
            return fixture["data"]
    return _EXTRACTION_FIXTURES[-1]["data"]


def _match_rfq_fixture(text: str) -> dict:
    subject_match = re.search(r"Current subject:\s*(.+)", text)
    body_match = re.search(r"Current body:\n([\s\S]+?)\nContext:", text)
    subject = subject_match.group(1).strip() if subject_match else "RFQ inquiry"
    body = body_match.group(1).strip() if body_match else "Please provide your quotation."
    return {
        "subject": f"[AI adapted] {subject}",
        "body": f"{body}\n\n[AI adapted for recipient context]",
    }


def _match_product_resolution_fixture(text: str) -> dict:
    rough_match = re.search(r"Rough product description:\s*(.+?)(?:\n\n|$)", text, re.DOTALL)
    rough = rough_match.group(1).strip() if rough_match else text
    if re.search(r"base\s*oil|sn\s*500|sn500", rough, re.IGNORECASE):
        return {
            "normalized_product_name": "SN500",
            "confidence": 0.86,
            "reasoning": "Rough description matches base oil SN500 from product catalog.",
            "parameters": [
                {
                    "parameter_name": "kinematic_viscosity_40c",
                    "unit": "cSt",
                    "value_min": "4.5",
                    "value_max": "5.0",
                    "status": "EXTRACTED",
                    "evidence_excerpt": "viscosity requirement 4.5-5.0 cSt",
                    "is_mandatory": True,
                },
                {
                    "parameter_name": "flash_point",
                    "unit": "C",
                    "value_min": "180",
                    "status": "MISSING",
                    "is_mandatory": True,
                },
            ],
            "missing_mandatory": ["flash_point"],
        }
    return {
        "normalized_product_name": None,
        "confidence": 0.2,
        "reasoning": "Could not map rough product to catalog.",
        "parameters": [],
        "missing_mandatory": [],
        "proposed_new_product": _proposed_product_from_rough(rough),
    }


def _proposed_product_from_rough(rough: str) -> dict:
    if re.search(r"гуар|guar", rough, re.IGNORECASE):
        return {
            "normalized_name": "Guar Gum",
            "category": "polymer",
            "aliases": [rough.strip(), "guar gum", "гуаровая камедь"],
            "typical_units": ["MT", "kg"],
            "parameters": [
                {
                    "parameter_name": "viscosity",
                    "unit": "cP",
                    "status": "MISSING",
                    "is_mandatory": True,
                    "parameter_kind": "VARIANT",
                    "variation_materiality": "MATERIAL",
                },
                {
                    "parameter_name": "mesh_size",
                    "unit": "mesh",
                    "status": "MISSING",
                    "is_mandatory": False,
                    "parameter_kind": "IDENTITY",
                    "variation_materiality": "MATERIAL",
                },
                {
                    "parameter_name": "purity",
                    "unit": "%",
                    "status": "MISSING",
                    "is_mandatory": False,
                    "parameter_kind": "VARIANT",
                    "variation_materiality": "IMMATERIAL",
                },
            ],
            "reasoning": "Guar gum for oilfield services — typical specs include viscosity and mesh size.",
        }
    return {
        "normalized_name": rough.strip()[:80] or "New Product",
        "category": "other",
        "aliases": [rough.strip()],
        "typical_units": ["MT", "kg"],
        "parameters": [],
        "reasoning": "No catalog match; propose open entry for manual refinement.",
    }


def _match_counterparty_enrichment_fixture(text: str) -> dict:
    if re.search(r"gulf|base\s*oil|sn500", text, re.IGNORECASE):
        return {
            "summary": "Producer/trader of base oils with Middle East origin.",
            "capabilities": [
                {
                    "capability_type": "PRODUCT",
                    "title": "Base Oil SN500 supply",
                    "rough_product_name": "Base Oil SN500",
                    "normalized_product_name": "SN500",
                    "regions": ["UAE", "Middle East"],
                    "routes": ["Jebel Ali → Rotterdam"],
                    "incoterms": ["FOB", "CIF"],
                    "notes": "Indicative availability from marketing materials.",
                    "evidence_excerpt": "SN500 base oil export availability",
                    "confirmation_level": "ESTIMATE",
                }
            ],
            "contact_hints": [
                {
                    "full_name": "Sales Desk",
                    "role_title": "Commercial",
                    "email": "sales@gulfbasoil.example.com",
                    "department": "Sales",
                    "evidence_excerpt": "Contact listed on supplier page",
                }
            ],
            "missing_fields": ["confirmed_prices"],
        }
    return {
        "summary": "Insufficient public information to infer detailed capabilities.",
        "capabilities": [],
        "contact_hints": [],
        "missing_fields": ["products", "routes", "contacts"],
    }


def _match_product_auto_fill_fixture(text: str) -> dict:
    if re.search(r"гуар|guar", text, re.IGNORECASE):
        return {
            "reasoning": "Guar gum oilfield grade — viscosity is material variant spec.",
            "parameters": [
                {
                    "parameter_name": "viscosity",
                    "unit": "cP",
                    "value_min": "3500",
                    "value_max": "5500",
                    "status": "EXTRACTED",
                    "parameter_kind": "VARIANT",
                    "variation_materiality": "MATERIAL",
                    "evidence_excerpt": "oilfield guar viscosity requirement",
                },
                {
                    "parameter_name": "mesh_size",
                    "unit": "mesh",
                    "value_min": "200",
                    "status": "EXTRACTED",
                    "parameter_kind": "IDENTITY",
                    "variation_materiality": "MATERIAL",
                },
            ],
        }
    if re.search(r"sn\s*500|base\s*oil", text, re.IGNORECASE):
        return {
            "parameters": [
                {
                    "parameter_name": "kinematic_viscosity_40c",
                    "unit": "cSt",
                    "value_min": "4.5",
                    "value_max": "5.0",
                    "parameter_kind": "IDENTITY",
                    "variation_materiality": "MATERIAL",
                }
            ],
            "reasoning": "Base oil SN500 viscosity range from source.",
        }
    return {"parameters": [], "reasoning": "No additional specs found."}


def _match_product_assistant_fixture(text: str) -> dict:
    if re.search(r"добав|add|mesh", text, re.IGNORECASE):
        return {
            "reply": "Добавил mesh_size как ключевую (IDENTITY) характеристику. Для гуара фракция определяет применение.",
            "spec_changes": [
                {
                    "action": "upsert",
                    "parameter_name": "mesh_size",
                    "parameter_kind": "IDENTITY",
                    "variation_materiality": "MATERIAL",
                    "unit": "mesh",
                    "is_mandatory": True,
                    "reasoning": "Mesh defines product grade for guar gum.",
                }
            ],
        }
    return {
        "reply": "Могу помочь изменить категорию, синонимы и спецификации. Уточните, что изменить.",
        "spec_changes": [],
    }


def _match_tender_search_fixture(text: str) -> dict:
    if "Page text:" not in text and "[no page text available]" in text:
        return {"hits": [], "notes": "No page text available for extraction."}

    page_text = text.split("Page text:\n", 1)[-1] if "Page text:\n" in text else text
    keywords_match = re.search(r"Product keywords:\s*(.+?)(?:\n|$)", text)
    keywords = [
        part.strip()
        for part in (keywords_match.group(1).split(",") if keywords_match else [])
        if part.strip()
    ]
    if not keywords:
        return {"hits": [], "notes": "No keywords provided."}

    lines = []
    for raw_line in page_text.splitlines():
        line = " ".join(raw_line.split())
        if len(line) < 20:
            continue
        if any(keyword.lower() in line.lower() for keyword in keywords):
            lines.append(line)
    if not lines:
        return {"hits": [], "notes": "No keyword matches in fetched page text."}

    source_match = re.search(r"Source:\s*(.+?)(?:\n|$)", text)
    source_name = source_match.group(1).strip() if source_match else "source"
    url_match = re.search(r"Base URL:\s*(.+?)(?:\n|$)", text)
    source_url = url_match.group(1).strip() if url_match else None
    return {
        "hits": [
            {
                "title": line[:240],
                "url": source_url,
                "product": next((k for k in keywords if k.lower() in line.lower()), keywords[0]),
                "body": line,
                "confidence": 0.7,
                "evidence_excerpt": line[:300],
            }
            for line in lines[:3]
        ],
        "notes": f"Extracted from real page text ({source_name})",
    }


def _match_tender_feasibility_fixture(text: str) -> dict:
    product = "commodity"
    if re.search(r"urea|carbamide|fertilizer|карбамид", text, re.IGNORECASE):
        product = "urea"
    elif re.search(r"sn\s*500|base oil", text, re.IGNORECASE):
        product = "base oil"

    if re.search(r"office furniture|chairs and desks", text, re.IGNORECASE):
        return {
            "feasible": False,
            "confidence": 0.82,
            "summary": "Тендер не относится к товарной номенклатуре трейдера — сделка нереализуема.",
            "supplier_hint": None,
            "supplier_reasoning": None,
            "risks": ["Несоответствие предмета закупки"],
        }

    supplier = "Gulf Fertilizer Trading FZE" if product == "urea" else "Black Sea Base Oils LLC"
    return {
        "feasible": True,
        "confidence": 0.78,
        "summary": (
            f"Предварительно реализуемо через поставщика {supplier}: закупка и поставка по тендеру "
            f"выглядят экономически возможными."
        ),
        "supplier_hint": supplier,
        "supplier_reasoning": "Поставщик покрывает маршрут и продукт по каталогу возможностей.",
        "buy_price_per_unit": "285",
        "buy_currency": "USD",
        "buy_incoterm": "FOB",
        "buy_basis": "FOB Middle East",
        "sell_price_per_unit": "332",
        "sell_currency": "USD",
        "sell_incoterm": "CIF",
        "sell_basis": "CIF destination",
        "transport_cost": "28",
        "gross_margin": "19",
        "gross_margin_percent": 6.5,
        "margin_currency": "USD",
        "risks": ["Срок подачи заявки", "Точная спецификация покупателя"],
    }
