import { useNotifications } from "../../context/useNotifications";

const NotificationCenter = () => {
  const { notifications, removeNotification } = useNotifications();

  if (!notifications.length) {
    return null;
  }

  return (
    <div className="notification-center" aria-live="polite">
      {notifications.map((item) => (
        <article key={item.id} className={`toast ${item.type}`}>
          <div>
            <h4>{item.title}</h4>
            {item.message ? <p>{item.message}</p> : null}
          </div>
          <button
            type="button"
            onClick={() => removeNotification(item.id)}
            aria-label="Dismiss notification"
          >
            x
          </button>
        </article>
      ))}
    </div>
  );
};

export default NotificationCenter;
