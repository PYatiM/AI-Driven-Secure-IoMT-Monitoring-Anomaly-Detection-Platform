import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import ProtectedRoute from "./components/layout/ProtectedRoute";
import { useAuth } from "./context/useAuth";
import "./App.css";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const DeviceDetail = lazy(() => import("./pages/DeviceDetail"));
const Login = lazy(() => import("./pages/Login"));

const RouteFallback = () => (
  <div className="page-loader" role="status" aria-live="polite">
    <div className="pulse" />
    <p>Loading secure workspace...</p>
  </div>
);

function App() {
  const { isAuthenticated, isReady } = useAuth();

  if (!isReady) {
    return (
      <div className="page-loader" role="status" aria-live="polite">
        <div className="pulse" />
        <p>Loading secure workspace...</p>
      </div>
    );
  }

  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route
          path="/"
          element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />}
        />
        <Route
          path="/login"
          element={
            isAuthenticated ? <Navigate to="/dashboard" replace /> : <Login />
          }
        />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/devices/:deviceId"
          element={
            <ProtectedRoute>
              <DeviceDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="*"
          element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />}
        />
      </Routes>
    </Suspense>
  );
}

export default App;

