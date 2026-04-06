import { useState, useContext } from "react";
import { AuthContext } from "../context/AuthContext";
import API from "../services/api";

const Login = () => {
  const { login } = useContext(AuthContext);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleLogin = async (e) => {
    e.preventDefault();

    try {
      const res = await API.post("/login", { email, password });

      login(res.data.access_token);
      window.location.href = "/dashboard";
    } catch (err) {
      alert("Login failed");
    }
  };

  return (
    <div style={{ padding: "2rem" }}>
      <h2>IoMT Platform Login</h2>

      <form onSubmit={handleLogin}>
        <input
          type="email"
          placeholder="Email"
          onChange={(e) => setEmail(e.target.value)}
        />
        <br />

        <input
          type="password"
          placeholder="Password"
          onChange={(e) => setPassword(e.target.value)}
        />
        <br />

        <button type="submit">Login</button>
      </form>
    </div>
  );
};

export default Login;