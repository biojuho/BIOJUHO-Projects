import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import process from 'node:process'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // Flag chunks over 200KB to catch bundle bloat before deploy
    chunkSizeWarningLimit: 200,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-charts': ['recharts'],
          'vendor-motion': ['framer-motion'],
          'vendor-i18n': ['i18next', 'react-i18next'],
          'vendor-icons': ['lucide-react'],
        },
      },
    },
  },
  // Strip console.log/debugger in production builds
  esbuild: {
    drop: process.env.NODE_ENV === 'production' ? ['console', 'debugger'] : [],
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8002',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        ws: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.js',
    exclude: ['tests/e2e/**', 'node_modules/**'],
    pool: 'forks',
    fileParallelism: false,
    minWorkers: 1,
    maxWorkers: 1,
    isolate: false,
    testTimeout: 30000,
    hookTimeout: 30000,
  },
})
