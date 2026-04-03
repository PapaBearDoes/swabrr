# ============================================================================
# Swabrr Web — Dockerfile
# ============================================================================
# Multi-stage build: Node.js, Next.js standalone output
#
# FILE VERSION: v1.0.0
# LAST MODIFIED: 2026-04-01
# COMPONENT: swabrr-web
# ============================================================================

# --------------------------------------------------------------------------
# Stage 1: Dependencies
# --------------------------------------------------------------------------
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* yarn.lock* ./
RUN npm ci --ignore-scripts 2>/dev/null || npm install

# --------------------------------------------------------------------------
# Stage 2: Build
# --------------------------------------------------------------------------
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# --------------------------------------------------------------------------
# Stage 3: Runtime
# --------------------------------------------------------------------------
FROM node:22-alpine AS runtime
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
