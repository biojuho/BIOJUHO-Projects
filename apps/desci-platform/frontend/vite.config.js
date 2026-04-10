import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["src/__tests__/setup.jsx"],
    exclude: ["tests/e2e/**", "node_modules/**"],
    // Single-worker forks are the most stable mode for this suite on Windows + Node 22.
    pool: "forks",
    fileParallelism: false,
    minWorkers: 1,
    maxWorkers: 1,
    isolate: false,
    testTimeout: 30000,
    hookTimeout: 30000,
    deps: {
      optimizer: {
        web: {
          include: [
            "@testing-library/react",
            "@testing-library/jest-dom",
            "react",
            "react-dom",
            "react-router-dom",
          ],
        },
      },
    },
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
