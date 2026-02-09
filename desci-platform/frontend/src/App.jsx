/**
 * DSCI-DecentBio Platform - Main App with Routing
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import BioLinker from './components/BioLinker';
import Upload from './components/Upload';
import Wallet from './components/Wallet';
import MyLab from './components/MyLab';
import Payment, { PaymentSuccess } from './components/Payment';
import ProtectedRoute from './components/ProtectedRoute';
import './App.css';

// Redirect authenticated users away from login
function LoginRoute() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-800 flex items-center justify-center">
        <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-cyan-400"></div>
      </div>
    );
  }

  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Login />;
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginRoute />} />

          {/* Protected routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/biolinker" element={<BioLinker />} />
            <Route path="/upload" element={<Upload />} />
            <Route path="/wallet" element={<Wallet />} />
            <Route path="/payment" element={<Payment />} />
            <Route path="/payment/success" element={<PaymentSuccess />} />
            <Route path="/payment/cancel" element={<Payment />} />
            <Route path="/payment/fail" element={<Payment />} />
            <Route path="/mylab" element={<MyLab />} />
          </Route>

          {/* Default redirect */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
