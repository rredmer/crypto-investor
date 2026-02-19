import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProgressBar } from "../src/components/ProgressBar";

describe("ProgressBar", () => {
  it("renders with default message", () => {
    render(<ProgressBar progress={0.5} />);
    expect(screen.getByText("Processing...")).toBeTruthy();
    expect(screen.getByText("50%")).toBeTruthy();
  });

  it("renders with custom message", () => {
    render(<ProgressBar progress={0.75} message="Downloading data..." />);
    expect(screen.getByText("Downloading data...")).toBeTruthy();
    expect(screen.getByText("75%")).toBeTruthy();
  });

  it("renders 0% progress", () => {
    render(<ProgressBar progress={0} />);
    expect(screen.getByText("0%")).toBeTruthy();
  });

  it("renders 100% progress", () => {
    render(<ProgressBar progress={1} />);
    expect(screen.getByText("100%")).toBeTruthy();
  });

  it("rounds fractional percentages", () => {
    render(<ProgressBar progress={0.333} />);
    expect(screen.getByText("33%")).toBeTruthy();
  });

  it("applies custom className", () => {
    const { container } = render(<ProgressBar progress={0.5} className="mt-4" />);
    expect(container.firstChild).toHaveClass("mt-4");
  });
});
