import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { PriceChart } from "../src/components/PriceChart";

// Mock lightweight-charts to avoid canvas/DOM issues in tests
vi.mock("lightweight-charts", () => ({
  createChart: () => ({
    addSeries: () => ({ setData: vi.fn() }),
    timeScale: () => ({ fitContent: vi.fn() }),
    remove: vi.fn(),
    applyOptions: vi.fn(),
  }),
  CandlestickSeries: "CandlestickSeries",
  LineSeries: "LineSeries",
  HistogramSeries: "HistogramSeries",
}));

const mockData = [
  { timestamp: 1706745600000, open: 42000, high: 42500, low: 41800, close: 42300, volume: 1234 },
  { timestamp: 1706749200000, open: 42300, high: 42700, low: 42100, close: 42600, volume: 987 },
];

describe("PriceChart", () => {
  it("renders chart container", () => {
    const { container } = render(<PriceChart data={mockData} />);
    expect(container.querySelector("div")).toBeTruthy();
  });

  it("renders with empty data", () => {
    const { container } = render(<PriceChart data={[]} />);
    expect(container.querySelector("div")).toBeTruthy();
  });

  it("renders with custom height", () => {
    const { container } = render(<PriceChart data={mockData} height={600} />);
    expect(container.querySelector("div")).toBeTruthy();
  });

  it("renders pane container when paneIndicators are provided", () => {
    const { container } = render(
      <PriceChart
        data={mockData}
        indicatorData={[{ timestamp: 1706745600000, rsi_14: 55 }]}
        paneIndicators={["rsi_14"]}
      />,
    );
    // Two child divs: main chart + pane chart
    const wrapperDiv = container.firstChild as HTMLElement;
    expect(wrapperDiv.children.length).toBe(2);
  });

  it("does not render pane container when no paneIndicators", () => {
    const { container } = render(<PriceChart data={mockData} />);
    const wrapperDiv = container.firstChild as HTMLElement;
    expect(wrapperDiv.children.length).toBe(1);
  });
});
