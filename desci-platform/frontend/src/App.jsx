/**
 * DSCI-DecentBio Platform - Main App with Routing
 */
import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { LocaleProvider } from './contexts/LocaleContext';
import { ToastProvider } from './contexts/ToastContext';
import { AnimatePresence } from 'framer-motion';
import ProtectedRoute from './components/ProtectedRoute';
import AppErrorBoundary from './components/ErrorBoundary';
import PageTransition from './components/ui/PageTransition';
import './App.css';

const Login = lazy(() => import('./components/Login'));
const Dashboard = lazy(() => import('./components/Dashboard'));
const BioLinker = lazy(() => import('./components/BioLinker'));
const AssetManager = lazy(() => import('./components/AssetManager'));
const Wallet = lazy(() => import('./components/Wallet'));
const MyLab = lazy(() => import('./components/MyLab'));
const VCDashboard = lazy(() => import('./components/VCDashboard'));
const Notices = lazy(() => import('./components/Notices'));
const AILab = lazy(() => import('./components/AILab'));
const PeerReview = lazy(() => import('./components/PeerReview'));
const UploadPaper = lazy(() => import('./components/UploadPaper'));
const Governance = lazy(() => import('./components/Governance'));

function RouteFallback() {
  return (
    <div className="min-h-screen bg-[#040811] flex items-center justify-center">
      <div className="animate-spin rounded-full h-14 w-14 border-2 border-white/10 border-t-primary"></div>
    </div>
  );
}

// Redirect authenticated users away from login
function LoginRoute() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-[#040811] flex items-center justify-center">
        <div className="animate-spin rounded-full h-16 w-16 border-2 border-white/10 border-t-primary"></div>
      </div>
    );
  }

  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <Suspense fallback={<RouteFallback />}>
      <Login />
    </Suspense>
  );
}

function AnimatedRoutes() {
  const location = useLocation();

  return (
    <Suspense fallback={<RouteFallback />}>
      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname}>
          {/* Public routes */}
          <Route path="/login" element={<LoginRoute />} />

          {/* Protected routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<PageTransition><Dashboard /></PageTransition>} />
            <Route path="/biolinker" element={<PageTransition><BioLinker /></PageTransition>} />
            <Route path="/upload" element={<PageTransition><UploadPaper /></PageTransition>} />
            <Route path="/wallet" element={<PageTransition><Wallet /></PageTransition>} />
            <Route path="/mylab" element={<PageTransition><MyLab /></PageTransition>} />
            <Route path="/vc-portal" element={<PageTransition><VCDashboard /></PageTransition>} />
            <Route path="/notices" element={<PageTransition><Notices /></PageTransition>} />
            <Route path="/ai-lab" element={<PageTransition><AILab /></PageTransition>} />
            <Route path="/peer-review" element={<PageTransition><PeerReview /></PageTransition>} />
            <Route path="/assets" element={<PageTransition><AssetManager /></PageTransition>} />
            <Route path="/governance" element={<PageTransition><Governance /></PageTransition>} />
          </Route>

          {/* Default redirect */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AnimatePresence>
    </Suspense>
  );
}

function App() {
  return (
    <AppErrorBoundary>
      <BrowserRouter>
        <LocaleProvider>
          <AuthProvider>
            <ToastProvider>
              <AnimatedRoutes />
            </ToastProvider>
          </AuthProvider>
        </LocaleProvider>
      </BrowserRouter>
    </AppErrorBoundary>
  );
}

export default App;
