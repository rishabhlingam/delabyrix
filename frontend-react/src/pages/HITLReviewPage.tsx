/**
 * HITLReviewPage — HITL Review Queue at /hitl
 *
 * Displays all pending review items with:
 * - border-l-4 PENDING status stripe
 * - Redacted patient inquiry well (original language default, bilingual toggle)
 * - Risk escalation flags (WarningAltFilled)
 * - Draft response editor (original language default, bilingual toggle)
 * - Rejection reason box (original language default, bilingual toggle)
 * - Square Carbon Approve/Reject buttons
 *
 * Calls POST /hitl/approve and POST /hitl/reject per architecture.md §6.4.
 * Calls POST /agent/translate for bidirectional translation toggles.
 */
import React, { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import {
  getHITLQueue,
  postHITLApprove,
  postHITLReject,
  postAgentTranslate,
  ApiError,
  type HITLItem,
} from "@/api/client";
import {
  CheckmarkFilled,
  CloseFilled,
  WarningAltFilled,
  Security,
  Time,
  Translate,
} from "@carbon/icons-react";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function statusStripe(item: HITLItem) {
  void item;
  return "border-l-[#f1c21b]";
}

/** Render [REDACTED_*] PII tokens as inline pills */
function RedactedText({ text }: { text: string }) {
  const parts = text.split(/(\[REDACTED_[A-Z0-9_]+\])/g);
  return (
    <>
      {parts.map((p, i) =>
        /^\[REDACTED_[A-Z0-9_]+\]$/.test(p) ? (
          <span
            key={i}
            className="rounded-none border border-[#c6c6c6] bg-[#e5e5e5] px-1.5 py-0.5 font-mono text-xs font-medium text-[#161616]"
          >
            {p}
          </span>
        ) : (
          <span key={i}>{p}</span>
        )
      )}
    </>
  );
}

/** Fallback rejection suffix per language when no draft content is available */
const REJECTION_SUFFIX: Record<string, string> = {
  en: "Please contact a licensed healthcare provider for further assistance.",
  es: "Por favor contacte a un proveedor de salud autorizado para más asistencia.",
  hi: "कृपया आगे की सहायता के लिए एक लाइसेंस प्राप्त स्वास्थ्य सेवा प्रदाता से संपर्क करें।",
};

const GENERIC_REJECTION: Record<string, string> = {
  en: "We are unable to process your request at this time. Please consult your healthcare provider directly for clinical guidance.",
  es: "No podemos procesar su solicitud en este momento. Por favor consulte directamente a su proveedor de salud para orientación clínica.",
  hi: "हम इस समय आपका अनुरोध संसाधित करने में असमर्थ हैं। कृपया नैदानिक मार्गदर्शन के लिए सीधे अपने स्वास्थ्य सेवा प्रदाता से संपर्क करें।",
};

/**
 * Build a concise, inquiry-specific rejection note from the draft response.
 *
 * Strategy: take the first sentence of the draft (which typically states the
 * key clinical finding, e.g. "Metamizole is restricted in the US due to …"),
 * strip any numbered-list preamble, then append a short action line in the
 * appropriate language.  Falls back to a generic message when the draft is
 * empty or too short to extract a meaningful sentence.
 */
function buildSpecificRejection(draftResponse: string, lang: string): string {
  const suffix = REJECTION_SUFFIX[lang.toLowerCase()] ?? REJECTION_SUFFIX["en"];
  const generic = GENERIC_REJECTION[lang.toLowerCase()] ?? GENERIC_REJECTION["en"];

  if (!draftResponse || !draftResponse.trim()) return generic;

  // Strip leading list markers like "1." or "•" and normalise whitespace
  const cleaned = draftResponse
    .replace(/^\s*[\d]+[.)]\s*/gm, " ")
    .replace(/\s+/g, " ")
    .trim();

  // Extract up to the first sentence-ending punctuation (. ! ?)
  const match = cleaned.match(/^(.{20,}?[.!?])/);
  if (!match) return generic;

  const firstSentence = match[1].trim();
  // Guard against extracting a sentence that is a numbered-list artefact
  // (pure digits + punctuation with no real words)
  if (firstSentence.length < 20) return generic;

  return `${firstSentence} ${suffix}`;
}

// ─── Bilingual toggle button ───────────────────────────────────────────────────

interface BilingualToggleProps {
  showingOriginal: boolean;
  sourceLang: string;
  onToggle: () => void;
  loading?: boolean;
}

function BilingualToggle({ showingOriginal, sourceLang, onToggle, loading }: BilingualToggleProps) {
  const langLabel = sourceLang.toUpperCase();
  return (
    <button
      type="button"
      disabled={loading}
      onClick={onToggle}
      className="inline-flex items-center text-xs font-medium text-[#0f62fe] hover:underline disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0f62fe]"
    >
      <Translate aria-hidden="true" className="mr-1 h-3.5 w-3.5" />
      {showingOriginal ? "Translate to English" : `Show Original (${langLabel})`}
    </button>
  );
}

