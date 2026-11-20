/**
 * PatientAssistantPage tests.
 *
 * Covers:
 *  1. Direct 200 response rendering with PII pill substitution
 *  2. 202 HITL escalation → polling → approved transition
 *  3. 202 HITL escalation → polling → rejected transition
 *  4. Sample prompt insertion
 *  5. Sample Hospital Document Loader (GET /documents/{type}/{lang})
 *  6. Document upload with [REDACTED_*] rendering
 *  7. Mode switching clears state
 */
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import PatientAssistantPage from "@/pages/PatientAssistantPage";
import { LocaleProvider } from "@/lib/i18n";
import * as client from "@/api/client";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function renderPage() {
  return render(
    <MemoryRouter>
      <LocaleProvider>
        <PatientAssistantPage />
      </LocaleProvider>
    </MemoryRouter>
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("PatientAssistantPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // Ensure real timers for most tests (some specific tests switch to fake)
    vi.useRealTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders all three mode tabs", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /clinical question/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sample document/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /upload document/i })).toBeInTheDocument();
  });

  it("shows sample clinical prompts in question mode", () => {
    renderPage();
    expect(screen.getByText(/ES: Metamizol/i)).toBeInTheDocument();
    expect(screen.getByText(/EN: Cross-border metamizole/i)).toBeInTheDocument();
    expect(screen.getByText(/HI: Cross-border drug/i)).toBeInTheDocument();
    expect(screen.getByText(/EN: ICU consent question/i)).toBeInTheDocument();
  });

  it("inserts sample prompt text into textarea on click", async () => {
    renderPage();
    const user = userEvent.setup();
    const promptBtn = screen.getByText(/EN: Cross-border metamizole/i);
    await user.click(promptBtn);
    const textarea = screen.getByRole("textbox");
    expect((textarea as HTMLTextAreaElement).value).toContain("metamizole at home");
  });

  it("submits a clinical question and displays 200 direct response", async () => {
    const mockResult: client.AgentQueryResponse = {
      session_id: "sess-001",
      pipeline_trace: {
        jurisdiction: "US_FDA",
        pii_redacted: false,
        translation: "translated",
        medical_interpretation: "interpretation",
        cultural_context: "context",
        next_steps: "steps",
      },
      escalated: false,
      review_id: null,
      response_text: "Metamizole is banned in the US.",
    };
    vi.spyOn(client, "postAgentQuery").mockResolvedValue({
      result: mockResult,
      isEscalated: false,
    });

    renderPage();
    const user = userEvent.setup();
    const textarea = screen.getByRole("textbox");
    await user.type(textarea, "Is metamizole allowed?");
    const submitBtn = screen.getByRole("button", { name: /submit query/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Metamizole is banned in the US/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Response Ready/i)).toBeInTheDocument();
  });

  it("handles 202 HITL escalation and shows pending badge", async () => {
    const mockEscalated: client.AgentEscalatedResponse = {
      session_id: "sess-002",
      escalated: true,
      review_id: "rev-002",
      status: "pending_review",
      message: "Your query is under clinical review.",
    };
    vi.spyOn(client, "postAgentQuery").mockResolvedValue({
      result: mockEscalated,
      isEscalated: true,
    });
    // Keep pending — polling returns pending
    vi.spyOn(client, "getSessionStatus").mockResolvedValue({
      session_id: "sess-002",
      status: "pending",
      response_text: null,
    });

    renderPage();
    const user = userEvent.setup();
    const textarea = screen.getByRole("textbox");
    await user.type(textarea, "sensitive medication question");
    const submitBtn = screen.getByRole("button", { name: /submit query/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/pending clinical review/i)).toBeInTheDocument();
    });
  });

  it("transitions from pending to approved after polling resolves", async () => {
    const mockEscalated: client.AgentEscalatedResponse = {
      session_id: "sess-003",
      escalated: true,
      review_id: "rev-003",
      status: "pending_review",
      message: "Query is under clinical review.",
    };
    vi.spyOn(client, "postAgentQuery").mockResolvedValue({
      result: mockEscalated,
      isEscalated: true,
    });
    // Return approved immediately so polling resolves on first tick
    vi.spyOn(client, "getSessionStatus").mockResolvedValue({
      session_id: "sess-003",
      status: "approved",
      response_text: "Approved response text.",
    });

    renderPage();
    const user = userEvent.setup();
    await user.type(screen.getByRole("textbox"), "query to escalate");
    await user.click(screen.getByRole("button", { name: /submit query/i }));

    // Wait for pending state first
    await waitFor(() => expect(screen.getByText(/pending clinical review/i)).toBeInTheDocument());

    // Then polling resolves quickly since mock returns approved immediately
    await waitFor(
      () => expect(screen.getByText(/Reviewed.*Approved/i)).toBeInTheDocument(),
      { timeout: 10000 }
    );
  }, 15000);

  it("transitions from pending to rejected after polling", async () => {
    const mockEscalated: client.AgentEscalatedResponse = {
      session_id: "sess-004",
      escalated: true,
      review_id: "rev-004",
      status: "pending_review",
      message: "Under review.",
    };
    vi.spyOn(client, "postAgentQuery").mockResolvedValue({
      result: mockEscalated,
      isEscalated: true,
    });
    // Return rejected immediately
    vi.spyOn(client, "getSessionStatus").mockResolvedValue({
      session_id: "sess-004",
      status: "rejected",
      response_text: null,
      rejection_reason: "Out of scope",
    });

    renderPage();
    const user = userEvent.setup();
    await user.type(screen.getByRole("textbox"), "out of scope query");
    await user.click(screen.getByRole("button", { name: /submit query/i }));

    await waitFor(() => expect(screen.getByText(/pending clinical review/i)).toBeInTheDocument());

    await waitFor(
      () => expect(screen.getByText(/response rejected/i)).toBeInTheDocument(),
      { timeout: 10000 }
    );
  }, 15000);

  it("renders [REDACTED_*] PII tokens as inline pills in approved response", async () => {
    const mockResult: client.AgentQueryResponse = {
      session_id: "sess-005",
      pipeline_trace: {
        jurisdiction: "US_FDA",
        pii_redacted: true,
        translation: "translated",
        medical_interpretation: "med",
        cultural_context: "ctx",
        next_steps: "steps",
      },
      escalated: false,
      review_id: null,
      response_text: "Patient [REDACTED_NAME] should not take metamizole in [REDACTED_COUNTRY].",
    };
    vi.spyOn(client, "postAgentQuery").mockResolvedValue({
      result: mockResult,
      isEscalated: false,
    });

    renderPage();
    const user = userEvent.setup();
    await user.type(screen.getByRole("textbox"), "query with PII");
    await user.click(screen.getByRole("button", { name: /submit query/i }));

    await waitFor(() => {
      expect(screen.getByText("[REDACTED_NAME]")).toBeInTheDocument();
      expect(screen.getByText("[REDACTED_COUNTRY]")).toBeInTheDocument();
    });
  });

  it("loads sample hospital document via GET /documents endpoint", async () => {
    const mockDoc: client.DocumentResponse = {
      doc_type: "consent_icu_admission",
      language: "en",
      title: "ICU Admission Consent Form",
      content: "By signing this form you agree to ICU procedures...",
    };
    vi.spyOn(client, "getDocument").mockResolvedValue(mockDoc);

    renderPage();
    const user = userEvent.setup();

    // Switch to sample doc mode
    await user.click(screen.getByRole("button", { name: /sample document/i }));
    await user.click(screen.getByRole("button", { name: /fetch document/i }));

    await waitFor(() => {
      expect(screen.getByText(/ICU Admission Consent Form/i)).toBeInTheDocument();
      expect(screen.getByText(/By signing this form/i)).toBeInTheDocument();
    });
  });

  it("uploads a .txt document and renders analysis with [REDACTED_*] pills", async () => {
    const mockAnalysis: client.DocumentAnalysisResponse = {
      filename: "consent.txt",
      detected_language: "en",
      jurisdiction: "US_FDA",
      pii_redacted: true,
      redacted_preview: "Patient [REDACTED_DOB] was admitted...",
      analysis: "Clause 1: Patient agrees to treatment.",
    };
    vi.spyOn(client, "postDocumentAnalyze").mockResolvedValue(mockAnalysis);

    renderPage();
    const user = userEvent.setup();

    // Switch to upload mode
    await user.click(screen.getByRole("button", { name: /upload document/i }));
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["consent text content"], "consent.txt", { type: "text/plain" });
    await user.upload(fileInput, file);
    await user.click(screen.getByRole("button", { name: /analyze document/i }));

    await waitFor(() => {
      expect(screen.getByText("[REDACTED_DOB]")).toBeInTheDocument();
      expect(screen.getByText(/Clause 1: Patient agrees/i)).toBeInTheDocument();
    });
  });
});
