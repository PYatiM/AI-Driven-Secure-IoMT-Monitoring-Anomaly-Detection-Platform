import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import NotificationCenter from "./components/common/NotificationCenter";
import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { NotificationProvider } from "./context/NotificationContext";
import { ThemeProvider } from "./context/ThemeContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <ThemeProvider>
    <NotificationProvider>
      <AuthProvider>
        <BrowserRouter>
          <App />
          <NotificationCenter />
        </BrowserRouter>
      </AuthProvider>
    </NotificationProvider>
  </ThemeProvider>
);
