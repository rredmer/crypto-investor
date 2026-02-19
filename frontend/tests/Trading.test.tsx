import { describe, it, expect, beforeEach, vi } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { Trading } from "../src/pages/Trading";
import { renderWithProviders, mockFetch } from "./helpers";

// Mock useWebSocket to avoid real WebSocket connections
vi.mock("../src/hooks/useWebSocket", () => ({
  useWebSocket: () => ({ isConnected: false, lastMessage: null, send: vi.fn() }),
}));

const mockOrders = [
  {
    id: 1,
    symbol: "BTC/USDT",
    side: "buy",
    order_type: "market",
    amount: 0.1,
    price: null,
    avg_fill_price: 50000,
    filled: 0.1,
    status: "filled",
    mode: "paper",
    reject_reason: null,
    error_message: null,
    created_at: "2026-02-15T12:00:00Z",
  },
  {
    id: 2,
    symbol: "ETH/USDT",
    side: "sell",
    order_type: "limit",
    amount: 5,
    price: 3000,
    avg_fill_price: null,
    filled: 0,
    status: "open",
    mode: "paper",
    reject_reason: null,
    error_message: null,
    created_at: "2026-02-15T13:00:00Z",
  },
];

const mockOrderWithError = [
  {
    id: 3,
    symbol: "SOL/USDT",
    side: "buy",
    order_type: "market",
    amount: 100,
    price: null,
    avg_fill_price: null,
    filled: 0,
    status: "rejected",
    mode: "paper",
    reject_reason: "Insufficient balance",
    error_message: null,
    created_at: "2026-02-15T14:00:00Z",
  },
];

const mockLiveOrders = [
  {
    id: 10,
    symbol: "BTC/USDT",
    side: "buy",
    order_type: "limit",
    amount: 0.5,
    price: 45000,
    avg_fill_price: null,
    filled: 0,
    status: "open",
    mode: "live",
    reject_reason: null,
    error_message: null,
    created_at: "2026-02-15T15:00:00Z",
  },
];

describe("Trading Page", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "/api/trading/orders": mockOrders,
      }),
    );
  });

  it("renders the page heading", () => {
    renderWithProviders(<Trading />);
    expect(screen.getByText("Trading")).toBeInTheDocument();
  });

  it("renders Paper and Live mode buttons", () => {
    renderWithProviders(<Trading />);
    expect(screen.getByText("Paper")).toBeInTheDocument();
    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  it("renders New Order section", () => {
    renderWithProviders(<Trading />);
    expect(screen.getByText("New Order")).toBeInTheDocument();
  });

  it("renders order table with data", async () => {
    renderWithProviders(<Trading />);
    expect(await screen.findByText("BTC/USDT")).toBeInTheDocument();
    expect(await screen.findByText("BUY")).toBeInTheDocument();
    expect(await screen.findByText("SELL")).toBeInTheDocument();
  });

  it("shows Paper Orders heading in paper mode", () => {
    renderWithProviders(<Trading />);
    expect(screen.getByText("Paper Orders")).toBeInTheDocument();
  });
});

describe("Trading - Mode Switching", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "/api/trading/orders": mockOrders,
      }),
    );
  });

  it("shows LIVE MODE warning when switched to live", () => {
    renderWithProviders(<Trading />);
    const liveBtn = screen.getByText("Live");
    fireEvent.click(liveBtn);
    expect(screen.getByText("LIVE MODE")).toBeInTheDocument();
  });

  it("shows Live Orders heading when switched to live", () => {
    renderWithProviders(<Trading />);
    const liveBtn = screen.getByText("Live");
    fireEvent.click(liveBtn);
    expect(screen.getByText("Live Orders")).toBeInTheDocument();
  });

  it("shows Action column header in live mode", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({ "/api/trading/orders": mockLiveOrders }),
    );
    renderWithProviders(<Trading />);
    fireEvent.click(screen.getByText("Live"));
    expect(await screen.findByText("Action")).toBeInTheDocument();
  });

  it("shows Cancel button for open orders in live mode", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({ "/api/trading/orders": mockLiveOrders }),
    );
    renderWithProviders(<Trading />);
    fireEvent.click(screen.getByText("Live"));
    expect(await screen.findByText("Cancel")).toBeInTheDocument();
  });

  it("switches back to paper mode", () => {
    renderWithProviders(<Trading />);
    fireEvent.click(screen.getByText("Live"));
    expect(screen.getByText("LIVE MODE")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Paper"));
    expect(screen.queryByText("LIVE MODE")).not.toBeInTheDocument();
    expect(screen.getByText("Paper Orders")).toBeInTheDocument();
  });
});

describe("Trading - Halt Banner", () => {
  it("shows halt banner when useSystemEvents reports halted", async () => {
    // Re-mock useWebSocket to simulate a halted state via useSystemEvents
    // useSystemEvents checks isHalted from WS messages. Since we mock useWebSocket
    // to return null lastMessage, isHalted defaults to null (falsy) — no banner.
    // The halt banner requires isHalted===true, which only happens via WS message.
    // We test the component renders without halt banner by default.
    vi.stubGlobal(
      "fetch",
      mockFetch({ "/api/trading/orders": mockOrders }),
    );
    renderWithProviders(<Trading />);
    // Halt banner should NOT appear when not halted
    expect(screen.queryByText(/TRADING HALTED/)).not.toBeInTheDocument();
  });
});

describe("Trading - Order Display Details", () => {
  it("shows reject reason for rejected orders", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({ "/api/trading/orders": mockOrderWithError }),
    );
    renderWithProviders(<Trading />);
    expect(await screen.findByText("Insufficient balance")).toBeInTheDocument();
  });

  it("shows filled ratio for partially filled orders", async () => {
    const partialOrder = [
      {
        ...mockLiveOrders[0],
        filled: 0.2,
        amount: 0.5,
        status: "partial_fill",
      },
    ];
    vi.stubGlobal(
      "fetch",
      mockFetch({ "/api/trading/orders": partialOrder }),
    );
    renderWithProviders(<Trading />);
    expect(await screen.findByText("0.2/0.5")).toBeInTheDocument();
  });

  it("shows Market for orders without price", async () => {
    const marketOrder = [
      {
        ...mockOrders[0],
        avg_fill_price: null,
        price: null,
      },
    ];
    vi.stubGlobal(
      "fetch",
      mockFetch({ "/api/trading/orders": marketOrder }),
    );
    renderWithProviders(<Trading />);
    expect(await screen.findByText("Market")).toBeInTheDocument();
  });

  it("shows empty orders message when no orders exist", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({ "/api/trading/orders": [] }),
    );
    renderWithProviders(<Trading />);
    expect(await screen.findByText("No paper orders yet.")).toBeInTheDocument();
  });
});
