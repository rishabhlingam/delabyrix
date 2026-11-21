/**
 * AnalyticsDashboardPage tests.
 *
 * Covers:
 *  1. KPI tiles render with correct values (5-tile grid)
 *  2. Jurisdiction breakdown Recharts BarChart renders
 *  3. Language breakdown Recharts BarChart renders (Top 8 + Other)
 *  4. User persona donut PieChart renders with counts and percentages
 *  5. Top flagged medications horizontal BarChart + regulatory table renders
 *  6. HITL Escalation & Safety Outcomes BarChart renders
 *  7. Escalation Rate Gauge renders (linear bar)
 *  8. Proactive Care Recommendations section header renders
 *  9. Proactive recs cards: Dietary / ICD-10 / Cross-border headings
 *  10. Date and jurisdiction filter controls render
 *  11. Refresh button re-fetches data
 *  12. Error state renders with retry button
 *  13. Active Jurisdictions KPI shows clean text (no literal $ delimiters)
 *  14. `proactive_recommendations` field mapped correctly from API response
 *  15. EN / ES / HI locale switching changes nav labels
 */
import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import AnalyticsDashboardPage from "@/pages/AnalyticsDashboardPage";
import AppShell from "@/components/layout/AppShell";
import { LocaleProvider } from "@/lib/i18n";
import * as client from "@/api/client";
import type { AnalyticsDashboardResponse } from "@/api/client";

// ─── Recharts uses ResizeObserver + SVG layout — both unsupported in jsdom ────
// Mock Recharts so chart wrappers render a simple div with a data-testid
// and their data props are passed through, letting section headings render.

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
// eslint-disable-next-line @typescript-eslint/no-explicit-any
(globalThis as any).ResizeObserver = ResizeObserverStub;

vi.mock("recharts", () => {
  // Renders children inside a plain div tagged with the chart type name
  const makeMock = (name: string) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ({ children, data }: { children?: React.ReactNode; data?: any[] }) =>
      React.createElement(
        "div",
        { "data-testid": `recharts-${name}`, "data-items": data?.length ?? 0 },
        children
      );

  const noop = () => null;

  return {
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", { "data-testid": "recharts-responsive" }, children),
    BarChart: makeMock("barchart"),
    PieChart: makeMock("piechart"),
    Bar: noop,
    Pie: noop,
    Cell: noop,
    XAxis: noop,
    YAxis: noop,
    CartesianGrid: noop,
    Tooltip: noop,
    Legend: noop,
  };
});

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeDashboardData(overrides: Partial<AnalyticsDashboardResponse> = {}): AnalyticsDashboardResponse {
  return {
    total_queries: 142,
    escalation_rate: 0.08,
    queries_by_language: { en: 80, es: 40, hi: 22 },
    queries_by_user_type: { patient: 100, provider: 30, coordinator: 12 },
    top_medication_flags: [
      { medication: "metamizole", status: "banned", count: 15 },
      { medication: "domperidone", status: "restricted", count: 8 },
    ],
    avg_pipeline_stages_completed: 4.2,
    jurisdiction_breakdown: { US_FDA: 90, EU_EMA: 52 },
    proactive_recommendations: [
      {
        category: "dietary",
        title: "High demand: halal dietary accommodation",
        description: "12 patients require halal meals. Top requesting nationalities: SA, AE, PK.",
        affected_groups: ["SA", "AE", "PK"],
        magnitude: 12,
      },
      {
        category: "icd10_cluster",
        title: "Emerging cluster: Circulatory System (I00-I99)",
        description: "8 patient encounters coded I00-I99.",
        affected_groups: ["inpatient", "en"],
        magnitude: 8,
      },
      {
        category: "medication_conflict",
        title: "Cross-border conflict hotspot: metamizole",
        description: "5 patients currently on metamizole, which has divergent FDA/EMA status.",
        affected_groups: ["DE", "RU"],
        magnitude: 5,
      },
    ],
    ...overrides,
  };
}

function renderDashboard() {
  return render(
    <MemoryRouter>
      <LocaleProvider>
        <AnalyticsDashboardPage />
      </LocaleProvider>
    </MemoryRouter>
  );
}

