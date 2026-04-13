const Sidebar = () => {
  const links = [
    { label: "Dashboard", badge: "Live" },
    { label: "Devices", badge: "128" },
    { label: "Alerts", badge: "12" },
    { label: "Threat Intel", badge: "New" },
  ];

  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <div>
        <p className="sidebar-tag">Secure IoMT Grid</p>
        <h1>PulseGuard</h1>
      </div>

      <nav>
        <ul className="sidebar-links">
          {links.map((item, index) => (
            <li key={item.label} className={index === 0 ? "active" : ""}>
              <span>{item.label}</span>
              <strong>{item.badge}</strong>
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
