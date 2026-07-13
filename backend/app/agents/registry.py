from app.agents.base import AgentCapability, BaseAgent
from app.domain.enums import AgentType


class _RegisteredAgent(BaseAgent):
    def __init__(self, capability: AgentCapability) -> None:
        self.capability = capability

    def task_type_for_operation(self, operation: str) -> str:
        return operation


AGENT_REGISTRY: dict[str, AgentCapability] = {
    AgentType.TENDER_DISCOVERY.value: AgentCapability(
        agent_type=AgentType.TENDER_DISCOVERY.value,
        label="Tender Discovery",
        description="Search and ingest tenders from external sources.",
        allowed_task_types=("search_run", "source_discovery", "monitoring_fetch"),
    ),
    AgentType.TENDER_QUALIFICATION.value: AgentCapability(
        agent_type=AgentType.TENDER_QUALIFICATION.value,
        label="Tender Qualification",
        description="Analyze tenders and extract structured requirements.",
        allowed_task_types=("hit_enrichment", "qualification", "document_analysis"),
    ),
    AgentType.SUPPLY_DISCOVERY.value: AgentCapability(
        agent_type=AgentType.SUPPLY_DISCOVERY.value,
        label="Supply Discovery",
        description="Find and rank potential suppliers.",
        allowed_task_types=("supplier_search", "supplier_match"),
    ),
    AgentType.LOGISTICS_DISCOVERY.value: AgentCapability(
        agent_type=AgentType.LOGISTICS_DISCOVERY.value,
        label="Logistics Discovery",
        description="Estimate and collect logistics routes and quotes.",
        allowed_task_types=("route_search", "freight_quote"),
    ),
    AgentType.DEAL_COORDINATOR.value: AgentCapability(
        agent_type=AgentType.DEAL_COORDINATOR.value,
        label="Deal Coordinator",
        description="Orchestrate workflow and next actions.",
        allowed_task_types=("next_action", "stage_transition"),
    ),
    AgentType.PRODUCT_MATCHING.value: AgentCapability(
        agent_type=AgentType.PRODUCT_MATCHING.value,
        label="Product Matching",
        description="Resolve rough product descriptions to catalog products.",
        allowed_task_types=("product_resolution",),
    ),
    AgentType.CATALOG_ASSISTANT.value: AgentCapability(
        agent_type=AgentType.CATALOG_ASSISTANT.value,
        label="Catalog Assistant",
        description="Assist with product catalog enrichment.",
        allowed_task_types=("catalog_assist", "auto_fill"),
    ),
    AgentType.COUNTERPARTY_RESEARCH.value: AgentCapability(
        agent_type=AgentType.COUNTERPARTY_RESEARCH.value,
        label="Counterparty Research",
        description="Enrich counterparty profiles from external text.",
        allowed_task_types=("counterparty_enrichment",),
    ),
    AgentType.COMMUNICATION.value: AgentCapability(
        agent_type=AgentType.COMMUNICATION.value,
        label="Communication",
        description="Draft RFQs and messages; send only after approval.",
        allowed_task_types=("rfq_draft", "clarification_draft"),
        can_send_external_messages=True,
    ),
    AgentType.LEGACY_TENDER_PROMOTION.value: AgentCapability(
        agent_type=AgentType.LEGACY_TENDER_PROMOTION.value,
        label="Legacy Tender Promotion",
        description="Combined feasibility + promotion (to be decomposed in Stage 2).",
        allowed_task_types=("feasibility_assessment",),
        can_create_binding_facts=False,
    ),
}


def get_agent_capability(agent_type: str) -> AgentCapability:
    capability = AGENT_REGISTRY.get(agent_type)
    if capability is None:
        raise ValueError(f"Unknown agent type: {agent_type}")
    return capability


def get_registered_agent(agent_type: str) -> BaseAgent:
    return _RegisteredAgent(get_agent_capability(agent_type))
