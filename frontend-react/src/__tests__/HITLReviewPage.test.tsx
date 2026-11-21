/**
 * HITLReviewPage tests.
 *
 * Covers:
 *  1. Renders pending items with border-l-4 stripe classes
 *  2. Reject button requires non-empty rejection reason (validation)
 *  3. Edit draft response then approve — sends edited_response to /hitl/approve
 *  4. Full two-step rejection with reason → calls /hitl/reject
 *  5. Resolved items are removed from the list immediately
 *  6. Badge count updates on resolution
 *  7. Empty queue shows "All caught up" state
 *  8. Bilingual: non-English item shows "Translate to English" toggle on inquiry
 *  9. Bilingual: non-English item shows "Translate to English" toggle on draft
 * 10. Bilingual: rejection box pre-filled with native-language default
 * 11. Bilingual: rejection box shows toggle for non-English items
 * 12. English-only item does NOT show translate toggles
 * 13. rejection_reason_english sent to /hitl/reject when translated
 */
import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import HITLReviewPage from "@/pages/HITLReviewPage";
import { LocaleProvider } from "@/lib/i18n";
import * as client from "@/api/client";
import type { HITLItem, HITLQueueResponse } from "@/api/client";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeItem(overrides: Partial<HITLItem> = {}): HITLItem {
  return {
    review_id: "rev-abc",
    session_id: "sess-abc",
    submitted_at: new Date().toISOString(),
    user_type: "patient",
    country: "US",
    pipeline_trace: {
      jurisdiction: "US_FDA",
      pii_redacted: false,
      translation: "Patient translation",
      medical_interpretation: "medical note",
      cultural_context: "cultural info",
      next_steps: "next steps",
    },
    draft_response: "Draft guidance for patient.",
    source_language: "en",
    ...overrides,
  };
}

