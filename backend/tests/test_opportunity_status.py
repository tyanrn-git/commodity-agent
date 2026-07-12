import pytest

from app.domain.enums import OpportunityStatus

pytestmark = pytest.mark.usefixtures("setup_database")


def test_create_opportunity_has_status_history(auth_client):
    created = auth_client.post(
        "/opportunities",
        json={"title": "Status history test"},
    )
    assert created.status_code == 201
    opp_id = created.json()["id"]
    assert created.json()["status"] == OpportunityStatus.NEW.value
    assert created.json()["status_changed_at"] is not None

    history = auth_client.get(f"/opportunities/{opp_id}/status-history")
    assert history.status_code == 200
    assert len(history.json()) >= 1
    assert history.json()[0]["status_code"] == OpportunityStatus.NEW.value


def test_change_opportunity_status(auth_client):
    created = auth_client.post("/opportunities", json={"title": "Status change test"}).json()
    response = auth_client.post(
        f"/opportunities/{created['id']}/status",
        json={"status": OpportunityStatus.ACCEPTED.value, "note": "Looks good"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == OpportunityStatus.ACCEPTED.value
    assert body["status_changed_at"] is not None


def test_board_includes_display_status_and_deadlines(auth_client):
    auth_client.post(
        "/opportunities",
        json={
            "title": "Board status row",
            "quote_deadline": "2026-08-15T12:00:00Z",
            "delivery_deadline": "2026-09-30T12:00:00Z",
        },
    )
    board = auth_client.get("/opportunities/board").json()
    item = next(o for o in board["opportunities"] if o["title"] == "Board status row")
    assert item["display_status"]["label"] == "Новая"
    assert item["quote_deadline"] is not None
    assert item["delivery_deadline"] is not None
