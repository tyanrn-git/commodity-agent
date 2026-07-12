from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.db.session import SessionLocal
from app.security.auth import ensure_admin_user
from app.services.ai_budget import ensure_ai_budget_settings
from app.services.counterparty import ensure_company_settings, seed_demo_counterparties
from app.services.email_loop import ensure_mailbox_connection
from app.services.internet_source_catalog import seed_internet_sources, sync_system_internet_sources
from app.services.monitoring import seed_demo_monitoring_rule
from app.services.opportunity import seed_products
from app.services.research import seed_product_specifications
from app.services.rfq import seed_rfq_templates


@asynccontextmanager
async def lifespan(_: FastAPI):
    db = SessionLocal()
    try:
        admin = ensure_admin_user(db)
        ensure_ai_budget_settings(db, admin)
        seed_products(db)
        seed_product_specifications(db)
        seed_rfq_templates(db)
        ensure_company_settings(db, admin)
        seed_demo_counterparties(db, admin)
        ensure_mailbox_connection(db, admin)
        seed_demo_monitoring_rule(db, admin)
        seed_internet_sources(db)
        sync_system_internet_sources(db)
    finally:
        db.close()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
