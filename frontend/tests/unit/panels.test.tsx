import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import i18n from "../../src/i18n";
import { CausesPanel } from "../../src/features/explorer/CausesPanel";
import { PersonaCards } from "../../src/features/explorer/PersonaCards";
import { AgentTrace } from "../../src/features/explorer/AgentTrace";
import type { Attribution } from "../../src/lib/api";

function withI18n(ui: React.ReactNode) {
  return render(<I18nextProvider i18n={i18n}>{ui}</I18nextProvider>);
}

const attribution: Attribution = {
  summary: "Likely contributors near this location: Landfill (Bhalswa).",
  likely_causes: [
    {
      rank: 1,
      category: "landfill",
      label: "Landfill (Bhalswa Landfill Area)",
      band: "High",
      evidence_ids: ["ev_1"],
      reasoning: "3.1 km upwind; influence 0.72",
      distance_km: 3.1,
      bearing_deg: 292,
    },
  ],
  confidence: "high",
  confidence_reason: "Multiple corroborating tool results",
  evidence: [
    {
      evidence_id: "ev_1",
      tool: "find_upwind_sources",
      args: { lat: 28.6, lon: 77.2 },
      summary: "1 candidate source within 12 km upwind",
      fetched_at: "2026-10-10T12:00:00Z",
      ok: true,
    },
  ],
  tool_calls: ["find_upwind_sources(...)"],
};

describe("CausesPanel", () => {
  it("renders causes with bands and evidence", () => {
    withI18n(<CausesPanel attribution={attribution} />);
    expect(screen.getByText(/Landfill \(Bhalswa/)).toBeDefined();
    expect(screen.getByText("High")).toBeDefined();
    expect(screen.getByText(/find_upwind_sources/)).toBeDefined();
  });

  it("disclaims the heuristic nature", () => {
    withI18n(<CausesPanel attribution={attribution} />);
    expect(screen.getByText(/not a causal proof/i)).toBeDefined();
  });

  it("shows the empty state when no causes", () => {
    withI18n(<CausesPanel attribution={{ ...attribution, likely_causes: [] }} />);
    expect(screen.getByText(/No specific sources stand out/i)).toBeDefined();
  });
});

describe("PersonaCards", () => {
  it("renders all personas with disclaimers", () => {
    withI18n(
      <PersonaCards
        advice={[
          {
            persona: "parent",
            headline: "children should limit outdoor time",
            actions: ["keep play short"],
            evidence_ids: [],
            disclaimer: "General guidance.",
          },
          {
            persona: "rider",
            headline: "riders should rest",
            actions: ["rest indoors"],
            evidence_ids: [],
            disclaimer: "General guidance.",
          },
          {
            persona: "worker",
            headline: "workers should rotate tasks",
            actions: ["rotate tasks"],
            evidence_ids: [],
            disclaimer: "General guidance.",
          },
        ]}
      />,
    );
    expect(screen.getAllByText("General guidance.").length).toBe(3);
    expect(screen.getByText(/children should limit outdoor time/)).toBeDefined();
  });
});

describe("AgentTrace", () => {
  it("renders the tool-call trace", () => {
    const query = {
      data: { served_by: "scripted-deterministic", attribution },
      isPending: false,
      error: null,
    } as never;
    withI18n(<AgentTrace explain={query} />);
    expect(screen.getByTestId("agent-trace")).toBeDefined();
    expect(screen.getByText(/find_upwind_sources/)).toBeDefined();
  });
});
