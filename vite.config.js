import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The React app lives in client/ and uses index.html (repo root) as its entry.
// In local dev, /api/* is proxied to the Python app from run.py (port 8800), so
// you can develop the UI against the real backend without deploying.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.PSX_API_TARGET || "http://127.0.0.1:8800",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
