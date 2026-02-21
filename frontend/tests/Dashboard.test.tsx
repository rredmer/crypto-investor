import { describe, it, expect, beforeEach, vi } from "vitest";
import { screen } from "@testing-library/react";
import { Dashboard } from "../src/pages/Dashboard";
import { renderWithProviders, mockFetch } from "./helpers";

const mockPlatformStatus = {
  frameworks: [
    { name: "Freqtrade", installed: true, version: "2024.1" },
    { name: "VectorBT", installed: true, version: "0.26.0" },
    { name: "NautilusTrader", installed: false, version: null },
  ],
  data_files: 12,
  active_jobs: 2,
};

const mockExchanges = [
  { id: "binance", name: "Binance", countries: ["MT"], has_fetch_tickers: true, has_fetch_ohlcv: true },
];

const mockPortfolios = [
  { id: 1, name: "Main", exchange_id: "binance", description: "", holdings: [], created_at: "", updated_at: "" },
];

const mockRegimeStates = [
  {
    symbol: "BTC/USDT",
    regime: "strong_trend_up",
    confidence: 0.85,
    adx_value: 45.0,
    bb_width_percentile: 60,
    ema_slope: 0.002,
    trend_alignment: 0.8,
    price_structure_score: 0.7,
    transition_probabilities: {},
  },
  {
    symbol: "ETH/USDT",
    regime: "ranging",
    confidence: 0.65,
    adx_value: 18.0,
    bb_width_percentile: 40,
    ema_slope: 0.0001,
    trend_alignment: 0.1,
    price_structure_score: 0.05,
    transition_probabilities: {},
  },
];

const mockJobs = [
  {
    id: "job-1",
    job_type: "backtest",
    status: "running",
    progress: 50,
    progress_message: "Processing...",
    params: null,
    result: null,
    error: null,
    started_at: "2026-02-15T10:00:00Z",
    completed_at: null,
    created_at: "2026-02-15T10:00:00Z",
  },
];

const mockRiskStatus = {
  equity: 10000,
  peak_equity: 10500,
  drawdown: 0.048,
  daily_pnl: 125.50,
  total_pnl: 500.00,
  open_positions: 2,
  is_halted: false,
  halt_reason: "",
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    mockFetch({
      "/api/platform/status": mockPlatformStatus,
      "/api/exchanges": mockExchanges,
      "/api/portfolios": mockPortfolios,
      "/api/regime/current": mockRegimeStates,
      "/api/jobs": mockJobs,
      "/api/risk/1/status/": mockRiskStatus,
    }),
  );
});

describe("Dashboard", () => {
  it("renders the page heading", () => {
    renderWithProviders(<Dashboard />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("renders summary cards", async () => {
    renderWithProviders(<Dashboard />);
    expect(await screen.findByText("Portfolios")).toBeInTheDocument();
    expect(screen.getByText("Exchanges")).toBeInTheDocument();
    expect(screen.getByText("Data Files")).toBeInTheDocument();
    expect(screen.getByText("Active Jobs")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
  });

  it("shows Online status", () => {
    renderWithProviders(<Dashboard />);
    expect(screen.getByText("Online")).toBeInTheDocument();
  });

  it("renders framework status section after data loads", async () => {
    renderWithProviders(<Dashboard />);
    expect(await screen.findByText("Framework Status")).toBeInTheDocument();
    expect(await screen.findByText("Freqtrade")).toBeInTheDocument();
    expect(screen.getByText("VectorBT")).toBeInTheDocument();
  });

  it("renders regime overview after data loads", async () => {
    renderWithProviders(<Dashboard />);
    expect(await screen.findByText("Regime Overview")).toBeInTheDocument();
    expect(screen.getByText("BTC/USDT")).toBeInTheDocument();
    expect(screen.getByText("ETH/USDT")).toBeInTheDocument();
    expect(screen.getByText("Strong Trend Up")).toBeInTheDocument();
    expect(screen.getByText("Ranging")).toBeInTheDocument();
  });
});
