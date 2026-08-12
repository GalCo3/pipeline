# dls-portal — one Next.js server for both the API and the UI.
#
# Build context is the REPO ROOT (like every other app here), so the paths below
# are repo-relative. Node 22 on Debian slim rather than Alpine: the Kafka client
# is a native librdkafka addon and its prebuilt binaries are glibc.

# ---- deps -------------------------------------------------------------------
FROM node:22-bookworm-slim AS deps
WORKDIR /app
COPY apps/services/dls-portal/package.json apps/services/dls-portal/package-lock.json* ./
# `npm ci` when a lockfile is present, `npm install` otherwise — the first build
# of a new checkout should not fail on a missing lock.
RUN --mount=type=cache,target=/root/.npm \
    if [ -f package-lock.json ]; then npm ci; else npm install; fi

# ---- build ------------------------------------------------------------------
FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY apps/services/dls-portal/ ./
# Next reads nothing from the environment at build time here: every value is
# read per request (see src/lib/config.ts), so one image promotes everywhere.
RUN npm run build

# ---- runtime ----------------------------------------------------------------
FROM node:22-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production
# 8080, not 3000: unprivileged and OpenShift-safe, matching the other frontends.
ENV PORT=8080
ENV HOSTNAME=0.0.0.0

# `output: standalone` emits a server plus exactly the node_modules it traced.
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
# The Kafka addon is declared external (see next.config.mjs), so tracing skips
# its .node binary — copy the package wholesale or the first replay fails with
# MODULE_NOT_FOUND.
COPY --from=build /app/node_modules/@confluentinc ./node_modules/@confluentinc

# OpenShift runs the container as an arbitrary UID whose group is 0.
RUN chgrp -R 0 /app && chmod -R g=u /app
USER 1001

EXPOSE 8080
CMD ["node", "server.js"]
