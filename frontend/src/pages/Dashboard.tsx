/**
 * Painel inicial.
 *
 * A pergunta que esta tela responde e "o que precisa de atencao agora?". Por
 * isso a fila de prioridade ocupa o centro, e os totais ficam como contexto
 * acima dela. Totais dizem como a planta esta; a fila diz o que fazer a seguir.
 */

import { Link } from "react-router-dom";
import { ROTULO_REGRA, type Dashboard as TDashboard } from "../api/types";
import {
  BarraConfianca,
  Carregando,
  Erro,
  NomeFalha,
  SeloCriticidade,
  SeloEvidencia,
  SeloSeveridade,
  Vazio,
  dataHora,
} from "../components/ui";
import { useApi } from "../hooks/useApi";

function Contador({
  rotulo,
  valor,
  cor,
}: {
  rotulo: string;
  valor: number;
  cor?: string;
}) {
  return (
    <div className="cartao" style={{ padding: "0.9rem 1.1rem" }}>
      <div style={{ fontSize: "1.75rem", fontWeight: 700, color: cor, lineHeight: 1.1 }}>
        {valor}
      </div>
      <div className="faint">{rotulo}</div>
    </div>
  );
}

export default function Dashboard() {
  const { dados, carregando, erro } = useApi<TDashboard>("/dashboard?top=10");

  if (carregando) return <Carregando linhas={6} />;
  if (erro) return <Erro>{erro.detail}</Erro>;
  if (!dados) return null;

  const c = dados.severity_counts;

  return (
    <div className="pilha">
      <div>
        <h1>Visão geral da planta</h1>
        <p className="faint" style={{ margin: "0.2rem 0 0" }}>
          {dados.monitored_motors} de {dados.total_motors} motores com medição ·{" "}
          {dados.measurements_last_7d} coletas nos últimos 7 dias
        </p>
      </div>

      <div
        className="grade"
        style={{ gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))" }}
      >
        <Contador rotulo="Saudáveis" valor={c.healthy} cor="var(--healthy)" />
        <Contador rotulo="Em atenção" valor={c.warning} cor="var(--warning)" />
        <Contador rotulo="Com falha" valor={c.failure} cor="var(--failure)" />
        <Contador rotulo="Sem medição" valor={c.unmeasured} cor="var(--text-faint)" />
        <Contador rotulo="Alertas abertos" valor={dados.open_alerts} />
      </div>

      {dados.divergence_alerts > 0 && (
        <div className="aviso atencao">
          <strong>
            {dados.divergence_alerts}{" "}
            {dados.divergence_alerts === 1 ? "alerta" : "alertas"} por divergência
            de evidências.
          </strong>{" "}
          Nesses casos o modelo e a assinatura física apontam condições
          diferentes — o diagnóstico é menos confiável e a inspeção tem
          prioridade.{" "}
          <Link to="/alertas?divergencia=1">Ver quais</Link>
        </div>
      )}

      <section className="cartao">
        <div
          className="linha"
          style={{ justifyContent: "space-between", marginBottom: "0.9rem" }}
        >
          <h2>Motores que exigem atenção</h2>
          <Link to="/alertas" className="faint">
            todos os alertas →
          </Link>
        </div>

        {dados.critical_motors.length === 0 ? (
          <Vazio>Nenhum alerta aberto. Todos os motores medidos estão em condição normal.</Vazio>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="responsiva">
              <thead>
                <tr>
                  <th style={{ width: 34 }}>#</th>
                  <th>Motor</th>
                  <th>Local</th>
                  <th style={{ width: 44 }}>Crit.</th>
                  <th>Condição</th>
                  <th>Tipo</th>
                  <th style={{ width: 150 }}>Confiança</th>
                  <th style={{ width: 80 }}>Prioridade</th>
                </tr>
              </thead>
              <tbody>
                {dados.critical_motors.map((m, i) => (
                  <tr key={m.motor_id}>
                    <td data-rotulo="" className="faint">{i + 1}</td>
                    <td data-rotulo="Motor" className="bloco">
                      <Link to={`/motores/${m.motor_id}`}>
                        <strong>{m.tag}</strong>
                      </Link>
                      <div className="faint">{m.name}</div>
                      {m.top_rule && (
                        <div className="faint" style={{ marginTop: 2 }}>
                          {ROTULO_REGRA[m.top_rule] ?? m.top_rule}
                        </div>
                      )}
                    </td>
                    <td data-rotulo="Local" className="faint bloco">
                      {m.area_name && <div>{m.area_name}</div>}
                      {m.line_name}
                    </td>
                    <td data-rotulo="Criticidade">
                      <SeloCriticidade valor={m.criticality} />
                    </td>
                    <td data-rotulo="Condição" className="bloco">
                      <SeloSeveridade valor={m.severity} />
                      {m.trend_pct !== null && m.trend_pct > 20 && (
                        <div
                          className="faint"
                          style={{ color: "var(--warning)", marginTop: 3 }}
                        >
                          ↑ {m.trend_pct.toFixed(0)}% vs anterior
                        </div>
                      )}
                    </td>
                    <td data-rotulo="Tipo" className="bloco">
                      <NomeFalha valor={m.fault_type} />
                      <div style={{ marginTop: 3 }}>
                        <SeloEvidencia
                          concorda={m.evidence_agreement}
                          tipoFisico={m.physical_type}
                        />
                      </div>
                    </td>
                    <td data-rotulo="Confiança">
                      {m.confidence !== null && <BarraConfianca valor={m.confidence} />}
                    </td>
                    <td data-rotulo="Prioridade">
                      <span
                        className="mono"
                        style={{
                          fontWeight: 700,
                          color:
                            m.priority_score >= 100
                              ? "var(--failure)"
                              : "var(--warning)",
                        }}
                      >
                        {m.priority_score.toFixed(0)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {dados.recent_alerts.length > 0 && (
        <section className="cartao">
          <h2 style={{ marginBottom: "0.8rem" }}>Alertas recentes</h2>
          <div className="pilha" style={{ gap: "0.6rem" }}>
            {dados.recent_alerts.slice(0, 5).map((a) => (
              <div
                key={a.id}
                className="linha"
                style={{ alignItems: "flex-start", gap: "0.7rem" }}
              >
                <span className={`ponto ${a.severity}`} style={{ marginTop: 7 }} />
                <div style={{ flex: 1 }}>
                  <Link to={`/motores/${a.motor_id}`}>
                    <strong>{a.motor_tag}</strong>
                  </Link>{" "}
                  <span className="faint">{ROTULO_REGRA[a.rule] ?? a.rule}</span>
                  <div className="faint">{dataHora(a.created_at)}</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
