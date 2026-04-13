const Navbar = ({ user, onLogout }) => {
  const displayName = user?.full_name || "Security Operator";
  const roleLabel = user?.role || "analyst";

  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">AI-Driven Monitoring</p>
        <h2>Operational Command Dashboard</h2>
      </div>

      <div className="topbar-actions">
        <div className="user-chip" title={displayName}>
          <span>{displayName}</span>
          <small>{roleLabel}</small>
        </div>
        <button type="button" onClick={onLogout} className="ghost-btn">
          Sign out
        </button>
      </div>
    </header>
  );
};

export default Navbar;
