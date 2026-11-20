/**
 * PatientAssistantPage — main patient-facing page at /patient
 *
 * Three modes:
 *   1. Clinical Question — POST /agent/query, polls GET /agent/session/{id} on 202
 *      + one-click Sample Clinical Prompts
 *   2. Load Sample Document — GET /documents/{type}/{lang} (preloaded templates)
 *   3. Upload Document     — POST /documents/analyze (multipart)
 *
 * Full IBM Carbon design system compliance per ui-design-system.md.
 */
import React, { useCallback, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import PipelineTraceSheet from "@/components/layout/PipelineTraceSheet";
import {
  postAgentQuery,
  postDocumentAnalyze,
  getSessionStatus,
  getDocument,
  ApiError,
  type AgentQueryResponse,
  type AgentEscalatedResponse,
  type DocumentAnalysisResponse,
  type DocumentResponse,
  type DocType,
} from "@/api/client";
import { CheckmarkFilled, CloseFilled, Time, Translate, DocumentView } from "@carbon/icons-react";

// ─── Sample prompts ────────────────────────────────────────────────────────────

interface SamplePrompt {
  label: string;
  text: string;
  language: string;
  country: string;
}

const SAMPLE_PROMPTS: SamplePrompt[] = [
  {
    label: "ES: Metamizol + PII escalation demo",
    text: "Soy María García, DNI 12345678A. Tomo metamizol en casa para el dolor. ¿Está permitido en los Estados Unidos? Mi médico en España me lo recetó.",
    language: "es",
    country: "US",
  },
  {
    label: "EN: Cross-border metamizole query",
    text: "I take metamizole at home for pain management. Is this medication allowed in the US? My doctor in Germany prescribed it.",
    language: "en",
    country: "US",
  },
  {
    label: "HI: Cross-border drug + Hindi",
    text: "मैं घर पर दर्द के लिए मेटामिज़ोल लेता हूं। क्या यह अमेरिका में अनुमत है? मेरे डॉक्टर ने भारत में इसे निर्धारित किया था।",
    language: "hi",
    country: "US",
  },
  {
    label: "EN: ICU consent question",
    text: "I need help understanding the ICU admission consent form. What am I agreeing to? Can you explain the risks mentioned?",
    language: "en",
    country: "DE",
  },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Render [REDACTED_*] tokens as inline PII pills */
function renderRedacted(text: string) {
  const parts = text.split(/(\[REDACTED_[A-Z0-9_]+\])/g);
  return parts.map((part, i) =>
    /^\[REDACTED_[A-Z0-9_]+\]$/.test(part) ? (
      <span
        key={i}
        className="rounded-none border border-[#c6c6c6] bg-[#e5e5e5] px-1.5 py-0.5 font-mono text-xs font-medium text-[#161616]"
      >
        {part}
      </span>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

type Mode = "question" | "sample_doc" | "upload";

const DOC_TYPES: { label: string; value: DocType }[] = [
  { label: "ICU Admission Consent", value: "consent_icu_admission" },
  { label: "Surgery Consent", value: "consent_surgery" },
  { label: "Billing & Deductible Explanation", value: "billing_deductible_explanation" },
];

// ─── Poll helper ──────────────────────────────────────────────────────────────

function usePollSession() {
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function startPolling(
    sessionId: string,
    onResolved: (status: string, text: string | null | undefined) => void
  ) {
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = setInterval(async () => {
      try {
        const s = await getSessionStatus(sessionId);
        if (s.status !== "pending") {
          clearInterval(intervalRef.current!);
          intervalRef.current = null;
          onResolved(s.status, s.response_text);
        }
      } catch {
        // keep polling
      }
    }, 3000);
  }

  function stopPolling() {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }

  return { startPolling, stopPolling };
}

// ─── Component ────────────────────────────────────────────────────────────────

type QueryState =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "pending"; sessionId: string; message: string }
  | { phase: "approved"; result: AgentQueryResponse }
  | { phase: "escalated_approved"; responseText: string }
  | { phase: "rejected"; reason?: string | null }
  | { phase: "error"; message: string };

type UploadState =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "done"; result: DocumentAnalysisResponse }
  | { phase: "error"; message: string };

type SampleDocState =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "done"; result: DocumentResponse }
  | { phase: "error"; message: string };

export default function PatientAssistantPage() {
  const [mode, setMode] = useState<Mode>("question");
  const [language, setLanguage] = useState("en");
  const [country, setCountry] = useState("US");

  // Reset stale state when switching modes
  function switchMode(next: Mode) {
    setMode(next);
    if (next === "question") {
      setUploadState({ phase: "idle" });
      setSampleDocState({ phase: "idle" });
    } else if (next === "sample_doc") {
      stopPolling();
      setQueryState({ phase: "idle" });
      setUploadState({ phase: "idle" });
    } else {
      stopPolling();
      setQueryState({ phase: "idle" });
      setSampleDocState({ phase: "idle" });
    }
  }

  // ── Clinical Question state ──────────────────────────────────────────────
  const [queryText, setQueryText] = useState("");
  const [queryState, setQueryState] = useState<QueryState>({ phase: "idle" });
  const { startPolling, stopPolling } = usePollSession();

  // ── Sample doc state ──────────────────────────────────────────────────────
  const [selectedDocType, setSelectedDocType] = useState<DocType>("consent_icu_admission");
  const [sampleDocState, setSampleDocState] = useState<SampleDocState>({ phase: "idle" });

  // ── Upload state ─────────────────────────────────────────────────────────
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<UploadState>({ phase: "idle" });

  // ── Insert sample prompt ──────────────────────────────────────────────────
  function insertSamplePrompt(prompt: SamplePrompt) {
    setQueryText(prompt.text);
    setLanguage(prompt.language);
    setCountry(prompt.country);
  }

  // ── Submit clinical question ──────────────────────────────────────────────
  const handleQuerySubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!queryText.trim()) return;
      stopPolling();
      setQueryState({ phase: "loading" });

      try {
        const { result, isEscalated } = await postAgentQuery({
          text: queryText,
          source_language: language,
          user_type: "patient",
          country,
        });

        if (isEscalated) {
          const esc = result as AgentEscalatedResponse;
          setQueryState({
            phase: "pending",
            sessionId: esc.session_id,
            message: esc.message,
          });
          startPolling(esc.session_id, (status, text) => {
            if (status === "approved") {
              setQueryState({ phase: "escalated_approved", responseText: text ?? "" });
            } else {
              setQueryState({ phase: "rejected" });
            }
          });
        } else {
          setQueryState({ phase: "approved", result: result as AgentQueryResponse });
        }
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "An unexpected error occurred.";
        setQueryState({ phase: "error", message: msg });
      }
    },
    [queryText, language, country, startPolling, stopPolling]
  );

  // ── Fetch sample hospital document ────────────────────────────────────────
  const handleFetchSampleDoc = useCallback(async () => {
    setSampleDocState({ phase: "loading" });
    try {
      const result = await getDocument(selectedDocType, language);
      setSampleDocState({ phase: "done", result });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to fetch document.";
      setSampleDocState({ phase: "error", message: msg });
    }
  }, [selectedDocType, language]);

  // ── Submit document upload ─────────────────────────────────────────────────
  const handleUploadSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!uploadFile) return;
      setUploadState({ phase: "loading" });

      try {
        const result = await postDocumentAnalyze(uploadFile, language, country);
        setUploadState({ phase: "done", result });
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "An unexpected error occurred.";
        setUploadState({ phase: "error", message: msg });
      }
    },
    [uploadFile, language, country]
  );

  return (
    <div className="flex flex-col gap-4 py-6">
      {/* Page title */}
      <div>
        <h1 className="text-base font-medium text-[#161616]">Patient &amp; Document Assistant</h1>
        <p className="mt-1 text-sm text-[#525252]">
          Ask a clinical question, load a sample hospital document, or upload a consent form / hospital bill for analysis.
        </p>
      </div>

      {/* Controls row */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Language */}
        <div className="flex items-center gap-1.5">
          <Translate className="h-3.5 w-3.5 text-[#525252]" />
          <span className="text-xs text-[#525252]">Language</span>
          <Select value={language} onValueChange={setLanguage}>
            <SelectTrigger className="h-8 w-24 rounded-none text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="en">English</SelectItem>
              <SelectItem value="es">Español</SelectItem>
              <SelectItem value="hi">हिन्दी</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Country */}
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-[#525252]">Country</span>
          <Select value={country} onValueChange={setCountry}>
            <SelectTrigger className="h-8 w-28 rounded-none text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[
                { code: "US", label: "United States" },
                { code: "DE", label: "Germany" },
                { code: "FR", label: "France" },
                { code: "ES", label: "Spain" },
                { code: "IN", label: "India" },
                { code: "MX", label: "Mexico" },
                { code: "GB", label: "United Kingdom" },
                { code: "CA", label: "Canada" },
              ].map(({ code, label }) => (
                <SelectItem key={code} value={code}>
                  {code} — {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Separator orientation="vertical" className="h-5" />

        {/* Mode switcher */}
        <div className="flex gap-1">
          {(
            [
              { key: "question", label: "Clinical Question" },
              { key: "sample_doc", label: "Sample Document" },
              { key: "upload", label: "Upload Document" },
            ] as const
          ).map(({ key, label }) => (
            <button
              key={key}
              onClick={() => switchMode(key)}
              className={`rounded-none px-3 py-1.5 text-xs font-medium transition-colors ${
                mode === key
                  ? "bg-[#0f62fe] text-white"
                  : "border border-[#e0e0e0] bg-white text-[#525252] hover:bg-[#f4f4f4]"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <Separator className="bg-[#e0e0e0]" />

      {/* ── Mode: Clinical Question ──────────────────────────────────────── */}
      {mode === "question" && (
        <div className="flex flex-col gap-4">
          {/* Sample prompts */}
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#525252]">
              Sample Clinical Prompts
            </p>
            <div className="flex flex-wrap gap-2">
              {SAMPLE_PROMPTS.map((p) => (
                <button
                  key={p.label}
                  type="button"
                  onClick={() => insertSamplePrompt(p)}
                  className="rounded-none border border-[#e0e0e0] bg-white px-2.5 py-1 text-xs text-[#525252] hover:border-[#0f62fe] hover:text-[#0f62fe] transition-colors"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={handleQuerySubmit} className="flex flex-col gap-3">
            <Textarea
              placeholder="e.g. 'I take metamizole at home. Is this allowed in the US?' / 'Tomo metamizol en casa. ¿Está permitido en los Estados Unidos?'"
              value={queryText}
              onChange={(e) => setQueryText(e.target.value)}
              rows={4}
              className="rounded-none"
              disabled={queryState.phase === "loading" || queryState.phase === "pending"}
            />
            <div className="flex justify-end">
              <Button
                type="submit"
                size="sm"
                className="h-8 rounded-none bg-[#0f62fe] text-xs font-medium text-white hover:bg-[#0353e9]"
                disabled={
                  !queryText.trim() ||
                  queryState.phase === "loading" ||
                  queryState.phase === "pending"
                }
              >
                Submit Query
              </Button>
            </div>
          </form>

          {/* Query Results */}
          {queryState.phase === "loading" && (
            <div className="border border-[#e0e0e0] bg-white p-4 text-sm text-[#525252]">
              Processing your query through the clinical pipeline…
            </div>
          )}

          {queryState.phase === "pending" && (
            <Card className="gap-0 rounded-none border border-l-4 border-l-[#f1c21b] border-[#e0e0e0] bg-white py-0 shadow-none ring-0">
              <CardHeader className="rounded-none bg-[#f4f4f4]/60 px-4 py-3">
                <Badge
                  variant="outline"
                  className="h-auto rounded-none border-[#f1c21b] bg-[#fcf4d6] px-2 py-0.5 text-xs font-medium text-[#161616]"
                >
                  <Time className="mr-1.5 h-3.5 w-3.5 text-[#b28600]" />
                  Pending Clinical Review
                </Badge>
              </CardHeader>
              <CardContent className="p-4">
                <p className="text-sm leading-relaxed text-[#161616]">
                  {queryState.message}
                </p>
                <p className="mt-2 font-mono text-xs text-[#525252]">
                  Session ID: {queryState.sessionId}
                </p>
              </CardContent>
            </Card>
          )}

          {queryState.phase === "approved" && (
            <Card className="gap-0 rounded-none border border-l-4 border-l-[#24a148] border-[#e0e0e0] bg-white py-0 shadow-none ring-0">
              <CardHeader className="rounded-none bg-[#f4f4f4]/60 px-4 py-3">
                <Badge
                  variant="outline"
                  className="h-auto rounded-none border-[#24a148] bg-[#defbe6] px-2 py-0.5 text-xs font-medium text-[#0e6027]"
                >
                  <CheckmarkFilled className="mr-1.5 h-3.5 w-3.5 text-[#24a148]" />
                  Response Ready
                </Badge>
              </CardHeader>
              <Separator className="bg-[#e0e0e0]" />
              <CardContent className="space-y-4 p-4">
                <span className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
                  Clinical Response
                </span>
                <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 text-sm leading-relaxed text-[#161616]">
                  {renderRedacted(queryState.result.response_text)}
                </div>
              </CardContent>
              <Separator className="bg-[#e0e0e0]" />
              <CardFooter className="flex flex-wrap items-center justify-between gap-3 rounded-none border-0 bg-[#f4f4f4]/40 px-4 py-2.5">
                <span className="font-mono text-xs text-[#525252]">
                  Session: {queryState.result.session_id}
                </span>
                <PipelineTraceSheet trace={queryState.result.pipeline_trace} />
              </CardFooter>
            </Card>
          )}

          {queryState.phase === "escalated_approved" && (
            <Card className="gap-0 rounded-none border border-l-4 border-l-[#24a148] border-[#e0e0e0] bg-white py-0 shadow-none ring-0">
              <CardHeader className="rounded-none bg-[#f4f4f4]/60 px-4 py-3">
                <Badge
                  variant="outline"
                  className="h-auto rounded-none border-[#24a148] bg-[#defbe6] px-2 py-0.5 text-xs font-medium text-[#0e6027]"
                >
                  <CheckmarkFilled className="mr-1.5 h-3.5 w-3.5 text-[#24a148]" />
                  Reviewed &amp; Approved
                </Badge>
              </CardHeader>
              <Separator className="bg-[#e0e0e0]" />
              <CardContent className="space-y-4 p-4">
                <span className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
                  Approved Clinical Response
                </span>
                <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 text-sm leading-relaxed text-[#161616]">
                  {renderRedacted(queryState.responseText)}
                </div>
              </CardContent>
            </Card>
          )}

          {queryState.phase === "rejected" && (
            <Card className="gap-0 rounded-none border border-l-4 border-l-[#da1e28] border-[#e0e0e0] bg-white py-0 shadow-none ring-0">
              <CardHeader className="rounded-none bg-[#f4f4f4]/60 px-4 py-3">
                <Badge
                  variant="outline"
                  className="h-auto rounded-none border-[#da1e28] bg-[#fff1f1] px-2 py-0.5 text-xs font-medium text-[#a2191f]"
                >
                  <CloseFilled className="mr-1.5 h-3.5 w-3.5 text-[#da1e28]" />
                  Response Rejected
                </Badge>
              </CardHeader>
              <CardContent className="p-4">
                <p className="text-sm text-[#161616]">
                  Your query could not be answered at this time. Please consult your
                  healthcare provider directly for clinical guidance.
                </p>
              </CardContent>
            </Card>
          )}

          {queryState.phase === "error" && (
            <div className="border border-[#da1e28] bg-[#fff1f1] p-3 text-sm text-[#a2191f]">
              {queryState.message}
            </div>
          )}
        </div>
      )}

      {/* ── Mode: Sample Hospital Document ───────────────────────────────── */}
      {mode === "sample_doc" && (
        <div className="flex flex-col gap-4">
          <p className="text-xs text-[#525252]">
            Load a preloaded synthetic consent or billing document from the backend in your
            selected language.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-[#525252]">Document Type</span>
              <Select
                value={selectedDocType}
                onValueChange={(v) => setSelectedDocType(v as DocType)}
              >
                <SelectTrigger className="h-8 w-56 rounded-none text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DOC_TYPES.map(({ label, value }) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              size="sm"
              className="h-8 rounded-none bg-[#0f62fe] text-xs font-medium text-white hover:bg-[#0353e9]"
              onClick={handleFetchSampleDoc}
              disabled={sampleDocState.phase === "loading"}
            >
              <DocumentView className="mr-1.5 h-3.5 w-3.5" />
              {sampleDocState.phase === "loading" ? "Loading…" : "Fetch Document"}
            </Button>
          </div>

          {sampleDocState.phase === "done" && (
            <Card className="gap-0 rounded-none border border-l-4 border-l-[#0f62fe] border-[#e0e0e0] bg-white py-0 shadow-none ring-0">
              <CardHeader className="rounded-none bg-[#f4f4f4]/60 px-4 py-3">
                <span className="text-xs font-semibold text-[#161616]">
                  {sampleDocState.result.title}
                </span>
                <span className="font-mono text-xs text-[#525252]">
                  {sampleDocState.result.doc_type} · {sampleDocState.result.language}
                </span>
              </CardHeader>
              <Separator className="bg-[#e0e0e0]" />
              <CardContent className="p-4">
                <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 text-sm leading-relaxed text-[#161616] whitespace-pre-wrap max-h-96 overflow-y-auto">
                  {sampleDocState.result.content}
                </div>
              </CardContent>
            </Card>
          )}

          {sampleDocState.phase === "error" && (
            <div className="border border-[#da1e28] bg-[#fff1f1] p-3 text-sm text-[#a2191f]">
              {sampleDocState.message}
            </div>
          )}
        </div>
      )}

      {/* ── Mode: Upload Document ─────────────────────────────────────────── */}
      {mode === "upload" && (
        <div className="flex flex-col gap-4">
          <form onSubmit={handleUploadSubmit} className="flex flex-col gap-3">
            <div className="border border-dashed border-[#e0e0e0] bg-white p-6">
              <div className="flex flex-col items-center gap-2">
                <DocumentView className="h-8 w-8 text-[#525252]" />
                <p className="text-sm text-[#525252]">
                  Upload a consent form or hospital bill (.txt or .pdf)
                </p>
                <Input
                  type="file"
                  accept=".txt,.pdf"
                  onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                  className="rounded-none"
                  disabled={uploadState.phase === "loading"}
                />
              </div>
            </div>
            <div className="flex justify-end">
              <Button
                type="submit"
                size="sm"
                className="h-8 rounded-none bg-[#0f62fe] text-xs font-medium text-white hover:bg-[#0353e9]"
                disabled={!uploadFile || uploadState.phase === "loading"}
              >
                {uploadState.phase === "loading" ? "Analyzing…" : "Analyze Document"}
              </Button>
            </div>
          </form>

          {/* Upload Results */}
          {uploadState.phase === "done" && (
            <Card className="gap-0 rounded-none border border-l-4 border-l-[#24a148] border-[#e0e0e0] bg-white py-0 shadow-none ring-0">
              <CardHeader className="rounded-none bg-[#f4f4f4]/60 px-4 py-3">
                <Badge
                  variant="outline"
                  className="h-auto rounded-none border-[#24a148] bg-[#defbe6] px-2 py-0.5 text-xs font-medium text-[#0e6027]"
                >
                  <CheckmarkFilled className="mr-1.5 h-3.5 w-3.5 text-[#24a148]" />
                  Analysis Complete
                </Badge>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-[#525252]">
                    {uploadState.result.filename}
                  </span>
                  {uploadState.result.pii_redacted && (
                    <span className="rounded-none border border-[#c6c6c6] bg-[#e5e5e5] px-1.5 py-0.5 font-mono text-xs font-medium text-[#161616]">
                      [PII_REDACTED]
                    </span>
                  )}
                </div>
              </CardHeader>
              <Separator className="bg-[#e0e0e0]" />
              <CardContent className="space-y-4 p-4">
                {/* Redacted preview */}
                <div>
                  <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-[#525252]">
                    Redacted Preview
                  </p>
                  <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 font-mono text-xs leading-relaxed text-[#161616]">
                    {renderRedacted(uploadState.result.redacted_preview)}
                  </div>
                </div>

                {/* Analysis */}
                <div>
                  <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-[#525252]">
                    Document Analysis
                  </p>
                  <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 text-sm leading-relaxed text-[#161616] whitespace-pre-wrap">
                    {uploadState.result.analysis}
                  </div>
                </div>
              </CardContent>
              <Separator className="bg-[#e0e0e0]" />
              <CardFooter className="rounded-none border-0 bg-[#f4f4f4]/40 px-4 py-2.5">
                <span className="font-mono text-xs text-[#525252]">
                  Jurisdiction: {uploadState.result.jurisdiction} &middot; Lang:{" "}
                  {uploadState.result.detected_language}
                </span>
              </CardFooter>
            </Card>
          )}

          {uploadState.phase === "error" && (
            <div className="border border-[#da1e28] bg-[#fff1f1] p-3 text-sm text-[#a2191f]">
              {uploadState.message}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
