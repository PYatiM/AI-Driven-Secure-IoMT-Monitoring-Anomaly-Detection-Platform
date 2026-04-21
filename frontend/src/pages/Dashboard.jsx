import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import Navbar from "../components/layout/Navbar";
import Sidebar from "../components/layout/Sidebar";
import { useNotifications } from "../context/useNotifications";
import { useTheme } from "../context/useTheme";
import { useAuth } from "../context/useAuth";
import {
  connectMonitoringSocket,
  getDeviceTelemetry,
  listAlerts,
  listDevices,
} from "../services/monitoringApi";

const TelemetryChart = lazy(() => import("../components/charts/TelemetryChart"));

const DEFAULT_ALERT_FILTERS = {
  severity: "",
  status: "",
  sortBy: "triggered_at",
  sortOrder: "desc",
};

const buildChartData = (items) =>
  items
    .slice()
    .reverse()
    .map((item) => ({
      recordedAt: item.recorded_at,
      value: item.value_numeric ?? 0,
      metric: item.metric_name,
      anomalyFlag: item.anomaly_flag,
    }));

const Dashboard = () => {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { pushNotification } = useNotifications();
  const navigate = useNavigate();

  const [devices, setDevices] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [summary, setSummary] = useState({
    total_devices: 0,
    active_devices: 0,
    open_alerts: 0,
    critical_alerts: 0,
    recent_anomalies: 0,
  });
  const [selectedDeviceId, setSelectedDeviceId] = useState(null);
  const [telemetryItems, setTelemetryItems] = useState([]);
  const [connectionState, setConnectionState] = useState("polling");
  const [isLoading, setIsLoading] = useState(true);
  const [alertFilters, setAlertFilters] = useState(DEFAULT_ALERT_FILTERS);

  const chartData = useMemo(() => buildChartData(telemetryItems), [telemetryItems]);

  const loadDevices = useCallback(async () => {
    const data = await listDevices({ page: 1, page_size: 100 });
    setDevices(data.items);
    if (!selectedDeviceId && data.items.length) {
      setSelectedDeviceId(data.items[0].id);
    }
    return data.items;
  }, [selectedDeviceId]);

  const loadTelemetry = useCallback(async (deviceId) => {
    if (!deviceId) {
      return;
    }
    const data = await getDeviceTelemetry(deviceId, { page: 1, page_size: 200 });
    setTelemetryItems(data.items);
  }, []);

  const loadAlerts = useCallback(async (filters = alertFilters) => {
    const data = await listAlerts({
      page: 1,
      page_size: 50,
      severity: filters.severity || undefined,
      status: filters.status || undefined,
      sort_by: filters.sortBy,
      sort_order: filters.sortOrder,
    });
    setAlerts(data.items);
  }, [alertFilters]);

  useEffect(() => {
    let cancelled = false;

    const initialLoad = async () => {
      setIsLoading(true);
      try {
        const loadedDevices = await loadDevices();
        await loadAlerts(DEFAULT_ALERT_FILTERS);
        if (loadedDevices.length && !cancelled) {
          await loadTelemetry(loadedDevices[0].id);
        }
      } catch (error) {
        if (!cancelled) {
          pushNotification({
            type: "error",
            title: "Dashboard sync failed",
            message: error.response?.data?.detail || "Unable to load monitoring feeds.",
          });
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    initialLoad();
    return () => {
      cancelled = true;
    };
  }, [loadAlerts, loadDevices, loadTelemetry, pushNotification]);

  useEffect(() => {
    if (!selectedDeviceId) {
      return;
    }

    loadTelemetry(selectedDeviceId).catch((error) => {
      pushNotification({
        type: "warning",
        title: "Telemetry refresh issue",
        message: error.response?.data?.detail || "Could not refresh telemetry stream.",
      });
    });
  }, [loadTelemetry, selectedDeviceId, pushNotification]);

  useEffect(() => {
    let socket;
    let pollingTimer;

    const setupSocket = () => {
      socket = connectMonitoringSocket({
        onOpen: () => setConnectionState("live"),
        onClose: () => {
          setConnectionState("polling");
          pollingTimer = window.setInterval(async () => {
            try {
              await loadAlerts();
              await loadDevices();
            } catch {
              // keep polling silently to avoid noisy notifications
            }
          }, 10000);
        },
        onError: () => {
          setConnectionState("polling");
        },
        onMessage: (message) => {
          if (message.type !== "snapshot") {
            return;
          }

          const incomingSummary = message.payload?.summary;
          if (incomingSummary) {
            setSummary(incomingSummary);
          }

          const incomingAlerts = message.payload?.latest_alerts ?? [];
          if (incomingAlerts.length) {
            setAlerts((current) => {
              const merged = [...incomingAlerts, ...current];
              const deduped = new Map();
              for (const item of merged) {
                deduped.set(item.id, item);
              }
              return Array.from(deduped.values()).slice(0, 100);
            });
          }
        },
      });
    };

    setupSocket();

    return () => {
      if (socket) {
        socket.close();
      }
      if (pollingTimer) {
        window.clearInterval(pollingTimer);
      }
    };
  }, [loadAlerts, loadDevices]);

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const handleAlertFilterChange = (field, value) => {
    const nextFilters = { ...alertFilters, [field]: value };
    setAlertFilters(nextFilters);
    loadAlerts(nextFilters).catch((error) => {
      pushNotification({
        type: "warning",
        title: "Alert filter failed",
        message: error.response?.data?.detail || "Unable to apply alert filters.",
      });
    });
  };

  const handleDeviceRowClick = (deviceId) => {
    navigate(`/devices/${deviceId}`);
  };

  const summaryCards = [
    { label: "Total Devices", value: String(summary.total_devices ?? devices.length) },
    { label: "Active Devices", value: String(summary.active_devices ?? 0) },
    { label: "Open Alerts", value: String(summary.open_alerts ?? 0) },
    { label: "Critical Alerts", value: String(summary.critical_alerts ?? 0) },
    { label: "Recent Anomalies (15m)", value: String(summary.recent_anomalies ?? 0) },
  ];

  if (isLoading) {
    return (
      <div className="page-loader">
        <div className="pulse" />
        <p>Loading monitoring dashboard...</p>
      </div>
    );
  }

  return (
    <div className="dashboard-shell">
      <Sidebar devicesCount={devices.length} />

      <main className="dashboard-main">
        <Navbar
          user={user}
          onLogout={handleLogout}
          onToggleTheme={toggleTheme}
          theme={theme}
          connectionState={connectionState}
        />

        <section className="metrics-grid" aria-label="Monitoring summary cards">
          {summaryCards.map((card) => (
            <article key={card.label} className="metric-card">
              <p>{card.label}</p>
              <h3>{card.value}</h3>
            </article>
          ))}
        </section>

        <section className="dashboard-panels">
          <article className="panel device-table-panel" id="devices">
            <header>
              <h3>Device List</h3>
              <span>{devices.length} devices</span>
            </header>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Identifier</th>
                    <th>Type</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {devices.map((device) => (
                    <tr
                      key={device.id}
                      onClick={() => handleDeviceRowClick(device.id)}
                      className={selectedDeviceId === device.id ? "selected" : ""}
                    >
                      <td>{device.name}</td>
                      <td>{device.device_identifier}</td>
                      <td>{device.device_type}</td>
                      <td>{device.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>

          <Suspense
            fallback={
              <article className="panel chart-panel">
                <div className="panel-header">
                  <h3>Real-time telemetry graph</h3>
                  <p>Loading chart module...</p>
                </div>
              </article>
            }
          >
            <TelemetryChart
              data={chartData}
              title="Real-time telemetry graph"
              metricName={chartData.at(-1)?.metric}
            />
          </Suspense>
        </section>

        <article className="panel" id="alerts">
          <header>
            <h3>Anomaly Alerts</h3>
            <span>{alerts.length} items</span>
          </header>
          <div className="filters">
            <label>
              Severity
              <select
                value={alertFilters.severity}
                onChange={(event) => handleAlertFilterChange("severity", event.target.value)}
              >
                <option value="">All</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </label>
            <label>
              Status
              <select
                value={alertFilters.status}
                onChange={(event) => handleAlertFilterChange("status", event.target.value)}
              >
                <option value="">All</option>
                <option value="open">Open</option>
                <option value="acknowledged">Acknowledged</option>
                <option value="resolved">Resolved</option>
                <option value="dismissed">Dismissed</option>
              </select>
            </label>
            <label>
              Sort
              <select
                value={alertFilters.sortBy}
                onChange={(event) => handleAlertFilterChange("sortBy", event.target.value)}
              >
                <option value="triggered_at">Triggered time</option>
                <option value="severity">Severity</option>
                <option value="anomaly_score">Anomaly score</option>
              </select>
            </label>
            <label>
              Order
              <select
                value={alertFilters.sortOrder}
                onChange={(event) => handleAlertFilterChange("sortOrder", event.target.value)}
              >
                <option value="desc">Descending</option>
                <option value="asc">Ascending</option>
              </select>
            </label>
          </div>
          <ul className="incident-list">
            {alerts.map((alert) => (
              <li key={alert.id}>
                <div>
                  <p>{alert.device_name}</p>
                  <h4>{alert.title}</h4>
                  <small>{alert.triggered_at}</small>
                </div>
                <strong className={`pill ${String(alert.severity).toLowerCase()}`}>
                  {alert.severity}
                </strong>
              </li>
            ))}
          </ul>
        </article>
      </main>
    </div>
  );
};

export default Dashboard;
