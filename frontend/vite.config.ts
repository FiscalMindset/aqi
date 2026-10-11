import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "tailwindcss";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg", "robots.txt"],
      manifest: {
        name: "Dhuan Detective",
        short_name: "Dhuan",
        description: "Street-level PM2.5 estimation and source attribution for Delhi-NCR",
        theme_color: "#0f766e",
        background_color: "#0b1020",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,png,woff2}"],
        // the map chunk is loaded on demand, never precached (keeps the shell small)
        globIgnores: ["**/maplibre-*.js", "**/maplibre-*.css"],
        // app shell is precached; the last API result is cached by the query layer
        runtimeCaching: [
          {
            urlPattern: /\/v1\/estimate/,
            handler: "NetworkFirst",
            options: {
              cacheName: "dhuan-api",
              expiration: { maxEntries: 50, maxAgeSeconds: 3600 },
            },
          },
        ],
      },
    }),
  ],
  server: {
    proxy: {
      "/v1": {
        target: process.env.VITE_PROXY_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  preview: {
    proxy: {
      "/v1": {
        target: process.env.VITE_PROXY_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    target: "es2022",
    rollupOptions: {
      output: {
        manualChunks: {
          // code-split map and charts (performance budgets)
          maplibre: ["maplibre-gl"],
          charts: ["recharts"],
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      // brief requires >= 80% line coverage; branch/function set below it
      // because React render-prop internals resist them in jsdom
      thresholds: { lines: 80, functions: 70, branches: 65 },
    },
  },
});
