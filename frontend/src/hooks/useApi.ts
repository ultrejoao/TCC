import { useCallback, useEffect, useState } from "react";
import { ApiError, get } from "../api/client";

/** Busca dados da API com estados de carregamento, erro e recarga. */
export function useApi<T>(caminho: string | null, deps: unknown[] = []) {
  const [dados, setDados] = useState<T | null>(null);
  const [carregando, setCarregando] = useState(caminho !== null);
  const [erro, setErro] = useState<ApiError | null>(null);
  const [gatilho, setGatilho] = useState(0);

  const recarregar = useCallback(() => setGatilho((n) => n + 1), []);

  useEffect(() => {
    if (!caminho) {
      setCarregando(false);
      return;
    }
    const controle = new AbortController();
    setCarregando(true);
    setErro(null);

    get<T>(caminho, controle.signal)
      .then((d) => setDados(d))
      .catch((e) => {
        if (e.name !== "AbortError") setErro(e as ApiError);
      })
      .finally(() => setCarregando(false));

    return () => controle.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caminho, gatilho, ...deps]);

  return { dados, carregando, erro, recarregar };
}
