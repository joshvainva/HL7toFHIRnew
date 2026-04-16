"""
HL7toFHIR message converter — FastAPI application entry point.
"""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ROOT_DIR / ".env", override=True)

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router
from app.db.session import engine, Base

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Database Tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")

    # Safe column migration: add new columns if they don't exist yet
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            for col, coldef in [
                ("message_type",      "VARCHAR(100)"),
                ("conversion_source", "VARCHAR(50)"),
            ]:
                result = conn.execute(text(
                    f"SELECT column_name FROM information_schema.columns "
                    f"WHERE table_name='fhir_resource' AND column_name='{col}'"
                ))
                if not result.fetchone():
                    conn.execute(text(
                        f"ALTER TABLE fhir_resource ADD COLUMN {col} {coldef}"
                    ))
                    logger.info(f"Added column fhir_resource.{col}")
            conn.commit()
    except Exception as e:
        logger.warning(f"Column migration skipped (may be expected on first run): {e}")
    yield

app = FastAPI(
    title="HL7toFHIR message converter",
    description=(
        "A web-based tool that automatically detects HL7 v2.x messages "
        "(ADT, ORU, ORM, and more) and converts them into FHIR R4 resources. "
        "Supports text input and file uploads (.hl7, .txt, .csv, .xlsx, .xls, .docx)."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS — permissive for local dev; tighten in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Static files & templates
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

static_dir = BASE_DIR / "static"
templates_dir = BASE_DIR / "app" / "templates"

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------
app.include_router(router, prefix="/api", tags=["converter"])


# ---------------------------------------------------------------------------
# UI route
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error", "details": str(exc)},
    )
