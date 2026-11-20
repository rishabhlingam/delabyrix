/**
 * HITLReviewPage — HITL Review Queue at /hitl
 *
 * Displays all pending review items with:
 * - border-l-4 PENDING status stripe
 * - Redacted patient inquiry well
 * - Risk escalation flags (WarningAltFilled)
 * - Optional response editor
 * - Square Carbon Approve/Reject buttons
 *
 * Calls POST /hitl/approve and POST /hitl/reject per architecture.md §6.4.
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
  ApiError,
  type HITLItem,
} from "@/api/client";
import {
  CheckmarkFilled,
  CloseFilled,
  WarningAltFilled,
  Security,
  Time,
} from "@carbon/icons-react";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function statusStripe(item: HITLItem) {
  // All items in queue are pending
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

// ─── Single review card ───────────────────────────────────────────────────────

interface ReviewCardProps {
  item: HITLItem;
  onResolved: (reviewId: string) => void;
}

function ReviewCard({ item, onResolved }: ReviewCardProps) {
  const [editedResponse, setEditedResponse] = useState(item.draft_response);
  const [reviewerNote, setReviewerNote] = useState("");
  const [rejectionReason, setRejectionReason] = useState("");
  const [showEditor, setShowEditor] = useState(false);
  const [action, setAction] = useState<"approving" | "rejecting" | null>(null);
  const [error, setError] = useState<string | null>(null);

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
            <Time className="mr-1.5 h-3.5 w-3.5 text-[#b28600]" />
            Pending Clinical Review
          </Badge>
          {/* Jurisdiction badge */}
          <Badge
            variant="outline"
            className="h-auto rounded-none border-[#a6c8ff] bg-[#edf5ff] px-2 py-0.5 font-mono text-xs font-normal text-[#0043ce]"
          >
            <Security className="mr-1 h-3.5 w-3.5" />
            {item.pipeline_trace?.jurisdiction ?? item.country}
          </Badge>
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
                <WarningAltFilled className="mr-1 h-3.5 w-3.5" />
                Medication Flag Detected
              </span>
            )}
            {isAmbiguous && (
              <span className="inline-flex items-center bg-[#fff1f1] px-2 py-0.5 text-xs font-medium text-[#da1e28]">
                <WarningAltFilled className="mr-1 h-3.5 w-3.5" />
                Ambiguous Jurisdiction
              </span>
            )}
          </div>
        )}

        {/* Patient inquiry (redacted) */}
        <div>
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-[#525252]">
            Patient Inquiry (Redacted)
          </p>
          <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 text-sm leading-relaxed text-[#161616]">
            <RedactedText text={item.pipeline_trace?.translation ?? "(no text)"} />
          </div>
        </div>

        {/* Draft response editor */}
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
              Draft Response
            </p>
            <button
              className="text-xs font-medium text-[#0f62fe] hover:underline"
              onClick={() => setShowEditor((v) => !v)}
            >
              {showEditor ? "Collapse editor" : "Edit response"}
            </button>
          </div>
          {showEditor ? (
            <Textarea
              value={editedResponse}
              onChange={(e) => setEditedResponse(e.target.value)}
              rows={5}
              className="rounded-none"
            />
          ) : (
            <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 text-sm leading-relaxed text-[#161616]">
              {editedResponse}
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
              value={reviewerNote}
              onChange={(e) => setReviewerNote(e.target.value)}
              placeholder="Internal note for audit trail…"
              rows={2}
              className="rounded-none"
            />
          </div>
        )}

        {/* Rejection reason (shown when reject is active) — required */}
        {action === "rejecting" && (
          <div>
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-[#525252]">
              Rejection Reason <span className="text-[#da1e28]">*</span>
            </p>
            <Textarea
              value={rejectionReason}
              onChange={(e) => {
                setRejectionReason(e.target.value);
                if (e.target.value.trim()) setError(null);
              }}
              placeholder="Reason for rejecting this response (required)…"
              rows={2}
              className="rounded-none"
            />
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
            variant="destructive"
            size="sm"
            className="h-8 rounded-none border-[#da1e28] text-xs font-medium text-[#da1e28] hover:bg-[#da1e28] hover:text-white"
            disabled={action === "approving"}
            onClick={
              action === "rejecting"
                ? handleReject
                : () => setAction("rejecting")
            }
          >
            <CloseFilled className="mr-1.5 h-3.5 w-3.5" />
            {action === "rejecting" ? "Confirm Reject" : "Reject"}
          </Button>
          <Button
            size="sm"
            className="h-8 rounded-none bg-[#0f62fe] text-xs font-medium text-white hover:bg-[#0353e9]"
            disabled={action === "rejecting"}
            onClick={handleApprove}
          >
            <CheckmarkFilled className="mr-1.5 h-3.5 w-3.5" />
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
          <CheckmarkFilled className="mx-auto mb-2 h-6 w-6 text-[#24a148]" />
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
