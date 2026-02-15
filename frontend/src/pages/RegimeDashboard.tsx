import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { regimeApi } from "../api/regime";
import type {
  RegimeState,
  RegimeType,
  RoutingDecision,
  RegimeHistoryEntry,
} from "../types";

const SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"];

const REGIME_COLORS: Record<RegimeType, string> = {
  strong_trend_up: "text-green-400",
  weak_trend_up: "text-emerald-400",
  ranging: "text-yellow-400",
  weak_trend_down: "text-orange-400",
  strong_trend_down: "text-red-400",
  high_volatility: "text-purple-400",
  unknown: "text-gray-400",
};

const REGIME_BG: Record<RegimeType, string> = {
  strong_trend_up: "bg-green-400/15",
  weak_trend_up: "bg-emerald-400/15",
  ranging: "bg-yellow-400/15",
  weak_trend_down: "bg-orange-400/15",
  strong_trend_down: "bg-red-400/15",
  high_volatility: "bg-purple-400/15",
  unknown: "bg-gray-400/15",
};

function formatRegime(regime: RegimeType): string {
  return regime
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function RegimeDashboard() {
  const [selectedSymbol, setSelectedSymbol] = useState(SYMBOLS[0]);

  const { data: regimeState } = useQuery<RegimeState>({
    queryKey: ["regime-current", selectedSymbol],
    queryFn: () => regimeApi.getCurrent(selectedSymbol),
    refetchInterval: 30000,
  });

  const { data: recommendation } = useQuery<RoutingDecision>({
    queryKey: ["regime-recommendation", selectedSymbol],
    queryFn: () => regimeApi.getRecommendation(selectedSymbol),
    refetchInterval: 30000,
  });

  const { data: history } = useQuery<RegimeHistoryEntry[]>({
    queryKey: ["regime-history", selectedSymbol],
    queryFn: () => regimeApi.getHistory(selectedSymbol, 50),
    refetchInterval: 30000,
  });

  const regime = regimeState?.regime ?? "unknown";
  const regimeColor = REGIME_COLORS[regime];

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-bold">Regime Dashboard</h2>
        <select
          value={selectedSymbol}
          onChange={(e) => setSelectedSymbol(e.target.value)}
          className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm"
        >
          {SYMBOLS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {/* Status Cards */}
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatusCard
          label="Current Regime"
          value={formatRegime(regime)}
          className={regimeColor}
        />
        <StatusCard
          label="Confidence"
          value={`${((regimeState?.confidence ?? 0) * 100).toFixed(1)}%`}
          className={
            (regimeState?.confidence ?? 0) > 0.7
              ? "text-green-400"
              : (regimeState?.confidence ?? 0) > 0.4
                ? "text-yellow-400"
                : "text-red-400"
          }
        />
        <StatusCard
          label="Primary Strategy"
          value={recommendation?.primary_strategy ?? "—"}
        />
        <StatusCard
          label="Position Modifier"
          value={`${((recommendation?.position_size_modifier ?? 0) * 100).toFixed(0)}%`}
          className={
            (recommendation?.position_size_modifier ?? 0) >= 0.8
              ? "text-green-400"
              : (recommendation?.position_size_modifier ?? 0) >= 0.5
                ? "text-yellow-400"
                : "text-red-400"
          }
        />
      </div>

      {/* Two-column grid */}
      <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left: Sub-Indicator Gauges */}
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
          <h3 className="mb-4 text-lg font-semibold">Sub-Indicators</h3>
          <div className="space-y-4">
            <Gauge
              label="ADX"
              value={regimeState?.adx_value ?? 0}
              max={100}
              thresholds={[25, 40]}
              format={(v) => v.toFixed(1)}
            />
            <Gauge
              label="BB Width Pct"
              value={regimeState?.bb_width_percentile ?? 0}
              max={100}
              thresholds={[50, 80]}
              format={(v) => v.toFixed(1)}
            />
            <Gauge
              label="EMA Slope"
              value={regimeState?.ema_slope ?? 0}
              max={0.05}
              min={-0.05}
              bipolar
              format={(v) => v.toFixed(5)}
            />
            <Gauge
              label="Trend Alignment"
              value={regimeState?.trend_alignment ?? 0}
              max={1}
              min={-1}
              bipolar
              format={(v) => v.toFixed(3)}
            />
            <Gauge
              label="Price Structure"
              value={regimeState?.price_structure_score ?? 0}
              max={1}
              min={-1}
              bipolar
              format={(v) => v.toFixed(3)}
            />
          </div>
        </div>

        {/* Right: Strategy Recommendation */}
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
          <h3 className="mb-4 text-lg font-semibold">Strategy Recommendation</h3>
          {recommendation ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-[var(--color-text-muted)]">
                  Primary
                </span>
                <span className="font-mono font-medium">
                  {recommendation.primary_strategy}
                </span>
              </div>

              {/* Weights table */}
              <div>
                <p className="mb-2 text-xs text-[var(--color-text-muted)]">
                  Strategy Weights
                </p>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--color-border)] text-left text-xs text-[var(--color-text-muted)]">
                      <th className="pb-2">Strategy</th>
                      <th className="pb-2">Weight</th>
                      <th className="pb-2">Size Factor</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recommendation.weights.map((w) => (
                      <tr
                        key={w.strategy_name}
                        className="border-b border-[var(--color-border)]/30"
                      >
                        <td className="py-1.5 font-mono text-xs">
                          {w.strategy_name}
                        </td>
                        <td className="py-1.5 font-mono">
                          {(w.weight * 100).toFixed(0)}%
                        </td>
                        <td className="py-1.5 font-mono">
                          {w.position_size_factor.toFixed(1)}x
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div>
                <p className="mb-1 text-xs text-[var(--color-text-muted)]">
                  Position Size Modifier
                </p>
                <p className="font-mono text-lg font-bold">
                  {(recommendation.position_size_modifier * 100).toFixed(0)}%
                </p>
              </div>

              <div>
                <p className="mb-1 text-xs text-[var(--color-text-muted)]">
                  Reasoning
                </p>
                <p className="text-sm italic text-[var(--color-text-muted)]">
                  {recommendation.reasoning}
                </p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-[var(--color-text-muted)]">
              No recommendation available
            </p>
          )}
        </div>
      </div>

      {/* Regime History */}
      <div className="mb-6 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
        <h3 className="mb-4 text-lg font-semibold">Regime History</h3>
        {history && history.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-left text-xs text-[var(--color-text-muted)]">
                  <th className="pb-2">Timestamp</th>
                  <th className="pb-2">Regime</th>
                  <th className="pb-2">Confidence</th>
                  <th className="pb-2">ADX</th>
                </tr>
              </thead>
              <tbody>
                {history.map((entry, i) => (
                  <tr
                    key={i}
                    className="border-b border-[var(--color-border)]/30"
                  >
                    <td className="py-1.5 font-mono text-xs">
                      {new Date(entry.timestamp).toLocaleString()}
                    </td>
                    <td className="py-1.5">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${REGIME_BG[entry.regime]} ${REGIME_COLORS[entry.regime]}`}
                      >
                        {formatRegime(entry.regime)}
                      </span>
                    </td>
                    <td className="py-1.5 font-mono">
                      {(entry.confidence * 100).toFixed(1)}%
                    </td>
                    <td className="py-1.5 font-mono">
                      {entry.adx_value.toFixed(1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-[var(--color-text-muted)]">
            No history available
          </p>
        )}
      </div>

      {/* Transition Probabilities */}
      {regimeState?.transition_probabilities &&
        Object.keys(regimeState.transition_probabilities).length > 0 && (
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
            <h3 className="mb-4 text-lg font-semibold">
              Transition Probabilities
            </h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-left text-xs text-[var(--color-text-muted)]">
                  <th className="pb-2">Target Regime</th>
                  <th className="pb-2">Probability</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(regimeState.transition_probabilities)
                  .sort(([, a], [, b]) => b - a)
                  .map(([target, prob]) => (
                    <tr
                      key={target}
                      className="border-b border-[var(--color-border)]/30"
                    >
                      <td className="py-1.5">
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${REGIME_BG[target as RegimeType] ?? "bg-gray-400/15"} ${REGIME_COLORS[target as RegimeType] ?? "text-gray-400"}`}
                        >
                          {formatRegime(target as RegimeType)}
                        </span>
                      </td>
                      <td className="py-1.5 font-mono">
                        {(prob * 100).toFixed(1)}%
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
    </div>
  );
}

function StatusCard({
  label,
  value,
  className = "",
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <p className="text-xs text-[var(--color-text-muted)]">{label}</p>
      <p className={`text-xl font-bold ${className}`}>{value}</p>
    </div>
  );
}

function Gauge({
  label,
  value,
  max = 100,
  min = 0,
  bipolar = false,
  thresholds,
  format,
}: {
  label: string;
  value: number;
  max?: number;
  min?: number;
  bipolar?: boolean;
  thresholds?: number[];
  format: (v: number) => string;
}) {
  const range = max - min;
  const pct = ((value - min) / range) * 100;
  const clampedPct = Math.max(0, Math.min(100, pct));

  let barColor = "bg-blue-400";
  if (bipolar) {
    barColor = value > 0 ? "bg-green-400" : value < 0 ? "bg-red-400" : "bg-gray-400";
  } else if (thresholds) {
    if (value >= thresholds[1]) barColor = "bg-red-400";
    else if (value >= thresholds[0]) barColor = "bg-yellow-400";
    else barColor = "bg-green-400";
  }

  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span className="text-[var(--color-text-muted)]">{label}</span>
        <span className="font-mono">{format(value)}</span>
      </div>
      <div className="h-2 w-full rounded-full bg-[var(--color-bg)]">
        <div
          className={`h-2 rounded-full transition-all ${barColor}`}
          style={{ width: `${clampedPct}%` }}
        />
      </div>
    </div>
  );
}
