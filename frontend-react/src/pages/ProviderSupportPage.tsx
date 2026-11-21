/**
 * ProviderSupportPage — Provider consultation intake and clinical guidance at /provider.
 *
 * Three tabs matching the legacy Streamlit page:
 *   Tab 1: Procedure Explanation — POST /agent/query (user_type: provider) with sample scenarios
 *   Tab 2: Local Policy Checklist — GET /documents/{type}/{lang}
 *   Tab 3: Drug Alert Checker — GET /registry/check with status highlighting and alternatives
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
  getDocument,
  getRegistryCheck,
  getSessionStatus,
  ApiError,
  type AgentQueryResponse,
  type AgentEscalatedResponse,
  type DocumentResponse,
  type RegistryRecord,
  type DocType,
} from "@/api/client";
import {
  CheckmarkFilled,
  CloseFilled,
  Time,
  Translate,
  WarningAltFilled,
  Security,
  DocumentView,
} from "@carbon/icons-react";

// ─── Sample provider scenarios ────────────────────────────────────────────────

interface SampleScenario {
  label: string;
  text: string;
  language: string;
  country: string;
}

const SAMPLE_SCENARIOS: SampleScenario[] = [
  {
    label: "Laparoscopic cholecystectomy (ES patient)",
    text: "My patient requires a laparoscopic cholecystectomy under general anaesthesia. Please explain the procedure, risks, and recovery in culturally sensitive Spanish terms for a patient from Mexico.",
    language: "en",
    country: "MX",
  },
  {
    label: "ICU admission for Hindi-speaking patient",
    text: "I need to explain ICU admission to a Hindi-speaking patient from India. Please provide a culturally adapted explanation of the ICU environment, monitoring, and consent requirements.",
    language: "en",
    country: "IN",
  },
  {
    label: "Cross-border metamizole conflict alert",
    text: "My patient is a German national who takes metamizole at home for chronic pain. They are now in the US and asking if they can continue the medication. What should I advise?",
    language: "en",
    country: "US",
  },
  {
    label: "Domperidone restricted status (EU patient in US)",
    text: "My patient is an EU national who takes domperidone for gastroparesis. They are traveling to the US. Please advise on the regulatory status and any required medication adjustment.",
    language: "en",
    country: "US",
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

// ─── Types ────────────────────────────────────────────────────────────────────

type QueryState =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "pending"; sessionId: string; message: string }
  | { phase: "approved"; result: AgentQueryResponse }
  | { phase: "escalated_approved"; responseText: string }
  | { phase: "rejected"; reason?: string | null }
  | { phase: "error"; message: string };

type PolicyState =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "done"; result: DocumentResponse }
  | { phase: "error"; message: string };

type DrugAlertState =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "done"; record: RegistryRecord }
  | { phase: "not_found" }
  | { phase: "error"; message: string };

// ─── Medication flag detector ─────────────────────────────────────────────────

function extractMedFlags(text: string): string[] {
  const flags: string[] = [];
  const lower = text.toLowerCase();
  if (lower.includes("banned") || lower.includes("delisted")) {
    flags.push("Cross-border medication restriction detected");
  }
  if (lower.includes("flag") || lower.includes("restricted")) {
    flags.push("Regulatory flag present");
  }
  return flags;
}

// ─── Component ────────────────────────────────────────────────────────────────

type TabId = "explain" | "policy" | "drug_alert";

export default function ProviderSupportPage() {
  const [activeTab, setActiveTab] = useState<TabId>("explain");

  // ── Tab 1: Procedure Explanation ─────────────────────────────────────────
  const [country, setCountry] = useState("US");
  const [language, setLanguage] = useState("en");
  const [queryText, setQueryText] = useState("");
  const [queryState, setQueryState] = useState<QueryState>({ phase: "idle" });
  const [showTrace, setShowTrace] = useState(false);
  const pollInterval = useRef<ReturnType<typeof setInterval> | null>(null);

  function startPolling(
    sessionId: string,
    onResolved: (status: string, text: string | null | undefined) => void
  ) {
    if (pollInterval.current) clearInterval(pollInterval.current);
    pollInterval.current = setInterval(async () => {
      try {
        const s = await getSessionStatus(sessionId);
        if (s.status !== "pending") {
          clearInterval(pollInterval.current!);
          pollInterval.current = null;
          onResolved(s.status, s.response_text);
        }
      } catch {
        // keep polling
      }
    }, 3000);
  }

  function stopPolling() {
    if (pollInterval.current) {
      clearInterval(pollInterval.current);
      pollInterval.current = null;
    }
  }

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!queryText.trim()) return;
      stopPolling();
      setQueryState({ phase: "loading" });

      try {
        const { result, isEscalated } = await postAgentQuery({
          text: queryText,
          source_language: language,
          user_type: "provider",
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
    [queryText, language, country]
  );

  const isSubmitting =
    queryState.phase === "loading" || queryState.phase === "pending";

  // ── Tab 2: Policy Checklist ───────────────────────────────────────────────
  const [policyDocType, setPolicyDocType] = useState<DocType>("consent_icu_admission");
  const [policyLang, setPolicyLang] = useState("en");
  const [policyState, setPolicyState] = useState<PolicyState>({ phase: "idle" });

  const handleFetchPolicy = useCallback(async () => {
    setPolicyState({ phase: "loading" });
    try {
      const result = await getDocument(policyDocType, policyLang);
      setPolicyState({ phase: "done", result });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to fetch document.";
      setPolicyState({ phase: "error", message: msg });
    }
  }, [policyDocType, policyLang]);

  // ── Tab 3: Drug Alert ─────────────────────────────────────────────────────
  const [drugName, setDrugName] = useState("");
  const [drugJurisdiction, setDrugJurisdiction] = useState<"US_FDA" | "EU_EMA">("US_FDA");
  const [drugAlertState, setDrugAlertState] = useState<DrugAlertState>({ phase: "idle" });

  const handleDrugCheck = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!drugName.trim()) return;
      setDrugAlertState({ phase: "loading" });
      try {
        const record = await getRegistryCheck({
          medication_name: drugName.trim(),
          jurisdiction: drugJurisdiction,
        });
        setDrugAlertState({ phase: "done", record });
      } catch (err) {
        if (err instanceof ApiError && err.statusCode === 404) {
          setDrugAlertState({ phase: "not_found" });
        } else {
          const msg = err instanceof ApiError ? err.message : "An unexpected error occurred.";
          setDrugAlertState({ phase: "error", message: msg });
        }
      }
    },
    [drugName, drugJurisdiction]
  );

  const DOC_TYPES: { label: string; value: DocType }[] = [
    { label: "ICU Admission Consent", value: "consent_icu_admission" },
    { label: "Surgery Consent", value: "consent_surgery" },
    { label: "Billing & Deductible Explanation", value: "billing_deductible_explanation" },
  ];

  return (
    <div className="flex flex-col gap-4 py-6">
      {/* Page title */}
      <div>
        <h1 className="text-base font-medium text-[#161616]">Provider Support</h1>
        <p className="mt-1 text-sm text-[#525252]">
          Culturally adapted clinical communication tools for healthcare providers.
        </p>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-1" role="group" aria-label="Select section">
        {(
          [
            { key: "explain" as const, label: "Procedure Explanation" },
            { key: "policy" as const, label: "Local Policy Checklist" },
            { key: "drug_alert" as const, label: "Drug Alert Checker" },
          ]
        ).map(({ key, label }) => (
          <button
            key={key}
            type="button"
            aria-pressed={activeTab === key}
            onClick={() => setActiveTab(key)}
            className={`rounded-none px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0f62fe] ${
              activeTab === key
                ? "bg-[#0f62fe] text-white"
                : "border border-[#e0e0e0] bg-white text-[#525252] hover:bg-[#f4f4f4]"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <Separator className="bg-[#e0e0e0]" />

      {/* ── Tab 1: Procedure Explanation ──────────────────────────────────── */}
      {activeTab === "explain" && (
        <div className="flex flex-col gap-4">
          <div>
            <p className="text-sm text-[#525252]">
              Describe a procedure or clinical situation. The pipeline adapts the explanation
              for the patient's language, culture, and jurisdiction.
            </p>
          </div>

          {/* Sample scenarios */}
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#525252]">
              Sample Provider Scenarios
            </p>
            <div className="flex flex-wrap gap-2">
              {SAMPLE_SCENARIOS.map((s) => (
                <button
                  key={s.label}
                  type="button"
                  onClick={() => {
                    setQueryText(s.text);
                    setLanguage(s.language);
                    setCountry(s.country);
                  }}
                  className="rounded-none border border-[#e0e0e0] bg-white px-2.5 py-1 text-xs text-[#525252] hover:border-[#0f62fe] hover:text-[#0f62fe] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0f62fe]"
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {/* Controls row */}
            <div className="flex flex-wrap items-center gap-3">
              {/* Provider country */}
              <div className="flex items-center gap-1.5">
                <Security aria-hidden="true" className="h-3.5 w-3.5 text-[#525252]" />
                <span className="text-xs text-[#525252]">Patient Country</span>
                <Select value={country} onValueChange={setCountry}>
                  <SelectTrigger aria-label="Patient Country" className="h-8 w-28 rounded-none text-xs">
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

              {/* Patient language */}
              <div className="flex items-center gap-1.5">
                <Translate aria-hidden="true" className="h-3.5 w-3.5 text-[#525252]" />
                <span className="text-xs text-[#525252]">Patient Language</span>
                <Select value={language} onValueChange={setLanguage}>
                  <SelectTrigger aria-label="Patient Language" className="h-8 w-24 rounded-none text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="es">Español</SelectItem>
                    <SelectItem value="hi">हिन्दी</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Clinical query textarea */}
            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
                Clinical Query
              </span>
              <Textarea
                aria-label="Clinical query"
                placeholder="Describe the procedure or clinical situation in English…"
                value={queryText}
                onChange={(e) => setQueryText(e.target.value)}
                rows={5}
                className="rounded-none"
                disabled={isSubmitting}
              />
            </div>

            <div className="flex justify-end">
              <Button
                type="submit"
                size="sm"
                className="h-8 rounded-none bg-[#0f62fe] text-xs font-medium text-white hover:bg-[#0353e9]"
                disabled={!queryText.trim() || isSubmitting}
              >
                {isSubmitting ? "Processing…" : "Generate Explanation"}
              </Button>
            </div>
          </form>

          {/* Results */}
          {queryState.phase === "loading" && (
            <div className="border border-[#e0e0e0] bg-white p-4 text-sm text-[#525252]">
              Running 5-stage clinical pipeline…
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
                  Session: {queryState.sessionId}
                </p>
              </CardContent>
            </Card>
          )}

          {queryState.phase === "approved" && (
            <Card className="gap-0 rounded-none border border-l-4 border-l-[#24a148] border-[#e0e0e0] bg-white py-0 shadow-none ring-0">
              <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 rounded-none bg-[#f4f4f4]/60 px-4 py-3">
                <Badge
                  variant="outline"
                  className="h-auto rounded-none border-[#24a148] bg-[#defbe6] px-2 py-0.5 text-xs font-medium text-[#0e6027]"
                >
                  <CheckmarkFilled aria-hidden="true" className="mr-1.5 h-3.5 w-3.5 text-[#24a148]" />
                  Clinical Guidance Ready
                </Badge>
                {queryState.result.pipeline_trace?.jurisdiction && (
                  <Badge
                    variant="outline"
                    className="h-auto rounded-none border-[#a6c8ff] bg-[#edf5ff] px-2 py-0.5 font-mono text-xs font-normal text-[#0043ce]"
                  >
                    <Security aria-hidden="true" className="mr-1 h-3.5 w-3.5" />
                    {queryState.result.pipeline_trace.jurisdiction}
                  </Badge>
                )}
              </CardHeader>
              <Separator className="bg-[#e0e0e0]" />
              <CardContent className="space-y-4 p-4">
                {/* Medication flags */}
                {(() => {
                  const flags = extractMedFlags(
                    queryState.result.pipeline_trace?.medical_interpretation ?? ""
                  );
                  return flags.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {flags.map((flag) => (
                        <span
                          key={flag}
                          className="inline-flex items-center bg-[#fff1f1] px-2 py-0.5 text-xs font-medium text-[#da1e28]"
                        >
                          <WarningAltFilled aria-hidden="true" className="mr-1 h-3.5 w-3.5" />
                          {flag}
                        </span>
                      ))}
                    </div>
                  ) : null;
                })()}

                {/* Clinical response */}
                <div>
                  <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-[#525252]">
                    Clinical Guidance
                  </span>
                  <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 text-sm leading-relaxed text-[#161616]">
                    {renderRedacted(queryState.result.response_text)}
                  </div>
                </div>

                {/* Cultural framing note */}
                <p className="text-xs italic text-[#525252]">
                  Clinical guidance is culturally framed for the provider's local context.
                </p>

                {/* Collapsible pipeline trace */}
                <div>
                  <button
                    type="button"
                    aria-expanded={showTrace}
                    className="text-xs font-medium text-[#0f62fe] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0f62fe]"
                    onClick={() => setShowTrace((v) => !v)}
                  >
                    {showTrace ? "Hide" : "Show"} 5-Stage Pipeline Trace
                  </button>

                  {showTrace && (
                    <div className="mt-3 space-y-3">
                      {[
                        { key: "translation" as const, label: "Stage 1 — Translation" },
                        { key: "medical_interpretation" as const, label: "Stage 2 — Medical Interpretation" },
                        { key: "cultural_context" as const, label: "Stage 3 — Cultural Context" },
                        { key: "next_steps" as const, label: "Stage 4 — Next Steps" },
                      ].map(({ key, label }) => (
                        <div key={key}>
                          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-[#525252]">
                            {label}
                          </p>
                          <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 text-sm leading-relaxed text-[#161616]">
                            {queryState.result.pipeline_trace[key]}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
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
                  Approved Clinical Guidance
                </span>
                <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 text-sm leading-relaxed text-[#161616]">
                  {renderRedacted(queryState.responseText)}
                </div>
                <p className="text-xs italic text-[#525252]">
                  Clinical guidance is culturally framed for the provider's local context.
                </p>
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
                  Guidance Rejected
                </Badge>
              </CardHeader>
              <CardContent className="p-4">
                <p className="text-sm text-[#161616]">
                  The clinical query could not be answered at this time. Please consult
                  your clinical governance team directly.
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

      {/* ── Tab 2: Local Policy Checklist ──────────────────────────────────── */}
      {activeTab === "policy" && (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-[#525252]">
            Retrieve consent or billing documents applicable to the patient's language and
            jurisdiction for pre-procedure review.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-[#525252]">Document Type</span>
              <Select
                value={policyDocType}
                onValueChange={(v) => setPolicyDocType(v as DocType)}
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
            <div className="flex items-center gap-1.5">
              <Translate className="h-3.5 w-3.5 text-[#525252]" />
              <span className="text-xs text-[#525252]">Language</span>
              <Select value={policyLang} onValueChange={setPolicyLang}>
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
            <Button
              size="sm"
              className="h-8 rounded-none bg-[#0f62fe] text-xs font-medium text-white hover:bg-[#0353e9]"
              onClick={handleFetchPolicy}
              disabled={policyState.phase === "loading"}
            >
              <DocumentView className="mr-1.5 h-3.5 w-3.5" />
              {policyState.phase === "loading" ? "Loading…" : "Load Policy Document"}
            </Button>
          </div>

          {policyState.phase === "done" && (
            <Card className="gap-0 rounded-none border border-l-4 border-l-[#0f62fe] border-[#e0e0e0] bg-white py-0 shadow-none ring-0">
              <CardHeader className="rounded-none bg-[#f4f4f4]/60 px-4 py-3">
                <span className="text-xs font-semibold text-[#161616]">
                  {policyState.result.title}
                </span>
                <span className="font-mono text-xs text-[#525252]">
                  {policyState.result.doc_type} · {policyState.result.language}
                </span>
              </CardHeader>
              <Separator className="bg-[#e0e0e0]" />
              <CardContent className="p-4">
                <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 text-sm leading-relaxed text-[#161616] whitespace-pre-wrap max-h-96 overflow-y-auto">
                  {policyState.result.content}
                </div>
              </CardContent>
            </Card>
          )}

          {policyState.phase === "error" && (
            <div className="border border-[#da1e28] bg-[#fff1f1] p-3 text-sm text-[#a2191f]">
              {policyState.message}
            </div>
          )}
        </div>
      )}

      {/* ── Tab 3: Drug Alert Checker ──────────────────────────────────────── */}
      {activeTab === "drug_alert" && (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-[#525252]">
            Check a patient's medication against the target jurisdiction registry. Flags
            banned, restricted, or delisted medications with therapeutic alternatives.
          </p>
          <form onSubmit={handleDrugCheck} className="flex flex-wrap items-center gap-3">
            <Input
              value={drugName}
              onChange={(e) => setDrugName(e.target.value)}
              placeholder="Medication name (INN or brand, e.g. metamizole, domperidone)"
              className="h-8 rounded-none text-xs flex-1 min-w-[200px]"
              disabled={drugAlertState.phase === "loading"}
            />
            <Select
              value={drugJurisdiction}
              onValueChange={(v) => setDrugJurisdiction(v as "US_FDA" | "EU_EMA")}
            >
              <SelectTrigger className="h-8 w-28 rounded-none text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="US_FDA">US_FDA</SelectItem>
                <SelectItem value="EU_EMA">EU_EMA</SelectItem>
              </SelectContent>
            </Select>
            <Button
              type="submit"
              size="sm"
              className="h-8 rounded-none bg-[#0f62fe] text-xs font-medium text-white hover:bg-[#0353e9]"
              disabled={!drugName.trim() || drugAlertState.phase === "loading"}
            >
              Check Medication
            </Button>
          </form>

          {drugAlertState.phase === "loading" && (
            <p className="text-sm text-[#525252]">Checking registry…</p>
          )}

          {drugAlertState.phase === "not_found" && (
            <div className="border border-[#e0e0e0] bg-white p-3 text-sm text-[#525252]">
              No record found for <code className="font-mono">{drugName}</code> in{" "}
              <code className="font-mono">{drugJurisdiction}</code>.
            </div>
          )}

          {drugAlertState.phase === "done" && (() => {
            const rec = drugAlertState.record;
            const stripe =
              rec.status === "approved"
                ? "border-l-[#24a148]"
                : rec.status === "banned" || rec.status === "delisted"
                ? "border-l-[#da1e28]"
                : "border-l-[#f1c21b]";
            const statusBadgeClass =
              rec.status === "approved"
                ? "border-[#24a148] bg-[#defbe6] text-[#0e6027]"
                : rec.status === "banned" || rec.status === "delisted"
                ? "border-[#da1e28] bg-[#fff1f1] text-[#a2191f]"
                : "border-[#f1c21b] bg-[#fcf4d6] text-[#161616]";
            const StatusIcon =
              rec.status === "approved"
                ? CheckmarkFilled
                : rec.status === "banned" || rec.status === "delisted"
                ? CloseFilled
                : WarningAltFilled;
            return (
              <Card className={`gap-0 rounded-none border border-l-4 border-[#e0e0e0] bg-white py-0 shadow-none ring-0 ${stripe}`}>
                <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 rounded-none bg-[#f4f4f4]/60 px-4 py-3">
                  <Badge
                    variant="outline"
                    className={`h-auto rounded-none px-2 py-0.5 text-xs font-medium ${statusBadgeClass}`}
                  >
                    <StatusIcon className="mr-1.5 h-3.5 w-3.5" />
                    {rec.status.charAt(0).toUpperCase() + rec.status.slice(1)}
                  </Badge>
                  <Badge
                    variant="outline"
                    className="h-auto rounded-none border-[#a6c8ff] bg-[#edf5ff] px-2 py-0.5 font-mono text-xs font-normal text-[#0043ce]"
                  >
                    <Security className="mr-1 h-3.5 w-3.5" />
                    {rec.jurisdiction}
                  </Badge>
                </CardHeader>
                <Separator className="bg-[#e0e0e0]" />
                <CardContent className="space-y-3 p-4">
                  <div>
                    <span className="mb-0.5 block text-xs font-semibold uppercase tracking-wider text-[#525252]">
                      Generic Name (INN)
                    </span>
                    <span className="text-sm text-[#161616]">{rec.name_generic}</span>
                  </div>
                  {rec.restriction_reason && (
                    <div className="inline-flex items-start bg-[#fff1f1] px-2 py-1.5 text-xs font-medium text-[#da1e28]">
                      <WarningAltFilled className="mr-1 mt-0.5 h-3.5 w-3.5 shrink-0" />
                      {rec.restriction_reason}
                    </div>
                  )}
                  {rec.therapeutic_alternatives.length > 0 && (
                    <div>
                      <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-[#525252]">
                        Therapeutic Alternatives
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {rec.therapeutic_alternatives.map((alt) => (
                          <span
                            key={alt}
                            className="border border-[#e0e0e0] bg-[#f4f4f4] px-2 py-0.5 font-mono text-xs text-[#161616]"
                          >
                            {alt}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
                <Separator className="bg-[#e0e0e0]" />
                <CardFooter className="rounded-none border-0 bg-[#f4f4f4]/40 px-4 py-2.5">
                  <span className="font-mono text-xs text-[#525252] tabular-nums">
                    Last updated: {rec.last_updated}
                  </span>
                </CardFooter>
              </Card>
            );
          })()}

          {drugAlertState.phase === "error" && (
            <div className="border border-[#da1e28] bg-[#fff1f1] p-3 text-sm text-[#a2191f]">
              {drugAlertState.message}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
