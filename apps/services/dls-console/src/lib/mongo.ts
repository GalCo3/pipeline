import "server-only";

import { readFileSync } from "node:fs";

import { MongoClient, type Db, type MongoClientOptions } from "mongodb";

import { config } from "@/lib/config";

/**
 * One MongoClient for the process, cached on `globalThis`.
 *
 * The global is not decoration: in dev, Next re-evaluates modules on every hot
 * reload, and a module-level client would leak a fresh connection pool per edit
 * until Mongo refuses new connections. In production the module is evaluated
 * once and the global is simply where it lives.
 */

declare global {
  var __dlsConsoleMongo: MongoClient | undefined;
}

/**
 * TLS as driver options rather than URI query parameters.
 *
 * Same reason the Kafka client takes paths: the certificates are files an
 * operator mounts, and a mistyped path should surface as this client failing to
 * read a file, not as a silently ignored query parameter in a connection
 * string.
 *
 * `$external` is a literal database name, not a shell variable — it is where
 * Mongo keeps identities it did not issue itself, which is every x509 subject.
 */
function tlsOptions(): MongoClientOptions {
  const { tls, x509 } = config.mongo;
  if (!tls) return {};
  // Two shapes of client material, one driver. `tlsCertificateKeyFile` is a
  // single PEM holding certificate *and* key — what pymongo takes, so what the
  // Python services' mounts look like. When the key arrives as its own file the
  // driver has no path option for the pair, so the files are read here and
  // handed to the TLS socket as `cert`/`key` buffers instead.
  const clientCert = tls.certPath
    ? tls.keyPath
      ? { cert: readFileSync(tls.certPath), key: readFileSync(tls.keyPath) }
      : { tlsCertificateKeyFile: tls.certPath }
    : {};
  return {
    tls: true,
    ...(tls.caPath ? { tlsCAFile: tls.caPath } : {}),
    ...clientCert,
    ...(x509 ? { authMechanism: "MONGODB-X509" as const, authSource: "$external" } : {}),
  };
}

function client(): MongoClient {
  if (!globalThis.__dlsConsoleMongo) {
    globalThis.__dlsConsoleMongo = new MongoClient(config.mongo.uri, {
      // A read path that hangs is worse than one that fails: every route treats
      // Mongo errors as a 5xx the operator can retry.
      serverSelectionTimeoutMS: 5_000,
      ...tlsOptions(),
    });
  }
  return globalThis.__dlsConsoleMongo;
}

/** The pipeline's own database (`hermes`), not a triage-side copy. */
export function db(): Db {
  return client().db(config.mongo.database);
}

export async function ping(): Promise<void> {
  await db().command({ ping: 1 });
}
