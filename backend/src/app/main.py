from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine
from app.models import Base
from app.routers import (
    backtest,
    data_pipeline,
    exchanges,
    indicators,
    jobs,
    market,
    paper_trading,
    platform,
    portfolio,
    regime,
    risk,
    screening,
    trading,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Ensure data directory exists
    db_path = settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create tables (use alembic for migrations in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Enable WAL mode for SQLite
    async with engine.begin() as conn:
        await conn.execute(  # type: ignore[arg-type]
            __import__("sqlalchemy").text("PRAGMA journal_mode=WAL")
        )

    yield

    # Cleanup: stop paper trading if running
    from app.deps import _paper_trading_service

    if _paper_trading_service is not None and _paper_trading_service.is_running:
        _paper_trading_service.stop()

    await engine.dispose()


app = FastAPI(
    title="crypto-investor",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for dev (Vite at :5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(exchanges.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(trading.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(data_pipeline.router, prefix="/api")
app.include_router(screening.router, prefix="/api")
app.include_router(risk.router, prefix="/api")
app.include_router(backtest.router, prefix="/api")
app.include_router(indicators.router, prefix="/api")
app.include_router(paper_trading.router, prefix="/api")
app.include_router(regime.router, prefix="/api")
app.include_router(platform.router, prefix="/api")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Serve frontend static files in production (must be last — catch-all mount)
frontend_dist = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
