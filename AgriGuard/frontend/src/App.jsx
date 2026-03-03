import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ToastProvider } from './contexts/ToastContext';
import Layout from './components/Layout';
import Dashboard from './components/dashboard/Dashboard';
import ProductRegistry from './components/ProductRegistry';
import ProductDetail from './components/ProductDetail';
import SupplyChain from './components/SupplyChain';
import QRReader from './components/QRReader';
import ColdChainMonitor from './components/ColdChainMonitor';

function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="registry" element={<ProductRegistry />} />
            <Route path="product/:id" element={<ProductDetail />} />
            <Route path="supply-chain" element={<SupplyChain />} />
            <Route path="scan" element={<QRReader />} />
          <Route path="cold-chain" element={<ColdChainMonitor />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}

export default App;

