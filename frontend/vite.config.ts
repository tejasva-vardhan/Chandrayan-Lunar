import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import cesium from "vite-plugin-cesium";

export default defineConfig({
  plugins: [react(), cesium()],
  build: { sourcemap: true },
  server: {
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/products": "http://127.0.0.1:8000",
      "/registration": "http://127.0.0.1:8000",
    },
  },
  preview: {
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/products": "http://127.0.0.1:8000",
      "/registration": "http://127.0.0.1:8000",
    },
  },
});