// ─── Single review card ───────────────────────────────────────────────────────

interface ReviewCardProps {
  item: HITLItem;
  onResolved: (reviewId: string) => void;
}

function ReviewCard({ item, onResolved }: ReviewCardProps) {
  const sourceLang = item.source_language || "en";
  const isNonEnglish = sourceLang.toLowerCase() !== "en";

  // ── Patient inquiry toggle ────────────────────────────────────────────────
  const [inquiryShowOriginal, setInquiryShowOriginal] = useState(true);
  const [inquiryTranslating, setInquiryTranslating] = useState(false);
  const [inquiryEnglish, setInquiryEnglish] = useState<string | null>(
    item.english_inquiry ?? null
  );
  const originalInquiry =
    item.redacted_original_text ?? item.pipeline_trace?.translation ?? "(no text)";

  async function toggleInquiry() {
    if (!inquiryShowOriginal) {
      setInquiryShowOriginal(true);
      return;
    }
    // Translate original → English if not cached
    if (!inquiryEnglish) {
      setInquiryTranslating(true);
      try {
        const r = await postAgentTranslate({
          text: originalInquiry,
          source_lang: sourceLang,
          target_lang: "en",
        });
        setInquiryEnglish(r.translated_text);
      } catch {
        // fall back silently — keep showing original
        setInquiryTranslating(false);
        return;
      }
      setInquiryTranslating(false);
    }
    setInquiryShowOriginal(false);
  }

  // ── Draft response toggle ─────────────────────────────────────────────────
  const [editedResponse, setEditedResponse] = useState(item.draft_response);
  const [draftShowOriginal, setDraftShowOriginal] = useState(true);
  const [draftTranslating, setDraftTranslating] = useState(false);
  const [draftEnglish, setDraftEnglish] = useState<string | null>(
    item.draft_response_english ?? null
  );
  const [showEditor, setShowEditor] = useState(false);
  const [reviewerNote, setReviewerNote] = useState("");

  async function toggleDraft() {
    if (!draftShowOriginal) {
      // switching back to original: sync the editedResponse to match what was last set
      setDraftShowOriginal(true);
      return;
    }
    // Translate current editedResponse → English
    setDraftTranslating(true);
    try {
      const r = await postAgentTranslate({
        text: editedResponse,
        source_lang: sourceLang,
        target_lang: "en",
      });
      setDraftEnglish(r.translated_text);
    } catch {
      setDraftTranslating(false);
      return;
    }
    setDraftTranslating(false);
    setDraftShowOriginal(false);
  }

  // ── Rejection reason toggle ───────────────────────────────────────────────
  const [rejectionReason, setRejectionReason] = useState("");
  const [rejectionShowOriginal, setRejectionShowOriginal] = useState(true);
  const [rejectionTranslating, setRejectionTranslating] = useState(false);
  const [rejectionEnglish, setRejectionEnglish] = useState<string | null>(null);

  async function toggleRejection() {
    if (!rejectionShowOriginal) {
      setRejectionShowOriginal(true);
      return;
    }
    setRejectionTranslating(true);
    try {
      const r = await postAgentTranslate({
        text: rejectionReason || buildSpecificRejection(editedResponse, sourceLang),
        source_lang: sourceLang,
        target_lang: "en",
      });
      setRejectionEnglish(r.translated_text);
    } catch {
      setRejectionTranslating(false);
      return;
    }
    setRejectionTranslating(false);
    setRejectionShowOriginal(false);
  }

  // ── Action state ──────────────────────────────────────────────────────────
  const [action, setAction] = useState<"approving" | "rejecting" | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Seed rejection reason from the draft content (inquiry-specific) when entering reject mode
  function enterRejectMode() {
    setRejectionReason(buildSpecificRejection(editedResponse, sourceLang));
    setRejectionShowOriginal(true);
    setRejectionEnglish(null);
    setAction("rejecting");
  }

  // Detect possible risk flags from pipeline_trace
  const hasMedFlags = item.pipeline_trace?.medical_interpretation
    ?.toLowerCase()
    .includes("flag");
  const isAmbiguous = item.pipeline_trace?.jurisdiction?.toLowerCase().includes("ambiguous");

  async function handleApprove() {
    setAction("approving");
    setError(null);
    try {
      await postHITLApprove({
        review_id: item.review_id,
        approved_response: editedResponse,
        reviewer_note: reviewerNote || null,
      });
      onResolved(item.review_id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Approval failed.");
      setAction(null);
    }
  }

  async function handleReject() {
    if (!rejectionReason.trim()) {
      setError("Please provide a rejection reason before confirming.");
      return;
    }
    setError(null);
    try {
      await postHITLReject({
        review_id: item.review_id,
        rejection_reason: rejectionReason.trim(),
        rejection_reason_english: rejectionEnglish ?? undefined,
      });
      onResolved(item.review_id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Rejection failed.");
      setAction(null);
    }
  }

  return (
    <Card
      className={`gap-0 rounded-none border border-[#e0e0e0] bg-white py-0 shadow-none ring-0 border-l-4 ${statusStripe(item)}`}
    >
      {/* Header */}
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 rounded-none bg-[#f4f4f4]/60 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            variant="outline"
            className="h-auto rounded-none border-[#f1c21b] bg-[#fcf4d6] px-2 py-0.5 text-xs font-medium text-[#161616]"
          >
            <Time aria-hidden="true" className="mr-1.5 h-3.5 w-3.5 text-[#b28600]" />
            Pending Clinical Review
          </Badge>
          {/* Jurisdiction badge */}
          <Badge
            variant="outline"
            className="h-auto rounded-none border-[#a6c8ff] bg-[#edf5ff] px-2 py-0.5 font-mono text-xs font-normal text-[#0043ce]"
          >
            <Security aria-hidden="true" className="mr-1 h-3.5 w-3.5" />
            {item.pipeline_trace?.jurisdiction ?? item.country}
          </Badge>
          {/* Language badge */}
          {sourceLang !== "en" && (
            <Badge
              variant="outline"
              className="h-auto rounded-none border-[#a6c8ff] bg-[#edf5ff] px-2 py-0.5 font-mono text-xs font-normal text-[#0043ce]"
            >
              {sourceLang.toUpperCase()}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-[#525252] tabular-nums">
            {new Date(item.submitted_at).toLocaleString()}
          </span>
          <span className="font-mono text-xs text-[#525252]">
            {item.user_type}
          </span>
        </div>
      </CardHeader>
      <Separator className="bg-[#e0e0e0]" />

      {/* Body */}
      <CardContent className="space-y-4 p-4">
        {/* Risk flags */}
        {(hasMedFlags || isAmbiguous) && (
          <div className="flex flex-wrap gap-2">
            {hasMedFlags && (
              <span className="inline-flex items-center bg-[#fff1f1] px-2 py-0.5 text-xs font-medium text-[#da1e28]">
                <WarningAltFilled aria-hidden="true" className="mr-1 h-3.5 w-3.5" />
                Medication Flag Detected
              </span>
            )}
            {isAmbiguous && (
              <span className="inline-flex items-center bg-[#fff1f1] px-2 py-0.5 text-xs font-medium text-[#da1e28]">
                <WarningAltFilled aria-hidden="true" className="mr-1 h-3.5 w-3.5" />
                Ambiguous Jurisdiction
              </span>
            )}
          </div>
        )}

        {/* Patient inquiry (redacted) — original language default with bilingual toggle */}
        <div>
          <div className="mb-1.5 flex items-center gap-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
              Patient Inquiry (Redacted)
            </p>
            {isNonEnglish && (
              <BilingualToggle
                showingOriginal={inquiryShowOriginal}
                sourceLang={sourceLang}
                onToggle={toggleInquiry}
                loading={inquiryTranslating}
              />
            )}
          </div>
          <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 text-sm leading-relaxed text-[#161616]">
            {inquiryTranslating ? (
              <span className="text-[#525252]">Translating…</span>
            ) : (
              <RedactedText
                text={
                  inquiryShowOriginal
                    ? originalInquiry
                    : (inquiryEnglish ?? originalInquiry)
                }
              />
            )}
          </div>
        </div>

        {/* Draft response editor — original language default with bilingual toggle */}
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
                Draft Response
              </p>
              {isNonEnglish && (
                <BilingualToggle
                  showingOriginal={draftShowOriginal}
                  sourceLang={sourceLang}
                  onToggle={toggleDraft}
                  loading={draftTranslating}
                />
              )}
            </div>
            <button
              type="button"
              aria-expanded={showEditor}
              className="text-xs font-medium text-[#0f62fe] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0f62fe]"
              onClick={() => setShowEditor((v) => !v)}
            >
              {showEditor ? "Collapse editor" : "Edit response"}
            </button>
          </div>
          {draftTranslating ? (
            <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 text-sm text-[#525252]">
              Translating…
            </div>
          ) : showEditor && draftShowOriginal ? (
            <Textarea
              aria-label="Draft response"
              value={editedResponse}
              onChange={(e) => {
                setEditedResponse(e.target.value);
                // Invalidate cached English translation on edit
                setDraftEnglish(null);
              }}
              rows={5}
              className="rounded-none"
            />
          ) : (
            <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 text-sm leading-relaxed text-[#161616]">
              {draftShowOriginal ? editedResponse : (draftEnglish ?? editedResponse)}
            </div>
          )}
        </div>

        {/* Optional reviewer note */}
        {showEditor && (
          <div>
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-[#525252]">
                Reviewer Note (optional, internal)
              </p>
              <Textarea
                aria-label="Reviewer note"
                value={reviewerNote}
                onChange={(e) => setReviewerNote(e.target.value)}
                placeholder="Internal note for audit trail…"
                rows={2}
                className="rounded-none"
              />
          </div>
        )}

        {/* Rejection reason (shown when reject is active) */}
        {action === "rejecting" && (
          <div>
            <div className="mb-1.5 flex items-center gap-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
                Rejection Reason <span className="text-[#da1e28]">*</span>
              </p>
              {isNonEnglish && (
                <BilingualToggle
                  showingOriginal={rejectionShowOriginal}
                  sourceLang={sourceLang}
                  onToggle={toggleRejection}
                  loading={rejectionTranslating}
                />
              )}
            </div>
            {rejectionTranslating ? (
              <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 text-sm text-[#525252]">
                Translating…
              </div>
            ) : rejectionShowOriginal ? (
              <Textarea
                aria-label="Rejection reason"
                value={rejectionReason}
                onChange={(e) => {
                  setRejectionReason(e.target.value);
                  setRejectionEnglish(null);
                  if (e.target.value.trim()) setError(null);
                }}
                placeholder="Reason for rejecting this response (required)…"
                rows={2}
                className="rounded-none"
              />
            ) : (
              <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 text-sm leading-relaxed text-[#161616]">
                {rejectionEnglish ?? rejectionReason}
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="border border-[#da1e28] bg-[#fff1f1] p-2 text-xs text-[#a2191f]">
            {error}
          </div>
        )}
      </CardContent>

      <Separator className="bg-[#e0e0e0]" />

      {/* Footer actions */}
      <CardFooter className="flex flex-wrap items-center justify-between gap-3 rounded-none border-0 bg-[#f4f4f4]/40 px-4 py-2.5">
        <span className="font-mono text-xs text-[#525252]">
          ID: {item.review_id}
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            className="h-8 rounded-none border-[#da1e28] text-xs font-medium text-[#da1e28] hover:bg-[#da1e28] hover:text-white"
            disabled={action === "approving"}
            onClick={
              action === "rejecting"
                ? handleReject
                : enterRejectMode
            }
          >
            <CloseFilled aria-hidden="true" className="mr-1.5 h-3.5 w-3.5" />
            {action === "rejecting" ? "Confirm Reject" : "Reject"}
          </Button>
          <Button
            size="sm"
            className="h-8 rounded-none bg-[#0f62fe] text-xs font-medium text-white hover:bg-[#0353e9]"
            disabled={action === "rejecting"}
            onClick={handleApprove}
          >
            <CheckmarkFilled aria-hidden="true" className="mr-1.5 h-3.5 w-3.5" />
            Approve Guidance
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function HITLReviewPage() {
  const [items, setItems] = useState<HITLItem[]>([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadQueue = useCallback(async () => {
    try {
      const q = await getHITLQueue();
      setItems(q.items);
      setPendingCount(q.pending_count);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load queue.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  function handleResolved(reviewId: string) {
    setItems((prev) => prev.filter((i) => i.review_id !== reviewId));
    setPendingCount((n) => Math.max(0, n - 1));
  }

  return (
    <div className="flex flex-col gap-4 py-6">
      {/* Page title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-base font-medium text-[#161616]">
            HITL Clinical Review Queue
          </h1>
          <p className="mt-1 text-sm text-[#525252]">
            Review and approve escalated patient queries before they are released.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {pendingCount > 0 && (
            <span className="inline-flex items-center rounded-none border border-[#f1c21b] bg-[#fcf4d6] px-2 py-0.5 font-mono text-xs font-medium text-[#161616] tabular-nums">
              {pendingCount} pending
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            className="h-8 rounded-none text-xs"
            onClick={loadQueue}
          >
            Refresh
          </Button>
        </div>
      </div>

      <Separator className="bg-[#e0e0e0]" />

      {loading && (
        <p className="text-sm text-[#525252]">Loading review queue…</p>
      )}

      {error && (
        <div className="border border-[#da1e28] bg-[#fff1f1] p-3 text-sm text-[#a2191f]">
          {error}
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="border border-[#e0e0e0] bg-white p-8 text-center text-sm text-[#525252]">
          <CheckmarkFilled aria-hidden="true" className="mx-auto mb-2 h-6 w-6 text-[#24a148]" />
          No pending reviews. All caught up!
        </div>
      )}

      <div className="flex flex-col gap-4">
        {items.map((item) => (
          <ReviewCard key={item.review_id} item={item} onResolved={handleResolved} />
        ))}
      </div>
    </div>
  );
}
