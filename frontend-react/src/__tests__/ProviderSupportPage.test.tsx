/**
 * ProviderSupportPage tests.
 *
 * Covers:
 *  1. Three tabs render correctly
 *  2. Sample provider scenarios can be inserted
 *  3. Provider query submission uses user_type: "provider"
 *  4. HITL escalation handling in provider context
 *  5. Policy Checklist tab — fetches document
 *  6. Drug Alert Checker tab — shows status and alternatives
 *  7. Drug Alert Checker — not found state
 */
import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import ProviderSupportPage from "@/pages/ProviderSupportPage";
import { LocaleProvider } from "@/lib/i18n";
import * as client from "@/api/client";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function renderPage() {
  return render(
    <MemoryRouter>
      <LocaleProvider>
        <ProviderSupportPage />
      </LocaleProvider>
    </MemoryRouter>
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("ProviderSupportPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders all three tabs", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /procedure explanation/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /local policy checklist/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /drug alert checker/i })).toBeInTheDocument();
  });

  it("shows sample provider scenarios", () => {
    renderPage();
    expect(screen.getByText(/laparoscopic cholecystectomy/i)).toBeInTheDocument();
    expect(screen.getByText(/ICU admission for Hindi-speaking patient/i)).toBeInTheDocument();
    expect(screen.getByText(/cross-border metamizole conflict alert/i)).toBeInTheDocument();
  });

  it("inserts sample scenario text on click", async () => {
    renderPage();
    const user = userEvent.setup();
    await user.click(screen.getByText(/cross-border metamizole conflict alert/i));
    const textarea = screen.getByRole("textbox");
    expect((textarea as HTMLTextAreaElement).value).toContain("metamizole");
  });

  it("submits query with user_type=provider", async () => {
    const mockResult: client.AgentQueryResponse = {
      session_id: "prov-001",
      pipeline_trace: {
        jurisdiction: "US_FDA",
        pii_redacted: false,
        translation: "translated",
        medical_interpretation: "clinical interp",
        cultural_context: "context",
        next_steps: "steps",
      },
      escalated: false,
      review_id: null,
      response_text: "Provider guidance: advise patient accordingly.",
    };
    const postMock = vi.spyOn(client, "postAgentQuery").mockResolvedValue({
      result: mockResult,
      isEscalated: false,
    });

    renderPage();
    const user = userEvent.setup();
    await user.type(screen.getByRole("textbox"), "Clinical provider question");
    await user.click(screen.getByRole("button", { name: /generate explanation/i }));

    await waitFor(() => {
      expect(screen.getByText(/Provider guidance/i)).toBeInTheDocument();
    });
    expect(postMock).toHaveBeenCalledWith(
      expect.objectContaining({ user_type: "provider" })
    );
  });

  it("shows pending badge on 202 escalation", async () => {
    const mockEscalated: client.AgentEscalatedResponse = {
      session_id: "prov-002",
      escalated: true,
      review_id: "rev-prov-002",
      status: "pending_review",
      message: "Provider query under review.",
    };
    vi.spyOn(client, "postAgentQuery").mockResolvedValue({
      result: mockEscalated,
      isEscalated: true,
    });
    vi.spyOn(client, "getSessionStatus").mockResolvedValue({
      session_id: "prov-002",
      status: "pending",
      response_text: null,
    });

    renderPage();
    const user = userEvent.setup();
    await user.type(screen.getByRole("textbox"), "escalation trigger query");
    await user.click(screen.getByRole("button", { name: /generate explanation/i }));

    await waitFor(() => {
      expect(screen.getByText(/pending clinical review/i)).toBeInTheDocument();
    });
  });

  it("Policy Checklist tab: loads document on button click", async () => {
    const mockDoc: client.DocumentResponse = {
      doc_type: "consent_surgery",
      language: "en",
      title: "Surgery Consent Form",
      content: "By proceeding, you consent to the surgical procedure...",
    };
    vi.spyOn(client, "getDocument").mockResolvedValue(mockDoc);

    renderPage();
    const user = userEvent.setup();

    // Switch to Policy Checklist tab
    await user.click(screen.getByRole("button", { name: /local policy checklist/i }));
    await user.click(screen.getByRole("button", { name: /load policy document/i }));

    await waitFor(() => {
      expect(screen.getByText(/Surgery Consent Form/i)).toBeInTheDocument();
      expect(screen.getByText(/By proceeding, you consent/i)).toBeInTheDocument();
    });
  });

  it("Drug Alert Checker tab: shows banned status and alternatives", async () => {
    const mockRecord: client.RegistryRecord = {
      medication_id: "med-002",
      name_generic: "metamizole",
      jurisdiction: "US_FDA",
      status: "banned",
      restriction_reason: "Agranulocytosis risk",
      therapeutic_alternatives: ["acetaminophen", "ibuprofen"],
      last_updated: "2026-01-01",
    };
    vi.spyOn(client, "getRegistryCheck").mockResolvedValue(mockRecord);

    renderPage();
    const user = userEvent.setup();

    // Switch to Drug Alert Checker tab
    await user.click(screen.getByRole("button", { name: /drug alert checker/i }));

    const medInput = screen.getByPlaceholderText(/medication name \(INN or brand/i);
    await user.type(medInput, "metamizole");
    await user.click(screen.getByRole("button", { name: /check medication/i }));

    await waitFor(() => {
      // "banned" appears in description text too — use getAllBy
      expect(screen.getAllByText(/\bBanned\b/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Agranulocytosis risk/i)).toBeInTheDocument();
      expect(screen.getByText("acetaminophen")).toBeInTheDocument();
      expect(screen.getByText("ibuprofen")).toBeInTheDocument();
    });
  });

  it("Drug Alert Checker tab: shows not-found message for unknown drug", async () => {
    vi.spyOn(client, "getRegistryCheck").mockRejectedValue(
      new client.ApiError(404, "Not found")
    );

    renderPage();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /drug alert checker/i }));
    await user.type(screen.getByPlaceholderText(/medication name \(INN or brand/i), "unknowndrug");
    await user.click(screen.getByRole("button", { name: /check medication/i }));

    await waitFor(() => {
      expect(screen.getByText(/no record found/i)).toBeInTheDocument();
    });
  });
});
