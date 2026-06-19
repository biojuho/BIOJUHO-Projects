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

# SPA fallback + security headers. The Vercel deploy sets these via vercel.json;
# mirror them here so the Docker/compose/self-host path is hardened too. nginx
# drops inherited add_header in any location that sets its own, so /assets
# re-adds nosniff.
RUN echo 'server { \
    listen 80; \
    root /usr/share/nginx/html; \
    index index.html; \
    add_header X-Frame-Options "DENY" always; \
    add_header X-Content-Type-Options "nosniff" always; \
    add_header Referrer-Policy "strict-origin-when-cross-origin" always; \
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always; \
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always; \
    location / { \
    try_files $uri $uri/ /index.html; \
    } \
    location /assets { \
    expires 1y; \
    add_header Cache-Control "public, immutable"; \
    add_header X-Content-Type-Options "nosniff" always; \
    } \
    }' > /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
