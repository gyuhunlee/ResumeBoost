import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // In dev, /api calls go to the FastAPI server so you don't need CORS locally.
    proxy: { "/api": "http://localhost:8000" },
  },
});
