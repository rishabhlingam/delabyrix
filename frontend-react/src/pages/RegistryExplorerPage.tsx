/**
 * RegistryExplorerPage — Cross-Border Registry Explorer at /registry
 *
 * Features:
 * - Search by medication name → GET /registry/check for US_FDA and EU_EMA
 * - Side-by-side regulatory status cards
 * - Paginated full registry listing → GET /registry/list
 *
 * Teammate 2 placeholder (RegulatorySyncDrawer) is imported and shown
 * within this page (see src/components/registry/RegulatorySyncDrawer.tsx).
 */
import React, { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import RegistryStatusCard from "@/components/registry/RegistryStatusCard";
import RegulatorySyncDrawer from "@/components/registry/RegulatorySyncDrawer";
import {
  getRegistryCheck,
  getRegistryList,
  ApiError,
  type RegistryRecord,
} from "@/api/client";
import { Security, WarningAltFilled, CheckmarkFilled, CloseFilled } from "@carbon/icons-react";

type SearchState =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "done"; fda: RegistryRecord | null; ema: RegistryRecord | null }
  | { phase: "error"; message: string };

function StatusIcon({ status }: { status: RegistryRecord["status"] }) {
  if (status === "approved") return <CheckmarkFilled className="h-3.5 w-3.5 text-[#24a148]" />;
  if (status === "banned" || status === "delisted") return <CloseFilled className="h-3.5 w-3.5 text-[#da1e28]" />;
  return <WarningAltFilled className="h-3.5 w-3.5 text-[#b28600]" />;
}

