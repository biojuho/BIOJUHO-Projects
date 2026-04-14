import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./components/charts', () => ({
  BarChart: () => <div data-testid="bar-chart" />,
  DoughnutChart: () => <div data-testid="doughnut-chart" />,
}))

const RESPONSES = {
  '/api/overview': {
    projects: {
      getdaytrends: { status: 'OK', total_runs: 12, latest_run: { started_at: '2026-04-01T09:00:00' } },
      cie: { status: 'OK', avg_qa_score: 88, total_contents: 7 },
      agriguard: { status: 'OK', sensor_readings: 1234, products: 12 },
      costs: { total_cost: 1.25, total_calls: 42 },
    },
  },
  '/api/getdaytrends': {
    total_runs: 12,
    total_trends: 340,
    total_tweets: 87,
    daily_runs: [],
    top_trends: [],
  },
  '/api/cie': {
    total_contents: 7,
    total_trends: 12,
    by_platform: [],
    qa_distribution: [],
  },
  '/api/agriguard': {
    tables: { products: 12, sensor_readings: 1234 },
    product_stats: { verified: 9, total: 12, cold_chain: 4 },
  },
  '/api/costs': {
    total_calls: 42,
    total_cost: 1.25,
    projects: {},
  },
  '/api/dailynews': {
    tables: ['content_reports'],
    counts: { reports: 5, articles: 16 },
  },
  '/api/ab_performance': {
    total_samples: 0,
    hook_stats: [],
    kick_stats: [],
    angle_stats: [],
    feedback: {},
    feedback_trend: [],
  },
  '/api/quality_overview': {
    qa_grades: [],
    top_blocking_reasons: [],
    lifecycle_distribution: [],
    daily_production: [],
    confidence_distribution: [],
  },
  '/api/sla_status': {
    sla_target: 99.0,
    lookback_days: 30,
    overall_success_rate: 100,
    overall_sla_met: true,
    pipelines: [],
  },
}

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url) => ({
      json: async () => RESPONSES[url],
    })),
  )
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('Dashboard App', () => {
  it('loads the dashboard and requests every API panel endpoint', async () => {
    const { default: App } = await import('./App')

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'AI Projects Dashboard' })).toBeInTheDocument()

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(9)
    })

    for (const endpoint of Object.keys(RESPONSES)) {
      expect(global.fetch).toHaveBeenCalledWith(
        endpoint,
        expect.objectContaining({ cache: 'no-store' }),
      )
    }
  })

  it('refreshes every panel when the refresh button is clicked', async () => {
    const { default: App } = await import('./App')

    render(<App />)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(9)
    })

    fireEvent.click(screen.getByRole('button'))

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(18)
    })
  })

  it('shows a panel error state instead of an infinite loader when a request fails', async () => {
    global.fetch.mockImplementation(async (url) => {
      if (url === '/api/getdaytrends') {
        return {
          ok: false,
          status: 503,
          json: async () => ({}),
        }
      }

      return {
        ok: true,
        json: async () => RESPONSES[url],
      }
    })

    const { default: App } = await import('./App')

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'AI Projects Dashboard' })).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Panel unavailable')).toBeInTheDocument()
      expect(screen.getByText('Request failed with status 503')).toBeInTheDocument()
    })
  })
})
