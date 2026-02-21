import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { exchangesApi } from "../api/exchanges";
import { portfoliosApi } from "../api/portfolios";
import { platformApi } from "../api/platform";
import { jobsApi } from "../api/jobs";
import { regimeApi } from "../api/regime";
import { riskApi } from "../api/risk";
import { ProgressBar } from "../components/ProgressBar";
import type {
  BackgroundJob,
  ExchangeInfo,
  PlatformStatus,
  Portfolio,
  RegimeState,
  RegimeType,
  RiskStatus,
} from "../types";

export function Dashboard() {
  const queryClient = useQueryClient();

  useEffect(() => { document.title = "Dashboard | Crypto Investor"; }, []);
  const exchanges = useQuery<ExchangeInfo[]>({
    queryKey: ["exchanges"],
    queryFn: exchangesApi.list,
  });
  const portfolios = useQuery<Portfolio[]>({
    queryKey: ["portfolios"],
    queryFn: portfoliosApi.list,
  });

  const { data: platformStatus } = useQuery<PlatformStatus>({
    queryKey: ["platform-status"],
    queryFn: platformApi.status,
  });

  const { data: recentJobs } = useQuery<BackgroundJob[]>({
    queryKey: ["recent-jobs"],
    queryFn: () => jobsApi.list(undefined, 5),
    refetchInterval: 5000,
  });

  const activeJobs = recentJobs?.filter(
    (j) => j.status === "pending" || j.status === "running",
  );

  const { data: regimeStates } = useQuery<RegimeState[]>({
    queryKey: ["regime-overview"],
    queryFn: regimeApi.getCurrentAll,
    refetchInterval: 30000,
  });

  // Compute aggregate portfolio value from holdings
  const totalValue = portfolios.data?.reduce(
    (sum, p) => sum + p.holdings.reduce((s, h) => s + (h.amount ?? 0) * (h.avg_buy_price ?? 0), 0),
    0,
  ) ?? 0;

  // Fetch risk status for the first portfolio (daily P&L)
  const primaryPortfolioId = portfolios.data?.[0]?.id;
  const { data: riskStatus } = useQuery<RiskStatus>({
    queryKey: ["risk-status", primaryPortfolioId],
    queryFn: () => riskApi.getStatus(primaryPortfolioId!),
    enabled: primaryPortfolioId != null,
  });

  return (
    <div>
      <h2 className="mb-6 text-2xl font-bold">Dashboard</h2>

      {(exchanges.isError || portfolios.isError) && (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
          {exchanges.isError && <p>Failed to load exchanges: {exchanges.error instanceof Error ? exchanges.error.message : "Unknown error"}</p>}
          {portfolios.isError && <p>Failed to load portfolios: {portfolios.error instanceof Error ? portfolios.error.message : "Unknown error"}</p>}
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-7">
        <SummaryCard
          label="Portfolios"
          value={portfolios.data?.length ?? 0}
          loading={portfolios.isLoading}
        />
        <SummaryCard
          label="Exchanges"
          value={exchanges.data?.length ?? 0}
          loading={exchanges.isLoading}
        />
        <SummaryCard
          label="Data Files"
          value={platformStatus?.data_files ?? 0}
        />
        <SummaryCard
          label="Active Jobs"
          value={activeJobs?.length ?? 0}
          pulse={activeJobs !== undefined && activeJobs.length > 0}
        />
        <SummaryCard
          label="Portfolio Value"
          text={`$${totalValue.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
          loading={portfolios.isLoading}
        />
        <SummaryCard
          label="Daily P&L"
          text={riskStatus ? `$${riskStatus.daily_pnl.toFixed(2)}` : "—"}
          textColor={riskStatus && riskStatus.daily_pnl >= 0 ? "text-green-400" : riskStatus && riskStatus.daily_pnl < 0 ? "text-red-400" : ""}
        />
        <SummaryCard label="Status" text="Online" textColor="text-[var(--color-success)]" />
      </div>

      {/* Regime Overview */}
      {regimeStates && regimeStates.length > 0 && (
        <div className="mt-6 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
          <h3 className="mb-4 text-lg font-semibold">Regime Overview</h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {regimeStates.map((rs) => (
              <div
                key={rs.symbol}
                className="flex items-center justify-between rounded-lg border border-[var(--color-border)] p-3"
              >
                <div>
                  <p className="font-medium">{rs.symbol}</p>
                  <p className="text-xs text-[var(--color-text-muted)]">
                    Confidence: {(rs.confidence * 100).toFixed(1)}%
                  </p>
                </div>
                <RegimeBadge regime={rs.regime} />
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Framework Status */}
        {platformStatus?.frameworks && (
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
            <h3 className="mb-4 text-lg font-semibold">Framework Status</h3>
            <div className="space-y-2">
              {platformStatus.frameworks.map((fw) => (
                <div
                  key={fw.name}
                  className="flex items-center justify-between rounded-lg border border-[var(--color-border)] p-3"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`h-2.5 w-2.5 rounded-full ${fw.installed ? "bg-green-400" : "bg-red-400"}`}
                    />
                    <span className="font-medium">{fw.name}</span>
                  </div>
                  <span className="text-xs text-[var(--color-text-muted)]">
                    {fw.version ?? "not installed"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Active / Recent Jobs */}
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-semibold">Recent Jobs</h3>
            <button
              onClick={() => queryClient.invalidateQueries({ queryKey: ["recent-jobs"] })}
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1 text-xs text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-surface)] hover:text-[var(--color-text)]"
              title="Refresh jobs"
            >
              &#8635; Refresh
            </button>
          </div>
          {(!recentJobs || recentJobs.length === 0) && (
            <div className="text-sm text-[var(--color-text-muted)]">
              <p>No recent jobs.</p>
              <p className="mt-1 text-xs">Jobs will appear when you run backtests or data downloads.</p>
            </div>
          )}
          {recentJobs && recentJobs.length > 0 && (
            <div className="space-y-3">
              {recentJobs.map((job) => (
                <div
                  key={job.id}
                  className="rounded-lg border border-[var(--color-border)] p-3"
                >
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-sm font-medium">
                      {job.job_type.replace(/_/g, " ")}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        job.status === "completed"
                          ? "bg-green-500/20 text-green-400"
                          : job.status === "failed"
                            ? "bg-red-500/20 text-red-400"
                            : job.status === "running" || job.status === "pending"
                              ? "bg-blue-500/20 text-blue-400"
                              : "bg-gray-500/20 text-gray-400"
                      }`}
                    >
                      {job.status}
                    </span>
                  </div>
                  {(job.status === "running" || job.status === "pending") && (
                    <ProgressBar
                      progress={job.progress}
                      message={job.progress_message}
                    />
                  )}
                  {job.status === "completed" && (
                    <p className="text-xs text-[var(--color-text-muted)]">
                      Completed{" "}
                      {job.completed_at
                        ? new Date(job.completed_at).toLocaleString()
                        : ""}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Exchange list */}
      {exchanges.data && (
        <div className="mt-6 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
          <h3 className="mb-4 text-lg font-semibold">Available Exchanges</h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {exchanges.data.map((ex) => (
              <div
                key={ex.id}
                className="flex items-center gap-3 rounded-lg border border-[var(--color-border)] p-3"
              >
                <div>
                  <p className="font-medium">{ex.name}</p>
                  <p className="text-xs text-[var(--color-text-muted)]">{ex.id}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const REGIME_COLORS: Record<RegimeType, string> = {
  strong_trend_up: "bg-green-400/15 text-green-400",
  weak_trend_up: "bg-emerald-400/15 text-emerald-400",
  ranging: "bg-yellow-400/15 text-yellow-400",
  weak_trend_down: "bg-orange-400/15 text-orange-400",
  strong_trend_down: "bg-red-400/15 text-red-400",
  high_volatility: "bg-purple-400/15 text-purple-400",
  unknown: "bg-gray-400/15 text-gray-400",
};

function formatRegime(regime: RegimeType): string {
  return regime
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function RegimeBadge({ regime }: { regime: RegimeType }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${REGIME_COLORS[regime] ?? "bg-gray-400/15 text-gray-400"}`}
    >
      {formatRegime(regime)}
    </span>
  );
}

function SummaryCard({
  label,
  value,
  text,
  loading,
  textColor = "",
  pulse = false,
}: {
  label: string;
  value?: number;
  text?: string;
  loading?: boolean;
  textColor?: string;
  pulse?: boolean;
}) {
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <div className="mb-2 flex items-center gap-2">
        <h3 className="text-sm font-medium text-[var(--color-text-muted)]">{label}</h3>
        {pulse && (
          <span className="h-2 w-2 animate-pulse rounded-full bg-blue-400" />
        )}
      </div>
      {loading ? (
        <div className="h-8 w-16 animate-pulse rounded bg-[var(--color-border)]" />
      ) : text ? (
        <p className={`text-2xl font-bold ${textColor}`}>{text}</p>
      ) : (
        <p className="text-2xl font-bold">{value ?? 0}</p>
      )}
    </div>
  );
}
