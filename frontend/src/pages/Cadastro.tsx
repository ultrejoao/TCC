/**
 * Cadastro da estrutura da fabrica.
 *
 * A hierarquia e montada no proprio lugar onde ela e exibida: cada no tem o
 * botao que cria o no filho. Formularios separados por nivel exigiriam que o
 * usuario escolhesse o pai numa lista suspensa, o que fica confuso quando a
 * planta cresce — aqui o contexto ja esta dado por onde ele clicou.
 */

import { useState } from "react";
import { ApiError, post } from "../api/client";
import {
  ROTULO_CRITICIDADE,
  type Criticality,
  type TreeArea,
  type TreeLine,
  type TreePlant,
} from "../api/types";
import { Carregando, Erro, SeloCriticidade, Vazio } from "../components/ui";
import { useApi } from "../hooks/useApi";

type Formulario =
  | { tipo: "planta" }
  | { tipo: "area"; plantaId: string; plantaNome: string }
  | { tipo: "linha"; areaId: string; areaNome: string }
  | { tipo: "motor"; linhaId: string; linhaNome: string }
  | null;

/**
 * Classe de maquina sugerida pela potencia, conforme a ISO 10816-1.
 *
 * A classe define os limiares das zonas A/B/C/D e, por consequencia, quando um
 * alerta normativo dispara. Cadastrar a classe errada distorce o diagnostico
 * sem que nada denuncie o engano, entao vale sugerir a partir da potencia.
 */
function classeSugerida(potenciaKw: number): string | null {
  if (!potenciaKw || potenciaKw <= 0) return null;
  if (potenciaKw <= 15) return "I";
  if (potenciaKw <= 75) return "II";
  return "III";
}


function BotaoAdicionar({
  onClick,
  children,
}: {
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      className="secundario"
      onClick={onClick}
      style={{ padding: "0.25rem 0.65rem", fontSize: "0.8rem" }}
    >
      + {children}
    </button>
  );
}

