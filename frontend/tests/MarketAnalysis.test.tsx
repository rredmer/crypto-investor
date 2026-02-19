import { describe, it, expect, beforeEach, vi } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { MarketAnalysis } from "../src/pages/MarketAnalysis";
import { renderWithProviders, mockFetch } from "./helpers";

// Mock lightweight-charts to avoid canvas/DOM issues in tests
vi.mock("lightweight-charts", () => ({
  createChart: () => ({
    addSeries: () => ({ setData: vi.fn() }),
    timeScale: () => ({ fitContent: vi.fn() }),
    remove: vi.fn(),
  }),
  CandlestickSeries: "CandlestickSeries",
  LineSeries: "LineSeries",
  HistogramSeries: "HistogramSeries",
}));

const mockOhlcv = [
  { timestamp: 1706745600000, open: 42000, high: 42500, low: 41800, close: 42300, volume: 1234 },
  { timestamp: 1706749200000, open: 42300, high: 42700, low: 42100, close: 42600, volume: 987 },
];

describe("MarketAnalysis Page", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "/api/market/ohlcv": mockOhlcv,
        "/api/indicators": { data: [] },
      }),
    );
  });

  it("renders the page heading", () => {
    renderWithProviders(<MarketAnalysis />);
    expect(screen.getByText("Market Analysis")).toBeInTheDocument();
  });

  it("renders symbol input with default value", () => {
    renderWithProviders(<MarketAnalysis />);
    expect(screen.getByDisplayValue("BTC/USDT")).toBeInTheDocument();
  });

  it("renders timeframe selector", () => {
    renderWithProviders(<MarketAnalysis />);
    expect(screen.getByDisplayValue("1h")).toBeInTheDocument();
  });

  it("renders exchange selector", () => {
    renderWithProviders(<MarketAnalysis />);
    expect(screen.getByDisplayValue("Sample")).toBeInTheDocument();
  });

  it("renders overlay indicator buttons", () => {
    renderWithProviders(<MarketAnalysis />);
    expect(screen.getByText("Overlays")).toBeInTheDocument();
    expect(screen.getByText("sma_21")).toBeInTheDocument();
    expect(screen.getByText("sma_50")).toBeInTheDocument();
    expect(screen.getByText("bb_upper")).toBeInTheDocument();
  });

  it("renders pane indicator buttons", () => {
    renderWithProviders(<MarketAnalysis />);
    expect(screen.getByText("Panes")).toBeInTheDocument();
    expect(screen.getByText("rsi_14")).toBeInTheDocument();
    expect(screen.getByText("macd")).toBeInTheDocument();
  });
});

describe("MarketAnalysis - Indicator Toggle Interaction", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "/api/market/ohlcv": mockOhlcv,
        "/api/indicators": { data: [] },
      }),
    );
  });

  it("toggles overlay indicator on click", () => {
    renderWithProviders(<MarketAnalysis />);
    const sma21 = screen.getByText("sma_21");
    // Click to select — button should still be in DOM
    fireEvent.click(sma21);
    expect(screen.getByText("sma_21")).toBeInTheDocument();
    // Click again to deselect
    fireEvent.click(sma21);
    expect(screen.getByText("sma_21")).toBeInTheDocument();
  });

  it("toggles pane indicator on click", () => {
    renderWithProviders(<MarketAnalysis />);
    const rsi = screen.getByText("rsi_14");
    fireEvent.click(rsi);
    expect(screen.getByText("rsi_14")).toBeInTheDocument();
  });

  it("can select multiple indicators", () => {
    renderWithProviders(<MarketAnalysis />);
    fireEvent.click(screen.getByText("sma_21"));
    fireEvent.click(screen.getByText("sma_50"));
    fireEvent.click(screen.getByText("rsi_14"));
    // All should still be in DOM
    expect(screen.getByText("sma_21")).toBeInTheDocument();
    expect(screen.getByText("sma_50")).toBeInTheDocument();
    expect(screen.getByText("rsi_14")).toBeInTheDocument();
  });

  it("renders all overlay indicator options", () => {
    renderWithProviders(<MarketAnalysis />);
    const overlays = ["sma_21", "sma_50", "sma_200", "ema_21", "ema_50", "bb_upper", "bb_mid", "bb_lower"];
    for (const ind of overlays) {
      expect(screen.getByText(ind)).toBeInTheDocument();
    }
  });

  it("renders all pane indicator options", () => {
    renderWithProviders(<MarketAnalysis />);
    const panes = ["rsi_14", "macd", "macd_signal", "macd_hist", "volume_ratio"];
    for (const ind of panes) {
      expect(screen.getByText(ind)).toBeInTheDocument();
    }
  });
});

describe("MarketAnalysis - Form Controls", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "/api/market/ohlcv": mockOhlcv,
        "/api/indicators": { data: [] },
      }),
    );
  });

  it("allows changing symbol input", () => {
    renderWithProviders(<MarketAnalysis />);
    const input = screen.getByDisplayValue("BTC/USDT");
    fireEvent.change(input, { target: { value: "ETH/USDT" } });
    expect(screen.getByDisplayValue("ETH/USDT")).toBeInTheDocument();
  });

  it("allows changing timeframe selector", () => {
    renderWithProviders(<MarketAnalysis />);
    const select = screen.getByDisplayValue("1h");
    fireEvent.change(select, { target: { value: "4h" } });
    expect(screen.getByDisplayValue("4h")).toBeInTheDocument();
  });

  it("allows changing exchange selector", () => {
    renderWithProviders(<MarketAnalysis />);
    const select = screen.getByDisplayValue("Sample");
    fireEvent.change(select, { target: { value: "binance" } });
    expect(screen.getByDisplayValue("Binance")).toBeInTheDocument();
  });

  it("renders all timeframe options", () => {
    renderWithProviders(<MarketAnalysis />);
    const timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"];
    for (const tf of timeframes) {
      expect(screen.getByRole("option", { name: tf })).toBeInTheDocument();
    }
  });
});
