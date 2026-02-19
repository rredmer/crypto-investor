"""
ML Feature Engineering
======================
Transforms OHLCV DataFrames into feature matrices for ML models.
Uses shared indicators from common.indicators.technical.
"""

import logging

import numpy as np
import pandas as pd

from common.indicators.technical import (
    adx,
    atr_indicator,
    bollinger_bands,
    cci,
    ema,
    macd,
    mfi,
    obv,
    rsi,
    sma,
    stochastic,
    williams_r,
)

logger = logging.getLogger(__name__)

# Default feature config — can be overridden via platform_config.yaml
DEFAULT_FEATURE_CONFIG = {
    "lag_periods": [1, 2, 3, 5],
    "return_periods": [1, 3, 5, 10],
    "target_horizon": 1,  # bars ahead for binary target
    "drop_na": True,
}


def compute_indicator_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute indicator-based features from an OHLCV DataFrame.

    Args:
        df: DataFrame with columns [open, high, low, close, volume].

    Returns:
        DataFrame with indicator columns added (NaN rows from warmup preserved).
    """
    feat = pd.DataFrame(index=df.index)

    # --- Trend ---
    for p in [7, 14, 21, 50]:
        feat[f"sma_{p}"] = sma(df["close"], p)
        feat[f"ema_{p}"] = ema(df["close"], p)

    # Price relative to moving averages (normalized)
    for p in [21, 50]:
        feat[f"close_over_sma_{p}"] = df["close"] / feat[f"sma_{p}"] - 1
        feat[f"close_over_ema_{p}"] = df["close"] / feat[f"ema_{p}"] - 1

    # EMA crossover signals
    feat["ema_7_over_21"] = feat["ema_7"] / feat["ema_21"] - 1
    feat["ema_21_over_50"] = feat["ema_21"] / feat["ema_50"] - 1

    # --- Momentum ---
    feat["rsi_14"] = rsi(df["close"], 14)
    macd_df = macd(df["close"])
    feat["macd"] = macd_df["macd"]
    feat["macd_signal"] = macd_df["macd_signal"]
    feat["macd_hist"] = macd_df["macd_hist"]
    stoch_df = stochastic(df)
    feat["stoch_k"] = stoch_df["stoch_k"]
    feat["stoch_d"] = stoch_df["stoch_d"]
    feat["cci_20"] = cci(df)
    feat["williams_r_14"] = williams_r(df)
    feat["adx_14"] = adx(df, 14)

    # --- Volatility ---
    feat["atr_14"] = atr_indicator(df, 14)
    feat["atr_pct"] = feat["atr_14"] / df["close"]  # Normalized ATR
    bb_df = bollinger_bands(df["close"])
    feat["bb_width"] = bb_df["bb_width"]
    feat["bb_pct"] = bb_df["bb_pct"]

    # --- Volume ---
    feat["obv"] = obv(df)
    feat["mfi_14"] = mfi(df)
    feat["volume_sma_20"] = sma(df["volume"], 20)
    feat["volume_ratio"] = df["volume"] / feat["volume_sma_20"]

    return feat


def add_lag_features(feat: pd.DataFrame, lag_periods: list[int] | None = None) -> pd.DataFrame:
    """Add lagged values for key indicators.

    Args:
        feat: DataFrame of indicator features.
        lag_periods: List of lag periods (default: [1, 2, 3, 5]).

    Returns:
        DataFrame with lag columns appended.
    """
    if lag_periods is None:
        lag_periods = DEFAULT_FEATURE_CONFIG["lag_periods"]

    lag_cols = ["rsi_14", "macd_hist", "bb_pct", "volume_ratio", "adx_14"]
    existing = [c for c in lag_cols if c in feat.columns]

    result = feat.copy()
    for col in existing:
        for lag in lag_periods:
            result[f"{col}_lag{lag}"] = feat[col].shift(lag)

    return result


def add_return_features(df: pd.DataFrame, periods: list[int] | None = None) -> pd.DataFrame:
    """Compute multi-horizon returns as features.

    Args:
        df: Original OHLCV DataFrame.
        periods: Return lookback periods (default: [1, 3, 5, 10]).

    Returns:
        DataFrame with return columns.
    """
    if periods is None:
        periods = DEFAULT_FEATURE_CONFIG["return_periods"]

    result = pd.DataFrame(index=df.index)
    for p in periods:
        result[f"return_{p}"] = df["close"].pct_change(p)
        result[f"log_return_{p}"] = np.log(df["close"] / df["close"].shift(p))

    # High-low range as fraction of close
    result["hl_range_pct"] = (df["high"] - df["low"]) / df["close"]

    return result


def compute_target(df: pd.DataFrame, horizon: int = 1) -> pd.Series:
    """Binary classification target: 1 if close goes up in `horizon` bars, 0 otherwise.

    Args:
        df: OHLCV DataFrame.
        horizon: Number of bars ahead for target.

    Returns:
        Series of 0/1 values. Last `horizon` rows will be NaN.
    """
    future_return = df["close"].shift(-horizon) / df["close"] - 1
    return (future_return > 0).astype(float).where(future_return.notna())


def build_feature_matrix(
    df: pd.DataFrame,
    config: dict | None = None,
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """Full pipeline: OHLCV → feature matrix + target.

    Args:
        df: OHLCV DataFrame with columns [open, high, low, close, volume].
        config: Optional override for DEFAULT_FEATURE_CONFIG.

    Returns:
        Tuple of (X features, y target, feature_names).
        Rows with any NaN are dropped.
    """
    cfg = {**DEFAULT_FEATURE_CONFIG, **(config or {})}

    # Compute all features
    indicators = compute_indicator_features(df)
    returns = add_return_features(df, cfg["return_periods"])
    features = pd.concat([indicators, returns], axis=1)
    features = add_lag_features(features, cfg["lag_periods"])

    # Target
    target = compute_target(df, cfg["target_horizon"])

    # Combine and drop NaN
    combined = features.copy()
    combined["__target__"] = target

    if cfg["drop_na"]:
        combined = combined.dropna()

    y = combined.pop("__target__")
    x_feat = combined
    feature_names = list(x_feat.columns)

    logger.info("Feature matrix: %d rows x %d features", len(x_feat), len(feature_names))
    return x_feat, y, feature_names
