import "server-only";

import { MongoClient, type Db } from "mongodb";

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
  var __dlsPortalMongo: MongoClient | undefined;
}

function client(): MongoClient {
  if (!globalThis.__dlsPortalMongo) {
    globalThis.__dlsPortalMongo = new MongoClient(config.mongo.uri, {
      // A read path that hangs is worse than one that fails: every route treats
      // Mongo errors as a 5xx the operator can retry.
      serverSelectionTimeoutMS: 5_000,
    });
  }
  return globalThis.__dlsPortalMongo;
}

/** The pipeline's own database (`hermes`), not a triage-side copy. */
export function db(): Db {
  return client().db(config.mongo.database);
}

export async function ping(): Promise<void> {
  await db().command({ ping: 1 });
}
