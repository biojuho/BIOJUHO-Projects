/* global describe, it, expect, vi, beforeEach */
import { QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('../../contexts/LocaleContext', () => ({
  useLocale: () => ({ locale: 'en', t: (key) => key }),
}));

vi.mock('../../services/api', () => ({
  default: { get: vi.fn() },
}));

import client from '../../services/api';
import { queryClient } from '../../lib/queryClient';
import ProductReadinessPanel from '../../components/ProductReadinessPanel';

const READY_PAYLOAD = {
  status: 'ready',
  summary: { ready_count: 4, total: 4, required_ready_count: 3, required_total: 3 },
  checks: [
    { id: 'api', status: 'pass', required: true },
    { id: 'auth', status: 'pass', required: true },
    { id: 'stripe', status: 'pass', required: true },
    { id: 'redis', status: 'pass', required: false },
  ],
  checked_at: '2026-05-11T10:00:00Z',
};

const LAUNCH_PAYLOAD = {
  product: 'DSCI-DecentBio',
  release_decision: 'go',
  operator_phase: 'launch-ready',
  readiness_status: 'ready',
  checked_at: '2026-05-11T10:00:00Z',
  score: { overall_percent: 100, required_percent: 100 },
  summary: {
    ready_count: 4,
    total: 4,
    required_ready_count: 3,
    required_total: 3,
    blocker_count: 0,
    warning_count: 0,
  },
  launch_blockers: [],
  next_actions: [],
};

function renderPanel() {
  return render(
    <QueryClientProvider client={queryClient}>
      <ProductReadinessPanel />
    </QueryClientProvider>,
  );
}

function mockReadinessAndLaunch({ ready = READY_PAYLOAD, launch = LAUNCH_PAYLOAD } = {}) {
  client.get.mockImplementation((path) => {
    if (path === '/ready') return Promise.resolve({ data: ready });
    if (path === '/launch') return Promise.resolve({ data: launch });
    return Promise.reject(new Error(`Unexpected path: ${path}`));
  });
}

describe('ProductReadinessPanel', () => {
  beforeEach(() => {
    client.get.mockReset();
    queryClient.clear();
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it('renders the readiness summary from /ready', async () => {
    mockReadinessAndLaunch();
    renderPanel();

    await waitFor(() => expect(client.get).toHaveBeenCalledWith('/ready', expect.objectContaining({
      suppressErrorLog: true,
      timeout: 10_000,
    })));
    await waitFor(() => expect(client.get).toHaveBeenCalledWith('/launch', expect.objectContaining({
      suppressErrorLog: true,
      timeout: 10_000,
    })));
    expect(await screen.findByTestId('product-readiness-panel')).toBeDefined();
    expect(screen.getByTestId('product-readiness-status')).toBeDefined();
    expect(screen.getByTestId('product-readiness-release-decision')).toHaveTextContent('go');
    expect(screen.getByTestId('product-readiness-operator-phase')).toHaveTextContent('launch-ready');
    expect(screen.getByTestId('product-readiness-launch-score')).toHaveTextContent('100%');
    expect(screen.getByTestId('product-readiness-check-api')).toBeDefined();
    expect(screen.getByTestId('product-readiness-check-auth')).toBeDefined();
    expect(screen.getByTestId('product-readiness-check-stripe')).toBeDefined();
    expect(await screen.findByText('100%')).toBeDefined();
    expect(screen.getByText('4/4 checks ready', { exact: false }) ||
      screen.getByText(/4.*4/)).toBeDefined();
  });

  it('falls back to the unavailable state when /ready fails', async () => {
    client.get.mockImplementation((path) => {
      if (path === '/ready') return Promise.reject(new Error('network down'));
      if (path === '/launch') return Promise.resolve({ data: LAUNCH_PAYLOAD });
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });
    renderPanel();

    await waitFor(() => expect(client.get).toHaveBeenCalled());
    expect(await screen.findByText('Readiness API is unavailable. Check backend connectivity before demo or launch.')).toBeDefined();
  });

  it('re-fetches when Refresh is clicked', async () => {
    let readyPayload = {
      ...READY_PAYLOAD,
      status: 'degraded',
      summary: { ready_count: 1, total: 3, required_ready_count: 1, required_total: 2 },
      checks: [
        { id: 'api', status: 'pass', required: true },
        { id: 'auth', status: 'warn', required: true, remediation: 'Configure auth provider' },
        {
          id: 'stripe',
          status: 'fail',
          required: true,
          remediation: 'Configure Stripe before launch',
          required_env: ['STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET'],
        },
        { id: 'redis', status: 'warn', required: false },
      ],
    };
    let launchPayload = {
      ...LAUNCH_PAYLOAD,
      release_decision: 'go-with-watch',
      operator_phase: 'operator-review',
      readiness_status: 'degraded',
      score: { overall_percent: 33, required_percent: 50 },
      summary: { ready_count: 1, total: 3, required_ready_count: 1, required_total: 2, blocker_count: 1, warning_count: 2 },
      launch_blockers: ['stripe'],
      next_actions: [
        { id: 'stripe', required: true, status: 'fail', remediation: 'Configure Stripe before launch' },
        { id: 'auth', required: true, status: 'warn', remediation: 'Configure auth provider' },
        { id: 'redis', required: false, status: 'warn' },
      ],
    };
    client.get.mockImplementation((path) => {
      if (path === '/ready') return Promise.resolve({ data: readyPayload });
      if (path === '/launch') return Promise.resolve({ data: launchPayload });
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });
    renderPanel();
    await waitFor(() => expect(client.get).toHaveBeenCalledTimes(2));
    expect(await screen.findByTestId('product-readiness-progress')).toHaveTextContent('33%');

    readyPayload = READY_PAYLOAD;
    launchPayload = LAUNCH_PAYLOAD;
    const button = screen.getByRole('button', { name: /Refresh/i });
    fireEvent.click(button);
    await waitFor(() => expect(client.get).toHaveBeenCalledTimes(4));
    await waitFor(() => expect(screen.getByTestId('product-readiness-progress')).toHaveTextContent('100%'));
  });

  it('renders launch next actions from failed and warning checks', async () => {
    const ready = {
        ...READY_PAYLOAD,
        status: 'blocked',
        summary: { ready_count: 1, total: 3, required_ready_count: 1, required_total: 3 },
        checks: [
          { id: 'api', status: 'pass', required: true },
          {
            id: 'stripe',
            status: 'fail',
            required: true,
            remediation: 'Set Stripe keys and Price IDs',
            required_env: ['STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET'],
          },
          {
            id: 'stripe_return_url',
            status: 'fail',
            required: true,
            remediation: 'Set deployed frontend HTTPS origin',
            required_env: ['DESCI_FRONTEND_URL'],
          },
          {
            id: 'stripe_portal',
            status: 'warn',
            required: false,
            remediation: 'Confirm default portal configuration',
            required_env: ['STRIPE_PORTAL_CONFIGURATION_ID'],
          },
          {
            id: 'web3',
            status: 'warn',
            required: false,
            remediation: 'Replace WEB3_RPC_URL with a public HTTPS Polygon Amoy RPC endpoint. Set valid non-zero EVM addresses for NFT_CONTRACT_ADDRESS, DESCI_DAO_CONTRACT_ADDRESS.',
            required_env: ['WEB3_RPC_URL', 'NFT_CONTRACT_ADDRESS', 'DESCI_DAO_CONTRACT_ADDRESS'],
          },
        ],
    };
    const launch = {
      ...LAUNCH_PAYLOAD,
      release_decision: 'no-go',
      operator_phase: 'blocked',
      readiness_status: 'blocked',
      score: { overall_percent: 33, required_percent: 33 },
      summary: {
        ready_count: 1,
        total: 3,
        required_ready_count: 1,
        required_total: 3,
        blocker_count: 2,
        warning_count: 2,
      },
      launch_blockers: ['stripe', 'stripe_return_url'],
      next_actions: [
        {
          id: 'stripe',
          required: true,
          status: 'fail',
          remediation: 'Set Stripe keys and Price IDs',
          required_env: ['STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET'],
        },
        {
          id: 'stripe_return_url',
          required: true,
          status: 'fail',
          remediation: 'Set deployed frontend HTTPS origin',
          required_env: ['DESCI_FRONTEND_URL'],
        },
        {
          id: 'stripe_portal',
          required: false,
          status: 'warn',
          remediation: 'Confirm default portal configuration',
          required_env: ['STRIPE_PORTAL_CONFIGURATION_ID'],
        },
        {
          id: 'web3',
          required: false,
          status: 'warn',
          remediation: 'Replace WEB3_RPC_URL with a public HTTPS Polygon Amoy RPC endpoint. Set valid non-zero EVM addresses for NFT_CONTRACT_ADDRESS, DESCI_DAO_CONTRACT_ADDRESS.',
          required_env: ['WEB3_RPC_URL', 'NFT_CONTRACT_ADDRESS', 'DESCI_DAO_CONTRACT_ADDRESS'],
        },
      ],
    };
    mockReadinessAndLaunch({ ready, launch });

    renderPanel();

    expect(await screen.findByTestId('product-readiness-next-actions')).toBeDefined();
    expect(screen.getByTestId('product-readiness-release-decision')).toHaveTextContent('no-go');
    expect(screen.getByTestId('product-readiness-operator-phase')).toHaveTextContent('blocked');
    expect(screen.getByTestId('product-readiness-next-action-stripe')).toHaveTextContent('Set Stripe keys and Price IDs');
    expect(screen.getByTestId('product-readiness-next-action-stripe')).toHaveTextContent('STRIPE_SECRET_KEY');
    expect(screen.getByTestId('product-readiness-next-action-stripe_return_url')).toHaveTextContent('Stripe return URL');
    expect(screen.getByTestId('product-readiness-next-action-stripe_return_url')).toHaveTextContent('DESCI_FRONTEND_URL');
    expect(screen.getByTestId('product-readiness-next-action-stripe_portal')).toHaveTextContent('Stripe portal configuration');
    expect(screen.getByTestId('product-readiness-next-action-stripe_portal')).toHaveTextContent('STRIPE_PORTAL_CONFIGURATION_ID');
    expect(screen.getByTestId('product-readiness-next-action-web3')).toHaveTextContent('Replace WEB3_RPC_URL with a public HTTPS Polygon Amoy RPC endpoint');
    expect(screen.getByTestId('product-readiness-next-action-web3')).toHaveTextContent('NFT_CONTRACT_ADDRESS');
    expect(screen.getByTestId('product-readiness-next-action-web3')).toHaveTextContent('DESCI_DAO_CONTRACT_ADDRESS');
    expect(screen.getByRole('button', { name: 'Copy all 4 launch actions' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Copy Stripe billing launch action' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Copy Stripe return URL launch action' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Copy Stripe portal configuration launch action' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Copy Web3 launch action' })).toBeDefined();
    expect(screen.getByTestId('product-readiness-env-handoff')).toHaveTextContent('Launch env handoff');
    expect(screen.getByTestId('product-readiness-env-handoff')).toHaveTextContent('7 placeholder env value(s)');
    expect(screen.getByTestId('product-readiness-env-handoff-required')).toHaveTextContent('STRIPE_SECRET_KEY');
    expect(screen.getByTestId('product-readiness-env-handoff-required')).toHaveTextContent('STRIPE_WEBHOOK_SECRET');
    expect(screen.getByTestId('product-readiness-env-handoff-required')).toHaveTextContent('DESCI_FRONTEND_URL');
    expect(screen.getByTestId('product-readiness-env-handoff-optional')).toHaveTextContent('STRIPE_PORTAL_CONFIGURATION_ID');
    expect(screen.getByTestId('product-readiness-env-handoff-optional')).toHaveTextContent('WEB3_RPC_URL');
    expect(screen.getByTestId('product-readiness-env-handoff-optional')).toHaveTextContent('NFT_CONTRACT_ADDRESS');

    fireEvent.click(screen.getByTestId('product-readiness-env-handoff-copy'));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
    expect(await screen.findByRole('status')).toHaveTextContent('Copied launch env handoff.');
    const copiedEnvPayload = navigator.clipboard.writeText.mock.calls[0][0];
    expect(copiedEnvPayload).toContain('# DSCI launch env handoff');
    expect(copiedEnvPayload).toContain('# Required before release');
    expect(copiedEnvPayload).toContain('STRIPE_SECRET_KEY=<set-secure-value>');
    expect(copiedEnvPayload).toContain('STRIPE_WEBHOOK_SECRET=<set-secure-value>');
    expect(copiedEnvPayload).toContain('DESCI_FRONTEND_URL=<set-secure-value>');
    expect(copiedEnvPayload).toContain('# Optional launch hardening');
    expect(copiedEnvPayload).toContain('STRIPE_PORTAL_CONFIGURATION_ID=<set-secure-value>');
    expect(copiedEnvPayload).toContain('WEB3_RPC_URL=<set-secure-value>');
    expect(copiedEnvPayload).toContain('NFT_CONTRACT_ADDRESS=<set-secure-value>');
    expect(copiedEnvPayload).not.toContain('Set Stripe keys');
    expect(copiedEnvPayload).not.toContain('sk_live_');

    navigator.clipboard.writeText.mockClear();
    fireEvent.click(screen.getByTestId('product-readiness-next-action-copy-stripe'));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
    expect(await screen.findByRole('status')).toHaveTextContent('Copied Stripe billing launch action.');
    const copiedPayload = navigator.clipboard.writeText.mock.calls[0][0];
    expect(copiedPayload).toContain('Launch action: Stripe billing');
    expect(copiedPayload).toContain('Priority: required');
    expect(copiedPayload).toContain('Set Stripe keys and Price IDs');
    expect(copiedPayload).toContain('Required env: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET');
    expect(copiedPayload).not.toContain('sk_live_');

    navigator.clipboard.writeText.mockClear();
    fireEvent.click(screen.getByTestId('product-readiness-next-actions-copy-all'));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Copied 4 launch actions.'));
    const copiedAllPayload = navigator.clipboard.writeText.mock.calls[0][0];
    expect(copiedAllPayload).toContain('Launch action: Stripe billing');
    expect(copiedAllPayload).toContain('Launch action: Stripe return URL');
    expect(copiedAllPayload).toContain('Launch action: Stripe portal configuration');
    expect(copiedAllPayload).toContain('Launch action: Web3');
    expect(copiedAllPayload).toContain('Required env: DESCI_FRONTEND_URL');
    expect(copiedAllPayload).toContain('Required env: STRIPE_PORTAL_CONFIGURATION_ID');
    expect(copiedAllPayload).toContain('Required env: WEB3_RPC_URL, NFT_CONTRACT_ADDRESS, DESCI_DAO_CONTRACT_ADDRESS');
    expect(copiedAllPayload).toContain('Replace WEB3_RPC_URL with a public HTTPS Polygon Amoy RPC endpoint');
    expect(copiedAllPayload).not.toContain('sk_live_');
  });

  it('uses /launch next actions when they differ from /ready checks', async () => {
    const ready = {
      ...READY_PAYLOAD,
      status: 'blocked',
      summary: { ready_count: 2, total: 3, required_ready_count: 2, required_total: 3 },
      checks: [
        { id: 'api', status: 'pass', required: true },
        {
          id: 'stripe',
          status: 'fail',
          required: true,
          remediation: 'Readiness-only Stripe remediation',
          required_env: ['STRIPE_SECRET_KEY'],
        },
      ],
      launch_blockers: ['stripe'],
    };
    const launch = {
      ...LAUNCH_PAYLOAD,
      release_decision: 'no-go',
      operator_phase: 'blocked',
      readiness_status: 'blocked',
      score: { overall_percent: 67, required_percent: 67 },
      summary: {
        ready_count: 2,
        total: 3,
        required_ready_count: 2,
        required_total: 3,
        blocker_count: 1,
        warning_count: 0,
      },
      launch_blockers: ['llm'],
      next_actions: [
        {
          id: 'llm',
          required: true,
          status: 'fail',
          remediation: 'Set one approved LLM provider key',
          required_env: ['OPENAI_API_KEY'],
        },
      ],
    };
    mockReadinessAndLaunch({ ready, launch });

    renderPanel();

    expect(await screen.findByTestId('product-readiness-next-action-llm')).toHaveTextContent('Set one approved LLM provider key');
    expect(screen.queryByTestId('product-readiness-next-action-stripe')).toBeNull();
    expect(screen.getByTestId('product-readiness-launch-drift')).toHaveTextContent('actions');
    expect(screen.getByTestId('product-readiness-launch-drift')).toHaveTextContent('requiredEnv');
  });

  it('does not flag action drift when /launch reorders matching /ready coverage', async () => {
    const ready = {
      ...READY_PAYLOAD,
      status: 'blocked',
      summary: { ready_count: 1, total: 4, required_ready_count: 1, required_total: 3 },
      checks: [
        { id: 'api', status: 'pass', required: true },
        {
          id: 'auth',
          status: 'warn',
          required: true,
          remediation: 'Configure auth provider',
          required_env: ['GOOGLE_APPLICATION_CREDENTIALS'],
        },
        {
          id: 'stripe',
          status: 'fail',
          required: true,
          remediation: 'Set Stripe keys',
          required_env: ['STRIPE_SECRET_KEY'],
        },
        {
          id: 'web3',
          status: 'warn',
          required: false,
          remediation: 'Review Web3 settings',
          required_env: ['WEB3_RPC_URL'],
        },
      ],
      launch_blockers: ['stripe'],
    };
    const launch = {
      ...LAUNCH_PAYLOAD,
      release_decision: 'no-go',
      operator_phase: 'blocked',
      readiness_status: 'blocked',
      score: { overall_percent: 25, required_percent: 33 },
      summary: {
        ready_count: 1,
        total: 4,
        required_ready_count: 1,
        required_total: 3,
        blocker_count: 1,
        warning_count: 2,
      },
      launch_blockers: ['stripe'],
      next_actions: [
        {
          id: 'stripe',
          required: true,
          status: 'fail',
          remediation: 'Set Stripe keys',
          required_env: ['STRIPE_SECRET_KEY'],
        },
        {
          id: 'auth',
          required: true,
          status: 'warn',
          remediation: 'Configure auth provider',
          required_env: ['GOOGLE_APPLICATION_CREDENTIALS'],
        },
        {
          id: 'web3',
          required: false,
          status: 'warn',
          remediation: 'Review Web3 settings',
          required_env: ['WEB3_RPC_URL'],
        },
      ],
    };
    mockReadinessAndLaunch({ ready, launch });

    renderPanel();

    expect(await screen.findByTestId('product-readiness-next-action-stripe')).toHaveTextContent('Set Stripe keys');
    expect(screen.queryByTestId('product-readiness-launch-drift')).toBeNull();
  });

  it('flags visible drift between /ready and /launch', async () => {
    mockReadinessAndLaunch({
      ready: {
        ...READY_PAYLOAD,
        status: 'blocked',
        summary: { ready_count: 3, total: 4, required_ready_count: 2, required_total: 3 },
        checks: [
          { id: 'api', status: 'pass', required: true },
          { id: 'auth', status: 'pass', required: true },
          {
            id: 'llm',
            status: 'fail',
            required: true,
            remediation: 'Set one approved LLM provider key',
            required_env: ['OPENAI_API_KEY'],
          },
          { id: 'redis', status: 'pass', required: false },
        ],
        launch_blockers: ['llm'],
      },
      launch: {
        ...LAUNCH_PAYLOAD,
        release_decision: 'no-go',
        operator_phase: 'blocked',
        readiness_status: 'blocked',
        score: { overall_percent: 100, required_percent: 100 },
        summary: {
          ready_count: 4,
          total: 4,
          required_ready_count: 3,
          required_total: 3,
          blocker_count: 1,
          warning_count: 0,
        },
        launch_blockers: ['stripe'],
        next_actions: [{ id: 'stripe', required: true, status: 'fail', required_env: ['STRIPE_SECRET_KEY'] }],
      },
    });

    renderPanel();

    expect(await screen.findByTestId('product-readiness-launch-drift')).toHaveTextContent(
      'Launch control does not match readiness evidence.',
    );
    expect(screen.getByTestId('product-readiness-launch-drift')).toHaveTextContent('summary');
    expect(screen.getByTestId('product-readiness-launch-drift')).toHaveTextContent('blockers');
    expect(screen.getByTestId('product-readiness-launch-drift')).toHaveTextContent('actions');
    expect(screen.getByTestId('product-readiness-launch-drift')).toHaveTextContent('requiredEnv');
  });

  it('shows an actionable alert when clipboard copy fails', async () => {
    navigator.clipboard.writeText.mockRejectedValueOnce(new Error('clipboard denied'));
    const ready = {
        ...READY_PAYLOAD,
        status: 'blocked',
        summary: { ready_count: 1, total: 2, required_ready_count: 1, required_total: 2 },
        checks: [
          { id: 'api', status: 'pass', required: true },
          {
            id: 'stripe',
            status: 'fail',
            required: true,
            remediation: 'Set Stripe keys and Price IDs',
            required_env: ['STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET'],
          },
        ],
    };
    const launch = {
      ...LAUNCH_PAYLOAD,
      release_decision: 'no-go',
      operator_phase: 'blocked',
      readiness_status: 'blocked',
      score: { overall_percent: 50, required_percent: 50 },
      summary: { ready_count: 1, total: 2, required_ready_count: 1, required_total: 2, blocker_count: 1, warning_count: 0 },
      launch_blockers: ['stripe'],
      next_actions: [
        {
          id: 'stripe',
          required: true,
          status: 'fail',
          remediation: 'Set Stripe keys and Price IDs',
          required_env: ['STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET'],
        },
      ],
    };
    mockReadinessAndLaunch({ ready, launch });

    renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: 'Copy Stripe billing launch action' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not copy Stripe billing. Use the visible remediation and env list.',
    );
    expect(screen.getByTestId('product-readiness-next-action-copy-stripe')).toHaveTextContent('Copy');
  });

  it('renders non-secret Web3 readiness triage details', async () => {
    const ready = {
      ...READY_PAYLOAD,
      status: 'degraded',
      summary: { ready_count: 3, total: 4, required_ready_count: 3, required_total: 3 },
      checks: [
        { id: 'api', status: 'pass', required: true },
        { id: 'auth', status: 'pass', required: true },
        { id: 'stripe', status: 'pass', required: true },
        {
          id: 'web3',
          status: 'warn',
          required: false,
          remediation: 'Verify production wallet and Amoy contract settings.',
          details: {
            rpc_configured: true,
            rpc_public_https: false,
            contract_count: 1,
            contracts: {
              DSCI_CONTRACT_ADDRESS: true,
              NFT_CONTRACT_ADDRESS: false,
              DESCI_DAO_CONTRACT_ADDRESS: false,
            },
            mock_mode_enabled: true,
            mock_mode_allowed: false,
            rpc_url: 'https://secret-rpc.example',
            contract_address: '0x1111111111111111111111111111111111111111',
          },
        },
      ],
    };
    const launch = {
      ...LAUNCH_PAYLOAD,
      release_decision: 'go-with-watch',
      operator_phase: 'operator-review',
      readiness_status: 'degraded',
      score: { overall_percent: 75, required_percent: 100 },
      summary: {
        ready_count: 3,
        total: 4,
        required_ready_count: 3,
        required_total: 3,
        blocker_count: 0,
        warning_count: 1,
      },
      next_actions: [
        {
          id: 'web3',
          required: false,
          status: 'warn',
          remediation: 'Disable MOCK_MODE before production handoff. Replace WEB3_RPC_URL with a public HTTPS Polygon Amoy RPC endpoint. Set valid non-zero EVM addresses for NFT_CONTRACT_ADDRESS, DESCI_DAO_CONTRACT_ADDRESS.',
          required_env: ['MOCK_MODE', 'WEB3_RPC_URL', 'NFT_CONTRACT_ADDRESS', 'DESCI_DAO_CONTRACT_ADDRESS'],
        },
      ],
    };
    mockReadinessAndLaunch({ ready, launch });

    renderPanel();

    expect(await screen.findByTestId('product-readiness-web3-triage')).toBeDefined();
    expect(screen.getByTestId('product-readiness-web3-rpc')).toHaveTextContent('RPC configured, not public HTTPS');
    expect(screen.getByTestId('product-readiness-web3-contracts')).toHaveTextContent('1 valid contract env value');
    expect(screen.getByTestId('product-readiness-web3-contract-DSCI_CONTRACT_ADDRESS')).toHaveTextContent('valid');
    expect(screen.getByTestId('product-readiness-web3-contract-NFT_CONTRACT_ADDRESS')).toHaveTextContent('missing');
    expect(screen.getByTestId('product-readiness-web3-mock')).toHaveTextContent('MOCK_MODE enabled in production path');
    expect(screen.getByTestId('product-readiness-next-action-web3')).toHaveTextContent('Disable MOCK_MODE before production handoff');
    expect(screen.getByTestId('product-readiness-next-action-web3')).toHaveTextContent('WEB3_RPC_URL');
    expect(screen.getByTestId('product-readiness-panel')).not.toHaveTextContent('https://secret-rpc.example');
    expect(screen.getByTestId('product-readiness-panel')).not.toHaveTextContent('0x1111111111111111111111111111111111111111');
  });
});
