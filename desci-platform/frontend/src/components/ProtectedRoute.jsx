/**
 * Protected Route Component
 * Redirects to login if not authenticated
 */
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Layout from './Layout';

export default function ProtectedRoute() {
    const { user, loading } = useAuth();

    // Loading state - show spinner
    if (loading) {
        return (
            <div className="min-h-screen bg-[#040811] flex items-center justify-center">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-14 w-14 border-2 border-white/10 border-t-primary mx-auto mb-4"></div>
                    <p className="text-white/60 text-sm font-medium">인증 확인 중...</p>
                </div>
            </div>
        );
    }

    // Not authenticated - redirect to login
    if (!user) {
        return <Navigate to="/login" replace />;
    }

    // Authenticated - render layout with child routes
    return (
        <Layout>
            <Outlet />
        </Layout>
    );
}
