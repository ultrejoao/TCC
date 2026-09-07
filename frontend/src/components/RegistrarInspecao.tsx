/**
 * Registro do que a inspeção encontrou.
 *
 * É o único ponto do sistema em que entra informação que o modelo não produziu.
 * Duas decisões de formulário que importam:
 *
 * 1. **"Não conclusivo" é uma opção de primeira classe.** Forçar o técnico a
 *    escolher um tipo quando ele não identificou nada produziria rótulo falso —
 *    e rótulo falso contamina a medida de acerto enquanto existir.
 * 2. **O diagnóstico previsto fica visível.** Esconder para "não influenciar"
 *    seria teatro: o técnico já viu o alerta que o mandou até a máquina. O que
 *    se pode fazer é deixar explícito que discordar é o resultado útil.
 */

import { useState, type FormEvent } from "react";
import { ApiError, post } from "../api/client";
import { ROTULO_FALHA, type FaultType } from "../api/types";

const TIPOS: FaultType[] = ["normal", "bearing", "misalignment", "unbalance"];

export default function RegistrarInspecao({
  motorId,
  predictionId,
  tipoPrevisto,
  aoRegistrar,
  aoCancelar,
}: {
  motorId: string;
  predictionId: string | null;
  tipoPrevisto: string | null;
  aoRegistrar: () => void;
  aoCancelar: () => void;
}) {
  const [confirmado, setConfirmado] = useState<string>("");
  const [achados, setAchados] = useState("");
  const [quando, setQuando] = useState(() => new Date().toISOString().slice(0, 16));
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const discorda = confirmado && tipoPrevisto && confirmado !== tipoPrevisto;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setSalvando(true);
    setErro(null);
    try {
      await post("/inspections", {
        motor_id: motorId,
        prediction_id: predictionId,
        performed_at: new Date(quando).toISOString(),
        confirmed_fault_type: confirmado || null,
        findings: achados || null,
      });
      aoRegistrar();
    } catch (ex) {
      setErro(ex instanceof ApiError ? ex.detail : "Não foi possível registrar.");
      setSalvando(false);
    }
  }

  return (
    <form onSubmit={enviar} className="cartao" style={{ borderColor: "var(--accent-dim)" }}>
      <h3 style={{ marginTop: 0 }}>Registrar inspeção</h3>

      {tipoPrevisto && (
        <p className="faint" style={{ marginTop: "0.2rem" }}>
          O sistema diagnosticou <strong>{ROTULO_FALHA[tipoPrevisto as FaultType] ?? tipoPrevisto}</strong>.
          Registrar que estava errado é tão útil quanto confirmar que estava certo —
          é assim que o acerto em campo passa a ser medido.
        </p>
      )}

      {erro && <div className="aviso erro" style={{ marginTop: "0.8rem" }}>{erro}</div>}

      <div className="campo" style={{ marginTop: "0.9rem" }}>
        <label htmlFor="i-quando">Data da inspeção</label>
        <input
          id="i-quando"
          type="datetime-local"
          value={quando}
          onChange={(e) => setQuando(e.target.value)}
          required
        />
      </div>

      <div className="campo">
        <label htmlFor="i-tipo">O que foi encontrado</label>
        <select
          id="i-tipo"
          value={confirmado}
          onChange={(e) => setConfirmado(e.target.value)}
        >
          <option value="">não conclusivo — não registrar confirmação</option>
          {TIPOS.map((t) => (
            <option key={t} value={t}>
              {ROTULO_FALHA[t]}
            </option>
          ))}
        </select>
        <div className="faint" style={{ marginTop: "0.3rem" }}>
          Só as inspeções com um tipo confirmado entram na medida de acerto.
        </div>
      </div>

      {discorda && (
        <div className="aviso atencao">
          A inspeção contradiz o diagnóstico. É exatamente o registro que falta
          para saber onde o modelo erra em campo.
        </div>
      )}

      <div className="campo">
        <label htmlFor="i-achados">Achados</label>
        <textarea
          id="i-achados"
          rows={3}
          value={achados}
          onChange={(e) => setAchados(e.target.value)}
          placeholder="O que foi observado ao inspecionar a máquina."
        />
      </div>

      <div className="linha" style={{ gap: "0.6rem" }}>
        <button type="submit" disabled={salvando}>
          {salvando ? "Registrando…" : "Registrar"}
        </button>
        <button type="button" className="secundario" onClick={aoCancelar} disabled={salvando}>
          Cancelar
        </button>
      </div>
    </form>
  );
}
