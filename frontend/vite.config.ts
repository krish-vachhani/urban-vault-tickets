/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const DEV_SERVER_PORT = 5173;

// Where the dev server forwards /api requests. Docker Compose sets this to the
// backend service; running `npm run dev` on the host falls back to localhost.
const apiProxyTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: DEV_SERVER_PORT,
    strictPort: true,
    // Proxying keeps the React app and the API on one browser origin, which the
    // JWT refresh cookie and CSRF protection rely on (README-authentication §4.4).
    proxy: {
      "/api": { target: apiProxyTarget },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
  },
});
