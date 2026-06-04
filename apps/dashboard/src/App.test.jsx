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
    workspace_smoke: {
      available: true,
      status: 'complete',
      duration_seconds: 28.028,
      summary: { total: 2, completed: 2, passed: 2, failed: 0, remaining: 0 },
      scope_summary: {
        mcp: { completed: 1, passed: 1, failed: 0, elapsed_seconds: 8.4 },
      },
      mcp_trace: {
        enabled: true,
        completed: 1,
        passed: 1,
        failed: 0,
        elapsed_seconds: 8.4,
        checked_units: ['automation/DailyNews'],
        command_kinds: { pytest: 1 },
        checks: [
          {
            name: 'DailyNews unit tests',
            cwd: 'automation/DailyNews',
            ok: true,
            returncode: 0,
            elapsed_seconds: 8.4,
            command_kind: 'pytest',
          },
        ],
      },
      slowest_checks: [
        { scope: 'cie', name: 'cie tests', ok: true, returncode: 0, elapsed_seconds: 27.273 },
      ],
    },
    dev_server_status: {
      available: true,
      status: 'ready',
      summary: { total: 2, ready: 2, unready: 0 },
      targets: [
        { id: 'dashboard-api', label: 'Dashboard API', project: 'dashboard', kind: 'api', ok: true },
        { id: 'dashboard-frontend', label: 'Dashboard Frontend', project: 'dashboard', kind: 'frontend', ok: true },
      ],
      unready_targets: [],
    },
    credential_boundaries: {
      available: true,
      status: 'pass',
      boundary_count: 5,
      missing_required_env_count: 5,
      missing_required_env: ['CANVA_CLIENT_SECRET', 'TELEGRAM_BOT_TOKEN'],
      status_counts: { external_auth_blocked: 1, future_scoped: 2 },
      next_unblock: {
        boundary_id: 'canva_oauth_and_openapi_tool_execution',
        title: 'Canva OAuth and OpenAPI tool execution',
        live_status: 'blocked_missing_required_env',
        plan_rank: 1,
        env_names: ['CANVA_CLIENT_ID', 'CANVA_CLIENT_SECRET'],
        verification_command_count: 2,
      },
      boundaries: [
        {
          id: 'canva_oauth_and_openapi_tool_execution',
          title: 'Canva OAuth and OpenAPI tool execution',
          status: 'external_auth_blocked',
          owner: 'operator',
          missing_required_env_count: 2,
          optional_env_available: false,
          evidence_count: 2,
        },
        {
          id: 'telegram_notification_mcp_credentials',
          title: 'Telegram notification MCP credentials',
          status: 'credential_gated',
          owner: 'operator',
          missing_required_env_count: 2,
          optional_env_available: false,
          evidence_count: 2,
        },
      ],
    },
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

  it('renders workspace smoke timing in the quality panel', async () => {
    const { default: App } = await import('./App')

    render(<App />)

    expect(await screen.findByText('Workspace Smoke')).toBeInTheDocument()
    expect(screen.getByText('2/2 PASS')).toBeInTheDocument()
    expect(screen.getByText('cie tests')).toBeInTheDocument()
    expect(screen.getByText('27.3')).toBeInTheDocument()
  })

  it('renders MCP trace metrics in the quality panel', async () => {
    const { default: App } = await import('./App')

    render(<App />)

    expect(await screen.findByText('MCP Trace')).toBeInTheDocument()
    expect(screen.getByText('1/1 PASS')).toBeInTheDocument()
    expect(screen.getByText('DailyNews unit tests')).toBeInTheDocument()
    expect(screen.getByText('pytest')).toBeInTheDocument()
  })

  it('renders dev-server readiness in the quality panel', async () => {
    const { default: App } = await import('./App')

    render(<App />)

    expect(await screen.findByText('Dev Servers')).toBeInTheDocument()
    expect(screen.getByText('2/2 READY')).toBeInTheDocument()
    expect(screen.getByText('Dashboard API')).toBeInTheDocument()
  })

  it('renders credential boundary blockers in the quality panel', async () => {
    const { default: App } = await import('./App')

    render(<App />)

    expect(await screen.findByText('Credential Boundaries')).toBeInTheDocument()
    expect(screen.getByText('5 ACTION')).toBeInTheDocument()
    expect(screen.getAllByText('Canva OAuth and OpenAPI tool execution').length).toBeGreaterThan(0)
    expect(screen.getByText('Next Unblock')).toBeInTheDocument()
    expect(screen.getByText('CANVA_CLIENT_ID, CANVA_CLIENT_SECRET')).toBeInTheDocument()
    expect(screen.getByText('external auth blocked')).toBeInTheDocument()
  })
})
