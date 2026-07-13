from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentCapability:
    agent_type: str
    label: str
    description: str
    allowed_task_types: tuple[str, ...] = field(default_factory=tuple)
    can_create_binding_facts: bool = False
    can_send_external_messages: bool = False


class BaseAgent(ABC):
    """Interface for specialized agents. Stage 1: metadata + task typing only."""

    capability: AgentCapability

    @abstractmethod
    def task_type_for_operation(self, operation: str) -> str:
        """Map a service operation name to an AgentTask.task_type value."""
