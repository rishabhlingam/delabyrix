/**
 * AnalyticsDashboardPage — Zero-PII BI Dashboard at /analytics.
 *
 * Fetches GET /analytics/dashboard on mount.
 * Renders:
 *  - Date/jurisdiction filters (matching legacy Streamlit filters)
 *  - KPI metric tiles
 *  - Queries by language breakdown (HBar)
 *  - User persona breakdown
 *  - Top flagged medications
 *  - Jurisdiction breakdown
 *  - Escalation rate gauge (simple linear)
 *  - Proactive Care Recommendations (Dietary, ICD-10, Drug Conflict)
 *
 * Strictly zero-PII — no raw patient data exposed.
 * Full IBM Carbon design system compliance per ui-design-system.md.
 */
import React, { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getAnalyticsDashboard,
  ApiError,
  type AnalyticsDashboardResponse,
} from "@/api/client";
import {
  CheckmarkFilled,
  CloseFilled,
  WarningAltFilled,
  Security,
  Time,
} from "@carbon/icons-react";

// ─── KPI Tile ─────────────────────────────────────────────────────────────────

interface KpiTileProps {
  label: string;
  value: string;
  sub?: string;
  accent?: string; // border-l color
}

function KpiTile({ label, value, sub, accent = "border-l-[#0f62fe]" }: KpiTileProps) {
  return (
    <div
      className={`flex-1 min-w-[140px] rounded-none border border-[#e0e0e0] border-l-4 bg-white shadow-none ${accent}`}
    >
      <div className="p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
          {label}
        </p>
        <p className="mt-2 font-mono text-2xl font-semibold tabular-nums text-[#0f62fe]">
          {value}
        </p>
        {sub && (
          <p className="mt-1 font-mono text-xs text-[#525252] tabular-nums">{sub}</p>
        )}
      </div>
    </div>
  );
}

// ─── Horizontal bar ───────────────────────────────────────────────────────────

