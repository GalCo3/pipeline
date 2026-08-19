# dls-console — one Next.js server for both the API and the UI.
#
# Build context is the REPO ROOT (like every other app here), so the paths below
# are repo-relative. Alpine is safe for the native librdkafka addon: the package
# resolves its binary through node-pre-gyp, whose `package_name` is templated on
# {libc}, and Confluent publishes the musl build alongside the glibc one
# (confluent-kafka-javascript-v<ver>-node-v127-linux-musl-x64.tar.gz). Nothing is
# compiled here — keep the deps and runtime stages on the SAME libc or the
# downloaded .node will not load.

# ---- deps -------------------------------------------------------------------
FROM node:22-alpine AS deps
WORKDIR /app
COPY apps/services/dls-console/package.json apps/services/dls-console/package-lock.json* ./
# `npm ci` when a lockfile is present, `npm install` otherwise — the first build
# of a new checkout should not fail on a missing lock.
RUN --mount=type=cache,target=/root/.npm \
    if [ -f package-lock.json ]; then npm ci; else npm install; fi

# ---- build ------------------------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY apps/services/dls-console/ ./
# Next reads nothing from the environment at build time here: every value is
# read per request (see src/lib/config.ts), so one image promotes everywhere.
RUN npm run build

# Prune and set permissions HERE, not in the runtime stage. A `RUN chgrp -R`
# after the COPYs rewrites every file it touches into a second full copy of
# /app — the image then ships the tree twice. Doing it before the COPY means
# the runtime stage is nothing but COPY layers, which carry uid/gid/mode over.
#
# What goes, and why the server never misses it:
#   @img          sharp/libvips, in both glibc *and* musl flavours — Next pulls
#                 it for next/image, which this UI does not use (33MB).
#   typescript,   devDependencies that Next's tracer follows through its own
#   caniuse-lite  conditional requires; nothing calls them from server.js (11MB).
#   kafka deps/   the librdkafka *source* tree. node-pre-gyp only ships it so a
#                 fallback build is possible; the downloaded .node is complete
#                 on its own, so build/Release and lib/ are the load-bearing
#                 parts (~15MB).
RUN rm -rf .next/standalone/node_modules/@img \
           .next/standalone/node_modules/typescript \
           .next/standalone/node_modules/caniuse-lite \
    && rm -rf node_modules/@confluentinc/kafka-javascript/deps \
              node_modules/@confluentinc/kafka-javascript/src \
              node_modules/@confluentinc/kafka-javascript/examples \
              node_modules/@confluentinc/kafka-javascript/cpplint.py \
              node_modules/@confluentinc/kafka-javascript/build/Release/obj.target \
    && chgrp -R 0 .next/standalone .next/static node_modules/@confluentinc \
    && chmod -R g=u .next/standalone .next/static node_modules/@confluentinc

# ---- runtime ----------------------------------------------------------------
FROM node:22-alpine AS runtime
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

# The package managers come from the base image, so they can only be dropped
# here. This deletes rather than rewrites, so the layer is just whiteouts — the
# tree above is already owned and moded correctly by the build stage.
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx \
           /opt/yarn-v* /usr/local/bin/yarn /usr/local/bin/yarnpkg \
           /usr/local/lib/node_modules/corepack /usr/local/bin/corepack \
           /usr/local/include/node

USER 1001

EXPOSE 8080
CMD ["node", "server.js"]
