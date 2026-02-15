"""
Market Regime Detector
======================
Classifies market conditions into regimes (trending, ranging, volatile)
using a weighted composite of ADX, Bollinger Band width, EMA slope,
trend alignment, and price structure indicators.

Used by the strategy router to select the optimal trading strategy
for current market conditions.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd

from common.indicators.technical import adx, bollinger_bands, ema, sma

logger = logging.getLogger("regime_detector")


class Regime(str, Enum):
    STRONG_TREND_UP = "strong_trend_up"
    WEAK_TREND_UP = "weak_trend_up"
    RANGING = "ranging"
    WEAK_TREND_DOWN = "weak_trend_down"
    STRONG_TREND_DOWN = "strong_trend_down"
    HIGH_VOLATILITY = "high_volatility"


@dataclass
class RegimeConfig:
    """Configurable thresholds for regime classification."""

    adx_strong: float = 40.0
    adx_weak: float = 25.0
    bb_high_vol_pct: float = 80.0
    ema_slope_period: int = 20
    ema_slope_lookback: int = 5
    alignment_ema_periods: list[int] = field(
        default_factory=lambda: [21, 50, 100, 200]
    )
    structure_lookback: int = 20
    strong_alignment_threshold: float = 0.5
    strong_structure_threshold: float = 0.3
    transition_lookback: int = 50
    bb_period: int = 20
    bb_std: float = 2.0
    adx_period: int = 14


@dataclass
class RegimeState:
    """Result of regime detection for a single point in time."""

    regime: Regime
    confidence: float  # 0-1
    adx_value: float
    bb_width_percentile: float
    ema_slope: float
    trend_alignment: float  # -1 to +1
    price_structure_score: float
    transition_probabilities: dict[str, float] = field(default_factory=dict)


class RegimeDetector:
    """Detects market regime from OHLCV data using composite sub-indicators."""

    def __init__(self, config: RegimeConfig | None = None) -> None:
        self.config = config or RegimeConfig()

    def detect(self, df: pd.DataFrame) -> RegimeState:
        """Detect the regime from the latest row of an OHLCV DataFrame."""
        indicators = self._compute_indicators(df)

        adx_val = float(indicators["adx_value"].iloc[-1])
        bb_pct = float(indicators["bb_width_percentile"].iloc[-1])
        slope = float(indicators["ema_slope"].iloc[-1])
        alignment = float(indicators["trend_alignment"].iloc[-1])
        structure = float(indicators["price_structure_score"].iloc[-1])

        regime, confidence = self._classify_regime(
            adx_val, bb_pct, slope, alignment, structure
        )

        # Compute transition probabilities from recent history
        regimes_series = indicators["regime"]
        transitions = self._compute_transition_probabilities(regimes_series)

        return RegimeState(
            regime=regime,
            confidence=confidence,
            adx_value=adx_val,
            bb_width_percentile=bb_pct,
            ema_slope=slope,
            trend_alignment=alignment,
            price_structure_score=structure,
            transition_probabilities=transitions,
        )

    def detect_series(self, df: pd.DataFrame) -> pd.DataFrame:
        """Classify regime for every row. Returns DataFrame with per-row regime."""
        indicators = self._compute_indicators(df)
        return indicators

    # ── Sub-indicator computation ──────────────────────────────

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute all sub-indicators and per-row regime classification."""
        result = df[[]].copy()
        cfg = self.config

        result["adx_value"] = self._compute_adx(df)
        result["bb_width_percentile"] = self._compute_bb_width_percentile(df)
        result["ema_slope"] = self._compute_ema_slope(df)
        result["trend_alignment"] = self._compute_trend_alignment(df)
        result["price_structure_score"] = self._compute_price_structure(df)

        # Per-row regime classification
        regimes = []
        confidences = []
        for i in range(len(result)):
            adx_val = result["adx_value"].iloc[i]
            bb_pct = result["bb_width_percentile"].iloc[i]
            slope = result["ema_slope"].iloc[i]
            alignment = result["trend_alignment"].iloc[i]
            structure = result["price_structure_score"].iloc[i]

            if pd.isna(adx_val) or pd.isna(bb_pct):
                regimes.append(Regime.RANGING)
                confidences.append(0.0)
            else:
                regime, conf = self._classify_regime(
                    float(adx_val),
                    float(bb_pct),
                    float(slope) if not pd.isna(slope) else 0.0,
                    float(alignment) if not pd.isna(alignment) else 0.0,
                    float(structure) if not pd.isna(structure) else 0.0,
                )
                regimes.append(regime)
                confidences.append(conf)

        result["regime"] = regimes
        result["confidence"] = confidences
        return result

    def _compute_adx(self, df: pd.DataFrame) -> pd.Series:
        """ADX trend strength (0-100)."""
        return adx(df, self.config.adx_period)

    def _compute_bb_width_percentile(self, df: pd.DataFrame) -> pd.Series:
        """Bollinger Band width as rolling percentile (0-100)."""
        bb = bollinger_bands(
            df["close"], self.config.bb_period, self.config.bb_std
        )
        bb_width = bb["bb_width"]
        # Rolling percentile rank over the last 100 periods
        window = min(100, len(df))
        min_p = min(20, window)
        pct_rank = bb_width.rolling(window=window, min_periods=min_p).apply(
            lambda x: (x.values[-1:] <= x.values).sum() / len(x) * 100,
            raw=False,
        )
        return pct_rank

    def _compute_ema_slope(self, df: pd.DataFrame) -> pd.Series:
        """EMA slope (rate of change) normalized by price."""
        cfg = self.config
        ema_val = ema(df["close"], cfg.ema_slope_period)
        slope = (ema_val - ema_val.shift(cfg.ema_slope_lookback)) / (
            ema_val.shift(cfg.ema_slope_lookback).replace(0, np.nan)
        )
        return slope

    def _compute_trend_alignment(self, df: pd.DataFrame) -> pd.Series:
        """
        EMA alignment score from -1 (bearish) to +1 (bullish).

        Checks whether shorter EMAs are above longer EMAs.
        """
        cfg = self.config
        periods = sorted(cfg.alignment_ema_periods)
        emas = {p: ema(df["close"], p) for p in periods}

        # Count aligned pairs: shorter above longer = +1, below = -1
        n_pairs = 0
        alignment = pd.Series(0.0, index=df.index)
        for i in range(len(periods)):
            for j in range(i + 1, len(periods)):
                fast_p, slow_p = periods[i], periods[j]
                diff = emas[fast_p] - emas[slow_p]
                alignment = alignment + np.sign(diff)
                n_pairs += 1

        if n_pairs > 0:
            alignment = alignment / n_pairs

        return alignment

    def _compute_price_structure(self, df: pd.DataFrame) -> pd.Series:
        """
        Price structure score from -1 (lower lows/lower highs) to +1 (higher highs/higher lows).

        Measures recent higher-high/higher-low structure.
        """
        lookback = self.config.structure_lookback
        close = df["close"]

        # Rolling comparison: is current close above/below lookback midpoint?
        rolling_high = close.rolling(window=lookback, min_periods=1).max()
        rolling_low = close.rolling(window=lookback, min_periods=1).min()
        midpoint = (rolling_high + rolling_low) / 2

        # Normalize position within range to [-1, +1]
        range_size = (rolling_high - rolling_low).replace(0, np.nan)
        score = 2 * (close - midpoint) / range_size
        return score.clip(-1, 1).fillna(0)

    # ── Classification ─────────────────────────────────────────

    def _classify_regime(
        self,
        adx_val: float,
        bb_pct: float,
        slope: float,
        alignment: float,
        structure: float,
    ) -> tuple[Regime, float]:
        """
        Classify regime using weighted scoring of sub-indicators.

        Returns (regime, confidence) where confidence is 0-1.
        """
        cfg = self.config

        # HIGH_VOLATILITY: high BB width + low trend strength
        if bb_pct > cfg.bb_high_vol_pct and adx_val < cfg.adx_weak:
            confidence = min(1.0, (bb_pct - cfg.bb_high_vol_pct) / 20 * 0.5 + 0.5)
            return Regime.HIGH_VOLATILITY, confidence

        # STRONG_TREND_UP
        if (
            adx_val > cfg.adx_strong
            and alignment > cfg.strong_alignment_threshold
            and slope > 0
            and structure > cfg.strong_structure_threshold
        ):
            confidence = min(
                1.0,
                (adx_val - cfg.adx_strong) / 20 * 0.3
                + alignment * 0.3
                + min(structure, 1.0) * 0.2
                + 0.2,
            )
            return Regime.STRONG_TREND_UP, confidence

        # STRONG_TREND_DOWN
        if (
            adx_val > cfg.adx_strong
            and alignment < -cfg.strong_alignment_threshold
            and slope < 0
            and structure < -cfg.strong_structure_threshold
        ):
            confidence = min(
                1.0,
                (adx_val - cfg.adx_strong) / 20 * 0.3
                + abs(alignment) * 0.3
                + min(abs(structure), 1.0) * 0.2
                + 0.2,
            )
            return Regime.STRONG_TREND_DOWN, confidence

        # WEAK_TREND_UP
        if cfg.adx_weak <= adx_val <= cfg.adx_strong and alignment > 0 and slope > 0:
            strength = (adx_val - cfg.adx_weak) / (cfg.adx_strong - cfg.adx_weak)
            confidence = 0.3 + strength * 0.4 + alignment * 0.15 + max(0, structure) * 0.15
            return Regime.WEAK_TREND_UP, min(1.0, confidence)

        # WEAK_TREND_DOWN
        if cfg.adx_weak <= adx_val <= cfg.adx_strong and alignment < 0 and slope < 0:
            strength = (adx_val - cfg.adx_weak) / (cfg.adx_strong - cfg.adx_weak)
            confidence = 0.3 + strength * 0.4 + abs(alignment) * 0.15 + min(0, -structure) * 0.15
            return Regime.WEAK_TREND_DOWN, min(1.0, confidence)

        # RANGING (default)
        confidence = max(0.3, 1.0 - adx_val / cfg.adx_strong)
        return Regime.RANGING, min(1.0, confidence)

    # ── Transition probabilities ───────────────────────────────

    def _compute_transition_probabilities(
        self, regimes: pd.Series
    ) -> dict[str, float]:
        """
        Compute empirical transition probabilities from recent regime history.

        Returns dict mapping target regime -> probability.
        """
        lookback = self.config.transition_lookback
        recent = regimes.iloc[-lookback:] if len(regimes) >= lookback else regimes

        if len(recent) < 2:
            return {}

        current = recent.iloc[-1]
        transitions: dict[str, int] = {}
        total = 0

        for i in range(len(recent) - 1):
            if recent.iloc[i] == current:
                next_regime = recent.iloc[i + 1]
                key = next_regime.value if isinstance(next_regime, Regime) else str(next_regime)
                transitions[key] = transitions.get(key, 0) + 1
                total += 1

        if total == 0:
            return {}

        return {k: round(v / total, 3) for k, v in transitions.items()}