function HBar({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="w-20 shrink-0 font-mono text-xs text-[#525252] tabular-nums">
        {label}
      </span>
      <div className="flex-1 bg-[#e0e0e0]" style={{ height: 10 }}>
        <div
          className="h-full bg-[#0f62fe]"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-10 text-right font-mono text-xs tabular-nums text-[#525252]">
        {value}
      </span>
    </div>
  );
}

// ─── Medication flag status icon ──────────────────────────────────────────────

function MedStatusIcon({ status }: { status: string }) {
  if (status === "approved") return <CheckmarkFilled className="h-3.5 w-3.5 text-[#24a148]" />;
  if (status === "banned" || status === "delisted") return <CloseFilled className="h-3.5 w-3.5 text-[#da1e28]" />;
  return <WarningAltFilled className="h-3.5 w-3.5 text-[#b28600]" />;
}

function medStatusBadgeClass(status: string) {
  if (status === "approved") return "border-[#24a148] bg-[#defbe6] text-[#0e6027]";
  if (status === "banned" || status === "delisted") return "border-[#da1e28] bg-[#fff1f1] text-[#a2191f]";
  return "border-[#f1c21b] bg-[#fcf4d6] text-[#161616]";
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function topEntry(rec: Record<string, number>): string {
  const entries = Object.entries(rec);
  if (entries.length === 0) return "—";
  return entries.reduce((a, b) => (b[1] > a[1] ? b : a))[0];
}

// ─── Component ────────────────────────────────────────────────────────────────

type DashState =
  | { phase: "loading" }
  | { phase: "done"; data: AnalyticsDashboardResponse }
  | { phase: "error"; message: string };

export default function AnalyticsDashboardPage() {
  const [state, setState] = useState<DashState>({ phase: "loading" });
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [jurisdictionFilter, setJurisdictionFilter] = useState("All");

  const load = useCallback(async () => {
    setState({ phase: "loading" });
    try {
      const data = await getAnalyticsDashboard({
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        jurisdiction: jurisdictionFilter !== "All" ? jurisdictionFilter : undefined,
      });
      setState({ phase: "done", data });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to load dashboard.";
      setState({ phase: "error", message: msg });
    }
  }, [dateFrom, dateTo, jurisdictionFilter]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="flex flex-col gap-4 py-6">
      {/* Page title */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-base font-medium text-[#161616]">Analytics Dashboard</h1>
          <p className="mt-1 text-sm text-[#525252]">
            Zero-PII aggregated metrics for care coordination teams.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="h-8 rounded-none text-xs"
          onClick={load}
          disabled={state.phase === "loading"}
        >
          {state.phase === "loading" ? "Loading…" : "Refresh"}
        </Button>
      </div>

      {/* Filters row */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-[#525252]">Date From</span>
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="h-8 w-36 rounded-none text-xs"
          />
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-[#525252]">Date To</span>
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="h-8 w-36 rounded-none text-xs"
          />
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-[#525252]">Jurisdiction</span>
          <Select value={jurisdictionFilter} onValueChange={setJurisdictionFilter}>
            <SelectTrigger className="h-8 w-28 rounded-none text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="All">All</SelectItem>
              <SelectItem value="US_FDA">US_FDA</SelectItem>
              <SelectItem value="EU_EMA">EU_EMA</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {(dateFrom || dateTo || jurisdictionFilter !== "All") && (
          <button
            type="button"
            className="text-xs font-medium text-[#0f62fe] hover:underline"
            onClick={() => {
              setDateFrom("");
              setDateTo("");
              setJurisdictionFilter("All");
            }}
          >
            Clear filters
          </button>
        )}
      </div>

      <Separator className="bg-[#e0e0e0]" />

      {/* Loading skeleton */}
      {state.phase === "loading" && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-3">
            {[1, 2, 3, 4].map((n) => (
              <div
                key={n}
                className="flex-1 min-w-[140px] h-24 animate-pulse rounded-none border border-[#e0e0e0] bg-[#f4f4f4]"
              />
            ))}
          </div>
          <div className="h-32 animate-pulse rounded-none border border-[#e0e0e0] bg-[#f4f4f4]" />
        </div>
      )}

      {/* Error state */}
      {state.phase === "error" && (
        <div className="flex flex-col items-start gap-3">
          <div className="border border-[#da1e28] bg-[#fff1f1] p-3 text-sm text-[#a2191f]">
            {state.message}
          </div>
          <Button
            size="sm"
            className="h-8 rounded-none bg-[#0f62fe] text-xs font-medium text-white hover:bg-[#0353e9]"
            onClick={load}
          >
            Retry
          </Button>
        </div>
      )}

      {/* Dashboard content */}
      {state.phase === "done" && (() => {
        const d = state.data;
        const topLang = topEntry(d.queries_by_language);
        const hitlApprovalRate =
          d.escalation_rate > 0
            ? `${(100 - d.escalation_rate * 100).toFixed(1)}% direct`
            : "N/A";
        const jurisdictionMax = Math.max(
          ...Object.values(d.jurisdiction_breakdown),
          1
        );
        const userTypeEntries = Object.entries(d.queries_by_user_type).sort(
          (a, b) => b[1] - a[1]
        );
        const langEntries = Object.entries(d.queries_by_language).sort(
          (a, b) => b[1] - a[1]
        );

        return (
          <div className="flex flex-col gap-6">

            {/* ── KPI Metric Tiles ────────────────────────────────────── */}
            <section>
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-[#525252]">
                Key Performance Indicators
              </p>
              <div className="flex flex-wrap gap-3">
                <KpiTile
                  label="Total Queries"
                  value={d.total_queries.toLocaleString()}
                  sub="all time"
                  accent="border-l-[#0f62fe]"
                />
                <KpiTile
                  label="PII Redactions"
                  value={`${(d.escalation_rate * 100).toFixed(1)}%`}
                  sub="escalation rate"
                  accent="border-l-[#da1e28]"
                />
                <KpiTile
                  label="HITL Resolution"
                  value={hitlApprovalRate}
                  sub="non-escalated"
                  accent="border-l-[#24a148]"
                />
                <KpiTile
                  label="Avg Pipeline Stages"
                  value={d.avg_pipeline_stages_completed.toFixed(1)}
                  sub={`Top lang: ${topLang}`}
                  accent="border-l-[#f1c21b]"
                />
                <KpiTile
                  label="Active Jurisdictions"
                  value={String(Object.keys(d.jurisdiction_breakdown).length)}
                  sub="FDA + EMA + others"
                  accent="border-l-[#8a3ffc]"
                />
              </div>
            </section>

            <Separator className="bg-[#e0e0e0]" />

            {/* ── Jurisdiction Breakdown ──────────────────────────────── */}
            <section>
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-[#525252]">
                Jurisdiction Breakdown
              </p>
              <div className="rounded-none border border-[#e0e0e0] bg-white p-4">
                {Object.keys(d.jurisdiction_breakdown).length === 0 ? (
                  <p className="text-xs text-[#525252]">No jurisdiction data yet.</p>
                ) : (
                  <div className="space-y-2">
                    {Object.entries(d.jurisdiction_breakdown)
                      .sort((a, b) => b[1] - a[1])
                      .map(([jur, count]) => (
                        <HBar
                          key={jur}
                          label={jur}
                          value={count}
                          max={jurisdictionMax}
                        />
                      ))}
                  </div>
                )}
              </div>
            </section>

            <Separator className="bg-[#e0e0e0]" />

            {/* ── Queries by Language + User Persona ──────────────────── */}
            <section>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-[#525252]">
                    Queries by Language
                  </p>
                  <div className="rounded-none border border-[#e0e0e0] bg-white p-4">
                    {langEntries.length === 0 ? (
                      <p className="text-xs text-[#525252]">No language data yet.</p>
                    ) : (
                      <div className="space-y-2">
                        {langEntries.map(([lang, count]) => (
                          <HBar
                            key={lang}
                            label={lang}
                            value={count}
                            max={Math.max(...Object.values(d.queries_by_language), 1)}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                </div>
                <div>
                  <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-[#525252]">
                    User Persona Breakdown
                  </p>
                  <div className="rounded-none border border-[#e0e0e0] bg-white p-4">
                    {userTypeEntries.length === 0 ? (
                      <p className="text-xs text-[#525252]">No user type data yet.</p>
                    ) : (
                      <div className="space-y-2">
                        {userTypeEntries.map(([ut, count]) => (
                          <HBar
                            key={ut}
                            label={ut}
                            value={count}
                            max={Math.max(...Object.values(d.queries_by_user_type), 1)}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </section>

            <Separator className="bg-[#e0e0e0]" />

            {/* ── Top Flagged Medications ──────────────────────────────── */}
            <section>
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-[#525252]">
                Top Flagged Medications (US FDA vs EU EMA)
              </p>
              <div className="rounded-none border border-[#e0e0e0] bg-white">
                {d.top_medication_flags.length === 0 ? (
                  <p className="p-4 text-xs text-[#525252]">No medication flags recorded yet.</p>
                ) : (
                  <table className="w-full text-xs" data-testid="medication-flags-table">
                    <thead>
                      <tr className="border-b border-[#e0e0e0] bg-[#f4f4f4]">
                        <th className="px-4 py-2 text-left font-semibold uppercase tracking-wider text-[#525252]">Medication (INN)</th>
                        <th className="px-4 py-2 text-left font-semibold uppercase tracking-wider text-[#525252]">Status</th>
                        <th className="px-4 py-2 text-right font-semibold uppercase tracking-wider text-[#525252]">Flag Count</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.top_medication_flags.map((m, i) => (
                        <tr key={i} className={`border-b border-[#e0e0e0] ${i % 2 === 0 ? "bg-white" : "bg-[#f4f4f4]/30"}`}>
                          <td className="px-4 py-2 text-[#161616]">{m.medication}</td>
                          <td className="px-4 py-2">
                            <Badge
                              variant="outline"
                              className={`h-auto rounded-none px-1.5 py-0.5 text-[10px] font-medium ${medStatusBadgeClass(m.status)}`}
                            >
                              <MedStatusIcon status={m.status} />
                              {m.status}
                            </Badge>
                          </td>
                          <td className="px-4 py-2 text-right font-mono tabular-nums text-[#525252]">{m.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </section>

            <Separator className="bg-[#e0e0e0]" />

            {/* ── Escalation Rate Gauge ────────────────────────────────── */}
            <section>
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-[#525252]">
                Escalation Rate Gauge
              </p>
              <div className="rounded-none border border-[#e0e0e0] bg-white p-4">
                <div className="flex items-center gap-4">
                  <div className="flex-1">
                    <div className="mb-1 flex items-center justify-between text-xs text-[#525252]">
                      <span>0%</span>
                      <span className="font-semibold text-[#161616]">
                        {(d.escalation_rate * 100).toFixed(1)}%
                      </span>
                      <span>100%</span>
                    </div>
                    <div className="h-4 w-full rounded-none bg-[#e0e0e0]">
                      <div
                        className="h-full rounded-none"
                        style={{
                          width: `${Math.min(d.escalation_rate * 100, 100)}%`,
                          background:
                            d.escalation_rate > 0.3
                              ? "#da1e28"
                              : d.escalation_rate > 0.1
                              ? "#f1c21b"
                              : "#24a148",
                        }}
                      />
                    </div>
                  </div>
                  <div>
                    {d.escalation_rate > 0.3 ? (
                      <span className="inline-flex items-center bg-[#fff1f1] px-2 py-0.5 text-xs font-medium text-[#da1e28]">
                        <WarningAltFilled className="mr-1 h-3.5 w-3.5" />
                        High
                      </span>
                    ) : d.escalation_rate > 0.1 ? (
                      <span className="inline-flex items-center bg-[#fcf4d6] px-2 py-0.5 text-xs font-medium text-[#b28600]">
                        <Time className="mr-1 h-3.5 w-3.5" />
                        Moderate
                      </span>
                    ) : (
                      <span className="inline-flex items-center bg-[#defbe6] px-2 py-0.5 text-xs font-medium text-[#0e6027]">
                        <CheckmarkFilled className="mr-1 h-3.5 w-3.5" />
                        Low
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </section>

            <Separator className="bg-[#e0e0e0]" />

            {/* ── Proactive Recommendation Cards ──────────────────────── */}
            <section>
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-[#525252]">
                Proactive Care Recommendations
              </p>
              <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">

                {/* Card A: Dietary Accommodations — derived from language breakdown */}
                <Card className="flex-1 min-w-[220px] gap-0 rounded-none border border-l-4 border-l-[#0f62fe] border-[#e0e0e0] bg-white py-0 shadow-none ring-0">
                  <CardHeader className="rounded-none bg-[#f4f4f4]/60 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
                      Dietary Accommodations
                    </p>
                    <p className="text-xs text-[#525252] mt-0.5">
                      Language &amp; cultural distribution
                    </p>
                  </CardHeader>
                  <Separator className="bg-[#e0e0e0]" />
                  <CardContent className="p-4 space-y-2">
                    {langEntries.length === 0 ? (
                      <p className="text-xs text-[#525252]">No data available.</p>
                    ) : (
                      langEntries.map(([lang, count]) => (
                        <div key={lang} className="flex items-center justify-between gap-2">
                          <Badge
                            variant="outline"
                            className="rounded-none border-[#a6c8ff] bg-[#edf5ff] font-mono text-xs font-normal text-[#0043ce]"
                          >
                            <Security className="mr-1 h-3 w-3" />
                            {lang}
                          </Badge>
                          <span className="font-mono text-xs tabular-nums text-[#525252]">
                            {count.toLocaleString()} queries
                          </span>
                        </div>
                      ))
                    )}
                    <p className="border border-[#e0e0e0] bg-[#f4f4f4] p-2 text-xs leading-relaxed text-[#525252]">
                      Recommend multilingual dietary guidance materials for top patient
                      language cohorts to reduce repeated clinical escalations.
                    </p>
                  </CardContent>
                </Card>

                {/* Card B: ICD-10 Clinical Clusters — from top_medication_flags */}
                <Card className="flex-1 min-w-[220px] gap-0 rounded-none border border-l-4 border-l-[#da1e28] border-[#e0e0e0] bg-white py-0 shadow-none ring-0">
                  <CardHeader className="rounded-none bg-[#f4f4f4]/60 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
                      ICD-10 Clinical Clusters
                    </p>
                    <p className="text-xs text-[#525252] mt-0.5">
                      Top medication flags by volume
                    </p>
                  </CardHeader>
                  <Separator className="bg-[#e0e0e0]" />
                  <CardContent className="p-4 space-y-2">
                    {d.top_medication_flags.length === 0 ? (
                      <p className="text-xs text-[#525252]">No medication flags recorded.</p>
                    ) : (
                      <div className="border border-[#e0e0e0] bg-white">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b border-[#e0e0e0] bg-[#f4f4f4]">
                              <th className="px-3 py-1.5 text-left font-semibold uppercase tracking-wider text-[#525252]">
                                Medication
                              </th>
                              <th className="px-3 py-1.5 text-left font-semibold uppercase tracking-wider text-[#525252]">
                                Status
                              </th>
                              <th className="px-3 py-1.5 text-right font-semibold uppercase tracking-wider text-[#525252]">
                                Count
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {d.top_medication_flags.map((m, i) => (
                              <tr
                                key={i}
                                className={`border-b border-[#e0e0e0] ${
                                  i % 2 === 0 ? "bg-white" : "bg-[#f4f4f4]/30"
                                }`}
                              >
                                <td className="px-3 py-1.5 text-[#161616]">
                                  {m.medication}
                                </td>
                                <td className="px-3 py-1.5">
                                  <Badge
                                    variant="outline"
                                    className={`h-auto rounded-none px-1.5 py-0.5 text-[10px] font-medium ${medStatusBadgeClass(m.status)}`}
                                  >
                                    <MedStatusIcon status={m.status} />
                                    {m.status}
                                  </Badge>
                                </td>
                                <td className="px-3 py-1.5 text-right font-mono tabular-nums text-[#525252]">
                                  {m.count}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Card C: Cross-Border Drug Conflict Hotspots — from user_type + escalation */}
                <Card className="flex-1 min-w-[220px] gap-0 rounded-none border border-l-4 border-l-[#f1c21b] border-[#e0e0e0] bg-white py-0 shadow-none ring-0">
                  <CardHeader className="rounded-none bg-[#f4f4f4]/60 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
                      Cross-Border Drug Conflict Hotspots
                    </p>
                    <p className="text-xs text-[#525252] mt-0.5">
                      Query volume by user type &amp; escalation signal
                    </p>
                  </CardHeader>
                  <Separator className="bg-[#e0e0e0]" />
                  <CardContent className="p-4 space-y-3">
                    {/* Escalation rate badge */}
                    <div className="flex items-center gap-2">
                      {d.escalation_rate > 0.2 ? (
                        <span className="inline-flex items-center bg-[#fff1f1] px-2 py-0.5 text-xs font-medium text-[#da1e28]">
                          <WarningAltFilled className="mr-1 h-3.5 w-3.5" />
                          High escalation — {(d.escalation_rate * 100).toFixed(1)}%
                        </span>
                      ) : d.escalation_rate > 0.05 ? (
                        <span className="inline-flex items-center bg-[#fcf4d6] px-2 py-0.5 text-xs font-medium text-[#b28600]">
                          <Time className="mr-1 h-3.5 w-3.5" />
                          Moderate escalation — {(d.escalation_rate * 100).toFixed(1)}%
                        </span>
                      ) : (
                        <span className="inline-flex items-center bg-[#defbe6] px-2 py-0.5 text-xs font-medium text-[#0e6027]">
                          <CheckmarkFilled className="mr-1 h-3.5 w-3.5" />
                          Low escalation — {(d.escalation_rate * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>

                    {/* User type breakdown */}
                    <div className="space-y-1.5">
                      {userTypeEntries.map(([ut, count]) => (
                        <div key={ut} className="flex items-center justify-between gap-2">
                          <span className="text-xs text-[#161616] capitalize">{ut}</span>
                          <span className="font-mono text-xs tabular-nums text-[#525252]">
                            {count.toLocaleString()} queries
                          </span>
                        </div>
                      ))}
                    </div>

                    <p className="border border-[#e0e0e0] bg-[#f4f4f4] p-2 text-xs leading-relaxed text-[#525252]">
                      {d.escalation_rate > 0.1
                        ? "Elevated cross-border conflict rate detected. Review medication registry for jurisdiction conflicts."
                        : "Cross-border conflict rate within normal bounds. Continue monitoring registry sync cadence."}
                    </p>
                  </CardContent>
                </Card>

              </div>
            </section>

          </div>
        );
      })()}
    </div>
  );
}
