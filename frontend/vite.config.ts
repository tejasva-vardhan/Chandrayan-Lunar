import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import cesium from "vite-plugin-cesium";

/** Catalog / large product uploads can exceed the default ~30s proxy idle timeout. */
const apiProxy = {
  target: "http://127.0.0.1:8000",
  changeOrigin: true,
  timeout: 600_000,
  proxyTimeout: 600_000,
} as const;

export default defineConfig({
  plugins: [react(), cesium()],
  build: { sourcemap: true },
  server: {
    proxy: {
      "/health": apiProxy,
      "/products": apiProxy,
      "/registration": apiProxy,
    },
  },
  preview: {
    proxy: {
      "/health": apiProxy,
      "/products": apiProxy,
      "/registration": apiProxy,
    },
  },
});
