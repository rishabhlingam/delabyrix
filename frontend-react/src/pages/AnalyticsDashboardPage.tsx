/**
 * AnalyticsDashboardPage — Zero-PII BI Dashboard at /analytics.
 *
 * Fetches GET /analytics/dashboard on mount.
 * Renders (matching legacy frontend/pages/4_BI_Dashboard.py exactly):
 *  - Date/jurisdiction filters
 *  - 5-tile KPI row (grid-cols-2 lg:grid-cols-5)
 *  - Queries by Jurisdiction (BarChart — Recharts)
 *  - Queries by Language, Top 8 + Other (BarChart — Recharts)
 *  - User Persona Breakdown (PieChart donut — Recharts)
 *  - Top Flagged Medications: horizontal BarChart + Regulatory table (Recharts)
 *  - HITL Escalation & Safety Outcomes (BarChart — Recharts)
 *  - Escalation Rate Gauge (custom linear bar)
 *  - Proactive Care Recommendations (Dietary / ICD-10 / Conflict cards + charts)
 *
 * Strictly zero-PII. Full IBM Carbon design system compliance.
 */
import React, { useCallback, useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
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
  type ProactiveRecommendation,
} from "@/api/client";
import {
  CheckmarkFilled,
  CloseFilled,
  WarningAltFilled,
  Security,
  Time,
} from "@carbon/icons-react";

// ─── Carbon chart palette ─────────────────────────────────────────────────────

const C_BLUE = "#0f62fe";
const C_GREEN = "#24a148";
const C_PURPLE = "#8a3ffc";
const C_YELLOW = "#f1c21b";
const C_RED = "#da1e28";
const C_TEAL = "#009d9a";
const C_ORANGE = "#ff832b";
const C_MAGENTA = "#ee5396";

const CHART_PALETTE = [C_BLUE, C_GREEN, C_PURPLE, C_YELLOW, C_RED, C_TEAL, C_ORANGE, C_MAGENTA];

// ─── Recharts shared custom tooltip ──────────────────────────────────────────

interface TooltipPayload {
  name: string;
  value: number;
  color?: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayload[];
  label?: string;
}

function CarbonTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-none border border-[#e0e0e0] bg-white px-3 py-2 font-mono text-xs text-[#161616] shadow-none">
      {label && <p className="mb-1 font-semibold text-[#161616]">{label}</p>}
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color ?? C_BLUE }}>
          {p.name}: <span className="tabular-nums">{p.value.toLocaleString()}</span>
        </p>
      ))}
    </div>
  );
}

// ─── Shared chart card wrapper ────────────────────────────────────────────────

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="gap-0 rounded-none border border-[#e0e0e0] bg-white py-0 shadow-none ring-0 hover:border-[#8d8d8d] transition-colors">
      <div className="bg-[#f4f4f4]/60 px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-[#525252]">{title}</p>
      </div>
      <div className="bg-[#e0e0e0]" style={{ height: 1 }} />
      <div className="p-4">{children}</div>
    </div>
  );
}

// ─── KPI Tile ─────────────────────────────────────────────────────────────────

interface KpiTileProps {
  label: string;
  value: string;
  sub?: string;
  accent?: string;
}

