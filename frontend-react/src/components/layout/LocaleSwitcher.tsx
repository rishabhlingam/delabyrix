/**
 * LocaleSwitcher — 3-button EN / ES / HI toggle in the AppShell header.
 * Uses Carbon Translate icon and wires to LocaleContext from @/lib/i18n.
 */
import React from "react";
import { Translate } from "@carbon/icons-react";
import { useLocale, type Locale } from "@/lib/i18n";

const LOCALE_LABELS: Record<Locale, string> = {
  en: "EN",
  es: "ES",
  hi: "HI",
};

export default function LocaleSwitcher() {
  const { locale, setLocale } = useLocale();

  return (
    <div className="flex items-center gap-1.5">
      <Translate className="h-3.5 w-3.5 text-[#525252]" />
      <div className="flex gap-0.5">
        {(["en", "es", "hi"] as Locale[]).map((l) => (
          <button
            key={l}
            onClick={() => setLocale(l)}
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
    </div>
  );
}
