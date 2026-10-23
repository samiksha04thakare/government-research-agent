import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/research": "http://127.0.0.1:8000",
      "/documents": "http://127.0.0.1:8000",
      "/history": "http://127.0.0.1:8000",
      "/sources": "http://127.0.0.1:8000",
      "/schemes": "http://127.0.0.1:8000",
      "/api": "http://127.0.0.1:8000",
      "/config": "http://127.0.0.1:8000",
      "/scraper": "http://127.0.0.1:8000",
    },
  },
});

