from fastapi import APIRouter, Query

from app.deps import PaperTradingServiceDep
from app.schemas.paper_trading import (
    PaperTradingActionResponse,
    PaperTradingStartRequest,
    PaperTradingStatusResponse,
)

router = APIRouter(prefix="/paper-trading", tags=["paper-trading"])


@router.get("/status", response_model=PaperTradingStatusResponse)
async def get_status(service: PaperTradingServiceDep) -> dict:
    """Get current paper trading status (running, strategy, uptime)."""
    return service.get_status()


@router.post("/start", response_model=PaperTradingActionResponse)
async def start_paper_trading(
    request: PaperTradingStartRequest,
    service: PaperTradingServiceDep,
) -> dict:
    """Start Freqtrade in dry-run (paper trading) mode."""
    return service.start(strategy=request.strategy)


@router.post("/stop", response_model=PaperTradingActionResponse)
async def stop_paper_trading(service: PaperTradingServiceDep) -> dict:
    """Gracefully stop the paper trading process."""
    return service.stop()


@router.get("/trades")
async def get_open_trades(service: PaperTradingServiceDep) -> list:
    """Get currently open trades from Freqtrade."""
    return await service.get_open_trades()


@router.get("/history")
async def get_trade_history(
    service: PaperTradingServiceDep,
    limit: int = Query(50, ge=1, le=500),
) -> list:
    """Get closed trade history from Freqtrade."""
    return await service.get_trade_history(limit)


@router.get("/profit")
async def get_profit(service: PaperTradingServiceDep) -> dict:
    """Get profit summary from Freqtrade."""
    return await service.get_profit()


@router.get("/performance")
async def get_performance(service: PaperTradingServiceDep) -> list:
    """Get per-pair performance from Freqtrade."""
    return await service.get_performance()


@router.get("/balance")
async def get_balance(service: PaperTradingServiceDep) -> dict:
    """Get wallet balance from Freqtrade."""
    return await service.get_balance()


@router.get("/log")
async def get_log(
    service: PaperTradingServiceDep,
    limit: int = Query(100, ge=1, le=1000),
) -> list:
    """Get recent paper trading event log entries."""
    return service.get_log_entries(limit)
