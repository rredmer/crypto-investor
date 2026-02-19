import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { EquityCurve } from "../src/components/EquityCurve";

// Mock lightweight-charts to avoid canvas/DOM issues in tests
vi.mock("lightweight-charts", () => ({
  createChart: () => ({
    addSeries: () => ({ setData: vi.fn() }),
    timeScale: () => ({ fitContent: vi.fn() }),
    priceScale: () => ({ applyOptions: vi.fn() }),
    remove: vi.fn(),
    applyOptions: vi.fn(),
  }),
  LineSeries: "LineSeries",
  AreaSeries: "AreaSeries",
}));

// Mock ResizeObserver as a class
class MockResizeObserver {
  observe = vi.fn();
  disconnect = vi.fn();
  unobserve = vi.fn();
}
vi.stubGlobal("ResizeObserver", MockResizeObserver);

const mockTrades = [
  { close_date: "2024-01-15T10:00:00Z", profit_abs: 150 },
  { close_date: "2024-01-16T14:00:00Z", profit_abs: -50 },
  { close_date: "2024-01-17T09:00:00Z", profit_abs: 200 },
];

describe("EquityCurve", () => {
  it("renders nothing when trades is empty", () => {
    const { container } = render(<EquityCurve trades={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders heading when trades are provided", () => {
    render(<EquityCurve trades={mockTrades} />);
    expect(screen.getByText("Equity Curve")).toBeTruthy();
  });

  it("renders chart container when trades are provided", () => {
    const { container } = render(<EquityCurve trades={mockTrades} />);
    expect(container.querySelector("div")).toBeTruthy();
  });

  it("accepts custom initialBalance", () => {
    render(<EquityCurve trades={mockTrades} initialBalance={50000} />);
    expect(screen.getByText("Equity Curve")).toBeTruthy();
  });

  it("accepts custom height", () => {
    render(<EquityCurve trades={mockTrades} height={500} />);
    expect(screen.getByText("Equity Curve")).toBeTruthy();
  });
});
