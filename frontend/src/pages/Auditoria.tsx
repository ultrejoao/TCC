/**
 * Trilha de auditoria.
 *
 * A trilha já era escrita por catorze pontos do sistema; o que faltava era onde
 * lê-la. Um controle que só se consulta com acesso direto ao banco é consultado
 * exatamente quando já é tarde.
 *
 * A tela abre no filtro de eventos sensíveis, não na lista completa. A lista
 * completa é dominada por operação normal — login, coleta, cadastro — e enterra
 * o que importa. Reúso de token e remoção de motor precisam ser vistos sem
 * ninguém ir procurar.
 */

import { useState } from "react";
import type { AuditEntry, AuditSummary, Page } from "../api/types";
import { Carregando, Erro, Metrica, Vazio, dataHora } from "../components/ui";
import { useApi } from "../hooks/useApi";

export default function Auditoria() {
  const [soSensiveis, setSoSensiveis] = useState(true);

  const resumo = useApi<AuditSummary>("/audit/summary?days=30");
  const eventos = useApi<Page<AuditEntry>>(
    `/audit?limit=100${soSensiveis ? "&only_sensitive=true" : ""}`,
    [soSensiveis],
  );

  const sensiveis = Object.entries(resumo.dados?.sensitive ?? {});

  return (
    <div className="pilha">
      <div>
        <h1>Auditoria</h1>
        <p className="faint" style={{ margin: "0.2rem 0 0" }}>
          Ações sensíveis registradas pelo sistema: autenticação, alteração de
          cadastro, remoção e detecção de reúso de token.
        </p>
      </div>

      {resumo.dados && (
        <section className="cartao">
          <div className="linha" style={{ gap: "2rem", flexWrap: "wrap" }}>
            <Metrica rotulo="Eventos em 30 dias" valor={resumo.dados.total} />
            <Metrica
              rotulo="Sensíveis"
              valor={Object.values(resumo.dados.sensitive).reduce((a, b) => a + b, 0)}
              destaque={sensiveis.length ? "var(--warning)" : undefined}
            />
            <Metrica rotulo="Primeiro registro" valor={dataHora(resumo.dados.first_event)} />
          </div>

          {sensiveis.length > 0 && (
            <div className="aviso atencao" style={{ marginTop: "1rem" }}>
              <strong>Eventos que merecem leitura</strong>
              <ul style={{ margin: "0.5rem 0 0", paddingLeft: "1.1rem", lineHeight: 1.6 }}>
                {sensiveis.map(([acao, n]) => (
                  <li key={acao}>
                    <span className="mono">{acao}</span> — {n}×
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      <div className="linha" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>
          {soSensiveis ? "Eventos sensíveis" : "Todos os eventos"}
        </h2>
        <button className="secundario" onClick={() => setSoSensiveis((v) => !v)}>
          {soSensiveis ? "Mostrar todos" : "Só sensíveis"}
        </button>
      </div>

      {eventos.carregando && <Carregando linhas={4} />}
      {eventos.erro && <Erro>{eventos.erro.detail}</Erro>}

      {eventos.dados && eventos.dados.items.length === 0 && (
        <Vazio>
          {soSensiveis
            ? "Nenhum evento sensível registrado — nada a investigar."
            : "Nenhum evento registrado."}
        </Vazio>
      )}

      {eventos.dados && eventos.dados.items.length > 0 && (
        <section className="cartao">
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Quando</th>
                  <th>Ação</th>
                  <th>Usuário</th>
                  <th>Origem</th>
                  <th>Detalhe</th>
                </tr>
              </thead>
              <tbody>
                {eventos.dados.items.map((e) => (
                  <tr key={e.id}>
                    <td>{dataHora(e.created_at)}</td>
                    <td>
                      <span
                        className="mono"
                        style={{ color: e.sensitive ? "var(--warning)" : undefined }}
                      >
                        {e.action}
                      </span>
                    </td>
                    <td>{e.user_name ?? <span className="faint">—</span>}</td>
                    <td className="mono faint">{e.ip_address ?? "—"}</td>
                    <td className="faint" style={{ fontSize: "0.8rem" }}>
                      {e.detail && Object.keys(e.detail).length
                        ? Object.entries(e.detail)
                            .map(([k, v]) => `${k}=${v}`)
                            .join(" · ")
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="faint" style={{ marginTop: "0.9rem", fontSize: "0.82rem" }}>
            {eventos.dados.items.length} de {eventos.dados.total} evento(s). A
            trilha é somente-leitura: não há endpoint que a altere ou apague.
          </p>
        </section>
      )}
    </div>
  );
}
