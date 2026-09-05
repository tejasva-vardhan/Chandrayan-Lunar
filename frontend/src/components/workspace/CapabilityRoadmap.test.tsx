import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import {
  CAPABILITY_ROWS,
  CapabilityRoadmap,
  PLANNED_SENSOR_CARDS,
} from "./CapabilityRoadmap";

describe("CapabilityRoadmap", () => {
  it("separates LIVE capabilities from planned/simulated paths without fake metrics", () => {
    render(<CapabilityRoadmap />);

    expect(screen.getByRole("heading", { name: "Capability status" })).toBeInTheDocument();
    expect(screen.getByText("OHRC ↔ LRO correspondence")).toBeInTheDocument();
    expect(screen.getAllByText("LIVE").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("TMC-2 support")).toBeInTheDocument();
    expect(screen.getByText("IIRS support")).toBeInTheDocument();
    expect(screen.getAllByText(/SPICE geometry/i).length).toBeGreaterThan(0);

    for (const card of PLANNED_SENSOR_CARDS) {
      const article = screen.getByRole("heading", { name: card.sensor }).closest("article");
      expect(article).toBeTruthy();
      expect(within(article as HTMLElement).getByText(card.badge)).toBeInTheDocument();
      expect(within(article as HTMLElement).getByRole("button", { name: /Not in this demo run/i })).toBeDisabled();
    }

    expect(screen.getByText(/no fake IIRS/i)).toBeInTheDocument();
    expect(screen.queryByText(/verified matches\s*=\s*\d+/i)).not.toBeInTheDocument();
    expect(CAPABILITY_ROWS.some((r) => r.status === "LIVE")).toBe(true);
    expect(CAPABILITY_ROWS.some((r) => r.tone === "planned")).toBe(true);
  });
});
