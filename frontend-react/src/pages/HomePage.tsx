/**
 * HomePage — Landing page at /home (or the splash shown before navigating).
 *
 * Surfaces:
 * - App description and hero header
 * - Quick-launch cards for every module
 * - Agentic pipeline overview and language/jurisdiction list
 *
 * Full IBM Carbon design system compliance per ui-design-system.md.
 */
import React from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  CheckmarkFilled,
  WarningAltFilled,
  Security,
  Time,
} from "@carbon/icons-react";

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
        <h1 className="text-2xl font-semibold tracking-tight text-[#161616]">
          Welcome to Delabyrix
        </h1>
        <p className="mt-1 text-sm font-medium text-[#0f62fe]">
          Multilingual Clinical AI Agent &amp; BI Platform
        </p>
        <p className="mt-3 text-sm leading-relaxed text-[#161616]">
          Delabyrix is a multilingual clinical AI platform that helps foreign
          patients, healthcare providers, and care coordinators navigate
          cross-border medical care. It goes beyond word-for-word translation —
          interpreting medical meaning, applying cultural context, checking
          jurisdiction-specific medication registries (US FDA &amp; EU EMA), and
          routing high-stakes outputs through mandatory human review before
          returning guidance.
        </p>
        <div className="mt-4 rounded-none border border-[#a6c8ff] border-l-4 border-l-[#0f62fe] bg-[#edf5ff] px-3.5 py-2.5 text-xs font-medium text-[#0043ce]">
          Powered by IBM watsonx.ai · Granite 4 · Cross-Border Medication
          Registry. Use the navigation above or the quick-launch cards below to
          get started.
        </div>
      </div>

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
