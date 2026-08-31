/**
 * Cliente HTTP da API.
 *
 * Autenticacao por cookie httpOnly: o token nunca passa por JavaScript, entao
 * nao ha o que roubar via XSS. O preco e que o navegador envia o cookie
 * automaticamente, o que reabre a porta para CSRF — por isso todo metodo que
 * altera estado repete, no cabecalho X-CSRF-Token, o valor do cookie csrf_token
 * (que e legivel de proposito). Um site atacante consegue disparar a
 * requisicao, mas nao consegue LER o cookie para preencher o cabecalho.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    public title: string,
    public detail: string,
    public errors?: { campo: string; mensagem: string }[],
  ) {
    super(detail || title);
    this.name = "ApiError";
  }
}

function lerCookie(nome: string): string | null {
  const alvo = `${nome}=`;
  for (const parte of document.cookie.split(";")) {
    const limpo = parte.trim();
    if (limpo.startsWith(alvo)) return decodeURIComponent(limpo.slice(alvo.length));
  }
  return null;
}

const METODOS_INSEGUROS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

let renovando: Promise<boolean> | null = null;

/** Renova o access token. Concorrentes aguardam a mesma renovacao. */
async function renovarSessao(): Promise<boolean> {
  if (!renovando) {
    renovando = fetch("/api/v1/auth/refresh", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRF-Token": lerCookie("csrf_token") ?? "" },
    })
      .then((r) => r.ok)
      .catch(() => false)
      .finally(() => {
        renovando = null;
      });
  }
  return renovando;
}

interface Opcoes {
  method?: string;
  body?: unknown;
  formData?: FormData;
  signal?: AbortSignal;
  /** uso interno: evita laco infinito de renovacao */
  _repetido?: boolean;
}

export async function api<T>(caminho: string, opcoes: Opcoes = {}): Promise<T> {
  const method = opcoes.method ?? "GET";
  const headers: Record<string, string> = {};

  if (METODOS_INSEGUROS.has(method)) {
    headers["X-CSRF-Token"] = lerCookie("csrf_token") ?? "";
  }

  let body: BodyInit | undefined;
  if (opcoes.formData) {
    body = opcoes.formData; // o navegador define o Content-Type com o boundary
  } else if (opcoes.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opcoes.body);
  }

  const resposta = await fetch(`/api/v1${caminho}`, {
    method,
    headers,
    body,
    credentials: "same-origin",
    signal: opcoes.signal,
  });

  // access token expirado: renova uma vez e repete a requisicao
  if (resposta.status === 401 && !opcoes._repetido && caminho !== "/auth/login") {
    if (await renovarSessao()) {
      return api<T>(caminho, { ...opcoes, _repetido: true });
    }
  }

  if (resposta.status === 204) return undefined as T;

  const texto = await resposta.text();
  const dados = texto ? JSON.parse(texto) : null;

  if (!resposta.ok) {
    throw new ApiError(
      resposta.status,
      dados?.title ?? "Erro",
      dados?.detail ?? "Nao foi possivel completar a operacao.",
      dados?.errors,
    );
  }
  return dados as T;
}

export const get = <T,>(caminho: string, signal?: AbortSignal) =>
  api<T>(caminho, { signal });
export const post = <T,>(caminho: string, body?: unknown) =>
  api<T>(caminho, { method: "POST", body });
export const put = <T,>(caminho: string, body?: unknown) =>
  api<T>(caminho, { method: "PUT", body });
export const del = (caminho: string) => api<void>(caminho, { method: "DELETE" });
export const upload = <T,>(caminho: string, formData: FormData) =>
  api<T>(caminho, { method: "POST", formData });
