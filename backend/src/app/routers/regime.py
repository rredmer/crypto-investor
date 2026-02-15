from fastapi import APIRouter, Query

from app.deps import RegimeServiceDep
from app.schemas.regime import (
    RegimeHistoryEntry,
    RegimePositionSizeRequest,
    RegimePositionSizeResponse,
    RegimeStateResponse,
    RoutingDecisionResponse,
)

router = APIRouter(prefix="/regime", tags=["regime"])


@router.get("/current", response_model=list[RegimeStateResponse])
async def get_all_regimes(service: RegimeServiceDep) -> list:
    """Get current regime states for all tracked symbols."""
    return service.get_all_current_regimes()


@router.get("/current/{symbol:path}", response_model=RegimeStateResponse)
async def get_regime(symbol: str, service: RegimeServiceDep) -> dict:
    """Get current regime state for a single symbol."""
    result = service.get_current_regime(symbol)
    if result is None:
        return {
            "symbol": symbol,
            "regime": "unknown",
            "confidence": 0.0,
            "adx_value": 0.0,
            "bb_width_percentile": 0.0,
            "ema_slope": 0.0,
            "trend_alignment": 0.0,
            "price_structure_score": 0.0,
        }
    return result


@router.get("/history/{symbol:path}", response_model=list[RegimeHistoryEntry])
async def get_regime_history(
    symbol: str,
    service: RegimeServiceDep,
    limit: int = Query(100, ge=1, le=1000),
) -> list:
    """Get regime history with transitions for a symbol."""
    return service.get_regime_history(symbol, limit)


@router.get("/recommendation/{symbol:path}", response_model=RoutingDecisionResponse)
async def get_recommendation(symbol: str, service: RegimeServiceDep) -> dict:
    """Get strategy recommendation for a symbol based on its current regime."""
    result = service.get_recommendation(symbol)
    if result is None:
        return {
            "symbol": symbol,
            "regime": "unknown",
            "confidence": 0.0,
            "primary_strategy": "none",
            "weights": [],
            "position_size_modifier": 0.0,
            "reasoning": "No data available",
        }
    return result


@router.get("/recommendations", response_model=list[RoutingDecisionResponse])
async def get_all_recommendations(service: RegimeServiceDep) -> list:
    """Get strategy recommendations for all tracked symbols."""
    return service.get_all_recommendations()


@router.post("/position-size", response_model=RegimePositionSizeResponse)
async def get_position_size(
    request: RegimePositionSizeRequest, service: RegimeServiceDep
) -> dict:
    """Calculate position size with regime-adjusted modifier."""
    from common.risk.risk_manager import RiskManager

    risk_manager = RiskManager()
    result = service.get_position_size(
        symbol=request.symbol,
        entry_price=request.entry_price,
        stop_loss_price=request.stop_loss_price,
        risk_manager=risk_manager,
    )
    if result is None:
        return {
            "symbol": request.symbol,
            "regime": "unknown",
            "regime_modifier": 0.0,
            "position_size": 0.0,
            "entry_price": request.entry_price,
            "stop_loss_price": request.stop_loss_price,
            "primary_strategy": "none",
        }
    return result
