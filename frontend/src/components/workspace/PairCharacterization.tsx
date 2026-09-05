import type { ResultsViewModel } from "../../api/resultsView";

function formatDims(width: number | null, height: number | null): string {
  if (width == null || height == null) return "Unavailable";
  return `${width.toLocaleString()} × ${height.toLocaleString()} px`;
}

function formatDeg(value: number | null | undefined): string | null {
  if (value == null || Number.isNaN(value)) return null;
  return `${value.toFixed(1)}°`;
}

/** Compact pair metadata — only fields present on the live/fixture view model. */
export function PairCharacterization({ results }: { results: ResultsViewModel }) {
  const sunAngle = formatDeg(results.sunAngleDifferenceDegrees);
  const sunAzDelta = formatDeg(results.sunAzimuthDifferenceDegrees);
  const sunIncDelta = formatDeg(results.sunIncidenceDifferenceDegrees);
  const sourceIllum =
    results.sunAzimuth != null && results.sunIncidence != null
      ? `Azimuth ${results.sunAzimuth.toFixed(1)}° / Incidence ${results.sunIncidence.toFixed(1)}°`
      : "Not available from product metadata";
  const referenceIllum =
    results.referenceSunAzimuth != null && results.referenceSunIncidence != null
      ? `Azimuth ${results.referenceSunAzimuth.toFixed(1)}° / Incidence ${results.referenceSunIncidence.toFixed(1)}°`
      : "Not available from product metadata";

  let sunInvarianceValue = "Unavailable — sun vectors / angles not present for both products";
  if (sunAngle) {
    sunInvarianceValue = `${sunAngle} sun-angle difference (pair characterization)`;
  } else if (sunAzDelta || sunIncDelta) {
    const parts = [
      sunAzDelta ? `Δazimuth ${sunAzDelta}` : null,
      sunIncDelta ? `Δincidence ${sunIncDelta}` : null,
    ].filter(Boolean);
    sunInvarianceValue = `${parts.join(" · ")} (from product sun metadata)`;
  }

  const rows: { label: string; value: string }[] = [
    { label: "Source sensor", value: results.source },
    { label: "Reference sensor", value: results.reference },
    {
      label: "Source dimensions",
      value: formatDims(results.sourceDims.width, results.sourceDims.height),
    },
    {
      label: "Reference dimensions",
      value: formatDims(results.referenceDims.width, results.referenceDims.height),
    },
    { label: "Source acquisition", value: results.acquisitionTimeSource },
    { label: "Reference acquisition", value: results.acquisitionTimeReference },
    { label: "Source GSD", value: results.sourceDims.gsd || "Unavailable" },
    { label: "Illumination (source)", value: sourceIllum },
    { label: "Illumination (reference)", value: referenceIllum },
    {
      label: "Sun invariance / sun-angle difference",
      value: sunInvarianceValue,
    },
  ];

  if (results.region) {
    rows.push({
      label: "Region",
      value: `${results.region.label} · lat ${results.region.lat[0]}–${results.region.lat[1]}° · lon ${results.region.lon[0]}–${results.region.lon[1]}°`,
    });
  }

  if (results.transformationModel) {
    rows.push({ label: "Transformation model", value: results.transformationModel });
  }

  return (
    <section className="results-block pair-characterization" aria-labelledby="pair-char-title">
      <header className="results-block-header">
        <div>
          <h3 id="pair-char-title">Pair Characterization</h3>
          <p className="results-block-subtitle">
            Sensor and product metadata for this image pair — values from the result object only.
          </p>
        </div>
      </header>
      <dl className="pair-char-grid">
        {rows.map((row) => (
          <div key={row.label}>
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
      <p className="pair-char-sun-note">
        Sun-angle difference describes illumination mismatch between the two products. It is not a
        claim that matching is sun-invariant.
      </p>
    </section>
  );
}
