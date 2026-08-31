# Frontend: build com Node, servido por nginx.
#
# O nginx tambem faz proxy de /api para o backend, servindo interface e API na
# MESMA ORIGEM. Isso nao e conveniencia: os cookies de autenticacao sao
# httpOnly e SameSite, e navegadores modernos os tratariam como third-party se
# a interface estivesse num dominio e a API em outro — a sessao simplesmente
# nao se manteria.

FROM node:22-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
