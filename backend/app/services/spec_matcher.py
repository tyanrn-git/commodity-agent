from app.domain.enums import SpecMatchResult


def _normalize_product_name(name: str | None) -> str:
    if not name:
        return ""
    return name.upper().replace("BASE OIL", "").replace(" ", "").strip()


def match_product(requirement_product: str | None, offer_product: str | None) -> dict:
    req = _normalize_product_name(requirement_product)
    offer = _normalize_product_name(offer_product)
    if not req or not offer:
        return {
            "field": "product",
            "result": SpecMatchResult.UNKNOWN.value,
            "requirement": requirement_product,
            "offer": offer_product,
        }
    if req in offer or offer in req:
        return {
            "field": "product",
            "result": SpecMatchResult.MATCH.value,
            "requirement": requirement_product,
            "offer": offer_product,
        }
    return {
        "field": "product",
        "result": SpecMatchResult.MISMATCH.value,
        "requirement": requirement_product,
        "offer": offer_product,
    }


def build_spec_summary(requirement_product: str | None, offer_product: str | None) -> dict:
    product_match = match_product(requirement_product, offer_product)
    overall = product_match["result"]
    if overall == SpecMatchResult.MISMATCH.value:
        health = "MISMATCH"
    elif overall == SpecMatchResult.UNKNOWN.value:
        health = "UNKNOWN"
    else:
        health = "OK"
    return {
        "overall": overall,
        "health_status": health,
        "checks": [product_match],
    }