export default function Cadastro() {
  const arvore = useApi<TreePlant[]>("/tree");
  const [form, setForm] = useState<Formulario>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  // campos compartilhados entre os formularios
  const [codigo, setCodigo] = useState("");
  const [nome, setNome] = useState("");
  const [local, setLocal] = useState("");
  const [tag, setTag] = useState("");
  const [criticidade, setCriticidade] = useState<Criticality>("B");
  const [potencia, setPotencia] = useState("");
  const [rotacao, setRotacao] = useState("");
  const [polos, setPolos] = useState("2");
  const [classeIso, setClasseIso] = useState("I");

  function abrir(f: Formulario) {
    setForm(f);
    setErro(null);
    setCodigo("");
    setNome("");
    setLocal("");
    setTag("");
    setCriticidade("B");
    setPotencia("");
    setRotacao("");
    setPolos("2");
    setClasseIso("I");
  }

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setSalvando(true);
    setErro(null);

    try {
      if (form.tipo === "planta") {
        await post("/plants", { code: codigo, name: nome, location: local || null });
      } else if (form.tipo === "area") {
        await post("/areas", { plant_id: form.plantaId, code: codigo, name: nome });
      } else if (form.tipo === "linha") {
        await post("/lines", { area_id: form.areaId, code: codigo, name: nome });
      } else {
        await post("/motors", {
          tag,
          name: nome,
          line_id: form.linhaId,
          criticality: criticidade,
          power_kw: potencia ? Number(potencia) : null,
          rated_rpm: rotacao ? Number(rotacao) : null,
          poles: polos ? Number(polos) : null,
          iso_machine_class: classeIso,
        });
      }
      setForm(null);
      arvore.recarregar();
    } catch (ex) {
      setErro(ex instanceof ApiError ? ex.detail : "Não foi possível salvar.");
    } finally {
      setSalvando(false);
    }
  }

  if (arvore.carregando) return <Carregando linhas={5} />;
  if (arvore.erro) return <Erro>{arvore.erro.detail}</Erro>;

  const plantas = arvore.dados ?? [];

  return (
    <div className="pilha">
      <div className="linha" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
        <div>
          <h1>Cadastro da estrutura</h1>
          <p className="faint" style={{ margin: "0.2rem 0 0" }}>
            Planta › Área › Linha › Motor. Cada nível cria o nível abaixo dele.
          </p>
        </div>
        <button onClick={() => abrir({ tipo: "planta" })}>+ Nova planta</button>
      </div>

      {form && (
        <section className="cartao" style={{ borderColor: "var(--accent-dim)" }}>
          <h2 style={{ marginBottom: "0.9rem" }}>
            {form.tipo === "planta" && "Nova planta"}
            {form.tipo === "area" && `Nova área em ${form.plantaNome}`}
            {form.tipo === "linha" && `Nova linha em ${form.areaNome}`}
            {form.tipo === "motor" && `Novo motor em ${form.linhaNome}`}
          </h2>

          {erro && (
            <div className="aviso erro" style={{ marginBottom: "1rem" }}>
              {erro}
            </div>
          )}

          <form onSubmit={salvar}>
            {form.tipo === "motor" ? (
              <>
                <div
                  className="grade"
                  style={{ gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}
                >
                  <div className="campo">
                    <label htmlFor="tag">Tag do motor</label>
                    <input
                      id="tag"
                      value={tag}
                      onChange={(e) => setTag(e.target.value)}
                      placeholder="MT-101"
                      required
                      autoFocus
                    />
                  </div>
                  <div className="campo">
                    <label htmlFor="nome">Descrição</label>
                    <input
                      id="nome"
                      value={nome}
                      onChange={(e) => setNome(e.target.value)}
                      placeholder="Motor principal da extrusora"
                      required
                    />
                  </div>
                </div>

                <div className="campo">
                  <label htmlFor="crit">Criticidade para a produção</label>
                  <select
                    id="crit"
                    value={criticidade}
                    onChange={(e) => setCriticidade(e.target.value as Criticality)}
                  >
                    {(["A", "B", "C"] as Criticality[]).map((c) => (
                      <option key={c} value={c}>
                        {c} — {ROTULO_CRITICIDADE[c]}
                      </option>
                    ))}
                  </select>
                  <div className="faint" style={{ marginTop: "0.3rem" }}>
                    Pondera a prioridade dos alertas: a mesma falha pesa mais num
                    motor que para a linha.
                  </div>
                </div>

                <div
                  className="grade"
                  style={{ gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))" }}
                >
                  <div className="campo">
                    <label htmlFor="pot">Potência (kW)</label>
                    <input
                      id="pot"
                      type="number"
                      step="any"
                      value={potencia}
                      onChange={(e) => {
                        setPotencia(e.target.value);
                        const sugerida = classeSugerida(Number(e.target.value));
                        if (sugerida) setClasseIso(sugerida);
                      }}
                    />
                  </div>
                  <div className="campo">
                    <label htmlFor="rot">Rotação (rpm)</label>
                    <input
                      id="rot"
                      type="number"
                      value={rotacao}
                      onChange={(e) => setRotacao(e.target.value)}
                    />
                  </div>
                  <div className="campo">
                    <label htmlFor="pol">Polos</label>
                    <input
                      id="pol"
                      type="number"
                      step="2"
                      min="2"
                      value={polos}
                      onChange={(e) => setPolos(e.target.value)}
                    />
                  </div>
                  <div className="campo">
                    <label htmlFor="iso">Classe ISO 10816</label>
                    <select
                      id="iso"
                      value={classeIso}
                      onChange={(e) => setClasseIso(e.target.value)}
                    >
                      <option value="I">I — até 15 kW</option>
                      <option value="II">II — 15 a 75 kW</option>
                      <option value="III">III — grande, base rígida</option>
                      <option value="IV">IV — grande, base flexível</option>
                    </select>
                    {potencia && classeSugerida(Number(potencia)) !== classeIso && (
                      <div className="faint" style={{ marginTop: "0.3rem", color: "var(--warning)" }}>
                        Para {potencia} kW a norma sugere a classe{" "}
                        {classeSugerida(Number(potencia))}. A classe define os
                        limiares de alerta.
                      </div>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div
                className="grade"
                style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}
              >
                <div className="campo">
                  <label htmlFor="cod">Código</label>
                  <input
                    id="cod"
                    value={codigo}
                    onChange={(e) => setCodigo(e.target.value)}
                    placeholder={form.tipo === "planta" ? "P01" : form.tipo === "area" ? "EXT" : "L01"}
                    required
                    autoFocus
                  />
                </div>
                <div className="campo">
                  <label htmlFor="nome">Nome</label>
                  <input
                    id="nome"
                    value={nome}
                    onChange={(e) => setNome(e.target.value)}
                    required
                  />
                </div>
                {form.tipo === "planta" && (
                  <div className="campo">
                    <label htmlFor="loc">Localização</label>
                    <input
                      id="loc"
                      value={local}
                      onChange={(e) => setLocal(e.target.value)}
                      placeholder="Cidade - UF"
                    />
                  </div>
                )}
              </div>
            )}

            <div className="linha" style={{ gap: "0.6rem", marginTop: "0.5rem" }}>
              <button type="submit" disabled={salvando}>
                {salvando ? "Salvando…" : "Salvar"}
              </button>
              <button
                type="button"
                className="secundario"
                onClick={() => setForm(null)}
                disabled={salvando}
              >
                Cancelar
              </button>
            </div>
          </form>
        </section>
      )}

      {plantas.length === 0 && !form && (
        <Vazio>
          Nenhuma planta cadastrada.
          <div style={{ marginTop: "0.8rem" }}>
            <button onClick={() => abrir({ tipo: "planta" })}>
              Cadastrar a primeira planta
            </button>
          </div>
        </Vazio>
      )}

      {plantas.map((p) => (
        <section key={p.id} className="cartao">
          <div className="linha" style={{ gap: "0.7rem", flexWrap: "wrap" }}>
            <h2>{p.name}</h2>
            <span className="mono faint">{p.code}</span>
            <div style={{ marginLeft: "auto" }}>
              <BotaoAdicionar
                onClick={() => abrir({ tipo: "area", plantaId: p.id, plantaNome: p.name })}
              >
                área
              </BotaoAdicionar>
            </div>
          </div>
          {p.location && <div className="faint">{p.location}</div>}

          {p.areas.length === 0 ? (
            <div className="faint" style={{ marginTop: "0.7rem" }}>
              nenhuma área cadastrada
            </div>
          ) : (
            p.areas.map((a: TreeArea) => (
              <div
                key={a.id}
                style={{
                  marginTop: "0.9rem",
                  marginLeft: "0.8rem",
                  paddingLeft: "0.9rem",
                  borderLeft: "1px solid var(--border)",
                }}
              >
                <div className="linha" style={{ gap: "0.6rem", flexWrap: "wrap" }}>
                  <span className="mono dim">{a.code}</span>
                  <strong>{a.name}</strong>
                  <div style={{ marginLeft: "auto" }}>
                    <BotaoAdicionar
                      onClick={() => abrir({ tipo: "linha", areaId: a.id, areaNome: a.name })}
                    >
                      linha
                    </BotaoAdicionar>
                  </div>
                </div>

                {a.lines.length === 0 ? (
                  <div className="faint" style={{ marginTop: "0.4rem" }}>
                    nenhuma linha cadastrada
                  </div>
                ) : (
                  a.lines.map((l: TreeLine) => (
                    <div
                      key={l.id}
                      style={{
                        marginTop: "0.7rem",
                        marginLeft: "0.8rem",
                        paddingLeft: "0.9rem",
                        borderLeft: "1px solid var(--border)",
                      }}
                    >
                      <div className="linha" style={{ gap: "0.6rem", flexWrap: "wrap" }}>
                        <span className="mono dim">{l.code}</span>
                        <span>{l.name}</span>
                        <div style={{ marginLeft: "auto" }}>
                          <BotaoAdicionar
                            onClick={() =>
                              abrir({ tipo: "motor", linhaId: l.id, linhaNome: l.name })
                            }
                          >
                            motor
                          </BotaoAdicionar>
                        </div>
                      </div>

                      {l.motors.length === 0 ? (
                        <div className="faint" style={{ marginTop: "0.35rem" }}>
                          nenhum motor cadastrado
                        </div>
                      ) : (
                        <div style={{ marginTop: "0.4rem" }}>
                          {l.motors.map((m) => (
                            <div
                              key={m.id}
                              className="linha"
                              style={{ gap: "0.6rem", padding: "0.25rem 0" }}
                            >
                              <SeloCriticidade valor={m.criticality} />
                              <span className="mono">{m.tag}</span>
                              <span className="faint">{m.name}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            ))
          )}
        </section>
      ))}
    </div>
  );
}
