from pydantic import BaseModel


class RegimeStateResponse(BaseModel):
    symbol: str
    regime: str
    confidence: float
    adx_value: float
    bb_width_percentile: float
    ema_slope: float
    trend_alignment: float
    price_structure_score: float
    transition_probabilities: dict[str, float] = {}


class StrategyWeightResponse(BaseModel):
    strategy_name: str
    weight: float
    position_size_factor: float


class RoutingDecisionResponse(BaseModel):
    symbol: str
    regime: str
    confidence: float
    primary_strategy: str
    weights: list[StrategyWeightResponse]
    position_size_modifier: float
    reasoning: str


class RegimeHistoryEntry(BaseModel):
    timestamp: str
    regime: str
    confidence: float
    adx_value: float
    bb_width_percentile: float


class RegimePositionSizeRequest(BaseModel):
    symbol: str
    entry_price: float
    stop_loss_price: float


class RegimePositionSizeResponse(BaseModel):
    symbol: str
    regime: str
    regime_modifier: float
    position_size: float
    entry_price: float
    stop_loss_price: float
    primary_strategy: str
