import { describe, it, expect, beforeEach, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Login } from "../src/pages/Login";
import { renderWithProviders } from "./helpers";

describe("Login", () => {
  const mockOnLogin = vi.fn();

  beforeEach(() => {
    mockOnLogin.mockReset();
  });

  it("renders login form with username and password fields", () => {
    renderWithProviders(<Login onLogin={mockOnLogin} />);
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign In" })).toBeInTheDocument();
    expect(screen.getByText("CryptoInvestor")).toBeInTheDocument();
    expect(screen.getByText("Sign in to continue")).toBeInTheDocument();
  });

  it("calls onLogin with credentials on form submit", async () => {
    mockOnLogin.mockResolvedValue(null);
    renderWithProviders(<Login onLogin={mockOnLogin} />);

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username"), "admin");
    await user.type(screen.getByLabelText("Password"), "secret");
    await user.click(screen.getByRole("button", { name: "Sign In" }));

    await waitFor(() => {
      expect(mockOnLogin).toHaveBeenCalledWith("admin", "secret");
    });
  });

  it("displays error message when login fails", async () => {
    mockOnLogin.mockResolvedValue("Invalid credentials");
    renderWithProviders(<Login onLogin={mockOnLogin} />);

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username"), "admin");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign In" }));

    await waitFor(() => {
      expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
    });
  });

  it("shows loading state while submitting", async () => {
    let resolveLogin: (val: string | null) => void;
    mockOnLogin.mockImplementation(
      () => new Promise((resolve) => { resolveLogin = resolve; }),
    );
    renderWithProviders(<Login onLogin={mockOnLogin} />);

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username"), "admin");
    await user.type(screen.getByLabelText("Password"), "pass");
    await user.click(screen.getByRole("button", { name: "Sign In" }));

    expect(screen.getByText("Signing in...")).toBeInTheDocument();
    expect(screen.getByRole("button")).toBeDisabled();

    resolveLogin!(null);
    await waitFor(() => {
      expect(screen.queryByText("Signing in...")).not.toBeInTheDocument();
    });
  });

  it("requires username and password fields", () => {
    renderWithProviders(<Login onLogin={mockOnLogin} />);
    expect(screen.getByLabelText("Username")).toBeRequired();
    expect(screen.getByLabelText("Password")).toBeRequired();
  });

  it("password field has type=password", () => {
    renderWithProviders(<Login onLogin={mockOnLogin} />);
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");
  });
});
