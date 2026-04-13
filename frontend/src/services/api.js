import axios from "axios";

export const AUTH_TOKEN_STORAGE_KEY = "iomt_auth_token";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

let authToken = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);

export const setAuthToken = (token) => {
  authToken = token;
};

const API = axios.create({
  baseURL,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});

API.interceptors.request.use((config) => {
  if (authToken) {
    config.headers.Authorization = `Bearer ${authToken}`;
  }

  return config;
});

export default API;
