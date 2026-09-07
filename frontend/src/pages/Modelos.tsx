/**
 * Registro de modelos — a ficha do que está diagnosticando.
 *
 * Esta tela existe porque a rastreabilidade estava só no banco: toda previsão
 * referencia o modelo que a gerou, e não havia onde ler esse registro.
 *
 * A decisão de apresentação que sustenta o resto: os protocolos de validação
 * aparecem **lado a lado**. O mesmo modelo mede 88,7% sob um e 80,6% sob outro,
 * e a diferença entre eles é o resultado metodológico do trabalho — não um
 * detalhe a esconder atrás do número mais favorável.
 */

import { useState } from "react";
import type { FieldAccuracy, ModelDetail, ModelSummary } from "../api/types";
import { Carregando, Erro, Metrica, Vazio, dataHora } from "../components/ui";
import { useApi } from "../hooks/useApi";

const pct = (v: number | null | undefined) =>
  v == null ? "—" : `${(v * 100).toFixed(1).replace(".", ",")}%`;

/** Recall por classe, em barras — a média esconde qual classe o modelo perde. */
function Recall({ titulo, valores }: { titulo: string; valores: Record<string, number> }) {
  const chaves = Object.keys(valores);
  if (!chaves.length) return null;

  return (
    <div style={{ marginTop: "0.9rem" }}>
      <div className="faint" style={{ marginBottom: "0.4rem" }}>{titulo}</div>
      <div className="pilha" style={{ gap: "0.35rem" }}>
        {chaves.sort((a, b) => valores[b] - valores[a]).map((c) => (
          <div key={c} className="linha" style={{ gap: "0.6rem", alignItems: "center" }}>
            <span style={{ width: 110, fontSize: "0.85rem" }}>{c}</span>
            <div
              style={{
                flex: 1,
                height: 6,
                background: "var(--bg-elev-2)",
                borderRadius: 3,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${valores[c] * 100}%`,
                  height: "100%",
                  background:
                    valores[c] >= 0.8
                      ? "var(--healthy)"
                      : valores[c] >= 0.5
                        ? "var(--warning)"
                        : "var(--failure)",
                }}
              />
            </div>
            <span className="mono" style={{ fontSize: "0.8rem", width: 52, textAlign: "right" }}>
              {pct(valores[c])}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Acerto contra inspeção de campo.
 *
 * Fica ao lado da acurácia de validação cruzada de propósito: são medidas de
 * naturezas diferentes. Uma compara contra a partição de teste do mesmo dataset
 * que treinou o modelo; a outra, contra o que alguém encontrou ao abrir a
 * máquina. A segunda é mais fraca em amostra e mais forte em significado.
 */
function AcertoEmCampo() {
  const { dados: a } = useApi<FieldAccuracy>("/inspections/field-accuracy");
  if (!a) return null;

  const linhas = Object.entries(a.confusion).filter(([, v]) =>
    Object.values(v).some((n) => n > 0),
  );

  return (
    <section className="cartao">
      <h3 style={{ marginTop: 0 }}>Acerto confirmado em campo</h3>

      {a.n_confirmed === 0 ? (
        <p className="faint" style={{ marginTop: "0.2rem" }}>
          Nenhuma inspeção confirmou um tipo de falha ainda. Registre inspeções
          na página do motor, ao lado de cada medição, para que o acerto passe a
          ser medido contra a realidade e não só contra a partição de teste.
        </p>
      ) : (
        <>
          <div className="linha" style={{ gap: "2rem", flexWrap: "wrap", marginTop: "0.6rem" }}>
            <Metrica rotulo="Acerto em campo" valor={pct(a.accuracy)} />
            <Metrica rotulo="Confirmações" valor={`${a.n_correct} de ${a.n_confirmed}`} />
            <Metrica rotulo="Inspeções registradas" valor={a.n_inspections} />
          </div>

          {linhas.length > 0 && (
            <div style={{ overflowX: "auto", marginTop: "1.1rem" }}>
              <table>
                <thead>
                  <tr>
                    <th>encontrado \ diagnosticado</th>
                    {Object.keys(a.confusion).map((c) => (
                      <th key={c}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {linhas.map(([real, prevs]) => (
                    <tr key={real}>
                      <td>{real}</td>
                      {Object.keys(a.confusion).map((c) => (
                        <td
                          key={c}
                          className="mono"
                          style={{
                            color: prevs[c] === 0 ? "var(--text-faint)"
                              : real === c ? "var(--healthy)" : "var(--failure)",
                          }}
                        >
                          {prevs[c]}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      <div className="aviso info" style={{ marginTop: "1rem" }}>
        {a.caveat}
      </div>
    </section>
  );
}

function Detalhe({ versao }: { versao: string }) {
  const { dados: m, carregando, erro } = useApi<ModelDetail>(`/models/${versao}`);

  if (carregando) return <Carregando linhas={6} />;
  if (erro) return <Erro>{erro.detail}</Erro>;
  if (!m) return null;

  const integro = m.integrity.matches;

  return (
    <div className="pilha">
      <section className="cartao">
        <div className="linha" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
          <div>
            <h2 className="mono" style={{ margin: 0 }}>{m.version}</h2>
            <p className="faint" style={{ margin: "0.25rem 0 0" }}>{m.description}</p>
          </div>
          {m.is_active && (
            <span className="selo" style={{ background: "var(--healthy-bg)", color: "var(--healthy)" }}>
              padrão
            </span>
          )}
        </div>

        <div
          className="grade"
          style={{
            gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
            marginTop: "1.1rem",
          }}
        >
          <Metrica rotulo="Features" valor={m.n_features ?? "—"} />
          <Metrica rotulo="Janelas de treino" valor={m.n_windows?.toLocaleString("pt-BR") ?? "—"} />
          <Metrica rotulo="Janela" valor={m.window_seconds ?? "—"} unidade="s" />
          <Metrica rotulo="Diagnósticos emitidos" valor={m.prediction_count} />
        </div>

        {/* "padrao" nao significa "o que rodou". O perfil e escolhido por
            medicao, pela instrumentacao que o tecnico enviou — um arquivo de
            um canal so nunca aciona o modelo de quatro. A contagem de
            diagnosticos acima e que diz qual esta de fato operando. */}
        <p className="faint" style={{ marginTop: "0.9rem", fontSize: "0.82rem" }}>
          O modelo usado em cada medição é escolhido pela instrumentação
          enviada, não por esta marcação: um arquivo de um canal nunca aciona o
          modelo de quatro. Quem diz qual está operando é a contagem de
          diagnósticos emitidos.
        </p>

        <div className="faint" style={{ marginTop: "1rem", lineHeight: 1.7 }}>
          <div>Algoritmo: {m.algorithm}</div>
          <div>Dataset: {m.dataset}</div>
          <div>Treinado em: {dataHora(m.trained_at)}</div>
          {m.last_prediction_at && <div>Último diagnóstico: {dataHora(m.last_prediction_at)}</div>}
        </div>
      </section>

      {/* Integridade: um artefato trocado sem passar pelo registro faria as
          previsões referenciarem uma versão que não foi a que rodou. */}
      <div className={`aviso ${integro === true ? "ok" : integro === false ? "erro" : "atencao"}`}>
        <strong>{integro === true ? "Artefato íntegro" : integro === false ? "Artefato divergente" : "Integridade não verificada"}</strong>
        <p style={{ margin: "0.35rem 0 0" }}>{m.integrity.message}</p>
        <p className="mono faint" style={{ margin: "0.35rem 0 0", fontSize: "0.75rem", wordBreak: "break-all" }}>
          {m.integrity.path}
        </p>
      </div>

      <section className="cartao">
        <h3 style={{ marginTop: 0 }}>Desempenho por protocolo de validação</h3>
        <p className="faint" style={{ marginTop: "0.2rem" }}>
          Protocolos diferentes medem dificuldades diferentes de generalização.
          Os dois aparecem juntos de propósito: publicar só o mais favorável
          seria a forma mais fácil de enganar sem mentir.
        </p>

        <div
          className="grade"
          style={{ gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", marginTop: "1rem" }}
        >
          {m.protocols.map((p) => (
            <div
              key={p.protocol}
              style={{
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-sm)",
                padding: "0.9rem",
              }}
            >
              <div className="mono" style={{ fontSize: "0.85rem", fontWeight: 600 }}>
                {p.protocol}
              </div>
              <p className="faint" style={{ margin: "0.4rem 0 0.8rem", fontSize: "0.82rem" }}>
                {p.description}
              </p>

              <div className="linha" style={{ gap: "1.6rem" }}>
                <Metrica rotulo="Tipo de falha" valor={pct(p.fault_type_accuracy)} />
                <Metrica rotulo="Severidade (ML)" valor={pct(p.severity_accuracy)} />
              </div>

              <Recall titulo="Recall por tipo de falha" valores={p.fault_type_recall} />
              <Recall titulo="Recall por severidade" valores={p.severity_recall} />
            </div>
          ))}
        </div>

        <p className="faint" style={{ marginTop: "1rem", fontSize: "0.82rem" }}>
          A severidade exibida ao técnico <strong>não</strong> vem do modelo: vem
          do critério físico da ISO 10816. A coluna acima mede o experimento
          preliminar de severidade por ML, mantido como achado do trabalho.
        </p>
      </section>

      {m.known_limitations.length > 0 && (
        <section className="cartao">
          <h3 style={{ marginTop: 0 }}>Limitações conhecidas</h3>
          <p className="faint" style={{ marginTop: "0.2rem" }}>
            Gravadas junto do modelo, para não dependerem de alguém lembrar de
            abrir a documentação.
          </p>
          <ul style={{ margin: "0.8rem 0 0", paddingLeft: "1.1rem", lineHeight: 1.65 }}>
            {m.known_limitations.map((l, i) => (
              <li key={i} style={{ marginBottom: "0.4rem" }}>{l}</li>
            ))}
          </ul>
        </section>
      )}

      {m.holdout_specimens.length > 0 && (
        <section className="cartao">
          <h3 style={{ marginTop: 0 }}>Espécimes reservados</h3>
          <p className="faint" style={{ marginTop: "0.2rem" }}>{m.holdout_note}</p>
          <div className="linha" style={{ gap: "0.4rem", flexWrap: "wrap", marginTop: "0.7rem" }}>
            {m.holdout_specimens.map((e) => (
              <span key={e} className="selo mono" style={{ fontSize: "0.78rem" }}>{e}</span>
            ))}
          </div>
        </section>
      )}

      <section className="cartao">
        <h3 style={{ marginTop: 0 }}>Entradas e hiperparâmetros</h3>

        <div className="linha" style={{ gap: "1.6rem", flexWrap: "wrap", marginTop: "0.6rem" }}>
          {Object.entries(m.feature_groups).map(([grupo, n]) => (
            <Metrica key={grupo} rotulo={grupo} valor={n} />
          ))}
        </div>

        <div
          className="grade"
          style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginTop: "1.2rem" }}
        >
          {Object.entries(m.hyperparameters).map(([algo, params]) => (
            <div key={algo}>
              <div className="faint mono" style={{ marginBottom: "0.35rem" }}>{algo}</div>
              <div className="mono" style={{ fontSize: "0.8rem", lineHeight: 1.7 }}>
                {Object.entries(params as Record<string, unknown>).map(([k, v]) => (
                  <div key={k} className="linha" style={{ justifyContent: "space-between", gap: "1rem" }}>
                    <span className="dim">{k}</span>
                    <span>{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <details style={{ marginTop: "1.2rem" }}>
          <summary className="faint" style={{ cursor: "pointer" }}>
            ver as {m.feature_columns.length} features
          </summary>
          <div
            className="mono"
            style={{
              marginTop: "0.6rem",
              fontSize: "0.75rem",
              lineHeight: 1.8,
              maxHeight: 220,
              overflowY: "auto",
              color: "var(--text-dim)",
            }}
          >
            {m.feature_columns.join(" · ")}
          </div>
        </details>
      </section>
    </div>
  );
}

export default function Modelos() {
  const { dados, carregando, erro } = useApi<ModelSummary[]>("/models");
  const [versao, setVersao] = useState<string | null>(null);

  const ativa = versao ?? dados?.find((m) => m.is_active)?.version ?? dados?.[0]?.version ?? null;

  return (
    <div className="pilha">
      <div>
        <h1>Modelos</h1>
        <p className="faint" style={{ margin: "0.2rem 0 0" }}>
          Quais modelos estão diagnosticando, quanto acertam sob cada protocolo
          de validação, e o que reconhecidamente não fazem.
        </p>
      </div>

      {carregando && <Carregando linhas={3} />}
      {erro && <Erro>{erro.detail}</Erro>}

      {dados && dados.length === 0 && (
        <Vazio>
          Nenhum modelo registrado. Rode <span className="mono">ml/scripts/09_train_profiles.py</span>{" "}
          e depois <span className="mono">backend/scripts/register_models.py</span>.
        </Vazio>
      )}

      {dados && dados.length > 0 && (
        <>
          <div className="linha" style={{ gap: "0.4rem", flexWrap: "wrap" }}>
            {dados.map((m) => (
              <button
                key={m.version}
                className={m.version === ativa ? "" : "secundario"}
                onClick={() => setVersao(m.version)}
                style={{ padding: "0.4rem 0.9rem", fontSize: "0.85rem" }}
              >
                <span className="mono">{m.version}</span>
                {m.is_active && " ·  padrão"}
              </button>
            ))}
          </div>

          <AcertoEmCampo />

          {ativa && <Detalhe key={ativa} versao={ativa} />}
        </>
      )}
    </div>
  );
}
