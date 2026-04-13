import { useNavigate } from "react-router-dom";

import Navbar from "../components/layout/Navbar";
import Sidebar from "../components/layout/Sidebar";
import { useAuth } from "../context/useAuth";

const summaryCards = [
  { label: "Online Devices", value: "128", trend: "+3.2%" },
  { label: "Critical Alerts", value: "04", trend: "-1 from last hour" },
  { label: "Anomaly Rate", value: "2.8%", trend: "Within safe baseline" },
  { label: "Avg Response", value: "14s", trend: "Automated pipeline active" },
];

const activeIncidents = [
  {
    id: "INC-4211",
    title: "Infusion pump traffic spike",
    severity: "Critical",
    zone: "Ward-A / Network-3",
  },
  {
    id: "INC-4209",
    title: "Unexpected firmware handshake",
    severity: "High",
    zone: "Imaging / VLAN-9",
  },
  {
    id: "INC-4204",
    title: "Abnormal telemetry drift",
    severity: "Medium",
    zone: "ICU / Bed Cluster 2",
  },
];

const Dashboard = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="dashboard-shell">
      <Sidebar />

      <main className="dashboard-main">
        <Navbar user={user} onLogout={handleLogout} />

        <section className="metrics-grid" aria-label="Key platform metrics">
          {summaryCards.map((card) => (
            <article key={card.label} className="metric-card">
              <p>{card.label}</p>
              <h3>{card.value}</h3>
              <small>{card.trend}</small>
            </article>
          ))}
        </section>

        <section className="dashboard-panels">
          <article className="panel">
            <header>
              <h3>Live Security Incidents</h3>
              <span>Updated now</span>
            </header>
            <ul className="incident-list">
              {activeIncidents.map((incident) => (
                <li key={incident.id}>
                  <div>
                    <p>{incident.id}</p>
                    <h4>{incident.title}</h4>
                    <small>{incident.zone}</small>
                  </div>
                  <strong className={`pill ${incident.severity.toLowerCase()}`}>
                    {incident.severity}
                  </strong>
                </li>
              ))}
            </ul>
          </article>

          <article className="panel">
            <header>
              <h3>Threat Posture</h3>
            </header>
            <div className="posture-card">
              <p>Detection confidence</p>
              <h4>96.4%</h4>
              <small>Isolation Forest + One-Class SVM ensemble</small>
            </div>
            <div className="posture-card">
              <p>Escalated critical anomalies</p>
              <h4>2 pending triage</h4>
              <small>Auto-escalation and audit trace active</small>
            </div>
          </article>
        </section>
      </main>
    </div>
  );
};

export default Dashboard;