function KpiTile({ label, value, sub, accent = "border-l-[#0f62fe]" }: KpiTileProps) {
  return (
    <div
      className={`rounded-none border border-[#e0e0e0] border-l-4 bg-white shadow-none ${accent}`}
    >
      <div className="p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-[#525252]">{label}</p>
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

// ─── Medication helpers ────────────────────────────────────────────────────────

function MedStatusIcon({ status }: { status: string }) {
  if (status === "approved") return <CheckmarkFilled className="h-3.5 w-3.5 text-[#24a148]" />;
  if (status === "banned" || status === "delisted")
    return <CloseFilled className="h-3.5 w-3.5 text-[#da1e28]" />;
  return <WarningAltFilled className="h-3.5 w-3.5 text-[#b28600]" />;
}

function medStatusBadgeClass(status: string) {
  if (status === "approved") return "border-[#24a148] bg-[#defbe6] text-[#0e6027]";
  if (status === "banned" || status === "delisted")
    return "border-[#da1e28] bg-[#fff1f1] text-[#a2191f]";
  return "border-[#f1c21b] bg-[#fcf4d6] text-[#161616]";
}

// ─── Proactive recommendation helpers ────────────────────────────────────────

function recsByCategory(
  recs: ProactiveRecommendation[],
  category: ProactiveRecommendation["category"]
) {
  return recs.filter((r) => r.category === category);
}

function stripPrefix(title: string, prefix: string) {
  return title.replace(prefix, "").trim();
}

// ─── Component state ──────────────────────────────────────────────────────────

type DashState =
  | { phase: "loading" }
  | { phase: "done"; data: AnalyticsDashboardResponse }
  | { phase: "error"; message: string };

// ─── Main component ───────────────────────────────────────────────────────────

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
      {/* Page title + refresh */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-base font-medium text-[#161616]">Analytics Dashboard</h1>
          <p className="mt-1 text-sm text-[#525252]">
            Aggregate, anonymized interaction metrics — zero raw query text or PII.
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
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            {[1, 2, 3, 4, 5].map((n) => (
              <div
                key={n}
                className="h-24 animate-pulse rounded-none border border-[#e0e0e0] bg-[#f4f4f4]"
              />
            ))}
          </div>
          <div className="h-64 animate-pulse rounded-none border border-[#e0e0e0] bg-[#f4f4f4]" />
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
        const recs = d.proactive_recommendations ?? [];

        // ── KPI derived values ────────────────────────────────────────────────
        const totalMedFlags = d.top_medication_flags.reduce((s, m) => s + m.count, 0);
        const activeJurisdictions = Object.keys(d.jurisdiction_breakdown);
        const activeJurCount = activeJurisdictions.length;
        const jurisdictionLabel = activeJurCount > 0
          ? activeJurisdictions.slice(0, 3).join(" · ") + (activeJurCount > 3 ? ` +${activeJurCount - 3}` : "")
          : "FDA · EMA · National";

        // ── Jurisdiction bar chart data ───────────────────────────────────────
        const jurisdictionChartData = Object.entries(d.jurisdiction_breakdown)
          .sort((a, b) => b[1] - a[1])
          .map(([name, value]) => ({ name, value }));

        // ── Language chart: top 8 + Other ────────────────────────────────────
        const allLangEntries = Object.entries(d.queries_by_language).sort(
          (a, b) => b[1] - a[1]
        );
        const TOP_N = 8;
        const topLangs = allLangEntries.slice(0, TOP_N);
        const otherCount = allLangEntries
          .slice(TOP_N)
          .reduce((s, [, v]) => s + v, 0);
        const langChartData = [
          ...topLangs.map(([name, value]) => ({ name, value })),
          ...(otherCount > 0 ? [{ name: "Other", value: otherCount }] : []),
        ];

        // ── User persona donut chart data ─────────────────────────────────────
        const personaChartData = Object.entries(d.queries_by_user_type)
          .sort((a, b) => b[1] - a[1])
          .map(([name, value]) => ({ name, value }));
        const totalPersona = personaChartData.reduce((s, x) => s + x.value, 0);

        // ── Top flagged meds horizontal bar chart data ────────────────────────
        const medsChartData = [...d.top_medication_flags]
          .sort((a, b) => b.count - a.count)
          .slice(0, 10)
          .map((m) => ({ name: m.medication, value: m.count, status: m.status }));

        // ── HITL / escalation outcomes ────────────────────────────────────────
        const totalLive = d.total_queries;
        const escalatedCount = Math.round(d.escalation_rate * totalLive);
        const autoCleared = totalLive - escalatedCount;
        // Backend doesn't break down HITL further — show what we have
        const hitlChartData = [
          { name: "Auto-Cleared", value: autoCleared },
          { name: "HITL Escalated", value: escalatedCount },
        ];

        // ── Proactive recs by category ────────────────────────────────────────
        const dietaryRecs = recsByCategory(recs, "dietary");
        const icdRecs = recsByCategory(recs, "icd10_cluster");
        const conflictRecs = recsByCategory(recs, "medication_conflict");

        // Dietary chart data
        const dietaryChartData = dietaryRecs.map((r) => ({
          name: stripPrefix(r.title, "High demand:").replace("dietary accommodation", "").trim(),
          value: r.magnitude,
        }));

        // ICD-10 chart data
        const icdChartData = icdRecs.map((r) => ({
          name: stripPrefix(r.title, "Emerging cluster:").trim(),
          value: r.magnitude,
        }));

        // Conflict chart data
        const conflictChartData = conflictRecs.map((r) => ({
          name: stripPrefix(r.title, "Cross-border conflict hotspot:").trim(),
          value: r.magnitude,
        }));

        return (
          <div className="flex flex-col gap-6">

            {/* ── KPI Metric Tiles (5 cards, single desktop row) ────────── */}
            <section>
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-[#525252]">
                Key Performance Indicators
              </p>
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
                <KpiTile
                  label="Total Queries"
                  value={d.total_queries.toLocaleString()}
                  sub="baseline + live"
                  accent="border-l-[#0f62fe]"
                />
                <KpiTile
                  label="Escalation Rate"
                  value={`${(d.escalation_rate * 100).toFixed(1)}%`}
                  sub="of live queries"
                  accent="border-l-[#da1e28]"
                />
                <KpiTile
                  label="Avg Pipeline Stages"
                  value={d.avg_pipeline_stages_completed.toFixed(1)}
                  sub="out of 4 stages"
                  accent="border-l-[#f1c21b]"
                />
                <KpiTile
                  label="Medication Flags"
                  value={totalMedFlags.toLocaleString()}
                  sub="live telemetry"
                  accent="border-l-[#24a148]"
                />
                <KpiTile
                  label="Active Jurisdictions"
                  value={String(activeJurCount || "—")}
                  sub={jurisdictionLabel}
                  accent="border-l-[#8a3ffc]"
                />
              </div>
            </section>

            <Separator className="bg-[#e0e0e0]" />

            {/* ── Row 1: Jurisdiction + Language ──────────────────────────── */}
            <section>
              <div className="grid gap-4 sm:grid-cols-2">

                {/* Chart 1: Queries by Jurisdiction (BarChart) */}
                <ChartCard title="Queries by Jurisdiction">
                  {jurisdictionChartData.length === 0 ? (
                    <p className="text-xs text-[#525252]">No jurisdiction data yet.</p>
                  ) : (
                    <ResponsiveContainer width="100%" height={260}>
                      <BarChart
                        data={jurisdictionChartData}
                        margin={{ top: 4, right: 8, left: -16, bottom: 0 }}
                      >
                        <CartesianGrid vertical={false} stroke="#e0e0e0" />
                        <XAxis
                          dataKey="name"
                          tick={{ fontFamily: "IBM Plex Mono, monospace", fontSize: 11, fill: "#525252" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          tick={{ fontFamily: "IBM Plex Mono, monospace", fontSize: 11, fill: "#525252" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip content={<CarbonTooltip />} />
                        <Bar dataKey="value" name="Queries" fill={C_BLUE} radius={[0, 0, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </ChartCard>

                {/* Chart 2: Queries by Language (BarChart, top 8 + Other) */}
                <ChartCard title="Queries by Language (Top 8 + Other)">
                  {langChartData.length === 0 ? (
                    <p className="text-xs text-[#525252]">No language data yet.</p>
                  ) : (
                    <ResponsiveContainer width="100%" height={260}>
                      <BarChart
                        data={langChartData}
                        margin={{ top: 4, right: 8, left: -16, bottom: 0 }}
                      >
                        <CartesianGrid vertical={false} stroke="#e0e0e0" />
                        <XAxis
                          dataKey="name"
                          tick={{ fontFamily: "IBM Plex Mono, monospace", fontSize: 11, fill: "#525252" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          tick={{ fontFamily: "IBM Plex Mono, monospace", fontSize: 11, fill: "#525252" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip content={<CarbonTooltip />} />
                        <Bar dataKey="value" name="Queries" radius={[0, 0, 0, 0]}>
                          {langChartData.map((_, idx) => (
                            <Cell
                              key={idx}
                              fill={CHART_PALETTE[idx % CHART_PALETTE.length]}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </ChartCard>
              </div>
            </section>

            <Separator className="bg-[#e0e0e0]" />

            {/* ── Row 2: User Persona Donut + HITL Outcomes ──────────────── */}
            <section>
              <div className="grid gap-4 sm:grid-cols-2">

                {/* Chart 3: User Persona Breakdown (PieChart donut) */}
                <ChartCard title="User Persona Breakdown">
                  {personaChartData.length === 0 ? (
                    <p className="text-xs text-[#525252]">No user type data yet.</p>
                  ) : (
                    <div className="flex items-center gap-6">
                      <ResponsiveContainer width="60%" height={200}>
                        <PieChart>
                          <Pie
                            data={personaChartData}
                            dataKey="value"
                            nameKey="name"
                            innerRadius={52}
                            outerRadius={80}
                            paddingAngle={2}
                          >
                            {personaChartData.map((_, idx) => (
                              <Cell
                                key={idx}
                                fill={CHART_PALETTE[idx % CHART_PALETTE.length]}
                              />
                            ))}
                          </Pie>
                          <Tooltip content={<CarbonTooltip />} />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="flex flex-col gap-2">
                        {personaChartData.map((entry, idx) => {
                          const pct = totalPersona > 0
                            ? ((entry.value / totalPersona) * 100).toFixed(1)
                            : "0.0";
                          return (
                            <div key={entry.name} className="flex items-center gap-2">
                              <span
                                className="inline-block h-3 w-3 shrink-0"
                                style={{ background: CHART_PALETTE[idx % CHART_PALETTE.length] }}
                              />
                              <span className="text-xs capitalize text-[#161616]">
                                {entry.name}
                              </span>
                              <span className="font-mono text-xs tabular-nums text-[#525252]">
                                {entry.value.toLocaleString()} ({pct}%)
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </ChartCard>

                {/* Chart 5: HITL Escalation & Safety Outcomes */}
                <ChartCard title="HITL Escalation & Safety Outcomes">
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart
                      data={hitlChartData}
                      margin={{ top: 4, right: 8, left: -16, bottom: 0 }}
                    >
                      <CartesianGrid vertical={false} stroke="#e0e0e0" />
                      <XAxis
                        dataKey="name"
                        tick={{ fontFamily: "IBM Plex Mono, monospace", fontSize: 11, fill: "#525252" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        tick={{ fontFamily: "IBM Plex Mono, monospace", fontSize: 11, fill: "#525252" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip content={<CarbonTooltip />} />
                      <Bar dataKey="value" name="Queries" radius={[0, 0, 0, 0]}>
                        <Cell fill={C_GREEN} />
                        <Cell fill={C_YELLOW} />
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  <div className="mt-3 flex items-center gap-4">
                    <span className="text-xs text-[#525252]">
                      Escalation Rate:&nbsp;
                      <span className="font-mono font-semibold tabular-nums text-[#161616]">
                        {(d.escalation_rate * 100).toFixed(1)}%
                      </span>
                    </span>
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
                </ChartCard>
              </div>
            </section>

            <Separator className="bg-[#e0e0e0]" />

            {/* ── Chart 4: Top Flagged Medications (horizontal bar + table) ── */}
            <section>
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-[#525252]">
                Top Flagged Medications — US FDA vs EU EMA
              </p>
              {d.top_medication_flags.length === 0 ? (
                <div className="rounded-none border border-[#e0e0e0] bg-white p-4">
                  <p className="text-xs text-[#525252]">No medication flags recorded yet.</p>
                </div>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  {/* Horizontal bar chart */}
                  <ChartCard title="Flag Count by Medication">
                    <ResponsiveContainer width="100%" height={Math.max(200, medsChartData.length * 36)}>
                      <BarChart
                        layout="vertical"
                        data={medsChartData}
                        margin={{ top: 4, right: 32, left: 8, bottom: 0 }}
                      >
                        <CartesianGrid horizontal={false} stroke="#e0e0e0" />
                        <XAxis
                          type="number"
                          tick={{ fontFamily: "IBM Plex Mono, monospace", fontSize: 11, fill: "#525252" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          type="category"
                          dataKey="name"
                          width={100}
                          tick={{ fontFamily: "IBM Plex Mono, monospace", fontSize: 11, fill: "#525252" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip content={<CarbonTooltip />} />
                        <Bar dataKey="value" name="Flags" fill={C_RED} radius={[0, 0, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </ChartCard>

                  {/* Regulatory status table */}
                  <div className="gap-0 rounded-none border border-[#e0e0e0] bg-white py-0 shadow-none ring-0 hover:border-[#8d8d8d] transition-colors">
                    <div className="bg-[#f4f4f4]/60 px-4 py-3">
                      <p className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
                        Regulatory Comparison Table
                      </p>
                    </div>
                    <div className="bg-[#e0e0e0]" style={{ height: 1 }} />
                    <table className="w-full text-xs" data-testid="medication-flags-table">
                      <thead>
                        <tr className="border-b border-[#e0e0e0] bg-[#f4f4f4]">
                          <th className="px-4 py-2 text-left font-semibold uppercase tracking-wider text-[#525252]">
                            Medication (INN)
                          </th>
                          <th className="px-4 py-2 text-left font-semibold uppercase tracking-wider text-[#525252]">
                            Status
                          </th>
                          <th className="px-4 py-2 text-right font-semibold uppercase tracking-wider text-[#525252]">
                            Flags
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {d.top_medication_flags.map((m, i) => (
                          <tr
                            key={i}
                            className={`border-b border-[#e0e0e0] ${i % 2 === 0 ? "bg-white" : "bg-[#f4f4f4]/30"}`}
                          >
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
                            <td className="px-4 py-2 text-right font-mono tabular-nums text-[#525252]">
                              {m.count}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </section>

            <Separator className="bg-[#e0e0e0]" />

            {/* ── Escalation Rate Gauge ────────────────────────────────────── */}
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
                              ? C_RED
                              : d.escalation_rate > 0.1
                              ? C_YELLOW
                              : C_GREEN,
                        }}
                      />
                    </div>
                    <div className="mt-2 flex gap-4 text-xs text-[#525252]">
                      <span>
                        <span
                          className="mr-1 inline-block h-2 w-4"
                          style={{ background: C_GREEN }}
                        />
                        Low (&lt;10%)
                      </span>
                      <span>
                        <span
                          className="mr-1 inline-block h-2 w-4"
                          style={{ background: C_YELLOW }}
                        />
                        Moderate (10–30%)
                      </span>
                      <span>
                        <span
                          className="mr-1 inline-block h-2 w-4"
                          style={{ background: C_RED }}
                        />
                        High (&gt;30%)
                      </span>
                    </div>
                  </div>
                  <div className="shrink-0">
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

            {/* ── Proactive Care Recommendations ──────────────────────────── */}
            <section>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-[#525252]">
                Emerging Care Needs &amp; Proactive Service Recommendations
              </p>
              <p className="mb-3 text-xs text-[#525252]">
                Pattern analysis from anonymized patient logs — dietary accommodation demand,
                high-frequency ICD-10 clusters by visitor group, and cross-border medication
                conflict hotspots. Zero PII.
              </p>

              {recs.length === 0 ? (
                <div className="rounded-none border border-[#e0e0e0] bg-white p-4">
                  <p className="text-xs text-[#525252]">
                    No proactive recommendations computed yet. Make sure{" "}
                    <code className="font-mono text-[10px]">synthetic_data/patient_logs.json</code>{" "}
                    exists.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">

                  {/* Card A: Dietary Accommodations */}
                  <Card className="gap-0 rounded-none border border-l-4 border-[#e0e0e0] border-l-[#0f62fe] bg-white py-0 shadow-none ring-0">
                    <CardHeader className="rounded-none bg-[#f4f4f4]/60 px-4 py-3">
                      <p className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
                        Dietary Accommodations
                      </p>
                      <p className="mt-0.5 text-xs text-[#525252]">
                        Patient dietary requirement demand by language cohort
                      </p>
                    </CardHeader>
                    <Separator className="bg-[#e0e0e0]" />
                    <CardContent className="space-y-3 p-4">
                      {dietaryRecs.length > 0 ? (
                        <>
                          <ResponsiveContainer width="100%" height={160}>
                            <BarChart
                              layout="vertical"
                              data={dietaryChartData}
                              margin={{ top: 0, right: 8, left: 4, bottom: 0 }}
                            >
                              <CartesianGrid horizontal={false} stroke="#e0e0e0" />
                              <XAxis
                                type="number"
                                tick={{ fontFamily: "IBM Plex Mono, monospace", fontSize: 10, fill: "#525252" }}
                                axisLine={false}
                                tickLine={false}
                              />
                              <YAxis
                                type="category"
                                dataKey="name"
                                width={72}
                                tick={{ fontFamily: "IBM Plex Mono, monospace", fontSize: 10, fill: "#525252" }}
                                axisLine={false}
                                tickLine={false}
                              />
                              <Tooltip content={<CarbonTooltip />} />
                              <Bar dataKey="value" name="Patients" fill={C_GREEN} radius={[0, 0, 0, 0]} />
                            </BarChart>
                          </ResponsiveContainer>

                          {/* Top 5 language cohorts + "+N more" pill */}
                          <div className="space-y-1.5">
                            {dietaryRecs.slice(0, 5).map((rec) => (
                              <div
                                key={rec.title}
                                className="flex items-center justify-between gap-2"
                              >
                                <div className="flex flex-wrap gap-1">
                                  {rec.affected_groups.slice(0, 2).map((g) => (
                                    <Badge
                                      key={g}
                                      variant="outline"
                                      className="rounded-none border-[#a6c8ff] bg-[#edf5ff] font-mono text-[10px] font-normal text-[#0043ce]"
                                    >
                                      <Security className="mr-1 h-3 w-3" />
                                      {g}
                                    </Badge>
                                  ))}
                                  {rec.affected_groups.length > 2 && (
                                    <span className="rounded-none border border-[#e0e0e0] bg-[#f4f4f4] px-1.5 py-0.5 font-mono text-[10px] text-[#525252]">
                                      +{rec.affected_groups.length - 2}
                                    </span>
                                  )}
                                </div>
                                <span className="font-mono text-xs tabular-nums text-[#525252]">
                                  {rec.magnitude}
                                </span>
                              </div>
                            ))}
                            {dietaryRecs.length > 5 && (
                              <span className="inline-block rounded-none border border-[#e0e0e0] bg-[#f4f4f4] px-2 py-0.5 font-mono text-[10px] text-[#525252]">
                                +{dietaryRecs.length - 5} more cohorts
                              </span>
                            )}
                          </div>
                        </>
                      ) : (
                        // Fallback: top language cohorts from queries_by_language
                        <>
                          {allLangEntries.slice(0, 5).map(([lang, count]) => (
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
                          ))}
                          {allLangEntries.length > 5 && (
                            <span className="inline-block rounded-none border border-[#e0e0e0] bg-[#f4f4f4] px-2 py-0.5 font-mono text-[10px] text-[#525252]">
                              +{allLangEntries.length - 5} more languages
                            </span>
                          )}
                        </>
                      )}
                      <p className="border border-[#e0e0e0] bg-[#f4f4f4] p-2 text-xs leading-relaxed text-[#525252]">
                        Recommend multilingual dietary guidance materials for top patient language
                        cohorts to reduce repeated clinical escalations.
                      </p>
                    </CardContent>
                  </Card>

                  {/* Card B: ICD-10 Clinical Clusters */}
                  <Card className="gap-0 rounded-none border border-l-4 border-[#e0e0e0] border-l-[#da1e28] bg-white py-0 shadow-none ring-0">
                    <CardHeader className="rounded-none bg-[#f4f4f4]/60 px-4 py-3">
                      <p className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
                        ICD-10 Clinical Clusters
                      </p>
                      <p className="mt-0.5 text-xs text-[#525252]">
                        High-frequency ICD-10 clusters by visitor group
                      </p>
                    </CardHeader>
                    <Separator className="bg-[#e0e0e0]" />
                    <CardContent className="space-y-3 p-4">
                      {icdRecs.length > 0 ? (
                        <>
                          <ResponsiveContainer width="100%" height={160}>
                            <BarChart
                              data={icdChartData}
                              margin={{ top: 0, right: 8, left: -16, bottom: 24 }}
                            >
                              <CartesianGrid vertical={false} stroke="#e0e0e0" />
                              <XAxis
                                dataKey="name"
                                tick={{ fontFamily: "IBM Plex Mono, monospace", fontSize: 9, fill: "#525252" }}
                                axisLine={false}
                                tickLine={false}
                                angle={-25}
                                textAnchor="end"
                              />
                              <YAxis
                                tick={{ fontFamily: "IBM Plex Mono, monospace", fontSize: 10, fill: "#525252" }}
                                axisLine={false}
                                tickLine={false}
                              />
                              <Tooltip content={<CarbonTooltip />} />
                              <Bar dataKey="value" name="Encounters" fill={C_BLUE} radius={[0, 0, 0, 0]} />
                            </BarChart>
                          </ResponsiveContainer>
                          <div className="space-y-2">
                            {icdRecs.slice(0, 3).map((rec) => (
                              <div key={rec.title} className="border border-[#e0e0e0] bg-white p-2">
                                <p className="font-mono text-xs font-medium text-[#161616]">
                                  {stripPrefix(rec.title, "Emerging cluster:")}
                                </p>
                                <p className="mt-0.5 text-xs leading-relaxed text-[#525252]">
                                  {rec.description}
                                </p>
                                {rec.affected_groups.length > 0 && (
                                  <p className="mt-1 font-mono text-[10px] text-[#525252]">
                                    Groups: {rec.affected_groups.join(" · ")}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        </>
                      ) : (
                        // Fallback: medication flags table
                        d.top_medication_flags.length === 0 ? (
                          <p className="text-xs text-[#525252]">No medication flags recorded.</p>
                        ) : (
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="border-b border-[#e0e0e0] bg-[#f4f4f4]">
                                <th className="px-3 py-1.5 text-left font-semibold uppercase tracking-wider text-[#525252]">Medication</th>
                                <th className="px-3 py-1.5 text-left font-semibold uppercase tracking-wider text-[#525252]">Status</th>
                                <th className="px-3 py-1.5 text-right font-semibold uppercase tracking-wider text-[#525252]">Count</th>
                              </tr>
                            </thead>
                            <tbody>
                              {d.top_medication_flags.map((m, i) => (
                                <tr key={i} className={`border-b border-[#e0e0e0] ${i % 2 === 0 ? "bg-white" : "bg-[#f4f4f4]/30"}`}>
                                  <td className="px-3 py-1.5 text-[#161616]">{m.medication}</td>
                                  <td className="px-3 py-1.5">
                                    <Badge variant="outline" className={`h-auto rounded-none px-1.5 py-0.5 text-[10px] font-medium ${medStatusBadgeClass(m.status)}`}>
                                      <MedStatusIcon status={m.status} />
                                      {m.status}
                                    </Badge>
                                  </td>
                                  <td className="px-3 py-1.5 text-right font-mono tabular-nums text-[#525252]">{m.count}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )
                      )}
                    </CardContent>
                  </Card>

                  {/* Card C: Cross-Border Drug Conflict Hotspots */}
                  <Card className="gap-0 rounded-none border border-l-4 border-[#e0e0e0] border-l-[#f1c21b] bg-white py-0 shadow-none ring-0">
                    <CardHeader className="rounded-none bg-[#f4f4f4]/60 px-4 py-3">
                      <p className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
                        Cross-Border Drug Conflict Hotspots
                      </p>
                      <p className="mt-0.5 text-xs text-[#525252]">
                        Patients on cross-jurisdiction conflict medications
                      </p>
                    </CardHeader>
                    <Separator className="bg-[#e0e0e0]" />
                    <CardContent className="space-y-3 p-4">
                      {conflictRecs.length > 0 ? (
                        <>
                          <ResponsiveContainer width="100%" height={160}>
                            <BarChart
                              layout="vertical"
                              data={conflictChartData}
                              margin={{ top: 0, right: 8, left: 4, bottom: 0 }}
                            >
                              <CartesianGrid horizontal={false} stroke="#e0e0e0" />
                              <XAxis
                                type="number"
                                tick={{ fontFamily: "IBM Plex Mono, monospace", fontSize: 10, fill: "#525252" }}
                                axisLine={false}
                                tickLine={false}
                              />
                              <YAxis
                                type="category"
                                dataKey="name"
                                width={80}
                                tick={{ fontFamily: "IBM Plex Mono, monospace", fontSize: 10, fill: "#525252" }}
                                axisLine={false}
                                tickLine={false}
                              />
                              <Tooltip content={<CarbonTooltip />} />
                              <Bar dataKey="value" name="Patients" fill={C_RED} radius={[0, 0, 0, 0]} />
                            </BarChart>
                          </ResponsiveContainer>
                          <div className="space-y-2">
                            {conflictRecs.slice(0, 3).map((rec) => (
                              <div key={rec.title} className="border border-[#e0e0e0] bg-white p-2">
                                <p className="font-mono text-xs font-medium text-[#161616]">
                                  {stripPrefix(rec.title, "Cross-border conflict hotspot:")}
                                </p>
                                <p className="mt-0.5 text-xs leading-relaxed text-[#525252]">
                                  {rec.description}
                                </p>
                                {rec.affected_groups.length > 0 && (
                                  <p className="mt-1 font-mono text-[10px] text-[#525252]">
                                    Nationalities: {rec.affected_groups.join(" · ")}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        </>
                      ) : (
                        // Fallback: escalation signal from user_type
                        <>
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
                          <div className="space-y-1.5">
                            {Object.entries(d.queries_by_user_type)
                              .sort((a, b) => b[1] - a[1])
                              .map(([ut, count]) => (
                                <div key={ut} className="flex items-center justify-between gap-2">
                                  <span className="text-xs capitalize text-[#161616]">{ut}</span>
                                  <span className="font-mono text-xs tabular-nums text-[#525252]">
                                    {count.toLocaleString()} queries
                                  </span>
                                </div>
                              ))}
                          </div>
                        </>
                      )}
                      <p className="border border-[#e0e0e0] bg-[#f4f4f4] p-2 text-xs leading-relaxed text-[#525252]">
                        {d.escalation_rate > 0.1
                          ? "Elevated cross-border conflict rate detected. Review medication registry for jurisdiction conflicts."
                          : "Cross-border conflict rate within normal bounds. Continue monitoring registry sync cadence."}
                      </p>
                    </CardContent>
                  </Card>

                </div>
              )}
            </section>

            <Separator className="bg-[#e0e0e0]" />
            <p className="font-mono text-xs text-[#525252]">
              🔒 Privacy: this dashboard contains only aggregate counts, language codes,
              and medication INN names. No raw query text or patient identifiers are present.
            </p>

          </div>
        );
      })()}
    </div>
  );
}
