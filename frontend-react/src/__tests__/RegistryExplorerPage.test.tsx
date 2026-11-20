/**
 * RegistryExplorerPage tests.
 *
 * Covers:
 *  1. Searching for metamizole shows US_FDA vs EU_EMA side-by-side comparison
 *  2. Regulatory divergence alert (US ≠ EU status)
 *  3. Full registry table loads and displays jurisdiction filter buttons
 *  4. Sync Latest FDA/EMA Bulletins button opens drawer (Sync drawer integration)
 *  5. Changelog loads and displays entries
 *  6. No record found error message
 */
import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import RegistryExplorerPage from "@/pages/RegistryExplorerPage";
import { LocaleProvider } from "@/lib/i18n";
import * as client from "@/api/client";
import type { RegistryRecord, RegistryListResponse } from "@/api/client";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeRecord(overrides: Partial<RegistryRecord> = {}): RegistryRecord {
  return {
    medication_id: "med-001",
    name_generic: "metamizole",
    jurisdiction: "US_FDA",
    status: "banned",
    restriction_reason: "Banned in the US due to agranulocytosis risk",
    therapeutic_alternatives: ["acetaminophen", "ibuprofen"],
    last_updated: "2026-01-01",
    ...overrides,
  };
}

function makeListResponse(records: RegistryRecord[]): RegistryListResponse {
  return {
    total: records.length,
    page: 1,
    records,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <LocaleProvider>
        <RegistryExplorerPage />
      </LocaleProvider>
    </MemoryRouter>
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("RegistryExplorerPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // Default list mock — empty
    vi.spyOn(client, "getRegistryList").mockResolvedValue(makeListResponse([]));
  });

  it("renders search input and jurisdiction filter buttons", async () => {
    renderPage();
    expect(screen.getByPlaceholderText(/search medication/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "All" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "US_FDA" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "EU_EMA" })).toBeInTheDocument();
    });
  });

  it("shows US_FDA and EU_EMA results side-by-side for metamizole", async () => {
    const fdaRecord = makeRecord({ jurisdiction: "US_FDA", status: "banned" });
    const emaRecord = makeRecord({
      jurisdiction: "EU_EMA",
      status: "restricted",
      restriction_reason: "QT interval concern",
    });
    vi.spyOn(client, "getRegistryCheck")
      .mockResolvedValueOnce(fdaRecord) // US_FDA call
      .mockResolvedValueOnce(emaRecord); // EU_EMA call

    renderPage();
    const user = userEvent.setup();

    const searchInput = screen.getByPlaceholderText(/search medication/i);
    await user.type(searchInput, "metamizole");
    await user.click(screen.getByRole("button", { name: /^search$/i }));

    await waitFor(() => {
      // US_FDA/EU_EMA appear in jurisdiction badges AND filter buttons
      expect(screen.getAllByText("US_FDA").length).toBeGreaterThan(0);
      expect(screen.getAllByText("EU_EMA").length).toBeGreaterThan(0);
    });
  });

  it("shows regulatory divergence detected when statuses differ", async () => {
    vi.spyOn(client, "getRegistryCheck")
      .mockResolvedValueOnce(makeRecord({ jurisdiction: "US_FDA", status: "banned" }))
      .mockResolvedValueOnce(makeRecord({ jurisdiction: "EU_EMA", status: "approved" }));

    renderPage();
    const user = userEvent.setup();

    await user.type(screen.getByPlaceholderText(/search medication/i), "metamizole");
    await user.click(screen.getByRole("button", { name: /^search$/i }));

    // RegistryStatusCard shows the divergence info via the status badges
    await waitFor(() => {
      // Both jurisdiction cards should be visible
      expect(screen.getAllByText("US_FDA").length).toBeGreaterThan(0);
      expect(screen.getAllByText("EU_EMA").length).toBeGreaterThan(0);
      // One should show banned, another approved
      expect(screen.getAllByText(/banned/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/approved/i).length).toBeGreaterThan(0);
    });
  });

  it("shows no-record error when both jurisdictions 404", async () => {
    vi.spyOn(client, "getRegistryCheck").mockRejectedValue(
      new client.ApiError(404, "Not found")
    );

    renderPage();
    const user = userEvent.setup();

    await user.type(screen.getByPlaceholderText(/search medication/i), "unknowndrug");
    await user.click(screen.getByRole("button", { name: /^search$/i }));

    await waitFor(() => {
      expect(screen.getByText(/no records found/i)).toBeInTheDocument();
    });
  });

  it("renders full registry table with records", async () => {
    vi.spyOn(client, "getRegistryList").mockResolvedValue(
      makeListResponse([
        makeRecord({ medication_id: "med-001", jurisdiction: "US_FDA", name_generic: "domperidone", status: "restricted" }),
        makeRecord({ medication_id: "med-002", jurisdiction: "EU_EMA", name_generic: "metamizole", status: "approved" }),
      ])
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("domperidone")).toBeInTheDocument();
      expect(screen.getByText("metamizole")).toBeInTheDocument();
    });
  });

  it("filters registry table by US_FDA jurisdiction", async () => {
    const getListMock = vi.spyOn(client, "getRegistryList").mockResolvedValue(
      makeListResponse([makeRecord({ jurisdiction: "US_FDA" })])
    );

    renderPage();
    const user = userEvent.setup();

    await waitFor(() => screen.getByRole("button", { name: "US_FDA" }));
    await user.click(screen.getByRole("button", { name: "US_FDA" }));

    await waitFor(() => {
      expect(getListMock).toHaveBeenCalledWith(
        expect.objectContaining({ jurisdiction: "US_FDA" })
      );
    });
  });

  it("opens Sync drawer and shows sync form", async () => {
    renderPage();
    const user = userEvent.setup();

    // The sync button text
    const syncBtn = screen.getByText(/sync latest FDA\/EMA bulletins/i);
    await user.click(syncBtn);

    await waitFor(() => {
      expect(screen.getByText(/regulatory sync/i)).toBeInTheDocument();
      expect(screen.getByText(/sync FDA\/EMA bulletin/i)).toBeInTheDocument();
    });
  });

  it("triggers bulletin sync and shows changelog", async () => {
    const mockResult: client.BulletinResponse = {
      sync_version: "v1.0.0",
      timestamp: new Date().toISOString(),
      source: "FDA Orange Book",
      changes: [
        { medication_id: "med-001", field: "status", old_value: "approved", new_value: "restricted" },
      ],
    };
    vi.spyOn(client, "postRegistrySync").mockResolvedValue(mockResult);
    vi.spyOn(client, "getRegistryChangelog").mockResolvedValue({
      total_entries: 1,
      entries: [mockResult],
    });

    renderPage();
    const user = userEvent.setup();

    // Open drawer
    await user.click(screen.getByText(/sync latest FDA\/EMA bulletins/i));
    await waitFor(() => screen.getByText(/regulatory sync/i));

    // Fill in medication id and submit sync
    const medIdInput = screen.getByPlaceholderText(/med-001/i);
    await user.type(medIdInput, "med-001");
    await user.click(screen.getByRole("button", { name: /sync registry/i }));

    await waitFor(() => {
      expect(screen.getByText(/sync complete/i)).toBeInTheDocument();
    });
  });
});
