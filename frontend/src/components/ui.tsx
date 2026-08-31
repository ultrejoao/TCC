/** Componentes visuais reaproveitados nas telas. */

import type { ReactNode } from "react";
import {
  ROTULO_CRITICIDADE,
  ROTULO_FALHA,
  ROTULO_SEVERIDADE,
  type Criticality,
  type FaultType,
  type Severity,
} from "../api/types";

export function SeloSeveridade({ valor }: { valor: Severity | null }) {
  if (!valor) return <span className="selo neutro">Sem medição</span>;
  return <span className={`selo ${valor}`}>{ROTULO_SEVERIDADE[valor]}</span>;
}

export function PontoSeveridade({ valor }: { valor: Severity | null }) {
  return <span className={`ponto ${valor ?? "neutro"}`} />;
}

export function SeloCriticidade({ valor }: { valor: Criticality }) {
  const cores: Record<Criticality, string> = {
    A: "FAILURE",
    B: "WARNING",
    C: "neutro",
  };
  return (
    <span className={`selo ${cores[valor]}`} title={ROTULO_CRITICIDADE[valor]}>
      {valor}
    </span>
  );
}

export function NomeFalha({ valor }: { valor: FaultType | null }) {
  if (!valor) return <span className="dim">—</span>;
  return <>{ROTULO_FALHA[valor]}</>;
}

export function Carregando({ linhas = 3 }: { linhas?: number }) {
  return (
    <div className="pilha" style={{ gap: "0.5rem" }}>
      {Array.from({ length: linhas }).map((_, i) => (
        <div key={i} className="esqueleto" style={{ width: `${100 - i * 12}%` }} />
      ))}
    </div>
  );
}

export function Vazio({ children }: { children: ReactNode }) {
  return <div className="vazio">{children}</div>;
}

export function Erro({ children }: { children: ReactNode }) {
  return <div className="aviso erro">{children}</div>;
}

/**
 * Barra de probabilidade.
 *
 * O rótulo é obrigatório: sem ele, um número solto ao lado da severidade é lido
 * como "certeza de que o motor vai falhar", quando pode ser a certeza sobre o
 * TIPO de falha — grandezas diferentes, que chegam a divergir bastante
 * (ex.: tipo com 99,3 % e severidade com 60,3 % na mesma medição).
 */
export function BarraConfianca({ valor }: { valor: number }) {
  const cor = valor >= 0.7 ? "var(--healthy)" : valor >= 0.5 ? "var(--warning)" : "var(--failure)";
  return (
    <div className="linha" style={{ gap: "0.5rem" }}>
      <div
        style={{
          flex: 1,
          height: 6,
          background: "var(--bg)",
          borderRadius: 999,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${Math.round(valor * 100)}%`,
            height: "100%",
            background: cor,
            transition: "width 0.3s",
          }}
        />
      </div>
      <span className="mono" style={{ minWidth: 42, textAlign: "right" }}>
        {(valor * 100).toFixed(0)}%
      </span>
    </div>
  );
}

/**
 * Selo de concordância entre o modelo e a evidência física.
 *
 * Divergência nunca é silenciosa: quando as duas evidências não batem, o
 * usuário precisa ver isso ao lado do diagnóstico, e não descobrir depois.
 */
export function SeloEvidencia({
  concorda,
  tipoFisico,
}: {
  concorda: boolean | null;
  tipoFisico?: FaultType | null;
}) {
  if (concorda === null) return null;
  if (concorda) {
    return <span className="selo HEALTHY">Evidências concordantes</span>;
  }
  return (
    <span
      className="selo WARNING"
      title={
        tipoFisico
          ? `A assinatura de vibração é compatível com ${ROTULO_FALHA[tipoFisico]}`
          : undefined
      }
    >
      Evidências divergentes
    </span>
  );
}

export function Metrica({
  rotulo,
  valor,
  unidade,
  destaque,
}: {
  rotulo: string;
  valor: string | number;
  unidade?: string;
  destaque?: string;
}) {
  return (
    <div>
      <div className="faint">{rotulo}</div>
      <div style={{ fontSize: "1.4rem", fontWeight: 600, color: destaque }}>
        {valor}
        {unidade && (
          <span style={{ fontSize: "0.8rem", marginLeft: 3 }} className="dim">
            {unidade}
          </span>
        )}
      </div>
    </div>
  );
}

export function dataHora(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function dataCurta(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
  });
}
