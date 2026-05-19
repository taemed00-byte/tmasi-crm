import os
import logging
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app import models
from app.routers import (
    auth, whatsapp, patients, doctors, clinics, bookings,
    users, media, portal, cases, finance, reports,
    network, clients, documents, audit,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="TMASI CRM", version="2.0.0", docs_url="/api/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(auth.router)
app.include_router(whatsapp.router)
app.include_router(patients.router)
app.include_router(doctors.router)
app.include_router(clinics.router)
app.include_router(bookings.router)
app.include_router(users.router)
app.include_router(media.router)
app.include_router(portal.router)
app.include_router(cases.router)
app.include_router(finance.router)
app.include_router(reports.router)
app.include_router(network.router)
app.include_router(clients.router)
app.include_router(documents.router)
app.include_router(audit.router)


@app.get("/api/health")
def health():
    from app.config import DATABASE_URL
    db_type = "postgresql" if DATABASE_URL.startswith("postgresql") else "sqlite"
    return {
        "status": "ok",
        "service": "TMASI CRM",
        "version": "2.0.0",
        "environment": os.environ.get("RENDER", "local"),
        "database": db_type,
    }


@app.get("/api/crm/whatsapp-lines")
def crm_whatsapp_lines():
    from app.database import SessionLocal
    from app.models.whatsapp import WhatsAppLine
    db = SessionLocal()
    try:
        lines = db.query(WhatsAppLine).filter(WhatsAppLine.is_active == True).all()
        return [{"id": l.id, "label": l.label, "short_code": l.short_code,
                 "display_phone_number": l.display_phone_number} for l in lines]
    finally:
        db.close()


STATIC_DIR  = Path(__file__).parent / "static"
INDEX_HTML  = STATIC_DIR / "index.html"
PORTAL_HTML = STATIC_DIR / "portal.html"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/portal", response_class=HTMLResponse, include_in_schema=False)
@app.get("/portal/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
async def portal_page(request: Request, full_path: str = ""):
    if PORTAL_HTML.exists():
        return HTMLResponse(PORTAL_HTML.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Patient Portal</h1>")

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
async def spa(request: Request, full_path: str = ""):
    if full_path.startswith(("api/", "static/", "portal")):
        raise HTTPException(status_code=404)
    if INDEX_HTML.exists():
        return HTMLResponse(INDEX_HTML.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>TMASI CRM</h1>")

@app.on_event("startup")
async def on_startup():
    try:
        from app.startup import run_startup
        run_startup()
        logger.info("TMASI CRM v2 startup complete.")
    except Exception as exc:
        logger.error(f"Startup routine error (non-fatal): {exc}", exc_info=True)
    # Start background SLA checker
    import asyncio
    asyncio.create_task(_sla_background_loop())


async def _sla_background_loop():
    """Run SLA and inactivity checks every 10 minutes."""
    import asyncio
    from app.business_rules import check_sla_breaches, check_inactive_cases
    while True:
        try:
            check_sla_breaches()
            check_inactive_cases()
        except Exception as e:
            logger.error(f"Background rules error: {e}")
        await asyncio.sleep(600)  # every 10 minutes
