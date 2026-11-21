/**
 * RegistryStatusCard — displays a single medication's registry status.
 * Used side-by-side for US_FDA vs EU_EMA comparison.
 */
import React from "react";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { CheckmarkFilled, CloseFilled, WarningAltFilled, Security } from "@carbon/icons-react";
import type { RegistryRecord } from "@/api/client";

interface Props {
  record: RegistryRecord | null;
  jurisdiction: "US_FDA" | "EU_EMA";
  loading?: boolean;
}

function StatusBadge({ status }: { status: RegistryRecord["status"] }) {
  if (status === "approved") {
    return (
      <Badge
        variant="outline"
        className="h-auto rounded-none border-[#24a148] bg-[#defbe6] px-2 py-0.5 text-xs font-medium text-[#0e6027]"
      >
        <CheckmarkFilled aria-hidden="true" className="mr-1.5 h-3.5 w-3.5 text-[#24a148]" />
        Approved
      </Badge>
    );
  }
  if (status === "banned" || status === "delisted") {
    return (
      <Badge
        variant="outline"
        className="h-auto rounded-none border-[#da1e28] bg-[#fff1f1] px-2 py-0.5 text-xs font-medium text-[#a2191f]"
      >
        <CloseFilled aria-hidden="true" className="mr-1.5 h-3.5 w-3.5 text-[#da1e28]" />
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    );
  }
  // restricted
  return (
    <Badge
      variant="outline"
      className="h-auto rounded-none border-[#f1c21b] bg-[#fcf4d6] px-2 py-0.5 text-xs font-medium text-[#161616]"
    >
      <WarningAltFilled aria-hidden="true" className="mr-1.5 h-3.5 w-3.5 text-[#b28600]" />
      Restricted
    </Badge>
  );
}

export default function RegistryStatusCard({ record, jurisdiction, loading }: Props) {
  const stripeColor =
    record?.status === "approved"
      ? "border-l-[#24a148]"
      : record?.status === "banned" || record?.status === "delisted"
      ? "border-l-[#da1e28]"
      : record?.status === "restricted"
      ? "border-l-[#f1c21b]"
      : "border-l-[#e0e0e0]";

  return (
    <div
      className={`flex-1 rounded-none border border-[#e0e0e0] bg-white border-l-4 ${stripeColor} shadow-none`}
    >
      {/* Card header */}
      <div className="flex items-center justify-between gap-2 rounded-none bg-[#f4f4f4]/60 px-4 py-3">
        <Badge
          variant="outline"
          className="h-auto rounded-none border-[#a6c8ff] bg-[#edf5ff] px-2 py-0.5 font-mono text-xs font-normal text-[#0043ce]"
        >
          <Security aria-hidden="true" className="mr-1 h-3.5 w-3.5" />
          {jurisdiction}
        </Badge>
        {record && <StatusBadge status={record.status} />}
      </div>
      <Separator className="bg-[#e0e0e0]" />

      {/* Body */}
      <div className="space-y-3 p-4">
        {loading && (
          <p className="text-sm text-[#525252]">Searching registry…</p>
        )}

        {!loading && !record && (
          <p className="text-sm text-[#525252]">No record found.</p>
        )}

        {!loading && record && (
          <>
            <div>
              <p className="mb-0.5 text-xs font-semibold uppercase tracking-wider text-[#525252]">
                Generic Name
              </p>
              <p className="text-sm text-[#161616]">{record.name_generic}</p>
            </div>

            {record.restriction_reason && (
              <div>
                <p className="mb-0.5 text-xs font-semibold uppercase tracking-wider text-[#525252]">
                  Restriction Reason
                </p>
                <div className="inline-flex items-start bg-[#fff1f1] px-2 py-1 text-xs font-medium text-[#da1e28]">
                  <WarningAltFilled aria-hidden="true" className="mr-1 mt-0.5 h-3.5 w-3.5 shrink-0" />
                  {record.restriction_reason}
                </div>
              </div>
            )}

            {record.therapeutic_alternatives.length > 0 && (
              <div>
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-[#525252]">
                  Therapeutic Alternatives
                </p>
                <ul className="space-y-1">
                  {record.therapeutic_alternatives.map((alt) => (
                    <li
                      key={alt}
                      className="border border-[#e0e0e0] bg-[#f4f4f4] px-2 py-1 text-xs text-[#161616]"
                    >
                      {alt}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <p className="font-mono text-xs text-[#525252] tabular-nums">
              Last updated: {record.last_updated}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
