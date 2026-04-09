import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    testTimeout: 30_000,
    // [QA 수정] pool: 'forks' + singleFork는 vitest 4에서 worker timeout 유발.
    // vmForks는 동일한 격리 보장 + 더 안정적인 worker 초기화를 제공.
    pool: 'vmForks',
    vmForks: {
      singleFork: true,
      forksTimeout: 120_000,
    },
  },
})

