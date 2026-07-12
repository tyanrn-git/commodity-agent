import pytest

from app.domain.enums import OpportunityType
from app.services.opportunity_commercial import build_indicative_economics_from_supplier_context

pytestmark = pytest.mark.usefixtures("setup_database")


def test_build_commercial_row_supplier_intake():
    context_data = build_indicative_economics_from_supplier_context(
        type("Ctx", (), {
            "supplier_hint": "Gulf Base Oil",
            "unit_price": 850,
            "currency": "USD",
            "incoterm": "FOB",
            "origin": "Jebel Ali",
        })()
    )
    assert context_data["seller_name"] == "Gulf Base Oil"
    assert context_data["buy_price_per_unit"] == 850
    assert context_data["buy_basis"] == "FOB Jebel Ali"


def test_opportunities_board_has_commercial_row(auth_client):
    created = auth_client.post(
        "/opportunities/supplier-led",
        json={
            "title": "Test supplier row",
            "buyer_or_supplier_hint": "Test Supplier",
            "unit_price": "900",
            "currency": "USD",
            "incoterm": "FOB",
            "origin": "Dubai",
            "quantity_min": "50",
            "quantity_max": "50",
            "quantity_unit": "MT",
        },
    )
    assert created.status_code == 201

    board = auth_client.get("/opportunities/board")
    assert board.status_code == 200
    item = next(o for o in board.json()["opportunities"] if o["title"] == "Test supplier row")
    row = item["commercial_row"]
    assert row["seller_name"] == "Test Supplier"
    assert row["buy_price_per_unit"] == 900
    assert row["volume"] == "50 MT"
    assert row["data_completeness"] in ("PARTIAL", "CONFIRMED")


def test_opportunities_board_monitoring_commercial_row(auth_client):
    rules = auth_client.get("/monitoring-rules").json()
    rule_id = rules[0]["id"]
    auth_client.post(f"/monitoring-rules/{rule_id}/run")

    board = auth_client.get("/opportunities/board")
    auto = [o for o in board.json()["opportunities"] if o["type"] == OpportunityType.AUTO_DISCOVERED.value]
    assert len(auto) >= 1
    assert "commercial_row" in auto[0]
    assert auto[0]["commercial_row"]["product_name"] or auto[0]["commercial_summary"]
