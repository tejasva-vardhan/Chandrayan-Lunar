import { OverlayViewer } from "./OverlayViewer";
import type { ResultsViewModel } from "../../api/resultsView";

type RegistrationDiagnosticProps = {
  results: ResultsViewModel;
};

export function RegistrationDiagnostic({ results }: RegistrationDiagnosticProps) {
  const hasFullRaster = Boolean(results.registeredArtifactUrl);
  const hasPreview = results.previewAvailable;

  return (
    <section className="results-block registration-diagnostic" aria-labelledby="reg-diag-title">
      <header className="results-block-header">
        <div>
          <h3 id="reg-diag-title">Registration Diagnostic</h3>
          <p className="results-block-subtitle">
            Visual check of the estimated alignment between the two images.
          </p>
        </div>
      </header>

      <p className="what-you-see">
        <span>What you&apos;re seeing</span>
        This view shows the visual result of applying the estimated transformation. It is
        diagnostic evidence, not independent accuracy validation.
      </p>

      <div className="diagnostic-artifact-labels">
        {hasPreview && (
          <span className="chip chip-region">Alignment diagnostic</span>
        )}
        {results.previewMode === "diagnostic_crop" && (
          <span className="chip">Correspondence / crop preview</span>
        )}
        {hasFullRaster && (
          <span className="chip chip-region">Registered output</span>
        )}
        {!hasFullRaster && results.fullRasterBlocked && (
          <span className="chip chip-warn">Full registered raster unavailable</span>
        )}
      </div>

      {results.fullRasterBlocked && (
        <div className="diagnostic-limitation" role="status">
          <b>Registered full-raster output unavailable for this run</b>
          <span>Reason: output-size safety limit (backend unchanged)</span>
          <p>
            BEFORE comparison uses source/reference previews when available. AFTER uses a
            diagnostic crop only when the pipeline genuinely produced one — never a fabricated
            registered strip.
          </p>
        </div>
      )}

      {!results.fullRasterBlocked && !hasFullRaster && !hasPreview && (
        <div className="diagnostic-limitation" role="status">
          <b>Registered full-raster output unavailable for this run</b>
          <span>No registered artifact or diagnostic preview was returned for this result.</span>
        </div>
      )}

      {hasFullRaster && (
        <p className="diagnostic-download">
          <a href={results.registeredArtifactUrl!} target="_blank" rel="noreferrer">
            Download registered source
          </a>
        </p>
      )}

      <OverlayViewer
        available={results.previewAvailable}
        referenceUrl={results.previewReferenceUrl}
        registeredUrl={results.previewRegisteredUrl}
        note={results.previewNote}
        mode={results.previewMode}
        isLive={results.isLive}
      />
    </section>
  );
}
