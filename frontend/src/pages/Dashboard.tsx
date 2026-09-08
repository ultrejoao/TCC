/**
 * Painel inicial.
 *
 * A pergunta que esta tela responde é "o que precisa de atenção agora?".
 *
 * Duas decisões de apresentação, ambas contra a versão anterior:
 *
 * 1. **A composição da planta é uma barra, não cinco contadores.** Cinco caixas
 *    iguais dizem quantos motores há em cada condição; nenhuma diz a proporção,
 *    que é a leitura útil. Dois motores com falha em quarenta é uma planta
 *    saudável com um problema; dois em quatro é uma planta em colapso. A barra
 *    mostra a diferença antes de qualquer número ser lido.
 *
 * 2. **A fila de inspeção é uma lista, não uma tabela.** Tabela serve para
 *    comparar valores célula a célula. Uma fila de triagem é varrida de cima
 *    para baixo e acionada — e oito colunas com sub-rótulos dentro das células
 *    tornavam essa varredura lenta justamente na tela onde ela precisa ser
 *    instantânea.
 */

import { Link } from "react-router-dom";
import {
  ROTULO_REGRA,
  type Dashboard as TDashboard,
  type Severity,
} from "../api/types";
import {
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

const FAIXAS: { chave: keyof Composicao; classe: string; rotulo: string }[] = [
  { chave: "failure", classe: "FAILURE", rotulo: "com falha" },
  { chave: "warning", classe: "WARNING", rotulo: "em atenção" },
  { chave: "healthy", classe: "HEALTHY", rotulo: "saudáveis" },
  { chave: "unmeasured", classe: "neutro", rotulo: "sem medição" },
];

interface Composicao {
  healthy: number;
  warning: number;
  failure: number;
  unmeasured: number;
}

/** A planta inteira numa peça: proporção acima, contagem como legenda. */
function ComposicaoDaPlanta({ c }: { c: Composicao }) {
  const total = c.healthy + c.warning + c.failure + c.unmeasured;
  if (total === 0) return null;

  return (
    <section className="cartao">
      <div className="rotulo" style={{ marginBottom: "0.7rem" }}>
        Composição da planta
      </div>

      <div className="proporcao" role="img" aria-label={
        FAIXAS.map((f) => `${c[f.chave]} ${f.rotulo}`).join(", ")
      }>
        {FAIXAS.map((f) =>
          c[f.chave] > 0 ? (
            <span
              key={f.chave}
              className={f.classe}
              style={{ width: `${(c[f.chave] / total) * 100}%` }}
            />
          ) : null,
        )}
      </div>

      <div
        className="linha"
        style={{ gap: "1.6rem", flexWrap: "wrap", marginTop: "0.9rem" }}
      >
        {FAIXAS.map((f) => (
          <div key={f.chave} className="linha" style={{ gap: "0.5rem" }}>
            <span className={`ponto ${f.classe}`} />
            <span className="medida" style={{ fontSize: "1.2rem" }}>
              {c[f.chave]}
            </span>
            <span className="faint">{f.rotulo}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function Dashboard() {
  const { dados, carregando, erro } = useApi<TDashboard>("/dashboard?top=10");

  if (carregando) return <Carregando linhas={6} />;
  if (erro) return <Erro>{erro.detail}</Erro>;
  if (!dados) return null;

  const c = dados.severity_counts;
  const fila = dados.critical_motors;

  return (
    <div className="pilha" style={{ gap: "1.3rem" }}>
      <div>
        <h1>Visão geral da planta</h1>
        <p className="faint" style={{ margin: "0.25rem 0 0" }}>
          {dados.monitored_motors} de {dados.total_motors} motores com medição ·{" "}
          {dados.measurements_last_7d} coletas nos últimos 7 dias ·{" "}
          {dados.open_alerts} {dados.open_alerts === 1 ? "alerta aberto" : "alertas abertos"}
        </p>
      </div>

      <ComposicaoDaPlanta c={c} />

      {dados.divergence_alerts > 0 && (
        <div className="aviso atencao">
          <strong>
            {dados.divergence_alerts}{" "}
            {dados.divergence_alerts === 1 ? "alerta" : "alertas"} por divergência
            de evidências.
          </strong>{" "}
          Nesses casos o modelo e a assinatura física apontam condições
          diferentes — o diagnóstico é menos confiável e a inspeção tem
          prioridade. <Link to="/alertas?divergencia=1">Ver quais</Link>
        </div>
      )}

      <section>
        <div
          className="linha"
          style={{ justifyContent: "space-between", marginBottom: "0.8rem" }}
        >
          <div>
            <h2>Fila de inspeção</h2>
            <p className="faint" style={{ margin: "0.15rem 0 0" }}>
              Ordenada por severidade × criticidade do motor × agravamento
            </p>
          </div>
          <Link to="/alertas" className="faint" style={{ whiteSpace: "nowrap" }}>
            todos os alertas →
          </Link>
        </div>

        {fila.length === 0 ? (
          <div className="cartao">
            <Vazio>
              Nenhum alerta aberto. Todos os motores medidos estão em condição
              normal.
            </Vazio>
          </div>
        ) : (
          <div className="triagem">
            {fila.map((m, i) => (
              <article
                key={m.motor_id}
                className={`triagem-item rail ${m.severity ?? "neutro"}`}
              >
                <div className="triagem-ordem">{i + 1}</div>

                <div className="triagem-corpo">
                  <div className="linha" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
                    <Link to={`/motores/${m.motor_id}`} className="triagem-tag">
                      {m.tag}
                    </Link>
                    <SeloSeveridade valor={m.severity} />
                    <SeloCriticidade valor={m.criticality} />
                    {m.trend_pct !== null && m.trend_pct > 20 && (
                      <span
                        className="mono"
                        style={{ color: "var(--warning)", fontSize: "0.78rem" }}
                      >
                        ↑ {m.trend_pct.toFixed(0)}%
                      </span>
                    )}
                  </div>

                  <div className="faint" style={{ marginTop: "0.15rem" }}>
                    {m.name}
                    {m.line_name && ` · ${m.line_name}`}
                    {m.area_name && ` · ${m.area_name}`}
                  </div>

                  {m.top_rule && (
                    <div style={{ marginTop: "0.3rem", fontSize: "0.85rem" }}>
                      {ROTULO_REGRA[m.top_rule] ?? m.top_rule}
                    </div>
                  )}
                </div>

                <div className="triagem-lado">
                  <div style={{ minWidth: 120 }}>
                    <div className="rotulo" style={{ fontSize: "0.62rem" }}>
                      Tipo provável
                    </div>
                    <div style={{ marginTop: "0.15rem" }}>
                      <NomeFalha valor={m.fault_type} />
                    </div>
                    <div style={{ marginTop: "0.25rem" }}>
                      <SeloEvidencia
                        concorda={m.evidence_agreement}
                        tipoFisico={m.physical_type}
                      />
                    </div>
                  </div>

                  <div style={{ textAlign: "right", minWidth: 62 }}>
                    <div className="rotulo" style={{ fontSize: "0.62rem" }}>
                      Prioridade
                    </div>
                    <div
                      className="medida"
                      style={{
                        color:
                          m.priority_score >= 100
                            ? "var(--failure)"
                            : "var(--warning)",
                      }}
                    >
                      {m.priority_score.toFixed(0)}
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {dados.recent_alerts.length > 0 && (
        <section className="cartao">
          <div className="rotulo" style={{ marginBottom: "0.8rem" }}>
            Atividade recente
          </div>
          <div className="pilha" style={{ gap: "0.7rem" }}>
            {dados.recent_alerts.slice(0, 5).map((a) => (
              <div
                key={a.id}
                className="linha"
                style={{ alignItems: "flex-start", gap: "0.7rem" }}
              >
                <span
                  className={`ponto ${a.severity as Severity}`}
                  style={{ marginTop: 7 }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <Link to={`/motores/${a.motor_id}`}>
                    <strong>{a.motor_tag}</strong>
                  </Link>{" "}
                  <span className="dim" style={{ fontSize: "0.87rem" }}>
                    {ROTULO_REGRA[a.rule] ?? a.rule}
                  </span>
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