function makeSpanishItem(overrides: Partial<HITLItem> = {}): HITLItem {
  return makeItem({
    source_language: "es",
    redacted_original_text: "Mi pregunta original en español.",
    english_inquiry: "My original question in Spanish.",
    draft_response: "Mi respuesta en español.",
    draft_response_english: "My response in English.",
    ...overrides,
  });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <LocaleProvider>
        <HITLReviewPage />
      </LocaleProvider>
    </MemoryRouter>
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("HITLReviewPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders pending items with PENDING badge and border-l-4 stripe", async () => {
    const queueData: HITLQueueResponse = {
      pending_count: 1,
      items: [makeItem()],
    };
    vi.spyOn(client, "getHITLQueue").mockResolvedValue(queueData);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Pending Clinical Review/i)).toBeInTheDocument();
    });
    const cards = document.querySelectorAll(".border-l-\\[\\#f1c21b\\]");
    expect(cards.length).toBeGreaterThan(0);
  });

  it("shows empty queue message when no items", async () => {
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({
      pending_count: 0,
      items: [],
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/no pending reviews/i)).toBeInTheDocument();
    });
  });

  it("shows pending count badge", async () => {
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({
      pending_count: 3,
      items: [makeItem({ review_id: "r1" }), makeItem({ review_id: "r2" }), makeItem({ review_id: "r3" })],
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/3 pending/i)).toBeInTheDocument();
    });
  });

  it("requires non-empty rejection reason before allowing rejection", async () => {
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({
      pending_count: 1,
      items: [makeItem()],
    });
    const rejectMock = vi.spyOn(client, "postHITLReject").mockResolvedValue({ status: "ok" });

    renderPage();
    const user = userEvent.setup();

    await waitFor(() => screen.getByText(/Pending Clinical Review/i));

    // Click Reject to enter rejection mode
    const rejectBtn = screen.getByRole("button", { name: /^Reject$/i });
    await user.click(rejectBtn);

    // Reject reason textarea should appear
    expect(screen.getByPlaceholderText(/reason for rejecting/i)).toBeInTheDocument();

    // Clear the textarea to simulate no reason
    const reasonTextarea = screen.getByPlaceholderText(/reason for rejecting/i);
    await user.clear(reasonTextarea);

    // Click "Confirm Reject" without filling in reason — should show validation error
    const confirmBtn = screen.getByRole("button", { name: /confirm reject/i });
    await user.click(confirmBtn);

    await waitFor(() => {
      expect(screen.getByText(/please provide a rejection reason/i)).toBeInTheDocument();
    });
    expect(rejectMock).not.toHaveBeenCalled();
  });

  it("submits rejection with reason and removes item", async () => {
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({
      pending_count: 1,
      items: [makeItem()],
    });
    const rejectMock = vi.spyOn(client, "postHITLReject").mockResolvedValue({ status: "ok" });

    renderPage();
    const user = userEvent.setup();

    await waitFor(() => screen.getByText(/Pending Clinical Review/i));

    // Enter rejection mode
    await user.click(screen.getByRole("button", { name: /^Reject$/i }));

    // Clear auto-filled and type custom reason
    const reasonTextarea = screen.getByPlaceholderText(/reason for rejecting/i);
    await user.clear(reasonTextarea);
    await user.type(reasonTextarea, "Clinical query outside scope");

    // Confirm reject
    await user.click(screen.getByRole("button", { name: /confirm reject/i }));

    await waitFor(() => {
      expect(rejectMock).toHaveBeenCalledWith(
        expect.objectContaining({
          review_id: "rev-abc",
          rejection_reason: "Clinical query outside scope",
        })
      );
    });

    // Item should be removed from list
    await waitFor(() => {
      expect(screen.getByText(/no pending reviews/i)).toBeInTheDocument();
    });
  });

  it("edits draft response and approves — sends edited text to /hitl/approve", async () => {
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({
      pending_count: 1,
      items: [makeItem({ draft_response: "Original draft." })],
    });
    const approveMock = vi.spyOn(client, "postHITLApprove").mockResolvedValue({ status: "ok" });

    renderPage();
    const user = userEvent.setup();

    await waitFor(() => screen.getByText(/Pending Clinical Review/i));

    // Open editor
    await user.click(screen.getByText(/edit response/i));

    // The textarea with draft content should be visible now
    const draftTextarea = screen.getByDisplayValue("Original draft.");
    await user.clear(draftTextarea);
    await user.type(draftTextarea, "Edited clinical guidance.");

    // Approve
    await user.click(screen.getByRole("button", { name: /approve guidance/i }));

    await waitFor(() => {
      expect(approveMock).toHaveBeenCalledWith(
        expect.objectContaining({
          review_id: "rev-abc",
          approved_response: "Edited clinical guidance.",
        })
      );
    });
  });

  it("renders [REDACTED_*] PII pills in patient inquiry well", async () => {
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({
      pending_count: 1,
      items: [
        makeItem({
          pipeline_trace: {
            jurisdiction: "US_FDA",
            pii_redacted: true,
            translation: "Patient [REDACTED_NAME] needs care",
            medical_interpretation: "med",
            cultural_context: "ctx",
            next_steps: "steps",
          },
        }),
      ],
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("[REDACTED_NAME]")).toBeInTheDocument();
    });
  });

  // ─── Bilingual toggle tests ─────────────────────────────────────────────────

  it("shows 'Translate to English' toggle on inquiry well for non-English item", async () => {
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({
      pending_count: 1,
      items: [makeSpanishItem()],
    });

    renderPage();

    await waitFor(() => screen.getByText(/Pending Clinical Review/i));

    // Should show translate toggle buttons (at least one for inquiry)
    const translateBtns = screen.getAllByText(/Translate to English/i);
    expect(translateBtns.length).toBeGreaterThan(0);
  });

  it("does NOT show translate toggle for English-only item", async () => {
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({
      pending_count: 1,
      items: [makeItem({ source_language: "en" })],
    });

    renderPage();

    await waitFor(() => screen.getByText(/Pending Clinical Review/i));

    // No translate toggles should be present
    expect(screen.queryByText(/Translate to English/i)).not.toBeInTheDocument();
  });

  it("shows 'Show Original (ES)' after translate toggle is clicked", async () => {
    const translateMock = vi.spyOn(client, "postAgentTranslate").mockResolvedValue({
      translated_text: "Translated inquiry text",
      source_lang: "es",
      target_lang: "en",
      mock: true,
    });
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({
      pending_count: 1,
      items: [makeSpanishItem({ english_inquiry: null })],
    });

    renderPage();
    const user = userEvent.setup();

    await waitFor(() => screen.getByText(/Pending Clinical Review/i));

    // Click the first "Translate to English" button (inquiry toggle)
    const translateBtns = screen.getAllByText(/Translate to English/i);
    await user.click(translateBtns[0]);

    await waitFor(() => {
      expect(translateMock).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.getAllByText(/Show Original \(ES\)/i).length).toBeGreaterThan(0);
    });
  });

  it("rejection box pre-filled with inquiry-specific content derived from the draft response", async () => {
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({
      pending_count: 1,
      items: [makeSpanishItem()],
    });

    renderPage();
    const user = userEvent.setup();

    await waitFor(() => screen.getByText(/Pending Clinical Review/i));

    // Enter reject mode
    await user.click(screen.getByRole("button", { name: /^Reject$/i }));

    // The textarea should be pre-filled with content derived from the draft's first sentence
    // ("Mi respuesta en español.") plus the Spanish action suffix — not a static generic message
    const reasonTextarea = screen.getByPlaceholderText(/reason for rejecting/i);
    const value = (reasonTextarea as HTMLTextAreaElement).value;
    // Draft's first sentence is present
    expect(value).toContain("Mi respuesta en español.");
    // Followed by the Spanish action suffix
    expect(value).toContain("Por favor contacte");
  });

  it("rejection_reason_english passed to postHITLReject after translate", async () => {
    vi.spyOn(client, "postAgentTranslate").mockResolvedValue({
      translated_text: "We are unable to process.",
      source_lang: "es",
      target_lang: "en",
      mock: true,
    });
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({
      pending_count: 1,
      items: [makeSpanishItem()],
    });
    const rejectMock = vi.spyOn(client, "postHITLReject").mockResolvedValue({ status: "ok" });

    renderPage();
    const user = userEvent.setup();

    await waitFor(() => screen.getByText(/Pending Clinical Review/i));

    // Enter reject mode
    await user.click(screen.getByRole("button", { name: /^Reject$/i }));

    // Find the translate toggle for the rejection box (last "Translate to English")
    const translateBtns = screen.getAllByText(/Translate to English/i);
    // Click the last one (rejection box toggle)
    await user.click(translateBtns[translateBtns.length - 1]);

    await waitFor(() =>
      expect(screen.getAllByText(/Show Original \(ES\)/i).length).toBeGreaterThan(0)
    );

    // Now switch back to original and confirm reject
    const showOrigBtns = screen.getAllByText(/Show Original \(ES\)/i);
    await user.click(showOrigBtns[showOrigBtns.length - 1]);

    // Confirm reject
    await user.click(screen.getByRole("button", { name: /confirm reject/i }));

    await waitFor(() => {
      expect(rejectMock).toHaveBeenCalledWith(
        expect.objectContaining({
          rejection_reason_english: "We are unable to process.",
        })
      );
    });
  });
});
