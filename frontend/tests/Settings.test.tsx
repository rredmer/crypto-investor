import { describe, it, expect, beforeEach, vi } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { Settings } from "../src/pages/Settings";
import { renderWithProviders, mockFetch } from "./helpers";

const mockConfigs = [
  {
    id: 1,
    name: "Binance Main",
    exchange_id: "binance",
    is_sandbox: true,
    is_default: true,
    api_key_masked: "abc...xyz",
    has_api_secret: true,
    has_passphrase: false,
    last_test_success: true,
    last_test_error: null,
    created_at: "2026-01-01T00:00:00Z",
  },
];

const mockDataSources = [
  {
    id: 1,
    exchange_config: 1,
    exchange_name: "Binance Main",
    symbols: ["BTC/USDT", "ETH/USDT"],
    timeframes: ["1h", "4h"],
    fetch_interval_minutes: 60,
    is_active: true,
    last_fetched_at: "2026-02-15T12:00:00Z",
  },
];

const mockNotifPrefs = {
  telegram_enabled: true,
  webhook_enabled: false,
  on_order_submitted: true,
  on_order_filled: true,
  on_order_cancelled: false,
  on_risk_halt: true,
  on_trade_rejected: true,
  on_daily_summary: false,
};

function setupMocks() {
  vi.stubGlobal(
    "fetch",
    mockFetch({
      "/api/exchange-configs": mockConfigs,
      "/api/data-sources": mockDataSources,
      "/api/notifications/preferences": mockNotifPrefs,
    }),
  );
}

