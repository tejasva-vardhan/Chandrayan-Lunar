import { describe, expect, it } from "vitest";
import {
  displayPointPercents,
  needsRotateToMatch,
  orientationFromSize,
  rotatePercentCw,
  sharedStripOrientation,
} from "./previewOrientation";

describe("previewOrientation", () => {
  it("classifies landscape and portrait strips", () => {
    expect(orientationFromSize(2000, 400)).toBe("landscape");
    expect(orientationFromSize(400, 2000)).toBe("portrait");
    expect(orientationFromSize(100, 100)).toBe("square");
  });

  it("unifies mismatched orientations to portrait by default", () => {
    expect(sharedStripOrientation("landscape", "portrait")).toBe("portrait");
    expect(needsRotateToMatch("landscape", "portrait")).toBe(true);
    expect(needsRotateToMatch("portrait", "portrait")).toBe(false);
  });

  it("remaps percent coords for 90° CW display rotation", () => {
    expect(rotatePercentCw(10, 20)).toEqual({ x: 20, y: 90 });
    expect(displayPointPercents(10, 20, false)).toEqual({ x: 10, y: 20 });
    expect(displayPointPercents(10, 20, true)).toEqual({ x: 20, y: 90 });
  });
});
