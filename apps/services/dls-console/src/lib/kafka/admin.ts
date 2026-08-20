import "server-only";

import type { KafkaJS } from "@confluentinc/kafka-javascript";

import { kafka } from "@/lib/kafka/client";

/**
 * Kafka metadata via the admin client — the only Kafka touch on the read path.
 *
 * No consumer, no subscribe, no poll — a console that joined a consumer group
 * would move the pipeline's own offsets.
 */

declare global {
  var __dlsConsoleAdmin: Promise<KafkaJS.Admin> | undefined;
}

function admin(): Promise<KafkaJS.Admin> {
  if (!globalThis.__dlsConsoleAdmin) {
    globalThis.__dlsConsoleAdmin = (async () => {
      const instance = kafka().admin();
      await instance.connect();
      return instance;
    })().catch((error) => {
      globalThis.__dlsConsoleAdmin = undefined;
      throw error;
    });
  }
  return globalThis.__dlsConsoleAdmin;
}

/** Health probe. Rejects when the cluster is unreachable. */
export async function ping(): Promise<void> {
  await (await admin()).listTopics();
}
