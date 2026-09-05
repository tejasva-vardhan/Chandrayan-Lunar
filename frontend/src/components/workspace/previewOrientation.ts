/** Helpers for matching landscape/portrait preview strips in the UI. */

export type StripOrientation = "landscape" | "portrait" | "square";

export function orientationFromSize(
  width: number | null | undefined,
  height: number | null | undefined,
): StripOrientation | null {
  if (width == null || height == null || width <= 0 || height <= 0) return null;
  const ratio = width / height;
  if (ratio > 1.08) return "landscape";
  if (ratio < 1 / 1.08) return "portrait";
  return "square";
}

/**
 * When source and reference disagree (one landscape, one portrait), pick a shared
 * target. Prefer portrait for typical lunar pushbroom strips.
 */
export function sharedStripOrientation(
  source: StripOrientation | null,
  reference: StripOrientation | null,
): StripOrientation | null {
  if (!source || !reference) return reference ?? source;
  if (source === reference) return source;
  if (source === "square") return reference;
  if (reference === "square") return source;
  return "portrait";
}

/** True when this image should be rotated 90° CW to match *target*. */
export function needsRotateToMatch(
  current: StripOrientation | null,
  target: StripOrientation | null,
): boolean {
  if (!current || !target) return false;
  if (current === "square" || target === "square") return false;
  return current !== target;
}

/** Remap percent coords after a 90° clockwise image rotation. */
export function rotatePercentCw(x: number, y: number): { x: number; y: number } {
  return { x: y, y: 100 - x };
}

export function displayPointPercents(
  x: number,
  y: number,
  rotate90Cw: boolean,
): { x: number; y: number } {
  return rotate90Cw ? rotatePercentCw(x, y) : { x, y };
}
