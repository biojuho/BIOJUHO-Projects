import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import process from 'node:process'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    chunkSizeWarningLimit: 200,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (/[\\/]node_modules[\\/](react|react-dom|react-router|react-router-dom|scheduler)[\\/]/.test(id)) {
            return 'vendor-react'
          }
          if (/[\\/]node_modules[\\/]framer-motion[\\/]/.test(id)) {
            return 'vendor-motion'
          }
          if (/[\\/]node_modules[\\/](i18next|react-i18next)[\\/]/.test(id)) {
            return 'vendor-i18n'
          }
          if (/[\\/]node_modules[\\/]lucide-react[\\/]/.test(id)) {
            return 'vendor-icons'
          }
          return undefined
        },
      },
    },
  },
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
    pool: 'threads',
    fileParallelism: false,
    minWorkers: 1,
    maxWorkers: 1,
    isolate: true,
    testTimeout: 30000,
    hookTimeout: 30000,
  },
})
