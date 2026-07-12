import os
from collections.abc import Generator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.session import get_db
from app.domain.models import Base
import app.domain.models  # noqa: F401 — register all tables for metadata.create_all
from app.main import app
from app.security.auth import ensure_admin_user
from app.services.ai_budget import ensure_ai_budget_settings
from app.services.counterparty import ensure_company_settings
from app.services.opportunity import seed_products
from app.services.research import seed_product_specifications
from app.services.rfq import seed_rfq_templates
from app.services.internet_source_catalog import seed_internet_sources, sync_system_internet_sources
from app.services.monitoring import seed_demo_monitoring_rule
from app.services.automation import ensure_automation_settings

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://commodity:commodity@localhost:5432/commodity_agent_test",
)

engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session")
def setup_database() -> Generator[None, None, None]:
    try:
        with engine.connect() as conn:
            conn.close()
    except Exception:
        pytest.skip("PostgreSQL is not available for integration tests")
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        admin = ensure_admin_user(db)
        ensure_ai_budget_settings(db, admin)
        seed_products(db)
        seed_product_specifications(db)
        seed_rfq_templates(db)
        ensure_company_settings(db, admin)
        seed_demo_monitoring_rule(db, admin)
        seed_internet_sources(db)
        sync_system_internet_sources(db)
        ensure_automation_settings(db, admin)
    finally:
        db.close()
    yield
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    @asynccontextmanager
    async def _noop_lifespan(_: FastAPI):
        yield

    app.dependency_overrides[get_db] = override_get_db
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan
    storage_path = Path(settings.storage_path) / "tests"
    storage_path.mkdir(parents=True, exist_ok=True)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.router.lifespan_context = original_lifespan
        app.dependency_overrides.clear()


@pytest.fixture()
def auth_client(client: TestClient) -> TestClient:
    response = client.post(
        "/auth/login",
        json={"email": settings.admin_email, "password": settings.admin_password},
    )
    assert response.status_code == 200
    return client
