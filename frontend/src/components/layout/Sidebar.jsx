import { NavLink } from "react-router-dom";

const Sidebar = ({ devicesCount }) => {
  const links = [
    { label: "Dashboard", to: "/dashboard", badge: "Live" },
    { label: "Devices", to: "/dashboard#devices", badge: String(devicesCount ?? 0) },
    { label: "Alerts", to: "/dashboard#alerts", badge: "Feed" },
    { label: "Threat Intel", to: "/dashboard#intel", badge: "AI" },
  ];

  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <div>
        <p className="sidebar-tag">Secure IoMT Grid</p>
        <h1>PulseGuard</h1>
      </div>

      <nav>
        <ul className="sidebar-links">
          {links.map((item) => (
            <li key={item.label}>
              <NavLink
                to={item.to}
                className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
              >
                <span>{item.label}</span>
                <strong>{item.badge}</strong>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="sidebar-note">
        <p>Network posture</p>
        <h2>Stable</h2>
        <small>All hospital zones encrypted</small>
      </div>
    </aside>
  );
};

export default Sidebar;
