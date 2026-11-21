/**
 * RegulatorySyncDrawer — "Sync Latest FDA/EMA Bulletins" sheet.
 * Calls POST /registry/sync and GET /registry/changelog.
 * Full IBM Carbon design system compliance per ui-design-system.md.
 */
import React, { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetBody,
} from "@/components/ui/sheet";
import {
  postRegistrySync,
  getRegistryChangelog,
  ApiError,
  type BulletinResponse,
  type ChangelogResponse,
} from "@/api/client";
import {
  CheckmarkFilled,
  CloseFilled,
  Security,
  WarningAltFilled,
} from "@carbon/icons-react";

// ─── Types ────────────────────────────────────────────────────────────────────

type SyncState =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "done"; result: BulletinResponse }
  | { phase: "error"; message: string };

// ─── Component ────────────────────────────────────────────────────────────────

interface Props {
  onSyncComplete?: () => void;
}

export default function RegulatorySyncDrawer({ onSyncComplete }: Props) {
  const [open, setOpen] = useState(false);

  // Sync form state
  const [medicationId, setMedicationId] = useState("");
  const [source, setSource] = useState("FDA Orange Book");
  const [status, setStatus] = useState("approved");
  const [restrictionReason, setRestrictionReason] = useState("");
  const [syncState, setSyncState] = useState<SyncState>({ phase: "idle" });

  // Changelog state
  const [changelog, setChangelog] = useState<ChangelogResponse | null>(null);
  const [changelogLoading, setChangelogLoading] = useState(false);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const loadChangelog = useCallback(async () => {
    setChangelogLoading(true);
    try {
      const data = await getRegistryChangelog(20);
      setChangelog(data);
    } catch {
      // silent — changelog is supplementary
    } finally {
      setChangelogLoading(false);
    }
  }, []);

  // Load changelog whenever sheet opens
  useEffect(() => {
    if (open) {
      loadChangelog();
    }
  }, [open, loadChangelog]);

  async function handleSync(e: React.FormEvent) {
    e.preventDefault();
    if (!medicationId.trim()) return;
    setSyncState({ phase: "loading" });

    try {
      const result = await postRegistrySync({
        medication_id: medicationId.trim(),
        source,
        updates: {
          status,
          restriction_reason: restrictionReason.trim() || null,
        },
      });
      setSyncState({ phase: "done", result });
      // Refresh changelog after successful sync
      await loadChangelog();
      // Notify parent to refresh registry list
      onSyncComplete?.();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Sync failed.";
      setSyncState({ phase: "error", message: msg });
    }
  }

  function statusBadgeClass(s: string) {
    if (s === "approved") return "border-[#24a148] bg-[#defbe6] text-[#0e6027]";
    if (s === "banned" || s === "delisted") return "border-[#da1e28] bg-[#fff1f1] text-[#a2191f]";
    return "border-[#f1c21b] bg-[#fcf4d6] text-[#161616]";
  }

  function statusIcon(s: string) {
    if (s === "approved") return <CheckmarkFilled className="mr-1 h-3 w-3 text-[#24a148]" />;
    if (s === "banned" || s === "delisted") return <CloseFilled className="mr-1 h-3 w-3 text-[#da1e28]" />;
    return <WarningAltFilled className="mr-1 h-3 w-3 text-[#b28600]" />;
  }

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex h-8 items-center gap-1.5 rounded-none bg-[#0f62fe] px-3 text-xs font-medium text-white hover:bg-[#0353e9] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0f62fe]"
      >
        Sync Latest FDA/EMA Bulletins
      </button>
      <SheetContent side="right" className="w-full sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Regulatory Sync</SheetTitle>
        </SheetHeader>
        <SheetBody className="space-y-6">

          {/* ── Section: Sync Form ─────────────────────────────────────── */}
          <div className="space-y-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
              Sync FDA/EMA Bulletin
            </p>

            <form onSubmit={handleSync} className="space-y-3">
              {/* Medication ID */}
              <div className="space-y-1">
                <label htmlFor="sync-medication-id" className="text-xs font-medium text-[#525252]">
                  Medication ID (UUID)
                </label>
                <Input
                  id="sync-medication-id"
                  value={medicationId}
                  onChange={(e) => setMedicationId(e.target.value)}
                  placeholder="e.g. med-001"
                  className="rounded-none text-xs"
                  disabled={syncState.phase === "loading"}
                />
              </div>

              {/* Source */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-[#525252]">Source</label>
                <Select value={source} onValueChange={setSource}>
                  <SelectTrigger aria-label="Source" className="h-8 w-full rounded-none text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="FDA Orange Book">FDA Orange Book</SelectItem>
                    <SelectItem value="EU Union Register">EU Union Register</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Status */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-[#525252]">New Status</label>
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger aria-label="New Status" className="h-8 w-full rounded-none text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="approved">Approved</SelectItem>
                    <SelectItem value="restricted">Restricted</SelectItem>
                    <SelectItem value="banned">Banned</SelectItem>
                    <SelectItem value="delisted">Delisted</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Restriction reason (optional) */}
              <div className="space-y-1">
                <label htmlFor="sync-restriction-reason" className="text-xs font-medium text-[#525252]">
                  Restriction Reason (optional)
                </label>
                <Textarea
                  id="sync-restriction-reason"
                  value={restrictionReason}
                  onChange={(e) => setRestrictionReason(e.target.value)}
                  placeholder="Reason for restriction, ban, or delisting…"
                  rows={3}
                  className="rounded-none text-xs"
                  disabled={syncState.phase === "loading"}
                />
              </div>

              <div className="flex items-center justify-between gap-3">
                <Button
                  type="submit"
                  size="sm"
                  className="h-8 rounded-none bg-[#0f62fe] text-xs font-medium text-white hover:bg-[#0353e9]"
                  disabled={!medicationId.trim() || syncState.phase === "loading"}
                >
                  {syncState.phase === "loading" ? "Syncing…" : "Sync Registry"}
                </Button>

                {syncState.phase === "done" && (
                  <div className="flex items-center gap-1.5">
                    <CheckmarkFilled className="h-3.5 w-3.5 text-[#24a148]" />
                    <span className="text-xs text-[#24a148]">
                      Sync complete — v{syncState.result.sync_version}
                    </span>
                  </div>
                )}

                {syncState.phase === "error" && (
                  <span className="text-xs text-[#da1e28]">{syncState.message}</span>
                )}
              </div>
            </form>

            {/* Sync result detail */}
            {syncState.phase === "done" && (
              <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 space-y-2">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="font-mono text-xs text-[#525252] tabular-nums">
                    {new Date(syncState.result.timestamp).toLocaleString()}
                  </span>
                  <Badge
                    variant="outline"
                    className="h-auto rounded-none border-[#a6c8ff] bg-[#edf5ff] font-mono text-xs font-normal text-[#0043ce]"
                  >
                    <Security aria-hidden="true" className="mr-1 h-3 w-3" />
                    {syncState.result.source}
                  </Badge>
                </div>
                <p className="text-xs text-[#525252]">
                  {syncState.result.changes.length} field change(s) applied
                </p>
                {syncState.result.changes.map((c, i) => (
                  <div key={i} className="font-mono text-xs text-[#525252]">
                    <span className="text-[#161616]">{c.field}</span>
                    {": "}
                    <span className="text-[#da1e28] line-through">
                      {String(c.old_value ?? "—")}
                    </span>
                    {" → "}
                    <span className="text-[#24a148]">{String(c.new_value ?? "—")}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <Separator className="bg-[#e0e0e0]" />

          {/* ── Section: Changelog ─────────────────────────────────────── */}
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
                Sync Changelog
                {changelog && (
                  <span className="ml-1.5 font-mono font-normal text-[#525252] tabular-nums">
                    ({changelog.total_entries} entries)
                  </span>
                )}
              </p>
              <button
                type="button"
                className="text-xs font-medium text-[#0f62fe] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0f62fe]"
                onClick={loadChangelog}
                disabled={changelogLoading}
              >
                {changelogLoading ? "Loading…" : "Refresh"}
              </button>
            </div>

            {changelogLoading && !changelog && (
              <p className="text-xs text-[#525252]">Loading changelog…</p>
            )}

            {!changelogLoading && changelog && changelog.entries.length === 0 && (
              <p className="text-xs text-[#525252]">No changelog entries yet.</p>
            )}

            {changelog && changelog.entries.length > 0 && (
              <div className="border border-[#e0e0e0] bg-white">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-[#e0e0e0] bg-[#f4f4f4]">
                      <th className="px-3 py-2 text-left font-semibold uppercase tracking-wider text-[#525252]">
                        Version
                      </th>
                      <th className="px-3 py-2 text-left font-semibold uppercase tracking-wider text-[#525252]">
                        Timestamp
                      </th>
                      <th className="px-3 py-2 text-left font-semibold uppercase tracking-wider text-[#525252]">
                        Source
                      </th>
                      <th className="px-3 py-2 text-left font-semibold uppercase tracking-wider text-[#525252]">
                        Changes
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {changelog.entries.map((entry, i) => {
                      const rowKey = entry.sync_version;
                      const isExpanded = expandedRow === rowKey;
                      // Determine status from first change that updates "status" field
                      const statusChange = entry.changes.find((c) => c.field === "status");
                      const newStatus = statusChange
                        ? String(statusChange.new_value)
                        : null;

                      return (
                        <React.Fragment key={rowKey}>
                          <tr
                            className={`border-b border-[#e0e0e0] cursor-pointer transition-colors ${
                              i % 2 === 0 ? "bg-white" : "bg-[#f4f4f4]/30"
                            } hover:bg-[#edf5ff]`}
                            onClick={() =>
                              setExpandedRow(isExpanded ? null : rowKey)
                            }
                          >
                            <td className="px-3 py-2 font-mono tabular-nums text-[#525252]">
                              {entry.sync_version}
                            </td>
                            <td className="px-3 py-2 font-mono tabular-nums text-[#525252]">
                              {new Date(entry.timestamp).toLocaleString()}
                            </td>
                            <td className="px-3 py-2">
                              <Badge
                                variant="outline"
                                className="h-auto rounded-none border-[#a6c8ff] bg-[#edf5ff] font-mono text-[10px] font-normal text-[#0043ce]"
                              >
                                <Security aria-hidden="true" className="mr-0.5 h-3 w-3" />
                                {entry.source}
                              </Badge>
                            </td>
                            <td className="px-3 py-2">
                              <span className="inline-flex items-center gap-1">
                                {newStatus && (
                                  <Badge
                                    variant="outline"
                                    className={`h-auto rounded-none px-1.5 py-0.5 text-[10px] font-medium ${statusBadgeClass(newStatus)}`}
                                  >
                                    {statusIcon(newStatus)}
                                    {newStatus}
                                  </Badge>
                                )}
                                <span className="font-mono text-[#525252] tabular-nums">
                                  {entry.changes.length} field{entry.changes.length !== 1 ? "s" : ""}
                                </span>
                              </span>
                            </td>
                          </tr>

                          {/* Expanded diff rows */}
                          {isExpanded && (
                            <tr
                              className={`border-b border-[#e0e0e0] ${
                                i % 2 === 0 ? "bg-white" : "bg-[#f4f4f4]/30"
                              }`}
                            >
                              <td colSpan={4} className="px-3 py-2">
                                <div className="space-y-1 pl-2 border-l-2 border-[#0f62fe]">
                                  {entry.changes.map((c, ci) => (
                                    <div key={ci} className="font-mono text-xs text-[#525252]">
                                      <span className="text-[#161616] font-medium">
                                        {c.medication_id} / {c.field}
                                      </span>
                                      {": "}
                                      <span className="text-[#da1e28] line-through">
                                        {String(c.old_value ?? "—")}
                                      </span>
                                      {" → "}
                                      <span className="text-[#24a148]">
                                        {String(c.new_value ?? "—")}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </SheetBody>
      </SheetContent>
    </Sheet>
  );
}
