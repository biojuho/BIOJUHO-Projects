import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    chunkSizeWarningLimit: 200,
    rolldownOptions: {
      output: {
        minify: {
          compress: {
            dropConsole: true,
            dropDebugger: true,
          },
        },
        codeSplitting: {
          minSize: 20000,
          maxSize: 190000,
          groups: [
            {
              name: 'vendor-react-dom',
              test: /[\\/]node_modules[\\/](react-dom|scheduler)[\\/]/,
              priority: 40,
            },
            {
              name: 'vendor-react-core',
              test: /[\\/]node_modules[\\/](react|react-router|react-router-dom)[\\/]/,
              priority: 35,
            },
            {
              name: 'vendor-recharts',
              test: /[\\/]node_modules[\\/]recharts[\\/]/,
              priority: 30,
            },
            {
              name: 'vendor-chart-utils',
              test: /[\\/]node_modules[\\/](d3-[^\\/]+|victory-vendor|react-smooth|decimal.js-light)[\\/]/,
              priority: 25,
            },
            {
              name: 'vendor-motion',
              test: /[\\/]node_modules[\\/]framer-motion[\\/]/,
              priority: 20,
            },
            {
              name: 'vendor-i18n',
              test: /[\\/]node_modules[\\/](i18next|react-i18next)[\\/]/,
              priority: 15,
            },
            {
              name: 'vendor-icons',
              test: /[\\/]node_modules[\\/]lucide-react[\\/]/,
              priority: 10,
            },
          ],
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8002',
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
