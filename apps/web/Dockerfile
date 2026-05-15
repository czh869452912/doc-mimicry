FROM node:22-alpine AS build

ARG VITE_API_BASE=http://127.0.0.1:8000
ARG VITE_ACP_UI_URL=
ENV VITE_API_BASE=$VITE_API_BASE
ENV VITE_ACP_UI_URL=$VITE_ACP_UI_URL

WORKDIR /app

COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

COPY apps/web ./
RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
