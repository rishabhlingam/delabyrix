/**
 * LocaleSwitcher — UI chrome localization for EN / ES / HI.
 *
 * TODO(teammate-4): Implement this component AND the i18n library at src/lib/i18n.ts.
 *
 * Requirements:
 * ─────────────
 * 1. Create src/lib/i18n.ts:
 *    - Export a type: Locale = "en" | "es" | "hi"
 *    - Export a constant TRANSLATIONS: Record<Locale, Record<string, string>>
 *      containing at minimum these keys:
 *        "nav.patient_assistant", "nav.hitl_review", "nav.registry",
 *        "nav.provider_support", "nav.analytics",
 *        "status.pending", "status.approved", "status.rejected",
 *        "action.submit", "action.approve", "action.reject", "action.refresh",
 *        "action.search", "action.analyze_document"
 *    - Export a React context: LocaleContext with { locale, setLocale }
 *    - Export a hook: useLocale() → { locale, t(key: string) → string, setLocale }
 *
 * 2. Wrap <App> in <LocaleProvider> in src/main.tsx.
 *
 * 3. This LocaleSwitcher component:
 *    - Should render as a 3-button toggle (EN | ES | HI) in the AppShell header.
 *    - Integrates with the LocaleContext to switch the active locale.
 *    - Use the same ghost/active button style as the mode switcher in PatientAssistantPage:
 *        active:   bg-[#0f62fe] text-white rounded-none px-2 py-1 text-xs
 *        inactive: border border-[#e0e0e0] bg-white text-[#525252] rounded-none px-2 py-1 text-xs
 *
 * 4. Integrate useLocale() into AppShell.tsx navigation labels so that nav links
 *    use t("nav.patient_assistant") etc. instead of hard-coded strings.
 *
 * 5. Integrate useLocale() into HITLReviewPage.tsx status badge text so badges
 *    display t("status.pending"), t("status.approved"), t("status.rejected").
 *
 * 6. Integrate useLocale() into button labels in PatientAssistantPage.tsx:
 *    t("action.submit"), t("action.analyze_document"), etc.
 *
 * File locations:
 *   This component → src/components/layout/LocaleSwitcher.tsx
 *   i18n library   → src/lib/i18n.ts
 *
 * Design system tokens (ui-design-system.md):
 *   - Zero border radius (rounded-none)
 *   - Active locale: bg-[#0f62fe] text-white
 *   - Inactive locale: border border-[#e0e0e0] text-[#525252] hover:bg-[#f4f4f4]
 */

import React from "react";

// TODO(teammate-4): Import and use LocaleContext from "@/lib/i18n"
// import { useLocale } from "@/lib/i18n";

export type Locale = "en" | "es" | "hi";

const LOCALE_LABELS: Record<Locale, string> = {
  en: "EN",
  es: "ES",
  hi: "HI",
};

export default function LocaleSwitcher() {
  // TODO(teammate-4): Replace this stub with real locale switching.
  // const { locale, setLocale } = useLocale();
  const locale: Locale = "en"; // stub

  return (
    <div className="flex gap-0.5">
      {(["en", "es", "hi"] as Locale[]).map((l) => (
        <button
          key={l}
          // TODO(teammate-4): onClick={() => setLocale(l)}
          className={`rounded-none px-2 py-1 text-xs font-medium transition-colors ${
            locale === l
              ? "bg-[#0f62fe] text-white"
              : "border border-[#e0e0e0] bg-white text-[#525252] hover:bg-[#f4f4f4]"
          }`}
        >
          {LOCALE_LABELS[l]}
        </button>
      ))}
    </div>
  );
}
