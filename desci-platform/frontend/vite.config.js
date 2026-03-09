import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: "jsdom",
    setupFiles: ["src/__tests__/setup.jsx"],
    exclude: ["tests/e2e/**", "node_modules/**"],
    pool: "forks",
    fileParallelism: false,
    minWorkers: 1,
    maxWorkers: 1,
    isolate: false,
    testTimeout: 30000,
    hookTimeout: 30000,
  },
  build: {
    minify: "esbuild",
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-firebase": ["firebase/app", "firebase/auth"],
          "vendor-motion": ["framer-motion"],
          "vendor-markdown": ["react-markdown"],
        },
      },
    },
  },
});
