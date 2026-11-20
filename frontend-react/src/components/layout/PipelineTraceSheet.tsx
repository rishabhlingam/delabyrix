/**
 * PipelineTraceSheet — slide-over that shows the 5-stage pipeline trace.
 * Triggered by a "View Trace" button on approved query results.
 */
import React, { useState } from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetBody,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { PipelineTrace } from "@/api/client";
import { DocumentView } from "@carbon/icons-react";

const STAGES = [
  { key: "translation", label: "Stage 1 — Translation" },
  { key: "medical_interpretation", label: "Stage 2 — Medical Interpretation" },
  { key: "cultural_context", label: "Stage 3 — Cultural Context" },
  { key: "next_steps", label: "Stage 4 — Next Steps" },
] as const;

interface Props {
  trace: PipelineTrace;
}

export default function PipelineTraceSheet({ trace }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 rounded-none px-2 text-xs text-[#0f62fe] hover:bg-[#edf5ff] hover:text-[#0043ce]"
        >
          <DocumentView className="mr-1.5 h-3.5 w-3.5" />
          View Pipeline Trace
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-full sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Pipeline Trace</SheetTitle>
        </SheetHeader>
        <SheetBody className="space-y-4 p-4">
          {/* Jurisdiction & PII flag */}
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-[#525252]">
              Jurisdiction
            </span>
            <span className="font-mono text-xs text-[#0043ce]">
              {trace.jurisdiction}
            </span>
            {trace.pii_redacted && (
              <span className="rounded-none border border-[#c6c6c6] bg-[#e5e5e5] px-1.5 py-0.5 font-mono text-xs font-medium text-[#161616]">
                [PII_REDACTED]
              </span>
            )}
          </div>
          <Separator className="bg-[#e0e0e0]" />
          {STAGES.map(({ key, label }) => (
            <div key={key}>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-[#525252]">
                {label}
              </p>
              <div className="border border-[#e0e0e0] bg-[#f4f4f4] p-3 text-sm leading-relaxed text-[#161616]">
                {trace[key]}
              </div>
            </div>
          ))}
        </SheetBody>
      </SheetContent>
    </Sheet>
  );
}
