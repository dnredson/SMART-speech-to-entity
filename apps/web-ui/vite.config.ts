import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 8503,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_API_URL ?? "http://127.0.0.1:8030",
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: "0.0.0.0",
    port: 8503,
    strictPort: true,
  },
});
