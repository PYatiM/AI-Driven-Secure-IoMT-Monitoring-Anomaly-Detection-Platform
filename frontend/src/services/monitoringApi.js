import API, { AUTH_TOKEN_STORAGE_KEY } from "./api";

const MONITORING_PREFIX = "/api/v1/monitoring";

export const listDevices = async (params = {}) => {
  const response = await API.get(`${MONITORING_PREFIX}/devices`, { params });
  return response.data;
};

export const getDeviceDetail = async (deviceId) => {
  const response = await API.get(`${MONITORING_PREFIX}/devices/${deviceId}`);
  return response.data;
};

export const getDeviceTelemetry = async (deviceId, params = {}) => {
  const response = await API.get(`${MONITORING_PREFIX}/devices/${deviceId}/telemetry`, {
    params,
  });
  return response.data;
};

export const listAlerts = async (params = {}) => {
  const response = await API.get(`${MONITORING_PREFIX}/alerts`, { params });
  return response.data;
};

const resolveWsBaseUrl = () => {
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
  if (apiBase.startsWith("https://")) {
    return apiBase.replace("https://", "wss://");
  }
  if (apiBase.startsWith("http://")) {
    return apiBase.replace("http://", "ws://");
  }
  return `ws://${apiBase}`;
};

export const connectMonitoringSocket = (callbacks = {}) => {
  const token = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
  if (!token) {
    return null;
  }

  const wsBase = resolveWsBaseUrl();
  const socket = new WebSocket(
    `${wsBase}${MONITORING_PREFIX}/ws?token=${encodeURIComponent(token)}`
  );

  socket.onopen = () => {
    callbacks.onOpen?.();
  };

  socket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      callbacks.onMessage?.(payload);
    } catch {
      callbacks.onError?.(new Error("Unable to parse monitoring socket payload."));
    }
  };

  socket.onerror = () => {
    callbacks.onError?.(new Error("Monitoring socket encountered an error."));
  };

  socket.onclose = () => {
    callbacks.onClose?.();
  };

  return socket;
};

