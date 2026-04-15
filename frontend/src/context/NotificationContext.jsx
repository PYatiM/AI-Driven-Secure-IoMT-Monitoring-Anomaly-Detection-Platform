import { useCallback, useMemo, useState } from "react";

import { NotificationContext } from "./notification-context";

export const NotificationProvider = ({ children }) => {
  const [notifications, setNotifications] = useState([]);

  const removeNotification = useCallback((id) => {
    setNotifications((current) => current.filter((item) => item.id !== id));
  }, []);

  const pushNotification = useCallback(
    ({ title, message, type = "info", ttlMs = 4500 }) => {
      const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      setNotifications((current) => [
        ...current,
        {
          id,
          title,
          message,
          type,
        },
      ]);

      const timeoutId = window.setTimeout(() => {
        removeNotification(id);
      }, ttlMs);

      return () => window.clearTimeout(timeoutId);
    },
    [removeNotification]
  );

  const value = useMemo(
    () => ({
      notifications,
      pushNotification,
      removeNotification,
    }),
    [notifications, pushNotification, removeNotification]
  );

  return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>;
};
