import type { ResultsViewModel } from "../../api/resultsView";

/** Sub-pixel refinement status from the live/fixture result — no invented coordinates. */
export function RefinementPanel({ results }: { results: ResultsViewModel }) {
  const indeterminate = /indeterminate/i.test(results.refinement);
  const unavailable = /unavailable/i.test(results.refinement);

  return (
    <section className="results-block refinement-panel" aria-labelledby="refinement-title">
      <header className="results-block-header">
        <div>
          <h3 id="refinement-title">Sub-pixel Refinement</h3>
          <p className="results-block-subtitle">
            Pipeline refinement state for this run. Does not imply sub-pixel accuracy was achieved.
          </p>
        </div>
      </header>
      <div className="refinement-status-card">
        <div>
          <span className="metric-kicker">STATUS</span>
          <b>
            {indeterminate
              ? "Indeterminate"
              : unavailable
                ? "Unavailable"
                : results.refinement}
          </b>
        </div>
        <p>
          {indeterminate
            ? "Sub-pixel refinement: Indeterminate. Unchanged coordinates are not claimed as successful refinement."
            : results.refinement}
        </p>
        <p className="refinement-disclaimer">
          Initial vs refined coordinates are shown only when the backend exposes them per point.
          This panel does not invent offsets.
        </p>
      </div>
    </section>
  );
}
