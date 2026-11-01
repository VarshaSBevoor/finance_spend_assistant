import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The browser talks only to this dev server, which forwards API calls to FastAPI.
// One origin means the backend needs no CORS setup.
const BACKEND = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/summary": BACKEND,
      "/ask": BACKEND,
    },
  },
});
