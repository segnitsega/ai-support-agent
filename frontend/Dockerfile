# Stage 1 — build the React app
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2 — static file server (no reverse proxy)
FROM node:22-alpine

WORKDIR /app

RUN npm install -g serve@14

COPY --from=build /app/dist ./dist
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENV PORT=3000

EXPOSE 3000

ENTRYPOINT ["/docker-entrypoint.sh"]
