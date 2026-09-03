// STATIC / REGRESSION FIXTURE — historical EXP-000 observation values.
// Do not display these as the result of a live uploaded-image registration run.
export const exp000 = {
  id: "EXP-000 / pair_01_equatorial",
  source: "Chandrayaan-2 OHRC",
  reference: "LRO NAC",
  sourceProduct: "ch2_ohr_ncp_20210402T0546284043_d_img_d18",
  referenceProduct: "M150368601RC",
  acquisitionTimeSource: "2021-04-02T05:46:28 UTC",
  acquisitionTimeReference: "2011-01-22T20:48:53 UTC",
  // Selenographic footprint (source OHRC)
  region: { lat: [0.22, 1.07], lon: [23.37, 23.50], label: "Equatorial" },
  // Image dimensions
  sourceDims: { width: 12000, height: 78175, gsd: "0.26 m/px" },
  referenceDims: { width: 5064, height: 52224 },
  // Matching view
  sourceStride: 15,
  referenceStride: 8,
  // Pipeline results
  rawMatches: 36,
  verified: 4,
  rejected: 32,
  inlierRatio: "11.1%",
  coverage: "23.2%",
  rmse: "9.41 × 10⁻¹⁰ px",
  runtimeSeconds: 31.16,
  refinement: "ZNCC parabolic — 0 coordinates shifted (indeterminate)",
  registration: "Blocked by 16 MP output-size cap (full-raster warp skipped)",
  independentAccuracy: "Not independently validated — no ground truth",
  residualNote:
    "Verification transfer residuals are image-space fit values, not accuracy. Four-point DLT near-zero residuals are expected and not independent.",
  flags: ["registration_output_too_large", "not_independently_validated"],
  // Real control points from EXP-000 refine_points stage (original image space, pixels)
  points: [
    { x: 56.5, y: 1.9,  rx: 54.4, ry: 89.8, residual: "2.40 × 10⁻¹¹" },
    { x: 22.7, y: 64.5, rx: 66.2, ry: 88.4, residual: "4.52 × 10⁻¹¹" },
    { x: 39.8, y: 46.9, rx: 95.1, ry: 65.4, residual: "8.57 × 10⁻¹⁰" },
    { x: 72.7, y: 9.1,  rx: 54.9, ry: 52.5, residual: "1.68 × 10⁻⁰⁹" },
  ],
} as const;
