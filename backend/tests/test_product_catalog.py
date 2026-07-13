import pytest

pytestmark = pytest.mark.usefixtures("setup_database")


def test_create_product_empty_spec(auth_client):
    created = auth_client.post(
        "/products",
        json={
            "normalized_name": "Carrageenan",
            "category": "polymer",
            "aliases": ["каррагинан", "carrageenan"],
            "typical_units": ["MT", "kg"],
            "spec_parameters": [],
        },
    )
    assert created.status_code == 201
    data = created.json()
    assert data["normalized_name"] == "Carrageenan"
    assert data["completeness"]["total_parameters"] >= 1
    assert data["completeness"]["completeness_percent"] >= 0


def test_create_product_with_partial_spec(auth_client):
    created = auth_client.post(
        "/products",
        json={
            "normalized_name": "Palm Olein",
            "category": "vegetable_oil",
            "spec_parameters": [
                {
                    "parameter_name": "ffa",
                    "unit": "%",
                    "is_mandatory": True,
                    "minimum_value": "0.1",
                    "maximum_value": "0.5",
                },
                {"parameter_name": "iodine_value", "unit": "g/100g", "is_mandatory": False},
            ],
        },
    )
    assert created.status_code == 201
    data = created.json()
    assert data["completeness"]["total_parameters"] == 2
    assert data["completeness"]["filled_parameters"] == 1
    assert data["completeness"]["completeness_percent"] == 50


def test_resolve_and_create_catalog_product(auth_client):
    opp = auth_client.post("/opportunities", json={"title": "Guar RFQ"}).json()

    preview = auth_client.post(
        f"/opportunities/{opp['id']}/resolve-product",
        json={"rough_product_name": "гуар для нефтесервиса", "create_if_missing": False},
    ).json()
    assert preview["matched"] is False
    assert preview["proposed_new_product"] is not None
    assert preview["proposed_new_product"]["normalized_name"] == "Guar Gum"

    created = auth_client.post(
        f"/opportunities/{opp['id']}/resolve-product",
        json={"rough_product_name": "гуар для нефтесервиса", "create_if_missing": True},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["product_created"] is False
    assert body["matched"] is True
    assert body["normalized_product_name"] == "Guar Gum"
    assert len(body["spec_values"]) >= 1

    catalog = auth_client.get("/products").json()
    assert any(item["normalized_name"] == "Guar Gum" for item in catalog)
