/**
 * Forma de onda do sinal coletado.
 *
 * O que é desenhado não são amostras, é o **envelope**: mínimo e máximo de cada
 * balde. Em vibração o conteúdo diagnóstico está em picos curtos — o impacto de
 * um defeito de pista dura microssegundos. Desenhar uma amostra a cada N
 * descartaria justamente esses picos e mostraria um sinal mais limpo do que o
 * medido, sem nada na tela indicando a perda.
 *
 * Os números ao lado vêm do sinal inteiro, não dos pontos desenhados, para que
 * a leitura não dependa da largura do gráfico.
 */

import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Waveform } from "../api/types";
import { Carregando, Metrica, dataHora } from "../components/ui";
import { useApi } from "../hooks/useApi";

export default function FormaDeOnda({
  medicaoId,
  quando,
}: {
  medicaoId: string;
  quando?: string | null;
}) {
  const { dados, carregando, erro } = useApi<Waveform>(
    `/measurements/${medicaoId}/waveform?max_points=1200`,
  );

  if (carregando) return <Carregando linhas={4} />;

  // Sinal indisponível não é erro do usuário, mas precisa aparecer: quem
  // selecionou a medição no gráfico espera uma resposta, e silêncio pareceria
  // falha da interface.
  if (erro || !dados) {
    return (
      <section className="cartao">
        <div className="rotulo">Forma de onda</div>
        <p className="faint" style={{ margin: "0.5rem 0 0" }}>
          O sinal bruto desta coleta não está mais armazenado. Os indicadores e o
          diagnóstico permanecem no histórico.
        </p>
      </section>
    );
  }

  const serie = dados.points.map((p) => ({ t: p.t, faixa: [p.min, p.max] }));
  const limite = Math.max(...dados.points.map((p) => Math.max(Math.abs(p.min), Math.abs(p.max))));

  return (
    <section className="cartao">
      <div className="linha" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
        <div>
          <div className="rotulo">Forma de onda · {dados.channel_name}</div>
          <p className="faint" style={{ margin: "0.25rem 0 0" }}>
            {quando && <>coleta de {dataHora(quando)} · </>}
            {dados.n_samples.toLocaleString("pt-BR")} amostras a{" "}
            {dados.sample_rate_hz.toLocaleString("pt-BR")} Hz ·{" "}
            {dados.duration_s.toFixed(2)} s
          </p>
        </div>
      </div>

      <div
        className="linha"
        style={{ gap: "2rem", flexWrap: "wrap", margin: "1rem 0 0.4rem" }}
      >
        <Metrica rotulo="Pico a pico" valor={dados.peak_to_peak_g.toFixed(3)} unidade="g" />
        <Metrica rotulo="Pico" valor={dados.peak_g.toFixed(3)} unidade="g" />
        <Metrica rotulo="RMS" valor={dados.rms_g.toFixed(3)} unidade="g" />
        <Metrica rotulo="Fator de crista" valor={dados.crest_factor.toFixed(2)} />
      </div>

      <div style={{ height: 190, marginTop: "0.6rem" }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={serie} margin={{ top: 6, right: 8, bottom: 2, left: -14 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              domain={[0, dados.duration_s]}
              tickFormatter={(v: number) => `${v.toFixed(2)}s`}
              stroke="var(--text-faint)"
              tick={{ fontSize: 11 }}
            />
            <YAxis
              domain={[-limite * 1.08, limite * 1.08]}
              tickFormatter={(v: number) => v.toFixed(1)}
              stroke="var(--text-faint)"
              tick={{ fontSize: 11 }}
              width={46}
            />
            <ReferenceLine y={0} stroke="var(--border-forte)" />
            <Tooltip
              contentStyle={{
                background: "var(--bg-elev-2)",
                border: "1px solid var(--border-forte)",
                borderRadius: 6,
                fontSize: "0.8rem",
              }}
              labelFormatter={(v) => `${Number(v).toFixed(4)} s`}
              formatter={(v: unknown) => {
                const [lo, hi] = v as [number, number];
                return [`${lo.toFixed(3)} a ${hi.toFixed(3)} g`, "faixa"];
              }}
            />
            <Area
              dataKey="faixa"
              stroke="var(--accent)"
              strokeWidth={0.6}
              fill="var(--accent)"
              fillOpacity={0.45}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <p className="faint" style={{ margin: "0.5rem 0 0", fontSize: "0.8rem" }}>
        Envelope: cada ponto do gráfico é o mínimo e o máximo de{" "}
        {dados.decimation} amostras. Os valores acima vêm do sinal completo — não
        dos pontos desenhados.
      </p>
    </section>
  );
}
