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
    // Threads + per-file isolation avoids worker startup deadlocks on Windows.
    pool: "threads",
    fileParallelism: false,
    minWorkers: 1,
    maxWorkers: 1,
    isolate: true,
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
    server: {
      deps: {
        inline: ["react-router", "react-router-dom"],
      },
    },
  },
  build: {
    minify: "oxc",
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (/[\\/]node_modules[\\/](react|react-dom|react-router|react-router-dom|scheduler)[\\/]/.test(id)) {
            return "vendor-react";
          }
          if (/[\\/]node_modules[\\/]@tanstack[\\/]react-query[\\/]/.test(id)) {
            return "vendor-query";
          }
          if (/[\\/]node_modules[\\/]@firebase[\\/]|[\\/]node_modules[\\/]firebase[\\/]/.test(id)) {
            return "vendor-firebase";
          }
          if (/[\\/]node_modules[\\/]framer-motion[\\/]/.test(id)) {
            return "vendor-motion";
          }
          if (/[\\/]node_modules[\\/]react-markdown[\\/]/.test(id)) {
            return "vendor-markdown";
          }
          return undefined;
        },
      },
    },
  },
});
