from __future__ import annotations

import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Generator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.registry import get_agent_capability
from app.config import settings
from app.domain.enums import AgentRunStatus, AgentTaskStatus
from app.domain.models import AgentResult, AgentRun, AgentTask, User
from app.services.ai_budget import log_ai_usage


PROMPT_VERSION = "2026-07-13"
TOOLSET_VERSION = "stage-1"


@dataclass
class AgentExecutionContext:
    agent_type: str
    task_type: str
    opportunity_id: uuid.UUID | None = None
    deal_id: uuid.UUID | None = None
    research_campaign_id: uuid.UUID | None = None
    internet_source_search_run_id: uuid.UUID | None = None
    internet_source_search_hit_id: uuid.UUID | None = None
    input_payload: dict[str, Any] = field(default_factory=dict)
    prompt_version: str = PROMPT_VERSION
    toolset_version: str = TOOLSET_VERSION


class AgentRunHandle:
    def __init__(self, db: Session, *, user: User, task: AgentTask, run: AgentRun) -> None:
        self._db = db
        self._user = user
        self.task = task
        self.run = run

    @property
    def id(self) -> uuid.UUID:
        return self.run.id

    def attach_ai_usage(
        self,
        *,
        model: str,
        operation: str,
        cost_usd: Decimal,
        input_tokens: int,
        output_tokens: int,
        opportunity_id: uuid.UUID | None = None,
        deal_id: uuid.UUID | None = None,
        source_id: uuid.UUID | None = None,
        research_campaign_id: uuid.UUID | None = None,
    ) -> None:
        usage = log_ai_usage(
            self._db,
            user=self._user,
            model=model,
            operation=operation,
            cost_usd=cost_usd,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            opportunity_id=opportunity_id or self.task.opportunity_id,
            deal_id=deal_id or self.task.deal_id,
            source_id=source_id,
            research_campaign_id=research_campaign_id or self.task.research_campaign_id,
            agent_run_id=self.run.id,
        )
        self.run.model = model
        self.run.input_tokens = input_tokens
        self.run.output_tokens = output_tokens
        self.run.estimated_cost = float(cost_usd)
        self.run.actual_cost = float(cost_usd)
        self.run.ai_usage_log_id = usage.id
        self._db.flush()

    def record_result(
        self,
        *,
        result_type: str,
        structured_payload: dict[str, Any],
        summary: str | None = None,
        confidence: float | None = None,
        requires_review: bool = False,
        applied: bool = True,
    ) -> AgentResult:
        result = AgentResult(
            agent_run_id=self.run.id,
            result_type=result_type,
            structured_payload=structured_payload,
            summary=summary,
            confidence=confidence,
            requires_review=requires_review,
            applied_at=datetime.now(timezone.utc) if applied else None,
            applied_by_id=self._user.id if applied else None,
        )
        self._db.add(result)
        self._db.flush()
        return result

    def succeed(self) -> None:
        now = datetime.now(timezone.utc)
        self.run.status = AgentRunStatus.SUCCESS.value
        self.run.completed_at = now
        self.task.status = AgentTaskStatus.COMPLETED.value
        self.task.completed_at = now
        self._db.flush()

    def fail(self, error: str) -> None:
        now = datetime.now(timezone.utc)
        self.run.status = AgentRunStatus.FAILED.value
        self.run.completed_at = now
        self.run.error = error[:4000]
        self.task.status = AgentTaskStatus.FAILED.value
        self.task.completed_at = now
        self.task.blocked_reason = error[:4000]
        self._db.flush()


def _provider_name() -> str:
    if settings.ai_provider == "mock" or not settings.openai_api_key:
        return "mock"
    return "openai"


def create_agent_task(
    db: Session,
    *,
    user: User,
    context: AgentExecutionContext,
    status: str = AgentTaskStatus.RUNNING.value,
) -> AgentTask:
    get_agent_capability(context.agent_type)
    now = datetime.now(timezone.utc)
    task = AgentTask(
        opportunity_id=context.opportunity_id,
        deal_id=context.deal_id,
        research_campaign_id=context.research_campaign_id,
        internet_source_search_run_id=context.internet_source_search_run_id,
        internet_source_search_hit_id=context.internet_source_search_hit_id,
        agent_type=context.agent_type,
        task_type=context.task_type,
        input_payload=context.input_payload,
        status=status,
        created_by_id=user.id,
        started_at=now if status == AgentTaskStatus.RUNNING.value else None,
    )
    db.add(task)
    db.flush()
    return task


def begin_agent_run(
    db: Session,
    *,
    user: User,
    context: AgentExecutionContext,
) -> AgentRunHandle:
    task = create_agent_task(db, user=user, context=context)
    run = AgentRun(
        agent_task_id=task.id,
        provider=_provider_name(),
        prompt_version=context.prompt_version,
        toolset_version=context.toolset_version,
        started_at=datetime.now(timezone.utc),
        status=AgentRunStatus.RUNNING.value,
    )
    db.add(run)
    db.flush()
    return AgentRunHandle(db, user=user, task=task, run=run)


@contextmanager
def tracked_agent_run(
    db: Session,
    *,
    user: User,
    context: AgentExecutionContext,
) -> Generator[AgentRunHandle, None, None]:
    handle = begin_agent_run(db, user=user, context=context)
    try:
        yield handle
        if handle.run.status == AgentRunStatus.RUNNING.value:
            handle.succeed()
    except Exception as exc:
        if handle.run.status == AgentRunStatus.RUNNING.value:
            handle.fail(str(exc))
        raise


def list_agent_activity(
    db: Session,
    *,
    user: User,
    opportunity_id: uuid.UUID | None = None,
    deal_id: uuid.UUID | None = None,
    agent_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    query = (
        select(AgentTask)
        .where(AgentTask.created_by_id == user.id)
        .order_by(AgentTask.created_at.desc())
        .limit(limit)
    )
    if opportunity_id is not None:
        query = query.where(AgentTask.opportunity_id == opportunity_id)
    if deal_id is not None:
        query = query.where(AgentTask.deal_id == deal_id)
    if agent_type is not None:
        query = query.where(AgentTask.agent_type == agent_type)

    tasks = list(db.scalars(query))
    activity: list[dict[str, Any]] = []
    for task in tasks:
        runs = list(db.scalars(select(AgentRun).where(AgentRun.agent_task_id == task.id)))
        results: list[AgentResult] = []
        for run in runs:
            results.extend(
                list(db.scalars(select(AgentResult).where(AgentResult.agent_run_id == run.id)))
            )
        activity.append({"task": task, "runs": runs, "results": results})
    return activity
