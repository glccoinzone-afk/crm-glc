import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("glc_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      localStorage.removeItem("glc_token");
      localStorage.removeItem("glc_user");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

export default api;

export const VERTICALS = [
  { key: "ALL", name: "All Verticals", tag: "GLC" },
  { key: "GLC Fresh", name: "GLC Fresh", tag: "Fresh" },
  { key: "GLC Store", name: "GLC Store", tag: "Store" },
  { key: "GLC Garden", name: "GLC Garden", tag: "Garden" },
  { key: "GLC Hardwares", name: "GLC Hardwares", tag: "Hardware" },
  { key: "Dhani Jewellers", name: "Dhani Jewellers", tag: "Dhani" },
  { key: "India Mandi", name: "India Mandi", tag: "Mandi" },
  { key: "GLC Property", name: "GLC Property", tag: "Property" },
  { key: "GLC Legal", name: "GLC Legal", tag: "Legal" },
];

export const fmtInr = (n) => {
  if (n === null || n === undefined || isNaN(n)) return "₹0";
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
};

export const fmtNum = (n) => Number(n || 0).toLocaleString("en-IN");

export const fmtDate = (iso) => {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
  } catch {
    return iso;
  }
};
