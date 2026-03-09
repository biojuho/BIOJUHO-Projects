# ── Stage 1: Dependencies ─────────────────────────────
FROM node:22-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

# ── Stage 2: Development (hot-reload) ─────────────────
FROM node:22-alpine AS development

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json vite.config.js index.html ./
# src는 volume mount로 실시간 반영

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ── Stage 3: Build ────────────────────────────────────
FROM node:22-alpine AS build

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ── Stage 4: Production (nginx) ───────────────────────
FROM nginx:alpine AS production

# SPA fallback 설정
RUN echo 'server { \
    listen 80; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
    try_files $uri $uri/ /index.html; \
    } \
    location /assets { \
    expires 1y; \
    add_header Cache-Control "public, immutable"; \
    } \
    }' > /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
