import "server-only";

import type { KafkaJS } from "@confluentinc/kafka-javascript";

import { groupIdFor } from "@/lib/config";
import { kafka } from "@/lib/kafka/client";

/**
 * Kafka metadata via the admin client — the only Kafka touch on the read path.
 *
 * Computes each service's consumer lag on the topic it consumes: committed
 * offsets from the group, high watermarks from the topic. No consumer, no
 * subscribe, no poll — a console that joined a consumer group would move the
 * pipeline's own offsets.
 *
 * Which topics to measure comes from the DLS documents on screen. Nothing here
 * enumerates topics by pattern: the only topics worth showing are the ones
 * something actually dead-lettered on.
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

async function highWatermarks(
  instance: KafkaJS.Admin,
  topic: string,
): Promise<Map<number, number>> {
  const offsets = await instance.fetchTopicOffsets(topic);
  return new Map(offsets.map((o) => [o.partition, Number(o.high)]));
}

async function committed(
  instance: KafkaJS.Admin,
  groupId: string,
  topic: string,
): Promise<Map<number, number>> {
  const fetched = await instance.fetchOffsets({ groupId, topics: [topic] });
  const entry = fetched.find((f) => f.topic === topic);
  return new Map((entry?.partitions ?? []).map((p) => [p.partition, Number(p.offset)]));
}

/**
 * `{ sourceTopic: lag }` for the given topics. Best-effort by design.
 *
 * Every failure mode here is a missing number, not an error: a topic deleted
 * since the failure, a group that never committed, a broker that times out. The
 * overview must render with or without lag, so each topic is isolated and a
 * rejection just leaves that row's lag null.
 */
export async function computeLag(topics: string[]): Promise<Record<string, number>> {
  if (topics.length === 0) return {};
  const instance = await admin();

  const results = await Promise.all(
    topics.map(async (topic) => {
      try {
        const [highs, offsets] = await Promise.all([
          highWatermarks(instance, topic),
          committed(instance, groupIdFor(topic), topic),
        ]);
        let total = 0;
        for (const [partition, high] of highs) {
          const offset = offsets.get(partition);
          // No committed offset yet (-1 or absent) → the group has read nothing
          // on that partition, so the whole partition counts as lag.
          total += offset === undefined || offset < 0 ? high : Math.max(0, high - offset);
        }
        return [topic, total] as const;
      } catch {
        return null;
      }
    }),
  );

  return Object.fromEntries(results.filter((r): r is readonly [string, number] => r !== null));
}
