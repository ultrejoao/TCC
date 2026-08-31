import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { put } from "../api/client";
import { ROTULO_REGRA, type Alert, type Page } from "../api/types";
import {
  Carregando,
  Erro,
  SeloCriticidade,
  SeloEvidencia,
  Vazio,
  dataHora,
} from "../components/ui";
import { useApi } from "../hooks/useApi";

export default function Alertas() {
  const [params, setParams] = useSearchParams();
  const soDivergencia = params.get("divergencia") === "1";
  const [salvando, setSalvando] = useState<string | null>(null);

  const caminho =
    `/alerts?status=OPEN&limit=100` + (soDivergencia ? "&only_divergence=true" : "");
  const { dados, carregando, erro, recarregar } = useApi<Page<Alert>>(caminho);

  async function tratar(id: string, status: string) {
    setSalvando(id);
    try {
      await put(`/alerts/${id}`, { status });
      recarregar();
    } finally {
      setSalvando(null);
    }
  }

  return (
    <div className="pilha">
      <div className="linha" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
        <div>
          <h1>Alertas abertos</h1>
          <p className="faint" style={{ margin: "0.2rem 0 0" }}>
            Ordenados por prioridade: severidade × criticidade do motor × agravamento.
          </p>
        </div>
        <button
          className="secundario"
          onClick={() => {
            const novo = new URLSearchParams(params);
            if (soDivergencia) novo.delete("divergencia");
            else novo.set("divergencia", "1");
            setParams(novo);
          }}
        >
          {soDivergencia ? "Mostrar todos" : "Só divergências"}
        </button>
      </div>

      {carregando && <Carregando linhas={4} />}
      {erro && <Erro>{erro.detail}</Erro>}

      {dados && dados.items.length === 0 && (
        <Vazio>
          {soDivergencia
            ? "Nenhum alerta por divergência de evidências."
            : "Nenhum alerta aberto."}
        </Vazio>
      )}

      {dados?.items.map((a) => (
        <section
          key={a.id}
          className="cartao"
          style={{
            borderLeft: `4px solid var(--${a.severity === "FAILURE" ? "failure" : "warning"})`,
          }}
        >
          <div className="linha" style={{ gap: "0.7rem", flexWrap: "wrap" }}>
            <Link to={`/motores/${a.motor_id}`}>
              <strong>{a.motor_tag}</strong>
            </Link>
            {a.criticality && <SeloCriticidade valor={a.criticality} />}
            <span className={`selo ${a.severity}`}>{ROTULO_REGRA[a.rule] ?? a.rule}</span>
            <SeloEvidencia concorda={a.evidence_agreement} tipoFisico={a.physical_type} />
            <span className="mono faint" style={{ marginLeft: "auto" }}>
              prioridade {a.priority_score.toFixed(0)}
            </span>
          </div>

          <div className="faint" style={{ marginTop: "0.25rem" }}>
            {[a.plant_name, a.area_name, a.line_name].filter(Boolean).join(" › ")}
          </div>

          <p style={{ margin: "0.55rem 0" }}>{a.message}</p>

          {a.reasons.length > 0 && (
            <ul className="faint" style={{ margin: "0.3rem 0", paddingLeft: "1.1rem" }}>
              {a.reasons.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          )}

          <div className="linha" style={{ gap: "0.5rem", marginTop: "0.7rem", flexWrap: "wrap" }}>
            <button
              className="secundario"
              disabled={salvando === a.id}
              onClick={() => tratar(a.id, "ACKNOWLEDGED")}
              style={{ padding: "0.3rem 0.75rem", fontSize: "0.85rem" }}
            >
              Reconhecer
            </button>
            <button
              className="secundario"
              disabled={salvando === a.id}
              onClick={() => tratar(a.id, "RESOLVED")}
              style={{ padding: "0.3rem 0.75rem", fontSize: "0.85rem" }}
            >
              Resolver
            </button>
            <span className="faint">{dataHora(a.created_at)}</span>
          </div>
        </section>
      ))}
    </div>
  );
}
