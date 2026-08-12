import "server-only";

import type { KafkaJS } from "@confluentinc/kafka-javascript";

import { config } from "@/lib/config";
import { kafka } from "@/lib/kafka/client";

/**
 * Replay producer — the portal's ONLY Kafka write path.
 *
 * Produces pre-encoded JSON bytes as-is, which is exactly what the services'
 * consumers deserialize: no Schema Registry, no Avro framing. `produce` awaits
 * the broker ack, so REPLAYED is set strictly after the record is durable.
 *
 * Neither a key nor the original headers can be reproduced: a DLS record stores
 * the decoded value and nothing else (`hermes.utils.dls.DLSRecord`), because the
 * consumer hands its handler an already-deserialized message. The one header
 * this sets is its own replay marker.
 */

/**
 * Stamped on every replayed record with the DLS document's `_id`. Nothing in the
 * pipeline reads it — services ignore unknown headers — but it is what lets an
 * operator tell a replay from an original in Kafbat, and what links a re-failure
 * back to the document it came from when the same message dead-letters twice.
 */
export const REPLAY_OF_HEADER = "x-dls-replay-of";

/** A produce that failed, timed out, or came back with a broker error. */
export class ProduceError extends Error {}

declare global {
  var __dlsPortalProducer: Promise<KafkaJS.Producer> | undefined;
}

/**
 * One connected producer for the process (see `mongo.ts` for why the global).
 *
 * The promise itself is cached, not the resolved producer: two concurrent
 * replays during a cold start would otherwise each open their own connection.
 */
function producer(): Promise<KafkaJS.Producer> {
  if (!globalThis.__dlsPortalProducer) {
    globalThis.__dlsPortalProducer = (async () => {
      const instance = kafka().producer({
        kafkaJS: {
          // acks=all: a replay reported as REPLAYED must be on every in-sync
          // replica, not just the leader — the DLS document is about to be
          // marked resolved on the strength of it.
          acks: -1,
          // Producer-level, not per-send: the client exposes no per-record
          // timeout. Bounds how long an unreachable broker can hold a replay
          // request open before it fails as a 502.
          timeout: config.kafka.produceTimeoutMs,
        },
      });
      await instance.connect();
      return instance;
    })().catch((error) => {
      // Don't cache a failed connect — the next replay should retry.
      globalThis.__dlsPortalProducer = undefined;
      throw error;
    });
  }
  return globalThis.__dlsPortalProducer;
}

export type ProduceResult = { partition: number; offset: number | null };

/**
 * Produce one record and await its ack. Throws `ProduceError` on any failure.
 */
export async function produce(
  topic: string,
  value: Buffer,
  replayOf: string,
): Promise<ProduceResult> {
  let reports: KafkaJS.RecordMetadata[];
  try {
    const instance = await producer();
    reports = await instance.send({
      topic,
      messages: [{ value, headers: { [REPLAY_OF_HEADER]: replayOf } }],
    });
  } catch (error) {
    throw new ProduceError(error instanceof Error ? error.message : String(error));
  }

  const report = reports[0];
  if (!report) throw new ProduceError("no delivery report from the broker");
  if (report.errorCode) throw new ProduceError(`broker error code ${report.errorCode}`);

  const offset = report.baseOffset === undefined ? null : Number(report.baseOffset);
  return { partition: report.partition ?? 0, offset: Number.isNaN(offset) ? null : offset };
}
