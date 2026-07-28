import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function ProtectedAdminRoute() {
  const { user, loading, sessionExpired } = useAuth();

  if (loading) {
    // Basic loading state while checking session
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', width: '100vw' }}>
        <p>Loading...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <Navigate
        to="/sign-in?role=admin"
        replace
        state={{ notice: sessionExpired ? 'Your session expired because of inactivity.' : undefined }}
      />
    );
  }

  return <Outlet />;
}
