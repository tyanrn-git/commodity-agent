import pytest

from app.domain.enums import AgentResultType, AgentRunStatus, AgentTaskStatus, AgentType
from app.services.agent_runtime import AgentExecutionContext, begin_agent_run, list_agent_activity

pytestmark = pytest.mark.usefixtures("setup_database")


def test_begin_agent_run_creates_task_and_run(db, auth_client):
    from app.security.auth import ensure_admin_user

    user = ensure_admin_user(db)
    context = AgentExecutionContext(
        agent_type=AgentType.PRODUCT_MATCHING.value,
        task_type="product_resolution",
        input_payload={"rough_product_name": "urea"},
    )
    handle = begin_agent_run(db, user=user, context=context)
    handle.attach_ai_usage(
        model="mock-model",
        operation="matching",
        cost_usd=0.01,
        input_tokens=10,
        output_tokens=20,
    )
    handle.record_result(
        result_type=AgentResultType.PRODUCT_RESOLUTION.value,
        structured_payload={"normalized_product_name": "Urea"},
        summary="Matched urea",
        confidence=0.9,
    )
    handle.succeed()
    db.commit()

    assert handle.task.status == AgentTaskStatus.COMPLETED.value
    assert handle.run.status == AgentRunStatus.SUCCESS.value
    assert handle.run.ai_usage_log_id is not None

    activity = list_agent_activity(db, user=user, agent_type=AgentType.PRODUCT_MATCHING.value)
    assert len(activity) == 1
    assert activity[0]["runs"][0].input_tokens == 10
    assert activity[0]["results"][0].result_type == AgentResultType.PRODUCT_RESOLUTION.value


def test_product_resolution_creates_agent_activity(auth_client):
    opp = auth_client.post("/opportunities", json={"title": "Agent tracked resolve"}).json()
    auth_client.post(
        f"/opportunities/{opp['id']}/resolve-product",
        json={"rough_product_name": "base oil group II SN500"},
    )
    activity = auth_client.get(f"/opportunities/{opp['id']}/agent-activity").json()
    assert len(activity) >= 1
    assert activity[0]["agent_type"] == AgentType.PRODUCT_MATCHING.value
    assert activity[0]["runs"]
    assert activity[0]["results"]


def test_agent_capabilities_endpoint(auth_client):
    caps = auth_client.get("/agent-capabilities").json()
    types = {item["agent_type"] for item in caps}
    assert AgentType.TENDER_DISCOVERY.value in types
    assert AgentType.PRODUCT_MATCHING.value in types