describe("Settings Page", () => {
  beforeEach(setupMocks);

  it("renders the page heading", () => {
    renderWithProviders(<Settings />);
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("renders Exchange Connections section", () => {
    renderWithProviders(<Settings />);
    expect(screen.getByText("Exchange Connections")).toBeInTheDocument();
  });

  it("renders exchange config card", async () => {
    renderWithProviders(<Settings />);
    const names = await screen.findAllByText("Binance Main");
    expect(names.length).toBeGreaterThanOrEqual(1);
    expect(await screen.findByText("binance")).toBeInTheDocument();
  });

  it("shows sandbox badge for sandbox config", async () => {
    renderWithProviders(<Settings />);
    expect(await screen.findByText("sandbox")).toBeInTheDocument();
  });

  it("shows default badge for default config", async () => {
    renderWithProviders(<Settings />);
    expect(await screen.findByText("default")).toBeInTheDocument();
  });

  it("renders Data Sources section", () => {
    renderWithProviders(<Settings />);
    expect(screen.getByText("Data Sources")).toBeInTheDocument();
  });

  it("renders data source with symbols and timeframes", async () => {
    renderWithProviders(<Settings />);
    expect(await screen.findByText("BTC/USDT")).toBeInTheDocument();
    expect(await screen.findByText("ETH/USDT")).toBeInTheDocument();
  });

  it("renders Notifications section", () => {
    renderWithProviders(<Settings />);
    expect(screen.getByText("Notifications")).toBeInTheDocument();
  });

  it("renders About section", () => {
    renderWithProviders(<Settings />);
    expect(screen.getByText("About")).toBeInTheDocument();
    expect(screen.getByText("crypto-investor v0.1.0")).toBeInTheDocument();
  });
});

describe("Settings - Add Exchange Flow", () => {
  beforeEach(setupMocks);

  it("shows Add Exchange button initially", async () => {
    renderWithProviders(<Settings />);
    expect(await screen.findByText("Add Exchange")).toBeInTheDocument();
  });

  it("shows exchange form when Add Exchange is clicked", async () => {
    renderWithProviders(<Settings />);
    const addBtn = await screen.findByText("Add Exchange");
    fireEvent.click(addBtn);
    // Form should appear with Name and Exchange fields
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("API Key")).toBeInTheDocument();
    expect(screen.getByText("API Secret")).toBeInTheDocument();
    expect(screen.getByText("Sandbox mode")).toBeInTheDocument();
  });

  it("hides Add Exchange button when form is open", async () => {
    renderWithProviders(<Settings />);
    const addBtn = await screen.findByText("Add Exchange");
    fireEvent.click(addBtn);
    // The "Add Exchange" button in the header should be gone
    // but the form submit button says "Add Exchange" too
    const addBtns = screen.queryAllByText("Add Exchange");
    // Only the form submit button should remain
    expect(addBtns.length).toBe(1);
  });

  it("shows Cancel button in add form", async () => {
    renderWithProviders(<Settings />);
    const addBtn = await screen.findByText("Add Exchange");
    fireEvent.click(addBtn);
    const cancelBtns = screen.getAllByText("Cancel");
    expect(cancelBtns.length).toBeGreaterThanOrEqual(1);
  });

  it("closes form when Cancel is clicked", async () => {
    renderWithProviders(<Settings />);
    const addBtn = await screen.findByText("Add Exchange");
    fireEvent.click(addBtn);
    expect(screen.getByText("API Key")).toBeInTheDocument();
    const cancelBtns = screen.getAllByText("Cancel");
    fireEvent.click(cancelBtns[0]);
    // Form should close, Add Exchange button should return in header
    expect(screen.queryByText("API Key")).not.toBeInTheDocument();
  });
});

describe("Settings - Edit and Delete Flow", () => {
  beforeEach(setupMocks);

  it("shows Edit button on config card", async () => {
    renderWithProviders(<Settings />);
    expect(await screen.findByText("Edit")).toBeInTheDocument();
  });

  it("shows edit form when Edit is clicked", async () => {
    renderWithProviders(<Settings />);
    const editBtn = await screen.findByText("Edit");
    fireEvent.click(editBtn);
    expect(screen.getByText("API Key")).toBeInTheDocument();
    expect(screen.getByText("Update")).toBeInTheDocument();
  });

  it("shows Delete buttons on config and data source cards", async () => {
    renderWithProviders(<Settings />);
    // Delete appears on both exchange config card and data source card
    const deleteBtns = await screen.findAllByText("Delete");
    expect(deleteBtns.length).toBeGreaterThanOrEqual(2);
  });

  it("shows Confirm and No buttons after Delete click on exchange config", async () => {
    renderWithProviders(<Settings />);
    const deleteBtns = await screen.findAllByText("Delete");
    // First Delete button is on the exchange config card
    fireEvent.click(deleteBtns[0]);
    expect(screen.getByText("Confirm")).toBeInTheDocument();
    expect(screen.getByText("No")).toBeInTheDocument();
  });

  it("cancels delete when No is clicked", async () => {
    renderWithProviders(<Settings />);
    const deleteBtns = await screen.findAllByText("Delete");
    fireEvent.click(deleteBtns[0]);
    fireEvent.click(screen.getByText("No"));
    // Should go back to normal state with Delete buttons
    const afterBtns = await screen.findAllByText("Delete");
    expect(afterBtns.length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("Confirm")).not.toBeInTheDocument();
  });
});

describe("Settings - Test Connection", () => {
  beforeEach(setupMocks);

  it("shows Test button on config card", async () => {
    renderWithProviders(<Settings />);
    expect(await screen.findByText("Test")).toBeInTheDocument();
  });

  it("shows Testing... state while test is running", async () => {
    renderWithProviders(<Settings />);
    const testBtn = await screen.findByText("Test");
    fireEvent.click(testBtn);
    expect(screen.getByText("Testing...")).toBeInTheDocument();
  });
});

describe("Settings - Connection Status", () => {
  it("shows green dot for successful connection", async () => {
    setupMocks();
    renderWithProviders(<Settings />);
    const dot = await screen.findByTitle("Connected");
    expect(dot).toBeInTheDocument();
  });

  it("shows gray dot for untested connection", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "/api/exchange-configs": [
          { ...mockConfigs[0], last_test_success: null },
        ],
        "/api/data-sources": mockDataSources,
        "/api/notifications/preferences": mockNotifPrefs,
      }),
    );
    renderWithProviders(<Settings />);
    const dot = await screen.findByTitle("Not tested");
    expect(dot).toBeInTheDocument();
  });

  it("shows red dot for failed connection", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "/api/exchange-configs": [
          { ...mockConfigs[0], last_test_success: false, last_test_error: "Auth failed" },
        ],
        "/api/data-sources": mockDataSources,
        "/api/notifications/preferences": mockNotifPrefs,
      }),
    );
    renderWithProviders(<Settings />);
    const dot = await screen.findByTitle("Auth failed");
    expect(dot).toBeInTheDocument();
  });
});

describe("Settings - Masked API Key", () => {
  beforeEach(setupMocks);

  it("shows masked API key on config card", async () => {
    renderWithProviders(<Settings />);
    expect(await screen.findByText("Key: abc...xyz")).toBeInTheDocument();
  });
});

describe("Settings - Empty State", () => {
  it("shows empty message when no configs exist", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        "/api/exchange-configs": [],
        "/api/data-sources": [],
        "/api/notifications/preferences": mockNotifPrefs,
      }),
    );
    renderWithProviders(<Settings />);
    expect(
      await screen.findByText(/No exchange connections configured/),
    ).toBeInTheDocument();
  });
});
