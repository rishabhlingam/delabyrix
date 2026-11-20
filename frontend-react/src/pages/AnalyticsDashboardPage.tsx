/**
 * AnalyticsDashboardPage — Zero-PII BI Dashboard at /analytics
 *
 * TODO(teammate-3): Implement this page.
 *
 * Requirements:
 * ─────────────
 * 1. On mount, call GET /analytics/dashboard via getAnalyticsDashboard() from "@/api/client".
 *    Optional: add date_from / date_to filter inputs and a jurisdiction dropdown.
 *
 * 2. KPI Metric Tiles row (use 3–4 flat Carbon cards side by side):
 *    - Total Queries (total_queries)
 *    - Escalation Rate (escalation_rate as a percentage)
 *    - Avg Pipeline Stages Completed (avg_pipeline_stages_completed)
 *    - Top language (derive from queries_by_language)
 *
 *    Card style: rounded-none border border-[#e0e0e0] bg-white shadow-none
 *    Large number: text-2xl font-semibold text-[#0f62fe] tabular-nums
 *    Label: text-xs font-semibold uppercase tracking-wider text-[#525252]
 *
 * 3. Jurisdiction breakdown section:
 *    - Simple horizontal bar chart (use a plain <div> bar with bg-[#0f62fe])
 *    - Or use the create_chart tool for a BarChart if available
 *    - Data: jurisdiction_breakdown from the response
 *
 * 4. Proactive Recommendations cards (queries_by_user_type, top_medication_flags):
 *    Display as three flat cards in a row:
 *      a. "Dietary Accommodations" — country + language breakdown
 *      b. "ICD-10 Clusters" — top medication flags table
 *      c. "Conflict Hotspots" — escalation_rate by jurisdiction
 *
 *    Each card uses the same IBM Carbon flat card conventions as HITLReviewPage.
 *    The cards must NOT show any raw patient data (zero-PII).
 *
 * API hook in @/api/client:
 *   getAnalyticsDashboard(params?)  → AnalyticsDashboardResponse
 *
 * Type reference:
 *   interface AnalyticsDashboardResponse {
 *     total_queries: number;
 *     escalation_rate: number;
 *     queries_by_language: Record<string, number>;
 *     queries_by_user_type: Record<string, number>;
 *     top_medication_flags: Array<{ medication: string; status: string; count: number }>;
 *     avg_pipeline_stages_completed: number;
 *     jurisdiction_breakdown: Record<string, number>;
 *   }
 *
 * Design system tokens (ui-design-system.md):
 *   - Zero border radius everywhere (rounded-none)
 *   - Cards: border border-[#e0e0e0] bg-white shadow-none ring-0
 *   - Section labels: text-xs font-semibold uppercase tracking-wider text-[#525252]
 *   - Muted text: text-[#525252] text-xs
 *   - Mono numbers: font-mono tabular-nums text-[#161616]
 */

import React from "react";
import { Separator } from "@/components/ui/separator";

export default function AnalyticsDashboardPage() {
  // TODO(teammate-3): Add state: data, loading, error, filters

  return (
    <div className="flex flex-col gap-4 py-6">
      <div>
        <h1 className="text-base font-medium text-[#161616]">Analytics Dashboard</h1>
        <p className="mt-1 text-sm text-[#525252]">
          Zero-PII aggregated metrics for care coordination teams.
        </p>
      </div>
      <Separator className="bg-[#e0e0e0]" />

      {/* TODO(teammate-3): Replace this placeholder with KPI tiles, charts, and
          proactive recommendation cards. See the JSDoc comment at the top of
          this file for detailed requirements. */}
      <div className="border border-dashed border-[#e0e0e0] bg-white p-8 text-center">
        <p className="text-sm font-medium text-[#525252]">
          Analytics Dashboard — Teammate 3
        </p>
        <p className="mt-1 text-xs text-[#525252]">
          Implement KPI tiles, jurisdiction charts, and proactive recommendation cards.
        </p>
      </div>
    </div>
  );
}
