import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.domain.enums import AuditAction
from app.domain.models import AuditLog, User


def log_audit(
    db: Session,
    *,
    actor: User | None,
    action: AuditAction | str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
) -> AuditLog:
    action_value = action.value if isinstance(action, AuditAction) else str(action)
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        action=action_value,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(entry)
    db.flush()
    return entry
