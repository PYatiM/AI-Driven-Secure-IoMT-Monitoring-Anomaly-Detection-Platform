import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../../context/useAuth";

const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, isReady } = useAuth();
  const location = useLocation();

  if (!isReady) {
    return (
      <div className="page-loader" role="status" aria-live="polite">
        <div className="pulse" />
        <p>Restoring secure session...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return children;
};

export default ProtectedRoute;

