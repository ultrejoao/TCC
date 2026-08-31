/**
 * Arvore de componentes da fabrica.
 *
 * Os contadores de alerta sobem na hierarquia: o problema de um motor aparece
 * na linha, na area e na planta. Assim o tecnico localiza onde esta a
 * ocorrencia sem abrir no por no.
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import type { TreeArea, TreeLine, TreePlant } from "../api/types";
import {
  Carregando,
  Erro,
  SeloCriticidade,
  SeloSeveridade,
  Vazio,
} from "../components/ui";
import { useApi } from "../hooks/useApi";

function Contagem({ n }: { n: number }) {
  if (n === 0) return null;
  return (
    <span
      className="selo FAILURE"
      title={`${n} ${n === 1 ? "alerta aberto" : "alertas abertos"}`}
    >
      {n}
    </span>
  );
}

function Seta({ aberto }: { aberto: boolean }) {
  return (
    <span
      className="dim"
      style={{
        display: "inline-block",
        transform: aberto ? "rotate(90deg)" : "none",
        transition: "transform 0.15s",
        width: 12,
      }}
    >
      ▸
    </span>
  );
}

function NoLinha({ linha }: { linha: TreeLine }) {
  const [aberto, setAberto] = useState(true);
  return (
    <div className="arvore-no" style={{ marginLeft: "1.3rem" }}>
      <button
        className="secundario"
        onClick={() => setAberto(!aberto)}
        style={{
          background: "transparent",
          padding: "0.35rem 0",
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          width: "100%",
          justifyContent: "flex-start",
          color: "var(--text)",
        }}
      >
        <Seta aberto={aberto} />
        <span className="mono dim">{linha.code}</span>
        <span>{linha.name}</span>
        <span className="faint">
          ({linha.motors.length} {linha.motors.length === 1 ? "motor" : "motores"})
        </span>
        <Contagem n={linha.open_alerts} />
      </button>

      {aberto && (
        <div className="arvore-no" style={{ marginLeft: "1.6rem", marginBottom: "0.4rem" }}>
          {linha.motors.length === 0 ? (
            <div className="faint" style={{ padding: "0.3rem 0" }}>
              nenhum motor cadastrado nesta linha
            </div>
          ) : (
            <table className="arvore-motores">
              <tbody>
                {linha.motors.map((m) => (
                  <tr key={m.id}>
                    <td style={{ width: 130 }}>
                      <Link to={`/motores/${m.id}`}>
                        <strong>{m.tag}</strong>
                      </Link>
                    </td>
                    <td className="dim">{m.name}</td>
                    <td style={{ width: 44 }}>
                      <SeloCriticidade valor={m.criticality} />
                    </td>
                    <td style={{ width: 120 }}>
                      <SeloSeveridade valor={m.last_severity} />
                    </td>
                    <td style={{ width: 90 }} className="mono faint">
                      {m.max_priority > 0 && `prior. ${m.max_priority.toFixed(0)}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

function NoArea({ area }: { area: TreeArea }) {
  const [aberto, setAberto] = useState(true);
  return (
    <div className="arvore-no" style={{ marginLeft: "1.1rem" }}>
      <button
        onClick={() => setAberto(!aberto)}
        style={{
          background: "transparent",
          padding: "0.4rem 0",
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          color: "var(--text)",
          fontWeight: 600,
        }}
      >
        <Seta aberto={aberto} />
        <span className="mono dim">{area.code}</span>
        <span>{area.name}</span>
        <Contagem n={area.open_alerts} />
      </button>
      {aberto && area.lines.map((l) => <NoLinha key={l.id} linha={l} />)}
    </div>
  );
}

function NoPlanta({ planta }: { planta: TreePlant }) {
  const [aberto, setAberto] = useState(true);
  return (
    <section className="cartao">
      <button
        onClick={() => setAberto(!aberto)}
        style={{
          background: "transparent",
          padding: 0,
          display: "flex",
          alignItems: "center",
          gap: "0.6rem",
          color: "var(--text)",
          marginBottom: aberto ? "0.6rem" : 0,
        }}
      >
        <Seta aberto={aberto} />
        <h2>{planta.name}</h2>
        <span className="mono faint">{planta.code}</span>
        <Contagem n={planta.open_alerts} />
      </button>

      <div className="faint" style={{ marginLeft: "1.7rem", marginBottom: "0.5rem" }}>
        {planta.location && `${planta.location} · `}
        {planta.motor_count} {planta.motor_count === 1 ? "motor" : "motores"}
      </div>

      {aberto &&
        (planta.areas.length === 0 ? (
          <div className="faint" style={{ marginLeft: "1.7rem" }}>
            nenhuma área cadastrada
          </div>
        ) : (
          planta.areas.map((a) => <NoArea key={a.id} area={a} />)
        ))}
    </section>
  );
}

export default function Planta() {
  const { dados, carregando, erro } = useApi<TreePlant[]>("/tree");

  if (carregando) return <Carregando linhas={5} />;
  if (erro) return <Erro>{erro.detail}</Erro>;

  return (
    <div className="pilha">
      <div>
        <h1>Componentes da fábrica</h1>
        <p className="faint" style={{ margin: "0.2rem 0 0" }}>
          Planta › Área › Linha › Motor. Os alertas somam de baixo para cima.
        </p>
      </div>

      {!dados || dados.length === 0 ? (
        <Vazio>
          Nenhuma planta cadastrada ainda.
          <div className="faint" style={{ marginTop: "0.6rem" }}>
            A estrutura da fábrica é criada pelos endpoints{" "}
            <span className="mono">/plants</span>,{" "}
            <span className="mono">/areas</span> e{" "}
            <span className="mono">/lines</span>.
          </div>
        </Vazio>
      ) : (
        dados.map((p) => <NoPlanta key={p.id} planta={p} />)
      )}
    </div>
  );
}