export default function RegistryExplorerPage() {
  const [search, setSearch] = useState("");
  const [searchState, setSearchState] = useState<SearchState>({ phase: "idle" });

  // Paginated list
  const [listPage, setListPage] = useState(1);
  const [listTotal, setListTotal] = useState(0);
  const [listRecords, setListRecords] = useState<RegistryRecord[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [jurisdictionFilter, setJurisdictionFilter] = useState<string>("");

  const PAGE_SIZE = 10;

  const loadList = useCallback(async (page: number, jur: string) => {
    setListLoading(true);
    try {
      const res = await getRegistryList({
        page,
        page_size: PAGE_SIZE,
        jurisdiction: jur || undefined,
      });
      setListRecords(res.records);
      setListTotal(res.total);
    } catch {
      // silent
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    loadList(listPage, jurisdictionFilter);
  }, [listPage, jurisdictionFilter, loadList]);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!search.trim()) return;
    setSearchState({ phase: "loading" });

    try {
      const [fdaResult, emaResult] = await Promise.allSettled([
        getRegistryCheck({ medication_name: search.trim(), jurisdiction: "US_FDA" }),
        getRegistryCheck({ medication_name: search.trim(), jurisdiction: "EU_EMA" }),
      ]);

      const fda = fdaResult.status === "fulfilled" ? fdaResult.value : null;
      const ema = emaResult.status === "fulfilled" ? emaResult.value : null;

      if (fda === null && ema === null) {
        setSearchState({
          phase: "error",
          message: `No records found for "${search.trim()}" in US_FDA or EU_EMA.`,
        });
      } else {
        setSearchState({ phase: "done", fda, ema });
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "An unexpected error occurred.";
      setSearchState({ phase: "error", message: msg });
    }
  }

  const totalPages = Math.ceil(listTotal / PAGE_SIZE);

  return (
    <div className="flex flex-col gap-4 py-6">
      {/* Page title */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-base font-medium text-[#161616]">
            Cross-Border Registry Explorer
          </h1>
          <p className="mt-1 text-sm text-[#525252]">
            Check medication regulatory status across US FDA and EU EMA.
          </p>
        </div>
        {/* Regulatory Sync Drawer — refreshes registry list on successful sync */}
        <RegulatorySyncDrawer onSyncComplete={() => loadList(1, jurisdictionFilter)} />
      </div>

      <Separator className="bg-[#e0e0e0]" />

      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search medication by INN or brand name…"
          className="rounded-none"
        />
        <Button
          type="submit"
          size="sm"
          className="h-9 rounded-none bg-[#0f62fe] text-xs font-medium text-white hover:bg-[#0353e9]"
          disabled={!search.trim() || searchState.phase === "loading"}
        >
          Search
        </Button>
      </form>

      {/* Search results — side-by-side jurisdiction cards */}
      {searchState.phase === "loading" && (
        <p className="text-sm text-[#525252]">Checking registries…</p>
      )}

      {searchState.phase === "error" && (
        <div className="border border-[#da1e28] bg-[#fff1f1] p-3 text-sm text-[#a2191f]">
          {searchState.message}
        </div>
      )}

      {searchState.phase === "done" && (
        <div className="flex flex-col gap-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
            Regulatory Status
          </p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <RegistryStatusCard
              record={searchState.fda}
              jurisdiction="US_FDA"
            />
            <RegistryStatusCard
              record={searchState.ema}
              jurisdiction="EU_EMA"
            />
          </div>
        </div>
      )}

      <Separator className="bg-[#e0e0e0]" />

      {/* Full registry listing */}
      <div>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
            Full Registry ({listTotal} records)
          </p>
          {/* Jurisdiction filter */}
          <div className="flex gap-1">
            {["", "US_FDA", "EU_EMA"].map((jur) => (
              <button
                key={jur}
                onClick={() => {
                  setJurisdictionFilter(jur);
                  setListPage(1);
                }}
                className={`rounded-none px-2 py-1 text-xs font-medium transition-colors ${
                  jurisdictionFilter === jur
                    ? "bg-[#0f62fe] text-white"
                    : "border border-[#e0e0e0] bg-white text-[#525252] hover:bg-[#f4f4f4]"
                }`}
              >
                {jur || "All"}
              </button>
            ))}
          </div>
        </div>

        {listLoading && <p className="text-sm text-[#525252]">Loading…</p>}

        {!listLoading && (
          <div className="border border-[#e0e0e0] bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#e0e0e0] bg-[#f4f4f4]">
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-[#525252]">
                    Generic Name
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-[#525252]">
                    Jurisdiction
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-[#525252]">
                    Status
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-[#525252]">
                    Last Updated
                  </th>
                </tr>
              </thead>
              <tbody>
                {listRecords.map((rec, i) => (
                  <tr
                    key={rec.medication_id}
                    className={`border-b border-[#e0e0e0] ${
                      i % 2 === 0 ? "bg-white" : "bg-[#f4f4f4]/30"
                    }`}
                  >
                    <td className="px-4 py-2 text-[#161616]">{rec.name_generic}</td>
                    <td className="px-4 py-2">
                      <Badge
                        variant="outline"
                        className="rounded-none border-[#a6c8ff] bg-[#edf5ff] font-mono text-xs font-normal text-[#0043ce]"
                      >
                        <Security className="mr-1 h-3 w-3" />
                        {rec.jurisdiction}
                      </Badge>
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`inline-flex items-center gap-1 text-xs font-medium ${
                          rec.status === "approved"
                            ? "text-[#24a148]"
                            : rec.status === "banned" || rec.status === "delisted"
                            ? "text-[#da1e28]"
                            : "text-[#b28600]"
                        }`}
                      >
                        <StatusIcon status={rec.status} />
                        {rec.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 font-mono text-xs text-[#525252] tabular-nums">
                      {rec.last_updated}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="mt-3 flex items-center justify-between">
            <span className="font-mono text-xs text-[#525252] tabular-nums">
              Page {listPage} of {totalPages}
            </span>
            <div className="flex gap-1">
              <Button
                variant="outline"
                size="sm"
                className="h-7 rounded-none px-2 text-xs"
                disabled={listPage <= 1}
                onClick={() => setListPage((p) => p - 1)}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-7 rounded-none px-2 text-xs"
                disabled={listPage >= totalPages}
                onClick={() => setListPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
