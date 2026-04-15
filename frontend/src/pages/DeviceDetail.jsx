import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import TelemetryChart from "../components/charts/TelemetryChart";
import { useNotifications } from "../context/useNotifications";
import { getDeviceDetail } from "../services/monitoringApi";

const formatChartData = (telemetryItems) =>
  telemetryItems
    .slice()
    .reverse()
    .map((item) => ({
      recordedAt: item.recorded_at,
      value: item.value_numeric ?? 0,
      metric: item.metric_name,
      anomalyFlag: item.anomaly_flag,
    }));

const DeviceDetail = () => {
  const { deviceId } = useParams();
  const navigate = useNavigate();
  const { pushNotification } = useNotifications();

  const [isLoading, setIsLoading] = useState(true);
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    const loadDetail = async () => {
      setIsLoading(true);
      setError("");

      try {
        const payload = await getDeviceDetail(deviceId);
        if (!cancelled) {
          setDetail(payload);
        }
      } catch (requestError) {
        const message =
          requestError.response?.data?.detail || "Unable to load device details.";
        if (!cancelled) {
          setError(message);
          pushNotification({
            type: "error",
            title: "Device detail unavailable",
            message,
          });
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    loadDetail();
    return () => {
      cancelled = true;
    };
  }, [deviceId, pushNotification]);

  const chartData = useMemo(
    () => formatChartData(detail?.telemetry_preview ?? []),
    [detail?.telemetry_preview]
  );

  if (isLoading) {
    return (
      <div className="page-loader">
        <div className="pulse" />
        <p>Loading device details...</p>
      </div>
    );
  }

  if (error) {
    return (
      <section className="standalone-page">
        <h2>Device details unavailable</h2>
        <p>{error}</p>
        <button type="button" className="ghost-btn" onClick={() => navigate("/dashboard")}>
          Back to dashboard
        </button>
      </section>
    );
  }

  if (!detail) {
    return null;
  }

  return (
    <section className="standalone-page">
      <div className="detail-header">
        <div>
          <p className="eyebrow">Device Intelligence</p>
          <h1>{detail.device.name}</h1>
          <small>
            {detail.device.device_identifier} · {detail.device.device_type}
          </small>
        </div>
        <Link className="ghost-btn inline-btn" to="/dashboard">
          Back
        </Link>
      </div>

      <div className="detail-grid">
        <article className="panel">
          <header>
            <h3>Device Profile</h3>
          </header>
          <div className="metadata-grid">
            <p>
              Status <strong>{detail.device.status}</strong>
            </p>
            <p>
              Manufacturer <strong>{detail.device.manufacturer || "Unknown"}</strong>
            </p>
            <p>
              Model <strong>{detail.device.model || "N/A"}</strong>
            </p>
            <p>
              Firmware <strong>{detail.device.firmware_version || "N/A"}</strong>
            </p>
            <p>
              Location <strong>{detail.device.location || "N/A"}</strong>
            </p>
            <p>
              Last Auth <strong>{detail.device.last_authenticated_at || "N/A"}</strong>
            </p>
          </div>
        </article>

        <TelemetryChart
          data={chartData}
          title="Telemetry timeline"
          metricName={chartData.at(-1)?.metric}
        />
      </div>

      <article className="panel">
        <header>
          <h3>Active Alerts</h3>
          <span>{detail.active_alerts.length} open/acknowledged</span>
        </header>
        <ul className="incident-list">
          {detail.active_alerts.map((alert) => (
            <li key={alert.id}>
              <div>
                <p>Device: {alert.device_name}</p>
                <h4>{alert.title}</h4>
                <small>{alert.triggered_at}</small>
              </div>
              <strong className={`pill ${alert.severity.toLowerCase()}`}>{alert.severity}</strong>
            </li>
          ))}
        </ul>
      </article>
    </section>
  );
};

export default DeviceDetail;
