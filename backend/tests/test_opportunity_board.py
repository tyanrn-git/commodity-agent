import pytest

from app.domain.enums import OpportunityType

pytestmark = pytest.mark.usefixtures("setup_database")


def test_opportunities_board_with_monitoring_context(auth_client):
    rules = auth_client.get("/monitoring-rules").json()
    rule_id = rules[0]["id"]
    auth_client.post(f"/monitoring-rules/{rule_id}/run")

    board = auth_client.get("/opportunities/board")
    assert board.status_code == 200
    data = board.json()

    auto = [o for o in data["opportunities"] if o["type"] == OpportunityType.AUTO_DISCOVERED.value]
    assert len(auto) >= 1
    assert auto[0]["commercial_summary"]
    assert auto[0]["origin_explanation"]
    assert auto[0]["commercial_row"]
    assert "SN500" in auto[0]["origin_explanation"] or "Base Oil" in auto[0]["origin_explanation"]

    skipped = data["skipped_monitoring"]
    assert any("Urea" in (s.get("product") or s.get("title") or "") for s in skipped)
    urea = next(s for s in skipped if "Urea" in (s.get("product") or ""))
    assert urea["filter_explanation"]
    assert "SN500" in urea["filter_explanation"]
