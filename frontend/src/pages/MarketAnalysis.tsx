import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { marketApi } from "../api/market";
import { indicatorsApi, type IndicatorData } from "../api/indicators";
import { regimeApi } from "../api/regime";
import { PriceChart } from "../components/PriceChart";
import type { OHLCVData, RegimeState, RegimeType } from "../types";

const DEFAULT_SYMBOL = "BTC/USDT";
const OVERLAY_INDICATORS = ["sma_21", "sma_50", "sma_200", "ema_21", "ema_50", "bb_upper", "bb_mid", "bb_lower"];
const PANE_INDICATORS = ["rsi_14", "macd", "macd_signal", "macd_hist", "volume_ratio"];

const REGIME_COLORS: Record<RegimeType, string> = {
  strong_trend_up: "bg-green-400/15 text-green-400",
  weak_trend_up: "bg-emerald-400/15 text-emerald-400",
  ranging: "bg-yellow-400/15 text-yellow-400",
  weak_trend_down: "bg-orange-400/15 text-orange-400",
  strong_trend_down: "bg-red-400/15 text-red-400",
  high_volatility: "bg-purple-400/15 text-purple-400",
  unknown: "bg-gray-400/15 text-gray-400",
};

function formatRegimeName(regime: RegimeType): string {
  return regime
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function MarketAnalysis() {
  const [symbol, setSymbol] = useState(DEFAULT_SYMBOL);
  const [timeframe, setTimeframe] = useState("1h");
  const [exchange, setExchange] = useState("sample");
  const [selectedIndicators, setSelectedIndicators] = useState<string[]>([]);

  useEffect(() => { document.title = "Market Analysis | Crypto Investor"; }, []);

  const { data: ohlcv, isLoading, isError, error } = useQuery<OHLCVData[]>({
    queryKey: ["ohlcv", symbol, timeframe],
    queryFn: () => marketApi.ohlcv(symbol, timeframe),
  });

  const { data: indicatorData } = useQuery<IndicatorData>({
    queryKey: ["indicators", exchange, symbol, timeframe, selectedIndicators],
    queryFn: () => indicatorsApi.get(exchange, symbol, timeframe, selectedIndicators, 500),
    enabled: selectedIndicators.length > 0,
  });

  const { data: regimeState } = useQuery<RegimeState>({
    queryKey: ["regime-current", symbol],
    queryFn: () => regimeApi.getCurrent(symbol),
    refetchInterval: 30000,
  });

  const toggleIndicator = (ind: string) => {
    setSelectedIndicators((prev) =>
      prev.includes(ind) ? prev.filter((i) => i !== ind) : [...prev, ind],
    );
  };

  return (
    <div>
      <h2 className="mb-6 text-2xl font-bold">Market Analysis</h2>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input
          type="text"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          placeholder="Symbol"
          className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm"
        />
        <select
          value={timeframe}
          onChange={(e) => setTimeframe(e.target.value)}
          className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm"
        >
          <option value="1m">1m</option>
          <option value="5m">5m</option>
          <option value="15m">15m</option>
          <option value="1h">1h</option>
          <option value="4h">4h</option>
          <option value="1d">1d</option>
        </select>
        <select
          value={exchange}
          onChange={(e) => setExchange(e.target.value)}
          className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm"
        >
          <option value="sample">Sample</option>
          <option value="binance">Binance</option>
        </select>
        {regimeState && (
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${REGIME_COLORS[regimeState.regime] ?? "bg-gray-400/15 text-gray-400"}`}
            title={`Confidence: ${(regimeState.confidence * 100).toFixed(1)}%`}
          >
            {formatRegimeName(regimeState.regime)}
          </span>
        )}
      </div>

      {/* Indicator selector */}
      <div className="mb-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <h3 className="mb-2 text-sm font-medium text-[var(--color-text-muted)]">Overlays</h3>
        <div className="mb-3 flex flex-wrap gap-1">
          {OVERLAY_INDICATORS.map((ind) => (
            <button
              key={ind}
              onClick={() => toggleIndicator(ind)}
              className={`rounded px-2 py-1 text-xs ${
                selectedIndicators.includes(ind)
                  ? "bg-[var(--color-primary)] text-white"
                  : "bg-[var(--color-bg)] text-[var(--color-text-muted)]"
              }`}
            >
              {ind}
            </button>
          ))}
        </div>
        <h3 className="mb-2 text-sm font-medium text-[var(--color-text-muted)]">Panes</h3>
        <div className="flex flex-wrap gap-1">
          {PANE_INDICATORS.map((ind) => (
            <button
              key={ind}
              onClick={() => toggleIndicator(ind)}
              className={`rounded px-2 py-1 text-xs ${
                selectedIndicators.includes(ind)
                  ? "bg-[var(--color-primary)] text-white"
                  : "bg-[var(--color-bg)] text-[var(--color-text-muted)]"
              }`}
            >
              {ind}
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        {isLoading && (
          <div className="flex h-64 items-center justify-center">
            <div className="h-full w-full animate-pulse rounded bg-[var(--color-border)]" />
          </div>
        )}
        {isError && (
          <div className="flex h-64 items-center justify-center">
            <div className="text-center">
              <p className="mb-2 text-sm text-red-400">{error instanceof Error ? error.message : "Failed to load market data"}</p>
              <p className="text-xs text-[var(--color-text-muted)]">Check your connection and try again</p>
            </div>
          </div>
        )}
        {ohlcv && (
          <PriceChart
            data={ohlcv}
            indicatorData={indicatorData?.data}
            overlayIndicators={selectedIndicators.filter((i) => OVERLAY_INDICATORS.includes(i))}
            paneIndicators={selectedIndicators.filter((i) => PANE_INDICATORS.includes(i))}
          />
        )}
      </div>
    </div>
  );
}
