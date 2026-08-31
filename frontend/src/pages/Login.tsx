import { useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import { useAuth } from "../hooks/useAuth";

export default function Login() {
  const { entrar } = useAuth();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function submeter(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await entrar(email, senha);
    } catch (ex) {
      setErro(ex instanceof ApiError ? ex.detail : "Falha ao entrar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: "1.5rem",
      }}
    >
      <form
        onSubmit={submeter}
        className="cartao"
        style={{ width: "100%", maxWidth: 380 }}
      >
        <h1 style={{ marginBottom: "0.3rem" }}>Predição de Falhas</h1>
        <p className="faint" style={{ marginTop: 0, marginBottom: "1.4rem" }}>
          Monitoramento de motores elétricos industriais
        </p>

        {erro && (
          <div className="aviso erro" style={{ marginBottom: "1rem" }}>
            {erro}
          </div>
        )}

        <div className="campo">
          <label htmlFor="email">E-mail</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="username"
            required
            autoFocus
          />
        </div>

        <div className="campo">
          <label htmlFor="senha">Senha</label>
          <input
            id="senha"
            type="password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>

        <button type="submit" disabled={enviando} style={{ width: "100%" }}>
          {enviando ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </div>
  );
}
