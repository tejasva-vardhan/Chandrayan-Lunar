import React from "react";

export function PairConfiguration() {
  return (
    <div className="workspace-card config-card">
      <div className="card-header">
        <div className="card-header-left">
          <span className="card-dot" />
          <span className="card-title">REGISTRATION CONFIGURATION</span>
        </div>
      </div>
      
      <p className="card-desc">Configure scientific parameters for the matching and registration pipeline. Some parameters are locked by the current experimental baseline.</p>

      <div className="config-grid">
        <div className="config-group">
          <label>Matcher Algorithm</label>
          <select disabled defaultValue="sift">
            <option value="sift">SIFT (Baseline)</option>
            <option value="rift">RIFT (Illumination Invariant - Unavailable)</option>
          </select>
          <span className="config-help">Currently locked to SIFT per EXP-000 baseline.</span>
        </div>

        <div className="config-group">
          <label>Geometric Verification</label>
          <select disabled defaultValue="ransac">
            <option value="ransac">RANSAC (Projective 2D)</option>
          </select>
          <span className="config-help">Filters out false correspondences using a projective model.</span>
        </div>

        <div className="config-group">
          <label>Subpixel Refinement</label>
          <select disabled defaultValue="zncc">
            <option value="zncc">ZNCC Parabolic Baseline</option>
          </select>
          <span className="config-help">Window radius: 7px, Search radius: 3px.</span>
        </div>
      </div>
    </div>
  );
}