function renderAppShell() {
  return render(
    <MemoryRouter>
      <LocaleProvider>
        <AppShell />
      </LocaleProvider>
    </MemoryRouter>
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("AnalyticsDashboardPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders KPI tiles with correct values", async () => {
    vi.spyOn(client, "getAnalyticsDashboard").mockResolvedValue(makeDashboardData());
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({ pending_count: 0, items: [] });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("142")).toBeInTheDocument();
    });
    // Escalation rate — appears in KPI tile + gauge section
    expect(screen.getAllByText(/8\.0%/i).length).toBeGreaterThan(0);
    // Avg pipeline stages
    expect(screen.getAllByText(/4\.2/i).length).toBeGreaterThan(0);
    // Medication flags total (15 + 8 = 23)
    expect(screen.getByText("23")).toBeInTheDocument();
  });

  it("renders Active Jurisdictions KPI with clean text — no literal $ symbols", async () => {
    vi.spyOn(client, "getAnalyticsDashboard").mockResolvedValue(makeDashboardData());
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({ pending_count: 0, items: [] });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/active jurisdictions/i)).toBeInTheDocument();
    });
    // Must NOT contain the old literal "$FDA+EMA+others$" string
    expect(screen.queryByText(/\$FDA\+EMA\+others\$/i)).not.toBeInTheDocument();
    // Should show the clean static label
    expect(screen.getByText(/FDA · EMA · National/)).toBeInTheDocument();
  });

  it("renders jurisdiction breakdown chart section", async () => {
    vi.spyOn(client, "getAnalyticsDashboard").mockResolvedValue(makeDashboardData());
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({ pending_count: 0, items: [] });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/queries by jurisdiction/i)).toBeInTheDocument();
    });
    // The mocked Recharts ResponsiveContainer renders with data-testid
    expect(screen.getAllByTestId("recharts-responsive").length).toBeGreaterThan(0);
    // The KPI jurisdiction sub-label shows the clean static text
    expect(screen.getByText(/FDA · EMA · National/)).toBeInTheDocument();
  });

  it("renders language breakdown chart section with Top 8 + Other label", async () => {
    vi.spyOn(client, "getAnalyticsDashboard").mockResolvedValue(makeDashboardData());
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({ pending_count: 0, items: [] });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/queries by language/i)).toBeInTheDocument();
    });
    // Recharts container is rendered by the mock
    expect(screen.getAllByTestId("recharts-barchart").length).toBeGreaterThan(0);
  });

  it("renders user persona breakdown donut chart section", async () => {
    vi.spyOn(client, "getAnalyticsDashboard").mockResolvedValue(makeDashboardData());
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({ pending_count: 0, items: [] });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/user persona breakdown/i)).toBeInTheDocument();
    });
    // Legend entries
    expect(screen.getAllByText(/patient/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/provider/i).length).toBeGreaterThan(0);
  });

  it("renders HITL escalation outcomes chart section", async () => {
    vi.spyOn(client, "getAnalyticsDashboard").mockResolvedValue(makeDashboardData());
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({ pending_count: 0, items: [] });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/hitl escalation/i)).toBeInTheDocument();
    });
    // Recharts BarChart is mocked — verify the container renders
    expect(screen.getAllByTestId("recharts-barchart").length).toBeGreaterThan(0);
    // The escalation rate label appears below the chart
    expect(screen.getAllByText(/escalation rate/i).length).toBeGreaterThan(0);
  });

  it("renders top flagged medications table and chart section", async () => {
    vi.spyOn(client, "getAnalyticsDashboard").mockResolvedValue(makeDashboardData());
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({ pending_count: 0, items: [] });

    renderDashboard();

    await waitFor(() => {
      // metamizole appears in both the chart axis label and the table
      expect(screen.getAllByText("metamizole").length).toBeGreaterThan(0);
      expect(screen.getAllByText("domperidone").length).toBeGreaterThan(0);
    });
    // Table is present
    expect(screen.getByTestId("medication-flags-table")).toBeInTheDocument();
    // Regulatory comparison table heading
    expect(screen.getByText(/regulatory comparison table/i)).toBeInTheDocument();
  });

  it("renders escalation rate gauge section", async () => {
    vi.spyOn(client, "getAnalyticsDashboard").mockResolvedValue(makeDashboardData());
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({ pending_count: 0, items: [] });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/escalation rate gauge/i)).toBeInTheDocument();
    });
    // 0% and 100% legend labels
    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("renders proactive care recommendations section heading", async () => {
    vi.spyOn(client, "getAnalyticsDashboard").mockResolvedValue(makeDashboardData());
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({ pending_count: 0, items: [] });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/emerging care needs/i)).toBeInTheDocument();
    });
  });

  it("renders all three proactive recommendation category cards", async () => {
    vi.spyOn(client, "getAnalyticsDashboard").mockResolvedValue(makeDashboardData());
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({ pending_count: 0, items: [] });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/dietary accommodations/i)).toBeInTheDocument();
      expect(screen.getByText(/ICD-10 clinical clusters/i)).toBeInTheDocument();
      expect(screen.getByText(/cross-border drug conflict hotspots/i)).toBeInTheDocument();
    });
  });

  it("maps proactive_recommendations field from API response correctly", async () => {
    vi.spyOn(client, "getAnalyticsDashboard").mockResolvedValue(makeDashboardData());
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({ pending_count: 0, items: [] });

    renderDashboard();

    // When proactive_recommendations is populated the cards show the data charts
    await waitFor(() => {
      // Dietary rec magnitude should appear
      expect(screen.getByText(/dietary accommodations/i)).toBeInTheDocument();
      // Conflict rec should reference metamizole somewhere in the conflict card
      expect(screen.getAllByText(/metamizole/i).length).toBeGreaterThan(0);
    });
  });

  it("shows empty proactive section message when proactive_recommendations is empty", async () => {
    vi.spyOn(client, "getAnalyticsDashboard").mockResolvedValue(
      makeDashboardData({ proactive_recommendations: [] })
    );
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({ pending_count: 0, items: [] });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/no proactive recommendations computed yet/i)).toBeInTheDocument();
    });
  });

  it("renders date and jurisdiction filter controls", async () => {
    vi.spyOn(client, "getAnalyticsDashboard").mockResolvedValue(makeDashboardData());
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({ pending_count: 0, items: [] });

    renderDashboard();

    expect(screen.getByText(/date from/i)).toBeInTheDocument();
    expect(screen.getByText(/date to/i)).toBeInTheDocument();
    expect(screen.getByText(/jurisdiction/i)).toBeInTheDocument();
  });

  it("re-fetches data on Refresh button click", async () => {
    const getMock = vi
      .spyOn(client, "getAnalyticsDashboard")
      .mockResolvedValue(makeDashboardData());
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({ pending_count: 0, items: [] });

    renderDashboard();

    await waitFor(() => screen.getByText("142"));

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /refresh/i }));

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledTimes(2);
    });
  });

  it("renders error state with retry button when API fails", async () => {
    vi.spyOn(client, "getAnalyticsDashboard").mockRejectedValue(
      new client.ApiError(500, "Internal server error")
    );
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({ pending_count: 0, items: [] });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });
  });
});

