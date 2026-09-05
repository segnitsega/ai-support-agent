import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/chat": "http://127.0.0.1:8000",
      "/approve": "http://127.0.0.1:8000",
      "/stats": "http://127.0.0.1:8000",
      "/approvals": "http://127.0.0.1:8000",
    },
  },
});
