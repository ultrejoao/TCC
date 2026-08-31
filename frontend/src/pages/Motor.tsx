/**
 * Detalhamento de um motor: condicao atual, evolucao e historico.
 *
 * Os graficos mostram os indicadores normativos ao longo do tempo, e nao o
 * RMS de aceleracao bruto: a velocidade em mm/s e a grandeza que a ISO
 * 10816 avalia, e e muito menos sensivel a variacao de carga.
 */

import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { put } from "../api/client";
import {
  ROTULO_FALHA,
  ROTULO_REGRA,
  type Alert,
  type Measurement,
  type MotorDetail,
  type Page,
} from "../api/types";
import {
  Carregando,
  Erro,
  Metrica,
  SeloCriticidade,
  SeloEvidencia,
  SeloSeveridade,
  Vazio,
  dataCurta,
  dataHora,
} from "../components/ui";
import { useApi } from "../hooks/useApi";

const CORES_GRAFICO = {
  v_rms: "#38bdf8",
  v_1x: "#a78bfa",
  a_hf: "#fb923c",
};

export default function Motor() {
  const { id } = useParams<{ id: string }>();
  const [salvando, setSalvando] = useState(false);

  const motor = useApi<MotorDetail>(id ? `/motors/${id}` : null);
  const medicoes = useApi<Page<Measurement>>(
    id ? `/motors/${id}/measurements?limit=60` : null,
  );
  const alertas = useApi<Page<Alert>>(
    id ? `/alerts?motor_id=${id}&status=OPEN` : null,
  );

  if (motor.carregando) return <Carregando linhas={6} />;
  if (motor.erro) return <Erro>{motor.erro.detail}</Erro>;
  if (!motor.dados) return null;

  const m = motor.dados;
  const historico = [...(medicoes.dados?.items ?? [])].reverse();

  const serie = historico.map((x) => ({
    data: dataCurta(x.collected_at),
    v_rms: x.iso_v_rms_mms,
    v_1x: x.iso_v_1x_mms,
    a_hf: x.iso_a_hf_g,
  }));

  async function tratarAlerta(alertaId: string, status: string) {
    setSalvando(true);
    try {
      await put(`/alerts/${alertaId}`, { status });
      alertas.recarregar();
      motor.recarregar();
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="pilha">
      <div>
        <div className="faint">
          {[m.plant_name, m.area_name, m.line_name].filter(Boolean).join(" › ") ||
            "sem local definido"}
        </div>
        <div className="linha" style={{ gap: "0.8rem", flexWrap: "wrap" }}>
          <h1>{m.tag}</h1>
          <SeloCriticidade valor={m.criticality} />
          <SeloSeveridade valor={m.last_severity} />
        </div>
        <p className="dim" style={{ margin: "0.15rem 0 0" }}>{m.name}</p>
      </div>

      <div
        className="grade"
        style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}
      >
        <div className="cartao">
          <Metrica rotulo="Medições" valor={m.measurement_count} />
        </div>
        <div className="cartao">
          <Metrica
            rotulo="Última coleta"
            valor={m.last_measurement_at ? dataCurta(m.last_measurement_at) : "—"}
          />
        </div>
        <div className="cartao">
          <Metrica
            rotulo="Diagnóstico"
            valor={m.last_fault_type ? ROTULO_FALHA[m.last_fault_type] : "—"}
          />
        </div>
        <div className="cartao">
          <Metrica
            rotulo="Alertas abertos"
            valor={m.open_alerts}
            destaque={m.open_alerts > 0 ? "var(--failure)" : undefined}
          />
        </div>
      </div>

      {!m.has_baseline && (
        <div className="aviso info">
          Este motor não tem <strong>medição de referência</strong> registrada. Com
          uma referência em condição normal, o sistema passa a informar a variação
          percentual de cada indicador — por exemplo, “a vibração aumentou 180% em
          relação à condição normal conhecida deste motor”. Ao coletar com o motor
          sabidamente saudável, marque a medição como referência.
        </div>
      )}

      {(alertas.dados?.items.length ?? 0) > 0 && (
        <section className="cartao">
          <h2 style={{ marginBottom: "0.9rem" }}>Alertas abertos</h2>
          <div className="pilha" style={{ gap: "0.9rem" }}>
            {alertas.dados!.items.map((a) => (
              <div
                key={a.id}
                style={{
                  borderLeft: `3px solid var(--${a.severity === "FAILURE" ? "failure" : "warning"})`,
                  paddingLeft: "0.9rem",
                }}
              >
                <div className="linha" style={{ gap: "0.6rem", flexWrap: "wrap" }}>
                  <strong>{ROTULO_REGRA[a.rule] ?? a.rule}</strong>
                  <span className="mono faint">prioridade {a.priority_score.toFixed(0)}</span>
                  <SeloEvidencia
                    concorda={a.evidence_agreement}
                    tipoFisico={a.physical_type}
                  />
                </div>
                <p style={{ margin: "0.3rem 0" }}>{a.message}</p>

                {a.reasons.length > 0 && (
                  <ul className="faint" style={{ margin: "0.3rem 0", paddingLeft: "1.1rem" }}>
                    {a.reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                )}

                <div className="linha" style={{ gap: "0.5rem", marginTop: "0.5rem" }}>
                  <button
                    className="secundario"
                    disabled={salvando}
                    onClick={() => tratarAlerta(a.id, "ACKNOWLEDGED")}
                    style={{ padding: "0.3rem 0.7rem", fontSize: "0.85rem" }}
                  >
                    Reconhecer
                  </button>
                  <button
                    className="secundario"
                    disabled={salvando}
                    onClick={() => tratarAlerta(a.id, "RESOLVED")}
                    style={{ padding: "0.3rem 0.7rem", fontSize: "0.85rem" }}
                  >
                    Resolver
                  </button>
                  <span className="faint">{dataHora(a.created_at)}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="cartao">
        <h2 style={{ marginBottom: "0.3rem" }}>Evolução dos indicadores</h2>
        <p className="faint" style={{ marginTop: 0 }}>
          Velocidade conforme ISO 10816 (mm/s) e aceleração em alta frequência (g),
          que é o indicador sensível a falha de rolamento.
        </p>

        {serie.length < 2 ? (
          <Vazio>
            São necessárias ao menos duas medições para traçar a evolução.
          </Vazio>
        ) : (
          <div style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={serie} margin={{ top: 8, right: 8, bottom: 4, left: -18 }}>
                <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
                <XAxis dataKey="data" stroke="#64748b" fontSize={12} />
                <YAxis
                  yAxisId="v"
                  stroke="#64748b"
                  fontSize={12}
                  label={{ value: "mm/s", angle: -90, position: "insideLeft", fill: "#64748b", fontSize: 11 }}
                />
                <YAxis yAxisId="a" orientation="right" stroke="#64748b" fontSize={12} />
                <Tooltip
                  contentStyle={{
                    background: "#1e293b",
                    border: "1px solid #334155",
                    borderRadius: 8,
                    fontSize: 13,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line
                  yAxisId="v"
                  type="monotone"
                  dataKey="v_rms"
                  name="Velocidade RMS (mm/s)"
                  stroke={CORES_GRAFICO.v_rms}
                  strokeWidth={2}
                  dot={{ r: 2 }}
                />
                <Line
                  yAxisId="v"
                  type="monotone"
                  dataKey="v_1x"
                  name="Componente 1× (mm/s)"
                  stroke={CORES_GRAFICO.v_1x}
                  strokeWidth={2}
                  dot={{ r: 2 }}
                />
                <Line
                  yAxisId="a"
                  type="monotone"
                  dataKey="a_hf"
                  name="Alta frequência (g)"
                  stroke={CORES_GRAFICO.a_hf}
                  strokeWidth={2}
                  dot={{ r: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>

      <section className="cartao">
        <div className="linha" style={{ justifyContent: "space-between", marginBottom: "0.8rem" }}>
          <h2>Histórico de medições</h2>
          <Link to={`/coleta?motor=${m.id}`} className="faint">
            nova coleta →
          </Link>
        </div>

        {medicoes.carregando ? (
          <Carregando />
        ) : historico.length === 0 ? (
          <Vazio>Nenhuma medição registrada para este motor.</Vazio>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Coleta</th>
                  <th>Ref.</th>
                  <th>v RMS</th>
                  <th>1×</th>
                  <th>a HF</th>
                  <th>Zona</th>
                  <th>Carga</th>
                  <th>Duração</th>
                </tr>
              </thead>
              <tbody>
                {[...historico].reverse().map((x) => (
                  <tr key={x.id}>
                    <td>{dataHora(x.collected_at)}</td>
                    <td>{x.is_baseline && <span className="selo HEALTHY">ref.</span>}</td>
                    <td className="mono">{x.iso_v_rms_mms?.toFixed(3) ?? "—"}</td>
                    <td className="mono">{x.iso_v_1x_mms?.toFixed(4) ?? "—"}</td>
                    <td className="mono">{x.iso_a_hf_g?.toFixed(3) ?? "—"}</td>
                    <td className="mono">{x.iso_zone ?? "—"}</td>
                    <td className="mono">{x.load_nm ?? "—"}</td>
                    <td className="mono faint">{x.duration_s.toFixed(1)}s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="cartao">
        <h2 style={{ marginBottom: "0.7rem" }}>Dados de placa</h2>
        <div
          className="grade"
          style={{ gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}
        >
          <div>
            <div className="faint">Fabricante</div>
            <div>{m.manufacturer ?? "—"}</div>
          </div>
          <div>
            <div className="faint">Modelo</div>
            <div>{m.model ?? "—"}</div>
          </div>
          <div>
            <div className="faint">Potência</div>
            <div>{m.power_kw ? `${m.power_kw} kW` : "—"}</div>
          </div>
          <div>
            <div className="faint">Rotação nominal</div>
            <div>{m.rated_rpm ? `${m.rated_rpm} rpm` : "—"}</div>
          </div>
          <div>
            <div className="faint">Polos</div>
            <div>{m.poles ?? "—"}</div>
          </div>
          <div>
            <div className="faint">Classe ISO 10816</div>
            <div>{m.iso_machine_class}</div>
          </div>
        </div>
      </section>
    </div>
  );
}
