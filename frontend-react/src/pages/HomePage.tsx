/**
 * HomePage — Landing page at /home (or the splash shown before navigating).
 *
 * Surfaces:
 * - Backend health status (GET /health)
 * - Active foundation model indicator (ibm/granite-4-h-small)
 * - Mock vs live watsonx status
 * - Quick-launch cards for every module
 *
 * Full IBM Carbon design system compliance per ui-design-system.md.
 */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { getHealth, ApiError, type HealthResponse } from "@/api/client";
import {
  CheckmarkFilled,
  CloseFilled,
  WarningAltFilled,
  Security,
  Time,
} from "@carbon/icons-react";

// ─── Backend health banner ─────────────────────────────────────────────────────

type HealthState =
  | { phase: "loading" }
  | { phase: "ok"; data: HealthResponse }
  | { phase: "error" };

function HealthBanner() {
  const [state, setState] = useState<HealthState>({ phase: "loading" });

  useEffect(() => {
    getHealth()
      .then((data) => setState({ phase: "ok", data }))
      .catch(() => setState({ phase: "error" }));
  }, []);

  if (state.phase === "loading") {
    return (
      <div className="flex items-center gap-2 border border-[#e0e0e0] bg-white px-4 py-2.5 text-xs text-[#525252]">
        <Time aria-hidden="true" className="h-3.5 w-3.5 text-[#b28600]" />
        Checking backend health…
      </div>
    );
  }

  if (state.phase === "error") {
    return (
      <div className="flex items-center gap-2 border border-[#da1e28] bg-[#fff1f1] px-4 py-2.5 text-xs text-[#a2191f]">
        <CloseFilled aria-hidden="true" className="h-3.5 w-3.5 text-[#da1e28]" />
        Backend offline — start{" "}
        <code className="font-mono">uvicorn backend.main:app --reload</code> to
        enable live mode.
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-3 border border-[#e0e0e0] bg-white px-4 py-2.5 text-xs">
      <span className="flex items-center gap-1.5 text-[#24a148]">
        <CheckmarkFilled aria-hidden="true" className="h-3.5 w-3.5" />
        Backend v{state.data.version} — {state.data.status}
      </span>
      <Separator orientation="vertical" className="h-4" />
      <span className="flex items-center gap-1.5 text-[#525252]">
        <Security aria-hidden="true" className="h-3.5 w-3.5 text-[#0f62fe]" />
        Model: ibm/granite-4-h-small
      </span>
      <Separator orientation="vertical" className="h-4" />
      <Badge
        variant="outline"
        className="h-auto rounded-none border-[#f1c21b] bg-[#fcf4d6] px-2 py-0.5 font-mono text-[10px] font-normal text-[#161616]"
      >
        <WarningAltFilled aria-hidden="true" className="mr-1 h-3 w-3 text-[#b28600]" />
        watsonx mock mode
      </Badge>
    </div>
  );
}

// ─── Quick-launch cards ────────────────────────────────────────────────────────

interface LaunchCard {
  to: string;
  title: string;
  role: string;
  description: string;
  stripe: string;
  icon: React.ReactNode;
}

const LAUNCH_CARDS: LaunchCard[] = [
  {
    to: "/patient",
    title: "Patient & Document Assistant",
    role: "Foreign Patient / International Traveler",
    description:
      "Get consent forms and billing documents explained in your language, check if your medications are allowed, and understand your care options.",
    stripe: "border-l-[#0f62fe]",
    icon: <CheckmarkFilled aria-hidden="true" className="h-3.5 w-3.5 text-[#24a148]" />,
  },
  {
    to: "/provider",
    title: "Provider Support",
    role: "Healthcare Provider",
    description:
      "Generate culturally adapted procedure explanations, review local policy checklists, and check for cross-border drug alerts for international patients.",
    stripe: "border-l-[#24a148]",
    icon: <Security aria-hidden="true" className="h-3.5 w-3.5 text-[#0f62fe]" />,
  },
  {
    to: "/hitl",
    title: "HITL Review Queue",
    role: "Care Coordinator / Administrator",
    description:
      "Review AI-generated responses that require human oversight, approve or edit draft responses, and monitor escalation activity.",
    stripe: "border-l-[#f1c21b]",
    icon: <Time aria-hidden="true" className="h-3.5 w-3.5 text-[#b28600]" />,
  },
  {
    to: "/analytics",
    title: "BI Analytics Dashboard",
    role: "Care Coordinator / Administrator",
    description:
      "Zero-PII aggregate interaction metrics: language breakdown, user persona, medication flags, jurisdiction distribution, and proactive care recommendations.",
    stripe: "border-l-[#8a3ffc]",
    icon: <CheckmarkFilled aria-hidden="true" className="h-3.5 w-3.5 text-[#8a3ffc]" />,
  },
  {
    to: "/registry",
    title: "Registry Explorer",
    role: "Any Role",
    description:
      "Browse and search the cross-border medication registry. Compare US FDA vs EU EMA regulatory status, sync latest bulletins, and view version changelog.",
    stripe: "border-l-[#da1e28]",
    icon: <WarningAltFilled aria-hidden="true" className="h-3.5 w-3.5 text-[#b28600]" />,
  },
];

// ─── Component ────────────────────────────────────────────────────────────────

export default function HomePage() {
  return (
    <div className="flex flex-col gap-6 py-6">
      {/* Hero header */}
      <div>
        <p className="text-xs font-semibold tracking-wide text-[#0f62fe]">
          Multilingual Clinical AI Agent &amp; BI Platform
        </p>
        <h1 className="mt-1 text-base font-medium text-[#161616]">
          Welcome to Delabyrix
        </h1>
        <p className="mt-1 text-sm text-[#525252]">
          Powered by IBM watsonx.ai · Granite 4 · Cross-Border Medication
          Registry. Use the navigation above or the quick-launch cards below to
          get started.
        </p>
      </div>

      {/* Backend health + model status */}
      <HealthBanner />

      <Separator className="bg-[#e0e0e0]" />

      {/* Quick-launch cards */}
      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-[#525252]">
          Quick Launch
        </p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {LAUNCH_CARDS.map((card) => (
            <Link key={card.to + card.title} to={card.to} aria-label={card.title} className="group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0f62fe]">
              <Card
                className={`h-full gap-0 rounded-none border border-l-4 border-[#e0e0e0] bg-white py-0 shadow-none ring-0 transition-colors hover:border-[#8d8d8d] ${card.stripe}`}
              >
                <CardHeader className="flex flex-row items-center gap-2 rounded-none bg-[#f4f4f4]/60 px-4 py-3">
                  {card.icon}
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-[#161616] truncate">
                      {card.title}
                    </p>
                    <p className="text-[10px] font-mono text-[#525252] truncate">
                      {card.role}
                    </p>
                  </div>
                </CardHeader>
                <Separator className="bg-[#e0e0e0]" />
                <CardContent className="p-4">
                  <p className="text-xs leading-relaxed text-[#525252]">
                    {card.description}
                  </p>
                  <span className="mt-3 inline-flex text-xs font-medium text-[#0f62fe] group-hover:underline">
                    Open →
                  </span>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </div>

      <Separator className="bg-[#e0e0e0]" />

      {/* Agentic pipeline overview */}
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#525252]">
            Agentic Pipeline (5 Stages)
          </p>
          <ol className="space-y-1.5 text-sm text-[#161616]">
            {[
              "Stage 0 — PII Redaction: strips personal identifiers before any LLM call",
              "Stage 1 — Translation: renders the query in English for downstream stages",
              "Stage 2 — Medical Interpretation: extracts clinical meaning + registry check",
              "Stage 3 — Cultural Context: adapts framing for jurisdiction and culture",
              "Stage 4 — Next Steps: generates role-appropriate guidance",
            ].map((s, i) => (
              <li
                key={i}
                className="border border-[#e0e0e0] bg-white px-3 py-2 text-xs text-[#161616]"
              >
                {s}
              </li>
            ))}
          </ol>
        </div>
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#525252]">
            Supported Languages &amp; Jurisdictions
          </p>
          <div className="space-y-2">
            {[
              { code: "en", name: "English" },
              { code: "es", name: "Español (Spanish)" },
              { code: "hi", name: "हिन्दी (Hindi)" },
            ].map(({ code, name }) => (
              <div key={code} className="flex items-center gap-2">
                <Badge
                  variant="outline"
                  className="rounded-none border-[#a6c8ff] bg-[#edf5ff] font-mono text-xs font-normal text-[#0043ce]"
                >
                  {code}
                </Badge>
                <span className="text-sm text-[#161616]">{name}</span>
              </div>
            ))}
            <div className="mt-2 flex flex-wrap gap-2">
              {["US_FDA", "EU_EMA"].map((j) => (
                <Badge
                  key={j}
                  variant="outline"
                  className="rounded-none border-[#a6c8ff] bg-[#edf5ff] font-mono text-xs font-normal text-[#0043ce]"
                >
                  <Security aria-hidden="true" className="mr-1 h-3 w-3" />
                  {j}
                </Badge>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
