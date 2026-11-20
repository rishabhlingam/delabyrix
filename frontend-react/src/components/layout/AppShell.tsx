/**
 * AppShell — Carbon-compliant top-nav layout with live HITL pending badge.
 * Uses IBM Carbon design tokens throughout per ui-design-system.md.
 */
import React, { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Separator } from "@/components/ui/separator";
import { getHITLQueue } from "@/api/client";
import { cn } from "@/lib/utils";

function PendingBadge({ count }: { count: number }) {
  if (count === 0) return null;
  return (
    <span className="ml-1.5 inline-flex items-center justify-center rounded-none bg-[#da1e28] px-1.5 py-0.5 font-mono text-[10px] font-medium text-white tabular-nums">
      {count}
    </span>
  );
}

const NAV_ITEMS = [
  { to: "/", label: "Patient Assistant" },
  { to: "/hitl", label: "HITL Review", showBadge: true },
  { to: "/registry", label: "Registry Explorer" },
  { to: "/provider", label: "Provider Support" },
  { to: "/analytics", label: "Analytics" },
] as const;

export default function AppShell() {
  const [pendingCount, setPendingCount] = useState(0);

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
    <div className="min-h-svh bg-background text-foreground">
      {/* Top Carbon Header */}
      <header className="border-b border-[#e0e0e0] bg-white">
        <div className="mx-auto max-w-6xl px-4">
          <div className="flex items-center gap-6 py-3">
            {/* Brand */}
            <span className="text-xs font-semibold tracking-wide text-[#0f62fe]">
              Delabyrix
            </span>
            <Separator orientation="vertical" className="h-4" />
            {/* Nav tabs */}
            <nav className="flex items-center gap-1 overflow-x-auto">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    cn(
                      "inline-flex items-center whitespace-nowrap rounded-none px-3 py-1.5 text-xs font-medium transition-colors",
                      isActive
                        ? "bg-[#edf5ff] text-[#0043ce]"
                        : "text-[#525252] hover:bg-[#f4f4f4] hover:text-[#161616]"
                    )
                  }
                >
                  {item.label}
                  {"showBadge" in item && item.showBadge && (
                    <PendingBadge count={pendingCount} />
                  )}
                </NavLink>
              ))}
            </nav>
          </div>
        </div>
      </header>

      {/* Page Content */}
      <main className="mx-auto max-w-6xl px-4">
        <Outlet />
      </main>
    </div>
  );
}
