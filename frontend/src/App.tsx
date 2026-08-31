import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import Alertas from "./pages/Alertas";
import Coleta from "./pages/Coleta";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import Motor from "./pages/Motor";
import Planta from "./pages/Planta";

function Rotas() {
  const { usuario, carregando } = useAuth();

  if (carregando) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
        <span className="dim">carregando…</span>
      </div>
    );
  }

  if (!usuario) return <Login />;

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/planta" element={<Planta />} />
        <Route path="/alertas" element={<Alertas />} />
        <Route path="/coleta" element={<Coleta />} />
        <Route path="/motores/:id" element={<Motor />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Rotas />
      </AuthProvider>
    </BrowserRouter>
  );
}
