import { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ToastProvider } from './contexts/ToastContext';
import Layout from './components/Layout';

// Route-level code splitting — each page loads on demand
const Dashboard = lazy(() => import('./components/dashboard/Dashboard'));
const ProductRegistry = lazy(() => import('./components/ProductRegistry'));
const ProductDetail = lazy(() => import('./components/ProductDetail'));
const SupplyChain = lazy(() => import('./components/SupplyChain'));
const QRReader = lazy(() => import('./components/QRReader'));
const ColdChainMonitor = lazy(() => import('./components/ColdChainMonitor'));

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-10 w-10 border-2 border-green-500 border-t-transparent" />
    </div>
  );
}

function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Suspense fallback={<LoadingSpinner />}><Dashboard /></Suspense>} />
            <Route path="registry" element={<Suspense fallback={<LoadingSpinner />}><ProductRegistry /></Suspense>} />
            <Route path="product/:id" element={<Suspense fallback={<LoadingSpinner />}><ProductDetail /></Suspense>} />
            <Route path="supply-chain" element={<Suspense fallback={<LoadingSpinner />}><SupplyChain /></Suspense>} />
            <Route path="scan" element={<Suspense fallback={<LoadingSpinner />}><QRReader /></Suspense>} />
            <Route path="cold-chain" element={<Suspense fallback={<LoadingSpinner />}><ColdChainMonitor /></Suspense>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}

export default App;
