"""FastAPI application entry point for Excellon RPA System."""

import sys
from pathlib import Path

from fastapi import FastAPI
from loguru import logger

from config.settings import settings
from api.routes import router

# Configure loguru
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

logger.remove()
logger.add(
    sys.stderr,
    level=settings.log_level,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}",
)
logger.add(
    str(_LOG_DIR / "agent.log"),
    level=settings.log_level,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}",
    rotation="10 MB",
    retention="7 days",
)

# FastAPI app
app = FastAPI(
    title="Excellon RPA System",
    description="Multi-agent RPA system for automating Excellon Bajaj 5.0 desktop application.",
    version="1.0.0",
)

app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """Log startup message."""
    logger.info("Excellon RPA System started on {}:{}", settings.api_host, settings.api_port)


@app.on_event("shutdown")
async def shutdown_event():
    """Log shutdown message."""
    logger.info("Excellon RPA System shutting down.")
