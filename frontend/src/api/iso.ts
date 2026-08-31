/**
 * Classificação de máquina conforme a ISO 10816-1.
 *
 * A classe define os limiares das zonas A/B/C/D e, portanto, quando um alerta
 * normativo dispara. Cadastrá-la errada distorce o diagnóstico em silêncio.
 *
 * O ponto que costuma passar batido: a norma **não** separa as classes III e IV
 * por potência, e sim pela rigidez da fundação na direção de medição. Uma
 * máquina grande em base rígida é classe III; a mesma máquina em base flexível
 * é classe IV, e os limiares mudam bastante — a fronteira C/D vai de 11,2 para
 * 18,0 mm/s. Sem saber a fundação, a classe de uma máquina grande não pode ser
 * determinada, e o formulário passa a pedir essa informação em vez de arbitrar.
 */

export type Foundation = "RIGID" | "FLEXIBLE";

export const LIMIARES_ISO: Record<string, [number, number, number]> = {
  I: [0.71, 1.8, 4.5],
  II: [1.12, 2.8, 7.1],
  III: [1.8, 4.5, 11.2],
  IV: [2.8, 7.1, 18.0],
};

export const DESCRICAO_CLASSE: Record<string, string> = {
  I: "I — máquinas pequenas, até 15 kW",
  II: "II — máquinas médias, 15 a 75 kW",
  III: "III — máquinas grandes, fundação rígida",
  IV: "IV — máquinas grandes, fundação flexível",
};

export const DESCRICAO_FUNDACAO: Record<Foundation, string> = {
  RIGID: "Rígida — base pesada, concreto ou estrutura enrijecida",
  FLEXIBLE: "Flexível — base leve, estrutura metálica ou amortecedores",
};

export interface SugestaoClasse {
  classe: string | null;
  motivo: string;
  precisaFundacao: boolean;
}

/** Sugere a classe a partir da potência e, quando necessário, da fundação. */
export function sugerirClasse(
  potenciaKw: number,
  fundacao: Foundation | null,
): SugestaoClasse {
  if (!potenciaKw || potenciaKw <= 0) {
    return { classe: null, motivo: "", precisaFundacao: false };
  }

  if (potenciaKw <= 15) {
    return {
      classe: "I",
      motivo: `${potenciaKw} kW: máquina pequena, classe I.`,
      precisaFundacao: false,
    };
  }

  if (potenciaKw <= 75) {
    return {
      classe: "II",
      motivo: `${potenciaKw} kW: máquina de médio porte, classe II.`,
      precisaFundacao: false,
    };
  }

  // Acima de 75 kW a norma decide pela fundação, não pela potência.
  if (!fundacao) {
    return {
      classe: null,
      motivo:
        `${potenciaKw} kW: acima de 75 kW a norma distingue classe III de IV ` +
        `pela rigidez da fundação, não pela potência. Informe o tipo de base.`,
      precisaFundacao: true,
    };
  }

  const classe = fundacao === "RIGID" ? "III" : "IV";
  return {
    classe,
    motivo:
      `${potenciaKw} kW em fundação ` +
      `${fundacao === "RIGID" ? "rígida" : "flexível"}: classe ${classe}.`,
    precisaFundacao: true,
  };
}

/** Texto com os limiares da classe, para exibir junto ao campo. */
export function limiaresTexto(classe: string): string {
  const l = LIMIARES_ISO[classe];
  if (!l) return "";
  return `zonas: A/B ${l[0]} · B/C ${l[1]} · C/D ${l[2]} mm/s`;
}
