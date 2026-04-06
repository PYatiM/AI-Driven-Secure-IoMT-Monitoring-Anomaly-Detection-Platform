import Sidebar from "../components/layout/Sidebar";
import Navbar from "../components/layout/navbar";

const Dashboard = () => {
  return (
    <div style={{ display: "flex" }}>
      <Sidebar />

      <div style={{ flex: 1 }}>
        <Navbar />

        <div style={{ padding: "1rem" }}>
          <h2>Overview</h2>

          <div style={{ display: "flex", gap: "1rem" }}>
            <div style={{ border: "1px solid #ccc", padding: "1rem" }}>
              <h3>Devices</h3>
              <p>12 Active</p>
            </div>

            <div style={{ border: "1px solid #ccc", padding: "1rem" }}>
              <h3>Anomalies</h3>
              <p>5 Detected</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;