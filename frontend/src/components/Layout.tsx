import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

const ITENS = [
  { para: "/", rotulo: "Painel", exato: true },
  { para: "/planta", rotulo: "Planta" },
  { para: "/alertas", rotulo: "Alertas" },
  { para: "/coleta", rotulo: "Coletar" },
  { para: "/cadastro", rotulo: "Cadastro" },
];

export default function Layout() {
  const { usuario, sair } = useAuth();

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header
        style={{
          borderBottom: "1px solid var(--border)",
          background: "var(--bg-elev)",
          position: "sticky",
          top: 0,
          zIndex: 10,
        }}
      >
        <div
          className="cabecalho-conteudo"
          style={{
            maxWidth: 1200,
            margin: "0 auto",
            padding: "0.7rem 1.1rem",
            display: "flex",
            alignItems: "center",
            gap: "1.5rem",
            flexWrap: "wrap",
          }}
        >
          <strong style={{ letterSpacing: "-0.02em" }}>Predição de Falhas</strong>

          <nav className="linha cabecalho-nav" style={{ gap: "0.3rem", flex: 1 }}>
            {ITENS.map((i) => (
              <NavLink
                key={i.para}
                to={i.para}
                end={i.exato}
                style={({ isActive }) => ({
                  padding: "0.4rem 0.8rem",
                  borderRadius: "var(--radius-sm)",
                  color: isActive ? "var(--text)" : "var(--text-dim)",
                  background: isActive ? "var(--bg-elev-2)" : "transparent",
                  textDecoration: "none",
                  fontWeight: isActive ? 600 : 400,
                  fontSize: "0.9rem",
                })}
              >
                {i.rotulo}
              </NavLink>
            ))}
          </nav>

          <div className="linha" style={{ gap: "0.8rem" }}>
            <span className="faint so-desktop">{usuario?.name}</span>
            <button className="secundario" onClick={sair} style={{ padding: "0.35rem 0.8rem" }}>
              Sair
            </button>
          </div>
        </div>
      </header>

      <main style={{ flex: 1, maxWidth: 1200, width: "100%", margin: "0 auto", padding: "1.4rem 1.1rem" }}>
        <Outlet />
      </main>
    </div>
  );
}
