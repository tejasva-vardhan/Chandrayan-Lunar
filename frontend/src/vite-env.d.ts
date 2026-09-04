/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Render (or other) API origin for production builds. Unset locally → Vite proxy. */
  readonly VITE_API_BASE_URL?: string;
  /** Optional Cesium ion token for the globe layer. */
  readonly VITE_CESIUM_ION_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
