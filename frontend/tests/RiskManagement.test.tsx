import { describe, it, expect, beforeEach, vi } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { RiskManagement } from "../src/pages/RiskManagement";
import { renderWithProviders, mockFetch } from "./helpers";

const mockStatus = {
  equity: 10000,
  peak_equity: 10000,
  drawdown: 0.02,
  daily_pnl: 150,
  total_pnl: 500,
  open_positions: 2,
  is_halted: false,
  halt_reason: "",
};

const mockLimits = {
  max_portfolio_drawdown: 0.15,
  max_single_trade_risk: 0.02,
  max_daily_loss: 0.05,
  max_open_positions: 10,
  max_position_size_pct: 0.20,
  max_correlation: 0.70,
  min_risk_reward: 1.5,
  max_leverage: 1.0,
};

const mockVaR = {
  var_95: 250.50,
  var_99: 420.75,
  cvar_95: 310.20,
  cvar_99: 530.40,
  method: "parametric",
  window_days: 90,
};

const mockHeatCheckHealthy = {
  healthy: true,
  issues: [],
  drawdown: 0.02,
  daily_pnl: 150,
  open_positions: 2,
  max_correlation: 0.35,
  high_corr_pairs: [],
  max_concentration: 0.15,
  position_weights: { "BTC/USDT": 0.6, "ETH/USDT": 0.4 },
  var_95: 250.50,
  var_99: 420.75,
  cvar_95: 310.20,
  cvar_99: 530.40,
  is_halted: false,
};

const mockHeatCheckUnhealthy = {
  ...mockHeatCheckHealthy,
  healthy: false,
  issues: ["Drawdown warning: 12% approaching limit 15%", "VaR warning: 99% VaR $1200 > 10% of equity"],
};

const mockMetricHistory = [
  {
    id: 1,
    portfolio_id: 1,
    var_95: 250.50,
    var_99: 420.75,
    cvar_95: 310.20,
    cvar_99: 530.40,
    method: "parametric",
    drawdown: 0.02,
    equity: 10000,
    open_positions_count: 2,
    recorded_at: "2026-02-15T12:00:00Z",
  },
];

const mockTradeLog = [
  {
    id: 1,
    portfolio_id: 1,
    symbol: "BTC/USDT",
    side: "buy",
    size: 0.1,
    entry_price: 50000,
    stop_loss_price: 48000,
    approved: true,
    reason: "approved",
    equity_at_check: 10000,
    drawdown_at_check: 0.02,
    open_positions_at_check: 0,
    checked_at: "2026-02-15T11:00:00Z",
  },
  {
    id: 2,
    portfolio_id: 1,
    symbol: "ETH/USDT",
    side: "buy",
    size: 5.0,
    entry_price: 3000,
    stop_loss_price: null,
    approved: false,
    reason: "Position too large: 150.00% > 20.00%",
    equity_at_check: 10000,
    drawdown_at_check: 0.02,
    open_positions_at_check: 1,
    checked_at: "2026-02-15T11:30:00Z",
  },
];

function setupAllMocks() {
  vi.stubGlobal(
    "fetch",
    mockFetch({
      "/api/risk/1/status": mockStatus,
      "/api/risk/1/limits": mockLimits,
      "/api/risk/1/var": mockVaR,
      "/api/risk/1/heat-check": mockHeatCheckHealthy,
      "/api/risk/1/metric-history": mockMetricHistory,
      "/api/risk/1/trade-log": mockTradeLog,
    }),
  );
}

describe("RiskManagement - VaR Summary", () => {
  beforeEach(() => {
    setupAllMocks();
  });

  it("renders the page heading", () => {
    renderWithProviders(<RiskManagement />);
    expect(screen.getByText("Risk Management")).toBeInTheDocument();
  });

  it("renders VaR summary card", async () => {
    renderWithProviders(<RiskManagement />);
    expect(await screen.findByText("Value at Risk")).toBeInTheDocument();
    // VaR labels appear in both summary card and history table
    const var95 = await screen.findAllByText("VaR 95%");
    expect(var95.length).toBeGreaterThanOrEqual(1);
    const var99 = await screen.findAllByText("VaR 99%");
    expect(var99.length).toBeGreaterThanOrEqual(1);
    const cvar95 = await screen.findAllByText("CVaR 95%");
    expect(cvar95.length).toBeGreaterThanOrEqual(1);
    const cvar99 = await screen.findAllByText("CVaR 99%");
    expect(cvar99.length).toBeGreaterThanOrEqual(1);
  });
});

describe("RiskManagement - Portfolio Health", () => {
  it("renders healthy badge when portfolio is healthy", async () => {
    setupAllMocks();
    renderWithProviders(<RiskManagement />);
    expect(await screen.findByText("Healthy")).toBeInTheDocument();
  });

  it("renders unhealthy badge and issues when portfolio has problems", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "/api/risk/1/status": mockStatus,
        "/api/risk/1/limits": mockLimits,
        "/api/risk/1/var": mockVaR,
        "/api/risk/1/heat-check": mockHeatCheckUnhealthy,
        "/api/risk/1/metric-history": [],
        "/api/risk/1/trade-log": [],
      }),
    );
    renderWithProviders(<RiskManagement />);
    expect(await screen.findByText("Unhealthy")).toBeInTheDocument();
  });
});

describe("RiskManagement - Limits Editor", () => {
  beforeEach(() => {
    setupAllMocks();
  });

  it("shows Edit button in read-only mode", async () => {
    renderWithProviders(<RiskManagement />);
    expect(await screen.findByText("Edit")).toBeInTheDocument();
  });

  it("shows Save and Cancel buttons in edit mode", async () => {
    renderWithProviders(<RiskManagement />);
    const editBtn = await screen.findByText("Edit");
    fireEvent.click(editBtn);
    expect(screen.getByText("Save")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });
});

describe("RiskManagement - Total PnL Card", () => {
  beforeEach(() => {
    setupAllMocks();
  });

  it("renders Total PnL status card", async () => {
    renderWithProviders(<RiskManagement />);
    expect(await screen.findByText("Total PnL")).toBeInTheDocument();
    expect(await screen.findByText("$500.00")).toBeInTheDocument();
  });
});

describe("RiskManagement - VaR History", () => {
  beforeEach(() => {
    setupAllMocks();
  });

  it("renders VaR History section heading", async () => {
    renderWithProviders(<RiskManagement />);
    expect(await screen.findByText("VaR History")).toBeInTheDocument();
  });
});

describe("RiskManagement - Trade Audit Log", () => {
  beforeEach(() => {
    setupAllMocks();
  });

  it("renders Trade Audit Log section heading", async () => {
    renderWithProviders(<RiskManagement />);
    expect(await screen.findByText("Trade Audit Log")).toBeInTheDocument();
  });

  it("renders approved and rejected badges", async () => {
    renderWithProviders(<RiskManagement />);
    const approved = await screen.findAllByText("Approved");
    expect(approved.length).toBeGreaterThanOrEqual(1);
    const rejected = await screen.findAllByText("Rejected");
    expect(rejected.length).toBeGreaterThanOrEqual(1);
  });
});
