/**
 * RegulatorySyncDrawer — "Sync Latest FDA/EMA Bulletins" drawer.
 *
 * TODO(teammate-2): Implement this component.
 *
 * Requirements:
 * ─────────────
 * 1. Render a trigger button: "Sync Bulletins" with a Renew (or Sync) Carbon icon.
 *    Use the ghost variant: rounded-none h-8 text-xs text-[#0f62fe].
 *
 * 2. On click, open a Sheet (slide-over from the right) using the Sheet primitives
 *    from "@/components/ui/sheet".
 *
 * 3. Inside the sheet:
 *    a. A "Sync FDA/EMA Bulletins" section:
 *       - A form with:
 *           medication_id: Input (UUID of the registry record)
 *           source: Select (options: "FDA Orange Book", "EU Union Register")
 *           status: Select (options: "approved", "restricted", "banned", "delisted")
 *           restriction_reason: Textarea (optional)
 *       - Submit calls POST /registry/sync via postRegistrySync() from "@/api/client"
 *       - Show success (green badge) or error (red inline message)
 *
 *    b. A "Sync Changelog" section below a <Separator>:
 *       - Load GET /registry/changelog via getRegistryChangelog() on sheet open
 *       - Display as an audit table: columns sync_version | timestamp | source | changes count
 *       - Use font-mono text-xs for version + timestamp
 *       - Each row expandable (or tooltip) to show individual field-level diffs
 *
 * API hooks in @/api/client:
 *   postRegistrySync(body: BulletinRequest)   → BulletinResponse
 *   getRegistryChangelog(limit?: number)       → ChangelogResponse
 *
 * Design system tokens (ui-design-system.md):
 *   - Sheet header: p-4 border-b border-[#e0e0e0] bg-[#f4f4f4]
 *   - Approve/submit button: bg-[#0f62fe] rounded-none h-8 text-xs
 *   - Version column: font-mono text-xs text-[#525252] tabular-nums
 *   - Zero border radius everywhere (rounded-none)
 */

import React from "react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
  SheetBody,
} from "@/components/ui/sheet";

export default function RegulatorySyncDrawer() {
  // TODO(teammate-2): Add open/close state and full implementation.

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 rounded-none px-2 text-xs text-[#0f62fe] hover:bg-[#edf5ff] hover:text-[#0043ce]"
        >
          {/* TODO(teammate-2): Add a Carbon Renew/Sync icon here */}
          Sync Bulletins
        </Button>
      </SheetTrigger>
      <SheetContent side="right">
        <SheetHeader>
          <SheetTitle>Regulatory Sync</SheetTitle>
        </SheetHeader>
        <SheetBody>
          {/* TODO(teammate-2): Add the bulletin sync form and changelog table here.
              See the JSDoc comment at the top of this file for detailed requirements. */}
          <div className="border border-dashed border-[#e0e0e0] p-6 text-center">
            <p className="text-sm text-[#525252]">
              Teammate 2 — implement the sync form and changelog table.
            </p>
          </div>
        </SheetBody>
      </SheetContent>
    </Sheet>
  );
}
