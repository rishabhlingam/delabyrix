/**
 * ProviderSupportPage — Provider consultation intake and clinical guidance view.
 *
 * TODO(teammate-1): Implement this page.
 *
 * Requirements:
 * ─────────────
 * 1. Add a form with fields:
 *    - Clinical query textarea (the provider's question)
 *    - Patient country selector (ISO 3166-1 alpha-2: US, DE, FR, ES, IN, GB)
 *    - Language selector (en, es, hi)
 *    - optional session_id input
 *
 * 2. On submit, call POST /agent/query with { user_type: "provider", ... }
 *    using the postAgentQuery() hook from "@/api/client".
 *    - If 200 OK: show the full AgentQueryResponse with pipeline trace
 *    - If 202 Accepted: start polling GET /agent/session/{id} every 3s
 *
 * 3. Display the response with the same IBM Carbon card conventions used in
 *    PatientAssistantPage.tsx:
 *    - PENDING: border-l-[#f1c21b] + WarningAltFilled badge
 *    - APPROVED: border-l-[#24a148] + CheckmarkFilled badge
 *    - REJECTED: border-l-[#da1e28] + CloseFilled badge
 *
 * 4. For approved responses, add a "View Pipeline Trace" slide-over using
 *    <PipelineTraceSheet trace={result.pipeline_trace} />.
 *
 * 5. Add a note: "Clinical guidance is culturally framed for the provider's
 *    local context." below the response.
 *
 * API hooks available in @/api/client:
 *   postAgentQuery(body: AgentQueryRequest)
 *   getSessionStatus(sessionId: string)
 *
 * Design system tokens (ui-design-system.md):
 *   - Use IBM Carbon border-l-4 stripes for status
 *   - Cards: rounded-none border border-[#e0e0e0] shadow-none ring-0
 *   - Buttons: rounded-none h-8 text-xs font-medium
 *   - Font: IBM Plex Mono for session IDs/timestamps
 */

import React from "react";
import { Separator } from "@/components/ui/separator";

export default function ProviderSupportPage() {
  return (
    <div className="flex flex-col gap-4 py-6">
      <div>
        <h1 className="text-base font-medium text-[#161616]">Provider Support</h1>
        <p className="mt-1 text-sm text-[#525252]">
          Culturally framed clinical guidance for healthcare providers.
        </p>
      </div>
      <Separator className="bg-[#e0e0e0]" />

      {/* TODO(teammate-1): Replace this placeholder with the full implementation.
          See the JSDoc comment at the top of this file for detailed requirements. */}
      <div className="border border-dashed border-[#e0e0e0] bg-white p-8 text-center">
        <p className="text-sm font-medium text-[#525252]">
          Provider Support — Teammate 1
        </p>
        <p className="mt-1 text-xs text-[#525252]">
          Implement the provider intake form and clinical guidance view in this file.
        </p>
      </div>
    </div>
  );
}
