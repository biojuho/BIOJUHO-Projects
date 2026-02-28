import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './components/dashboard/Dashboard';
import ProductRegistry from './components/ProductRegistry';
import ProductDetail from './components/ProductDetail';
import SupplyChain from './components/SupplyChain';
import QRReader from './components/QRReader';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="registry" element={<ProductRegistry />} />
          <Route path="product/:id" element={<ProductDetail />} />
          <Route path="supply-chain" element={<SupplyChain />} />
          <Route path="scan" element={<QRReader />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
