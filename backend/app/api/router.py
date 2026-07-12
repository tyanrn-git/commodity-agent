from fastapi import APIRouter

from app.api.routes import (
    ai_settings,
    auth,
    automation,
    company_settings,
    configurations,
    counterparties,
    deals_rfq,
    extraction,
    inbox,
    intelligence,
    internet_sources,
    monitoring,
    offers,
    opportunities,
    products,
    research,
    supplier_lead,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(ai_settings.router)
api_router.include_router(company_settings.router)
api_router.include_router(opportunities.router)
api_router.include_router(products.router)
api_router.include_router(extraction.router)
api_router.include_router(intelligence.router)
api_router.include_router(research.router)
api_router.include_router(counterparties.router)
api_router.include_router(deals_rfq.router)
api_router.include_router(configurations.router)
api_router.include_router(offers.router)
api_router.include_router(monitoring.router)
api_router.include_router(internet_sources.router)
api_router.include_router(supplier_lead.router)
api_router.include_router(automation.router)
api_router.include_router(inbox.router)
