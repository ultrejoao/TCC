/**
 * Edição e remoção de um motor.
 *
 * A remoção é um soft delete: o motor sai do cadastro ativo, mas medições,
 * previsões e alertas permanecem. Isso precisa ficar claro na confirmação —
 * "excluir" sugere perda de dados, e aqui não há.
 */

import { useState, type FormEvent } from "react";
import { ApiError, del, put } from "../api/client";
import {
  ROTULO_CRITICIDADE,
  type Criticality,
  type Line,
  type MotorDetail,
} from "../api/types";
import { useApi } from "../hooks/useApi";

/** Classe de máquina sugerida pela potência, conforme ISO 10816-1. */
function classeSugerida(potenciaKw: number): string | null {
  if (!potenciaKw || potenciaKw <= 0) return null;
  if (potenciaKw <= 15) return "I";
  if (potenciaKw <= 75) return "II";
  return "III";
}

export default function EditarMotor({
  motor,
  aoSalvar,
  aoCancelar,
  aoExcluir,
}: {
  motor: MotorDetail;
  aoSalvar: () => void;
  aoCancelar: () => void;
  aoExcluir: () => void;
}) {
  const linhas = useApi<Line[]>("/lines");

  const [nome, setNome] = useState(motor.name);
  const [linhaId, setLinhaId] = useState(motor.line_id ?? "");
  const [criticidade, setCriticidade] = useState<Criticality>(motor.criticality);
  const [fabricante, setFabricante] = useState(motor.manufacturer ?? "");
  const [modelo, setModelo] = useState(motor.model ?? "");
  const [potencia, setPotencia] = useState(motor.power_kw?.toString() ?? "");
  const [rotacao, setRotacao] = useState(motor.rated_rpm?.toString() ?? "");
  const [polos, setPolos] = useState(motor.poles?.toString() ?? "");
  const [classeIso, setClasseIso] = useState(motor.iso_machine_class);
  const [observacoes, setObservacoes] = useState(motor.notes ?? "");

  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [confirmando, setConfirmando] = useState(false);
  const [textoConfirma, setTextoConfirma] = useState("");

  async function salvar(e: FormEvent) {
    e.preventDefault();
    setSalvando(true);
    setErro(null);
    try {
      await put(`/motors/${motor.id}`, {
        name: nome,
        line_id: linhaId || null,
        criticality: criticidade,
        manufacturer: fabricante || null,
        model: modelo || null,
        power_kw: potencia ? Number(potencia) : null,
        rated_rpm: rotacao ? Number(rotacao) : null,
        poles: polos ? Number(polos) : null,
        iso_machine_class: classeIso,
        notes: observacoes || null,
      });
      aoSalvar();
    } catch (ex) {
      setErro(ex instanceof ApiError ? ex.detail : "Não foi possível salvar.");
    } finally {
      setSalvando(false);
    }
  }

  async function excluir() {
    setSalvando(true);
    setErro(null);
    try {
      await del(`/motors/${motor.id}`);
      aoExcluir();
    } catch (ex) {
      setErro(ex instanceof ApiError ? ex.detail : "Não foi possível remover.");
      setSalvando(false);
    }
  }

  const sugerida = potencia ? classeSugerida(Number(potencia)) : null;

  return (
    <section className="cartao" style={{ borderColor: "var(--accent-dim)" }}>
      <h2 style={{ marginBottom: "0.9rem" }}>Editar {motor.tag}</h2>

      {erro && (
        <div className="aviso erro" style={{ marginBottom: "1rem" }}>
          {erro}
        </div>
      )}

      <form onSubmit={salvar}>
        <div className="campo">
          <label htmlFor="e-nome">Descrição</label>
          <input
            id="e-nome"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            required
          />
        </div>

        <div
          className="grade"
          style={{ gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}
        >
          <div className="campo">
            <label htmlFor="e-linha">Linha</label>
            <select
              id="e-linha"
              value={linhaId}
              onChange={(e) => setLinhaId(e.target.value)}
            >
              <option value="">sem linha definida</option>
              {linhas.dados?.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.code} — {l.name}
                </option>
              ))}
            </select>
          </div>

          <div className="campo">
            <label htmlFor="e-crit">Criticidade</label>
            <select
              id="e-crit"
              value={criticidade}
              onChange={(e) => setCriticidade(e.target.value as Criticality)}
            >
              {(["A", "B", "C"] as Criticality[]).map((c) => (
                <option key={c} value={c}>
                  {c} — {ROTULO_CRITICIDADE[c]}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div
          className="grade"
          style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}
        >
          <div className="campo">
            <label htmlFor="e-fab">Fabricante</label>
            <input
              id="e-fab"
              value={fabricante}
              onChange={(e) => setFabricante(e.target.value)}
            />
          </div>
          <div className="campo">
            <label htmlFor="e-mod">Modelo</label>
            <input id="e-mod" value={modelo} onChange={(e) => setModelo(e.target.value)} />
          </div>
        </div>

        <div
          className="grade"
          style={{ gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))" }}
        >
          <div className="campo">
            <label htmlFor="e-pot">Potência (kW)</label>
            <input
              id="e-pot"
              type="number"
              step="any"
              value={potencia}
              onChange={(e) => {
                setPotencia(e.target.value);
                const s = classeSugerida(Number(e.target.value));
                if (s) setClasseIso(s);
              }}
            />
          </div>
          <div className="campo">
            <label htmlFor="e-rot">Rotação (rpm)</label>
            <input
              id="e-rot"
              type="number"
              value={rotacao}
              onChange={(e) => setRotacao(e.target.value)}
            />
          </div>
          <div className="campo">
            <label htmlFor="e-pol">Polos</label>
            <input
              id="e-pol"
              type="number"
              step="2"
              min="2"
              value={polos}
              onChange={(e) => setPolos(e.target.value)}
            />
          </div>
          <div className="campo">
            <label htmlFor="e-iso">Classe ISO 10816</label>
            <select
              id="e-iso"
              value={classeIso}
              onChange={(e) => setClasseIso(e.target.value)}
            >
              <option value="I">I — até 15 kW</option>
              <option value="II">II — 15 a 75 kW</option>
              <option value="III">III — grande, base rígida</option>
              <option value="IV">IV — grande, base flexível</option>
            </select>
            {sugerida && sugerida !== classeIso && (
              <div
                className="faint"
                style={{ marginTop: "0.3rem", color: "var(--warning)" }}
              >
                Para {potencia} kW a norma sugere a classe {sugerida}. Ela define
                os limiares de severidade.
              </div>
            )}
          </div>
        </div>

        <div className="campo">
          <label htmlFor="e-obs">Observações</label>
          <textarea
            id="e-obs"
            rows={2}
            value={observacoes}
            onChange={(e) => setObservacoes(e.target.value)}
          />
        </div>

        <div className="linha" style={{ gap: "0.6rem", flexWrap: "wrap" }}>
          <button type="submit" disabled={salvando}>
            {salvando ? "Salvando…" : "Salvar alterações"}
          </button>
          <button
            type="button"
            className="secundario"
            onClick={aoCancelar}
            disabled={salvando}
          >
            Cancelar
          </button>
        </div>
      </form>

      <hr
        style={{
          border: "none",
          borderTop: "1px solid var(--border)",
          margin: "1.3rem 0 1rem",
        }}
      />

      {!confirmando ? (
        <button
          className="perigo"
          onClick={() => setConfirmando(true)}
          style={{ padding: "0.4rem 0.9rem", fontSize: "0.9rem" }}
        >
          Remover do cadastro
        </button>
      ) : (
        <div className="aviso atencao">
          <strong>Remover {motor.tag} do cadastro ativo?</strong>
          <p style={{ margin: "0.4rem 0" }}>
            O motor deixa de aparecer nas listagens e no painel. As{" "}
            <strong>{motor.measurement_count} medições</strong>, as previsões e os
            alertas <strong>permanecem armazenados</strong> — nada é apagado, e o
            histórico segue disponível para auditoria.
          </p>
          <p className="faint" style={{ margin: "0.4rem 0" }}>
            A tag <span className="mono">{motor.tag}</span> ficará reservada e não
            poderá ser reutilizada em um novo cadastro.
          </p>

          <div className="campo" style={{ marginTop: "0.7rem" }}>
            <label htmlFor="e-conf">
              Digite <span className="mono">{motor.tag}</span> para confirmar
            </label>
            <input
              id="e-conf"
              value={textoConfirma}
              onChange={(e) => setTextoConfirma(e.target.value)}
              autoComplete="off"
            />
          </div>

          <div className="linha" style={{ gap: "0.6rem" }}>
            <button
              className="perigo"
              onClick={excluir}
              disabled={salvando || textoConfirma !== motor.tag}
            >
              {salvando ? "Removendo…" : "Confirmar remoção"}
            </button>
            <button
              className="secundario"
              onClick={() => {
                setConfirmando(false);
                setTextoConfirma("");
              }}
              disabled={salvando}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
