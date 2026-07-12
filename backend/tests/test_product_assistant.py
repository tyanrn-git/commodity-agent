import pytest

pytestmark = pytest.mark.usefixtures("setup_database")


def test_product_assistant_propose_and_apply(auth_client):
    created = auth_client.post(
        "/products",
        json={"normalized_name": "Guar Gum", "category": "polymer", "spec_parameters": []},
    ).json()

    chat = auth_client.post(
        f"/products/{created['id']}/assistant",
        json={"message": "добавь mesh_size как ключевую характеристику", "apply_changes": True},
    )
    assert chat.status_code == 200
    body = chat.json()
    assert "mesh_size" in body["reply"].lower() or body["applied_changes"]
    assert body["applied_changes"]

    detail = auth_client.get(f"/products/{created['id']}").json()
    names = [spec["parameter_name"] for spec in detail["specification_profiles"]]
    assert "mesh_size" in names
    mesh = next(spec for spec in detail["specification_profiles"] if spec["parameter_name"] == "mesh_size")
    assert mesh["parameter_kind"] == "IDENTITY"


def test_auto_create_product_on_resolve(auth_client):
    opp = auth_client.post("/opportunities", json={"title": "Auto guar"}).json()
    result = auth_client.post(
        f"/opportunities/{opp['id']}/resolve-product",
        json={"rough_product_name": "гуар для нефтесервиса"},
    ).json()
    assert result["product_created"] is True
    assert result["normalized_product_name"] == "Guar Gum"

    detail = auth_client.get("/products").json()
    guar = next(item for item in detail if item["normalized_name"] == "Guar Gum")
    assert guar["completeness"]["total_parameters"] >= 1
