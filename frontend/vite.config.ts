import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // O proxy faz o navegador enxergar API e front na MESMA origem durante o
    // desenvolvimento. Sem isso, os cookies httpOnly de autenticacao seriam
    // tratados como third-party e bloqueados por navegadores modernos.
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
});
