import pytest

from app.config import settings

pytestmark = pytest.mark.usefixtures("setup_database")


@pytest.fixture(autouse=True)
def use_mock_ai(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "mock")
    monkeypatch.setattr(settings, "openai_api_key", "")


def test_list_system_internet_sources(auth_client):
    response = auth_client.get("/internet-sources")
    assert response.status_code == 200
    sources = response.json()
    assert len(sources) >= 4
    assert all(source["is_system"] for source in sources)
    names = {source["name"] for source in sources}
    assert "TED — EU Notices API" in names
    assert "World Bank Procurement" in names


def test_match_urea_sources_russian_keyword(auth_client):
    response = auth_client.get("/internet-sources/match?product_keywords=карбамид&regions=EU,Global")
    assert response.status_code == 200
    data = response.json()
    assert data["matched_count"] >= 1
    names = [source["name"] for source in data["sources"]]
    assert "TED — EU Notices API" in names or "World Bank Procurement" in names


def test_match_urea_sources(auth_client):
    response = auth_client.get("/internet-sources/match?product_keywords=urea,fertilizer&regions=India,Global")
    assert response.status_code == 200
    data = response.json()
    assert data["matched_count"] >= 2
    names = [source["name"] for source in data["sources"]]
    assert "World Bank Procurement" in names


def test_match_guar_gum_sources_russian_keyword(auth_client):
    response = auth_client.get(
        "/internet-sources/match?product_keywords=гуаровая%20камедь&regions=India,EU,Global"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["matched_count"] >= 1
    names = [source["name"] for source in data["sources"]]
    assert "TED — EU Notices API" in names or "World Bank Procurement" in names


def test_match_transformer_oil_includes_ted(auth_client):
    response = auth_client.get(
        "/internet-sources/match",
        params={
            "product_keywords": "трансформаторное масло",
            "regions": "India,EU,Global",
            "auto_discover": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    names = [source["name"] for source in data["sources"]]
    assert "TED — EU Notices API" in names


def test_match_russia_prefers_russian_sources(auth_client):
    response = auth_client.get(
        "/internet-sources/match",
        params={
            "product_keywords": "трансформаторное масло",
            "regions": "Russia",
            "auto_discover": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    names = [source["name"] for source in data["sources"]]
    assert "ЕИС Закупки (zakupki.gov.ru)" in names
    assert "TED — EU Notices API" not in names


def test_create_user_internet_source(auth_client):
    created = auth_client.post(
        "/internet-sources",
        json={
            "name": "My tender portal",
            "base_url": "https://example.com/my-tenders",
            "product_tags": ["urea"],
            "regions": ["Turkey"],
            "search_hints": "Daily urea import tenders",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["is_system"] is False
    assert body["owner_id"] is not None

    listed = auth_client.get("/internet-sources?product_tag=urea")
    assert listed.status_code == 200
    names = {source["name"] for source in listed.json()}
    assert "My tender portal" in names


def test_create_credentials_internet_source(auth_client):
    created = auth_client.post(
        "/internet-sources",
        json={
            "name": "Platts closed portal",
            "base_url": "https://portal.platts.example/tenders",
            "access_mode": "CREDENTIALS",
            "fetch_config": {
                "credentials": {
                    "platform_name": "Platts",
                    "login_url": "https://portal.platts.example/login",
                    "username": "desk@company.com",
                    "password_hint": "vault:platts-prod",
                    "access_notes": "VPN required",
                }
            },
            "product_tags": ["transformer oil"],
            "regions": ["Global"],
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["access_mode"] == "CREDENTIALS"
    assert body["fetch_config"]["credentials"]["username"] == "desk@company.com"


def test_system_source_is_read_only(auth_client):
    sources = auth_client.get("/internet-sources?include_inactive=true").json()
    system_source = next(source for source in sources if source["is_system"])
    response = auth_client.patch(
        f"/internet-sources/{system_source['id']}",
        json={"name": "Changed"},
    )
    assert response.status_code == 403


def test_system_source_toggle_active(auth_client):
    sources = auth_client.get("/internet-sources?include_inactive=true").json()
    system_source = next(source for source in sources if source["is_system"])
    toggled = auth_client.patch(
        f"/internet-sources/{system_source['id']}",
        json={"is_active": not system_source["is_active"]},
    )
    assert toggled.status_code == 200
    assert toggled.json()["is_active"] is not system_source["is_active"]


def test_include_inactive_sources(auth_client):
    active = auth_client.get("/internet-sources").json()
    all_sources = auth_client.get("/internet-sources?include_inactive=true").json()
    assert len(all_sources) >= len(active)
