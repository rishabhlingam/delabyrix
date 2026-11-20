# Teammate Tasks — Delabyrix React Frontend

This document describes the four open starter tasks reserved for teammates.
Each task has a dedicated file with a detailed JSDoc comment at the top explaining
exactly what to build, which API hooks to use, and which design tokens to follow.

> **Dev environment**: `cd frontend-react && npm install && npm run dev`
> Backend must be running: `uvicorn backend.main:app --reload --port 8000`

---

## Teammate 1 — Provider Support Page

**File**: [`src/pages/ProviderSupportPage.tsx`](src/pages/ProviderSupportPage.tsx)
**Route**: `/provider`

### What to build
A provider consultation intake form with culturally framed clinical guidance:

1. Form fields: clinical query textarea, patient country selector (US/DE/FR/ES/IN/GB), language selector (en/es/hi), optional session_id.
2. Submit calls `POST /agent/query` with `user_type: "provider"` using `postAgentQuery()` from `@/api/client`.
3. Handle both 200 (direct) and 202 (escalated) responses identically to `PatientAssistantPage.tsx`.
4. Show `<PipelineTraceSheet>` for approved responses.
5. Render status cards with `border-l-4` stripes (PENDING/APPROVED/REJECTED) using the same IBM Carbon conventions as the existing pages.

### Key imports already available
```ts
import { postAgentQuery, getSessionStatus } from "@/api/client";
import PipelineTraceSheet from "@/components/layout/PipelineTraceSheet";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckmarkFilled, WarningAltFilled, CloseFilled, Time } from "@carbon/icons-react";
```

### No merge conflicts with
Teammate 2, 3, 4 — all working in separate files.

---

## Teammate 2 — Regulatory Sync Drawer

**File**: [`src/components/registry/RegulatorySyncDrawer.tsx`](src/components/registry/RegulatorySyncDrawer.tsx)
**Location**: Embedded in `/registry` via `<RegulatorySyncDrawer />` already imported in `RegistryExplorerPage.tsx`

### What to build
A Sheet slide-over for syncing FDA/EMA regulatory bulletins and viewing the changelog:

1. **Sync form** (top half of sheet):
   - `medication_id` Input (UUID)
   - `source` Select: "FDA Orange Book" | "EU Union Register"
   - Mutable fields: `status` Select, `restriction_reason` Textarea
   - Submit → `postRegistrySync(body)` from `@/api/client`
   - Show success/error inline

2. **Changelog table** (bottom half, below `<Separator>`):
   - Load `getRegistryChangelog()` when sheet opens
   - Columns: `sync_version` | `timestamp` | `source` | changes count
   - Use `font-mono text-xs tabular-nums` for version and timestamp
   - Expandable rows showing field-level diffs (or tooltip)

### Key imports already available
```ts
import { postRegistrySync, getRegistryChangelog } from "@/api/client";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger, SheetBody } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
```

### No merge conflicts with
Teammate 1, 3, 4 — `RegistryExplorerPage.tsx` already has `<RegulatorySyncDrawer />` as a stub.

---

## Teammate 3 — Analytics Dashboard

**File**: [`src/pages/AnalyticsDashboardPage.tsx`](src/pages/AnalyticsDashboardPage.tsx)
**Route**: `/analytics`

### What to build
A zero-PII BI dashboard:

1. **KPI tiles row** (3–4 flat Carbon cards side-by-side):
   - Total Queries, Escalation Rate (%), Avg Pipeline Stages, Top Language
   - Card style: `rounded-none border border-[#e0e0e0] bg-white shadow-none`
   - Number: `text-2xl font-semibold text-[#0f62fe] tabular-nums`

2. **Jurisdiction breakdown** — horizontal bar chart (use plain `<div>` bars with `bg-[#0f62fe]`).

3. **Proactive Recommendation cards** (3 cards, `flex gap-4`):
   - "Dietary Accommodations" — country+language breakdown table
   - "ICD-10 Clusters" — `top_medication_flags` table
   - "Conflict Hotspots" — escalation rate visual

4. Optional: add `date_from` / `date_to` filter inputs + a jurisdiction dropdown at the top.

### Key API hook
```ts
import { getAnalyticsDashboard, type AnalyticsDashboardResponse } from "@/api/client";
```

### Response shape
```ts
{
  total_queries: number;
  escalation_rate: number;        // 0.0–1.0
  queries_by_language: Record<string, number>;
  queries_by_user_type: Record<string, number>;
  top_medication_flags: Array<{ medication: string; status: string; count: number }>;
  avg_pipeline_stages_completed: number;
  jurisdiction_breakdown: Record<string, number>;
}
```

### No merge conflicts with
Teammate 1, 2, 4.

---

## Teammate 4 — Locale Switcher & i18n

**Files**:
- [`src/components/layout/LocaleSwitcher.tsx`](src/components/layout/LocaleSwitcher.tsx)
- [`src/lib/i18n.ts`](src/lib/i18n.ts)

### What to build

1. **`src/lib/i18n.ts`** — Add `LocaleContext`, `LocaleProvider`, and `useLocale()` hook.
   The scaffold/comments for this are already in `i18n.ts`. Translation keys for EN/ES/HI
   are pre-filled — just wire up the React context around them.

2. **`src/components/layout/LocaleSwitcher.tsx`** — Wire the `useLocale()` hook and remove the
   `const locale = "en"` stub so the 3-button toggle actually switches locale.

3. **`src/main.tsx`** — Wrap `<App />` with `<LocaleProvider>`.

4. **`src/components/layout/AppShell.tsx`** — Replace hard-coded nav labels with `t("nav.*")` calls.

5. **`src/pages/HITLReviewPage.tsx`** — Replace status badge text with `t("status.*")` calls.

6. **`src/pages/PatientAssistantPage.tsx`** — Replace button labels with `t("action.*")` calls.

### No merge conflicts with
Teammate 1, 2, 3 — none of their files use the locale system.

---

## Design System Reference

All UI must follow [`../.bob/rules-agent/ui-design-system.md`](../.bob/rules-agent/ui-design-system.md).

Key rules:
- **Zero border radius everywhere** — always use `rounded-none` on cards, buttons, badges, inputs
- **Status stripes** — `border-l-4 border-l-[#f1c21b | #24a148 | #da1e28]` for PENDING/APPROVED/REJECTED
- **Font** — IBM Plex Sans for all UI text, IBM Plex Mono (`font-mono tabular-nums`) for IDs/timestamps/jurisdiction
- **Carbon icons** — `@carbon/icons-react` for all product actions; `lucide-react` only inside shadcn primitives
- **Card** — `rounded-none border border-[#e0e0e0] bg-white shadow-none ring-0`
- **Primary button** — `h-8 rounded-none bg-[#0f62fe] text-xs font-medium text-white hover:bg-[#0353e9]`
- **Ghost button** — `h-7 rounded-none px-2 text-xs text-[#0f62fe] hover:bg-[#edf5ff] hover:text-[#0043ce]`
- **PII tokens** — `border border-[#c6c6c6] bg-[#e5e5e5] px-1.5 py-0.5 font-mono text-xs`

## Validation

Before submitting, run:
```sh
cd frontend-react
npm run build          # must pass with zero errors
npx tsc --noEmit       # must pass with zero errors
```

Then start backend and check your page loads at http://localhost:5173.
