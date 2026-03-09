/* global describe, it, expect, vi */
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';

// Mock lazy-loaded components to keep tests fast
vi.mock('../components/dashboard/Dashboard', () => ({
  default: () => <div data-testid="dashboard">Dashboard</div>,
}));
vi.mock('../components/ProductRegistry', () => ({
  default: () => <div data-testid="product-registry">Registry</div>,
}));
vi.mock('../components/ProductDetail', () => ({
  default: () => <div data-testid="product-detail">Detail</div>,
}));
vi.mock('../components/SupplyChain', () => ({
  default: () => <div data-testid="supply-chain">Supply</div>,
}));
vi.mock('../components/QRReader', () => ({
  default: () => <div data-testid="qr-reader">QR</div>,
}));
vi.mock('../components/ColdChainMonitor', () => ({
  default: () => <div data-testid="cold-chain">ColdChain</div>,
}));

// Helper that wraps render with MemoryRouter
function renderApp() {
  // We need to render just the routes part, since App includes BrowserRouter
  // Instead, we test the App directly — BrowserRouter is internal
  return render(<App />);
}

describe('App smoke tests', () => {
  it('renders without crashing', () => {
    renderApp();
    // Layout should always render (nav, sidebar, etc.)
    expect(document.body).toBeTruthy();
  });

  it('renders the dashboard on the root route', async () => {
    renderApp('/');
    const dashboard = await screen.findByTestId('dashboard');
    expect(dashboard).toBeInTheDocument();
  });
});
