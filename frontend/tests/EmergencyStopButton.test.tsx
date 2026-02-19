import { describe, it, expect, beforeEach, vi } from "vitest";
import { screen } from "@testing-library/react";
import { EmergencyStopButton } from "../src/components/EmergencyStopButton";
import { renderWithProviders, mockFetch } from "./helpers";

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch({}));
});

describe("EmergencyStopButton", () => {
  it("renders EMERGENCY STOP button when not halted", () => {
    renderWithProviders(<EmergencyStopButton isHalted={false} />);
    expect(screen.getByText("EMERGENCY STOP")).toBeInTheDocument();
  });

  it("renders HALTED badge when halted", () => {
    renderWithProviders(<EmergencyStopButton isHalted={true} />);
    expect(screen.getByText("HALTED")).toBeInTheDocument();
    expect(screen.queryByText("EMERGENCY STOP")).not.toBeInTheDocument();
  });

  it("renders EMERGENCY STOP when isHalted is null", () => {
    renderWithProviders(<EmergencyStopButton isHalted={null} />);
    expect(screen.getByText("EMERGENCY STOP")).toBeInTheDocument();
  });

  it("button is not disabled in normal state", () => {
    renderWithProviders(<EmergencyStopButton isHalted={false} />);
    const button = screen.getByRole("button");
    expect(button).not.toBeDisabled();
  });
});
