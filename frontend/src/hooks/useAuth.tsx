import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { get, post } from "../api/client";
import type { LoginResponse, User } from "../api/types";

interface Contexto {
  usuario: User | null;
  carregando: boolean;
  entrar: (email: string, senha: string) => Promise<void>;
  sair: () => Promise<void>;
}

const AuthContext = createContext<Contexto | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<User | null>(null);
  const [carregando, setCarregando] = useState(true);

  // Na carga inicial, tenta identificar a sessao pelo cookie httpOnly. O
  // proprio cliente HTTP renova o access token se estiver expirado, entao um
  // retorno de erro aqui significa mesmo que nao ha sessao.
  useEffect(() => {
    get<User>("/auth/me")
      .then(setUsuario)
      .catch(() => setUsuario(null))
      .finally(() => setCarregando(false));
  }, []);

  async function entrar(email: string, password: string) {
    const r = await post<LoginResponse>("/auth/login", { email, password });
    setUsuario(r.user);
  }

  async function sair() {
    try {
      await post("/auth/logout");
    } finally {
      setUsuario(null);
    }
  }

  return (
    <AuthContext.Provider value={{ usuario, carregando, entrar, sair }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth precisa estar dentro de AuthProvider");
  return ctx;
}