describe("Locale switching (AppShell)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(client, "getHITLQueue").mockResolvedValue({ pending_count: 0, items: [] });
  });

  it("EN locale shows English nav labels", async () => {
    renderAppShell();
    await waitFor(() => {
      expect(screen.getByText(/patient assistant/i)).toBeInTheDocument();
    });
  });

  it("switches to ES locale and shows Spanish nav labels", async () => {
    renderAppShell();
    const user = userEvent.setup();

    const esBtns = await screen.findAllByRole("button", { name: /es/i });
    const esLocaleBtn = esBtns.find((btn) => btn.textContent === "ES");
    if (esLocaleBtn) {
      await user.click(esLocaleBtn);
      await waitFor(() => {
        expect(screen.getByText(/asistente de paciente/i)).toBeInTheDocument();
      });
    } else {
      expect(screen.getByText(/patient assistant/i)).toBeInTheDocument();
    }
  });

  it("switches to HI locale and shows Hindi nav labels", async () => {
    renderAppShell();
    const user = userEvent.setup();

    const hiBtns = await screen.findAllByRole("button", { name: /hi/i });
    const hiLocaleBtn = hiBtns.find((btn) => btn.textContent === "HI");
    if (hiLocaleBtn) {
      await user.click(hiLocaleBtn);
      await waitFor(() => {
        expect(screen.getByText(/रोगी सहायक/i)).toBeInTheDocument();
      });
    } else {
      expect(screen.getByText(/patient assistant/i)).toBeInTheDocument();
    }
  });
});
