/**
 * AppShell — Carbon-compliant top-nav layout with live HITL pending badge and locale switcher.
 * Uses IBM Carbon design tokens throughout per ui-design-system.md.
 */
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Separator } from "@/components/ui/separator";
import LocaleSwitcher from "@/components/layout/LocaleSwitcher";
import { getHITLQueue } from "@/api/client";
import { useLocale } from "@/lib/i18n";
import { cn } from "@/lib/utils";

function PendingBadge({ count }: { count: number }) {
  if (count === 0) return null;
  return (
    <span
      aria-label={`${count} pending items`}
      className="ml-1.5 inline-flex items-center justify-center rounded-none bg-[#da1e28] px-1.5 py-0.5 font-mono text-[10px] font-medium text-white tabular-nums"
    >
      {count}
    </span>
  );
}

// Maps sub-route paths to their page title i18n keys
const ROUTE_TITLE_KEYS: Record<string, string> = {
  "/patient": "page.patient_title",
  "/hitl": "page.hitl_title",
  "/registry": "page.registry_title",
  "/provider": "page.provider_title",
  "/analytics": "page.analytics_title",
};

const NAV_ITEMS = [
  { to: "/", labelKey: "nav.home" },
  { to: "/patient", labelKey: "nav.patient_assistant" },
  { to: "/hitl", labelKey: "nav.hitl_review", showBadge: true },
  { to: "/registry", labelKey: "nav.registry" },
  { to: "/provider", labelKey: "nav.provider_support" },
  { to: "/analytics", labelKey: "nav.analytics" },
] as const;

const SITE_NAME = "Delabyrix";
const DEFAULT_HOME_TITLE = "Delabyrix — Cross-Border Clinical AI Navigation";

export default function AppShell() {
  const [pendingCount, setPendingCount] = useState(0);
  const { t } = useLocale();
  const location = useLocation();

  // Update browser tab title on every navigation using active locale
  useEffect(() => {
    const key = ROUTE_TITLE_KEYS[location.pathname];
    const pageLabel = key ? t(key) : null;
    document.title = pageLabel
      ? `${pageLabel} · ${SITE_NAME}`
      : DEFAULT_HOME_TITLE;
  }, [location.pathname, t]);

  useEffect(() => {
    let cancelled = false;

    async function fetchPending() {
      try {
        const q = await getHITLQueue();
        if (!cancelled) setPendingCount(q.pending_count);
      } catch {
        // Backend may be offline during dev; ignore silently
      }
    }

    fetchPending();
    const timer = setInterval(fetchPending, 15_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  return (
    <div className="flex min-h-svh flex-col bg-background text-foreground">
      {/* Skip to main content — visually hidden, appears on keyboard focus only */}
      <a
        href="#main-content"
        className="sr-only focus-visible:not-sr-only focus-visible:absolute focus-visible:left-4 focus-visible:top-4 focus-visible:z-50 focus-visible:bg-white focus-visible:px-4 focus-visible:py-2 focus-visible:text-xs focus-visible:font-medium focus-visible:text-[#0f62fe] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0f62fe]"
      >
        Skip to main content
      </a>

      {/* Top Carbon Header */}
      <header className="border-b border-[#e0e0e0] bg-white">
        <div className="mx-auto max-w-6xl px-4">
          <div className="flex items-center gap-6 py-3">
            {/* Brand */}
            <span className="text-lg font-semibold tracking-tight text-[#0f62fe]">
              Delabyrix
            </span>
            <Separator orientation="vertical" className="h-4" />
            {/* Nav tabs */}
            <nav aria-label="Main navigation" className="flex flex-1 items-center gap-1 overflow-x-auto">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    cn(
                      "inline-flex items-center whitespace-nowrap rounded-none px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0f62fe]",
                      isActive
                        ? "bg-[#edf5ff] text-[#0043ce]"
                        : "text-[#525252] hover:bg-[#f4f4f4] hover:text-[#161616]"
                    )
                  }
                >
                  {t(item.labelKey)}
                  {"showBadge" in item && item.showBadge && (
                    <PendingBadge count={pendingCount} />
                  )}
                </NavLink>
              ))}
            </nav>
            {/* Locale switcher */}
            <LocaleSwitcher />
          </div>
        </div>
      </header>

      {/* Page Content */}
      <main id="main-content" className="mx-auto w-full max-w-6xl flex-1 px-4">
        <Outlet />
      </main>

      {/* Persistent clinical safety footer */}
      <footer className="mt-auto border-t border-[#e0e0e0] bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <p className="text-xs text-[#525252]">{t("footer.disclaimer")}</p>
          <span className="font-mono text-xs text-[#525252]">
            Delabyrix v0.2.0 · IBM Granite-4 · Zero-PII Mode
          </span>
        </div>
      </footer>
    </div>
  );
}