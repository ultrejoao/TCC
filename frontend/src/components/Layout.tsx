/**
 * Moldura da aplicação.
 *
 * A navegação tem sete destinos, e sete itens lado a lado viram uma fileira
 * indiferenciada onde nada é encontrado rápido. Por isso vêm em dois grupos
 * separados por um divisor: o que se usa **no turno** (painel, planta, alertas,
 * coleta) e o que se usa **de vez em quando** (cadastro, modelos, auditoria).
 * O agrupamento é a informação — diz com que frequência cada tela é aberta.
 */

import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

const OPERACAO = [
  { para: "/", rotulo: "Painel", exato: true },
  { para: "/planta", rotulo: "Planta" },
  { para: "/alertas", rotulo: "Alertas" },
  { para: "/coleta", rotulo: "Coletar" },
];

const ADMINISTRACAO = [
  { para: "/cadastro", rotulo: "Cadastro" },
  { para: "/modelos", rotulo: "Modelos" },
  { para: "/auditoria", rotulo: "Auditoria" },
];

function Item({
  para,
  rotulo,
  exato,
}: {
  para: string;
  rotulo: string;
  exato?: boolean;
}) {
  return (
    <NavLink
      to={para}
      end={exato}
      style={({ isActive }) => ({
        padding: "0.35rem 0.7rem",
        borderRadius: "var(--radius-sm)",
        color: isActive ? "var(--text)" : "var(--text-dim)",
        background: isActive ? "var(--bg-elev-2)" : "transparent",
        textDecoration: "none",
        fontWeight: isActive ? 600 : 450,
        fontSize: "0.875rem",
        whiteSpace: "nowrap",
      })}
    >
      {rotulo}
    </NavLink>
  );
}

export default function Layout() {
  const { usuario, sair } = useAuth();

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header
        style={{
          borderBottom: "1px solid var(--border)",
          background: "rgba(16, 18, 20, 0.85)",
          backdropFilter: "blur(10px)",
          position: "sticky",
          top: 0,
          zIndex: 10,
        }}
      >
        <div
          className="cabecalho-conteudo"
          style={{
            maxWidth: 1240,
            margin: "0 auto",
            padding: "0.65rem 1.2rem",
            display: "flex",
            alignItems: "center",
            gap: "1.4rem",
            flexWrap: "wrap",
          }}
        >
          {/* Marca: o ponto verde é o estado do próprio sistema, não decoração —
              se a interface está desenhada, a API respondeu. */}
          <div className="linha" style={{ gap: "0.5rem" }}>
            <span className="ponto HEALTHY" aria-hidden="true" />
            <strong style={{ letterSpacing: "-0.03em", fontSize: "0.98rem" }}>
              Predição de Falhas
            </strong>
          </div>

          <nav className="linha cabecalho-nav" style={{ gap: "0.15rem", flex: 1 }}>
            {OPERACAO.map((i) => (
              <Item key={i.para} {...i} />
            ))}

            <span
              aria-hidden="true"
              style={{
                width: 1,
                height: 18,
                background: "var(--border-forte)",
                margin: "0 0.5rem",
                flexShrink: 0,
              }}
            />

            {ADMINISTRACAO.map((i) => (
              <Item key={i.para} {...i} />
            ))}
          </nav>

          <div className="linha" style={{ gap: "0.8rem" }}>
            <span className="faint so-desktop">{usuario?.name}</span>
            <button
              className="secundario"
              onClick={sair}
              style={{ padding: "0.3rem 0.75rem", fontSize: "0.85rem" }}
            >
              Sair
            </button>
          </div>
        </div>
      </header>

      <main
        style={{
          flex: 1,
          maxWidth: 1240,
          width: "100%",
          margin: "0 auto",
          padding: "1.6rem 1.2rem 4rem",
        }}
      >
        <Outlet />
      </main>
    </div>
  );
}
