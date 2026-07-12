import re
from datetime import datetime, timezone
from decimal import Decimal


BANK_CHANGE_PATTERNS = [
    r"bank details? (?:have |has )?changed",
    r"new (?:bank )?account",
    r"updated (?:bank )?(?:details|information)",
    r"\biban\b",
    r"\bswift\b",
]


def parse_eml_headers_and_body(content: bytes) -> dict:
    text = content.decode("utf-8", errors="ignore")
    headers: dict[str, str] = {}
    body = text
    if "\r\n\r\n" in text:
        header_part, body = text.split("\r\n\r\n", 1)
    elif "\n\n" in text:
        header_part, body = text.split("\n\n", 1)
    else:
        header_part = ""
    for line in header_part.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    return {
        "subject": headers.get("subject", ""),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "in-reply-to": headers.get("in-reply-to", ""),
        "body": body.strip(),
    }


def detect_bank_details_changed(text: str) -> bool:
    lower = text.lower()
    return any(re.search(pattern, lower) for pattern in BANK_CHANGE_PATTERNS)


def extract_supply_offer_fields(text: str, requested_fields: list[str] | None = None) -> dict:
    lower = text.lower()
    extracted: dict = {}
    missing: list[str] = []

    if "sn500" in lower or "sn150" in lower or "base oil" in lower:
        extracted["product_name"] = "Base Oil SN500" if "sn500" in lower else "Base Oil SN150"
    qty_match = re.search(r"(\d+(?:\.\d+)?)\s*(mt|metric tons?)", lower)
    if qty_match:
        extracted["available_quantity"] = qty_match.group(1)
        extracted["quantity_unit"] = "MT"
    price_match = re.search(r"(?:usd|\$)\s*(\d+(?:\.\d+)?)", lower) or re.search(
        r"(\d+(?:\.\d+)?)\s*(?:usd|/mt)", lower
    )
    if price_match:
        extracted["price"] = price_match.group(1)
        extracted["currency"] = "USD"
    for term in ("cif", "fob", "cfr", "dap"):
        if term in lower:
            extracted["incoterm"] = term.upper()
            break
    if "uae" in lower or "jebel ali" in lower:
        extracted["origin"] = "UAE"
    if "tt" in lower or "telegraphic transfer" in lower:
        extracted["payment_terms"] = {"instrument": "TT"}
    elif "lc" in lower or "letter of credit" in lower:
        extracted["payment_terms"] = {"instrument": "LC"}

    fields = requested_fields or [
        "quantity",
        "price",
        "currency",
        "incoterm",
        "origin",
        "payment_terms",
    ]
    field_map = {
        "quantity": "available_quantity",
        "price": "price",
        "currency": "currency",
        "incoterm": "incoterm",
        "origin": "origin",
        "payment_terms": "payment_terms",
        "validity": "offer_valid_until",
        "specification": "product_name",
    }
    for field in fields:
        key = field_map.get(field, field)
        if key not in extracted and field not in extracted:
            missing.append(field)

    return {"extracted": extracted, "missing_fields": missing}


def answered_requested_fields(requested_fields: list[str], extracted: dict) -> tuple[list[str], list[str]]:
    answered: list[str] = []
    missing: list[str] = []
    field_map = {
        "quantity": "available_quantity",
        "price": "price",
        "currency": "currency",
        "incoterm": "incoterm",
        "origin": "origin",
        "payment_terms": "payment_terms",
        "validity": "offer_valid_until",
        "specification": "product_name",
        "freight_cost": "price",
        "equipment_type": "equipment_type",
        "transit_time": "transit_time",
    }
    for field in requested_fields:
        key = field_map.get(field, field)
        if key in extracted or field in extracted:
            answered.append(field)
        else:
            missing.append(field)
    return answered, missing
