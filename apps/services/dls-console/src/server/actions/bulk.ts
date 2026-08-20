import "server-only";

import { randomUUID } from "node:crypto";

import { ActionError } from "@/lib/errors";
import type { BulkEdit, BulkTarget } from "@/lib/types";
import { discard, undiscard } from "@/server/actions/discard";
import { replay } from "@/server/actions/replay";
import { appendResult, createBulk, finishBulk, resolveTarget } from "@/server/repository/bulk";

/**
 * Bulk replay / discard orchestration — async, per-message.
 *
 * Each id runs through the SAME single-message action (with a shared `bulkId` on
 * every audit entry it writes), so there is exactly one implementation of the
 * state machine. Partial failure is normal and reported per message; successes
 * are never rolled back.
 */

/** Resolve the target, persist a RUNNING bulk, return the ticket. */
export async function start(input: {
  action: "REPLAY" | "DISCARD" | "UNDISCARD";
  actor: string;
  target: BulkTarget;
}): Promise<{ bulkId: string; messageIds: string[] }> {
  const messageIds = await resolveTarget(input.target);
  const bulkId = randomUUID();
  await createBulk(bulkId, {
    action: input.action,
    actor: input.actor,
    target: input.target,
    total: messageIds.length,
  });
  return { bulkId, messageIds };
}

/**
 * Run every message through the single-message action.
 *
 * Started after the response is sent, so it must never reject: an unhandled
 * rejection in a detached task takes the whole node process down, and with it
 * every other operator's session.
 */
export async function run(input: {
  bulkId: string;
  action: "REPLAY" | "DISCARD" | "UNDISCARD";
  actor: string;
  messageIds: string[];
  reason?: string | null;
  edit?: BulkEdit | null;
}): Promise<void> {
  try {
    for (const messageId of input.messageIds) {
      const { outcome, detail } = await runOne(input, messageId);
      await appendResult(input.bulkId, { messageId, outcome, detail });
    }
    await finishBulk(input.bulkId);
  } catch (error) {
    console.error("bulk run failed", input.bulkId, error);
    await finishBulk(input.bulkId).catch(() => undefined);
  }
}

/** One message → (outcome, detail). Never throws — failures become results. */
async function runOne(
  input: {
    bulkId: string;
    action: "REPLAY" | "DISCARD" | "UNDISCARD";
    actor: string;
    reason?: string | null;
    edit?: BulkEdit | null;
  },
  messageId: string,
): Promise<{ outcome: "ok" | "failed" | "skipped"; detail: Record<string, unknown> }> {
  try {
    if (input.action === "REPLAY") {
      const result = await replay(messageId, input.actor, {
        edit: input.edit,
        bulkId: input.bulkId,
      });
      return { outcome: "ok", detail: { producedOffset: result.producedOffset } };
    }
    if (input.action === "UNDISCARD") {
      await undiscard(messageId, input.actor, { bulkId: input.bulkId });
      return { outcome: "ok", detail: {} };
    }
    await discard(messageId, input.actor, { reason: input.reason, bulkId: input.bulkId });
    return { outcome: "ok", detail: {} };
  } catch (error) {
    if (error instanceof ActionError) {
      return { outcome: error.kind, detail: { error: String(error.detail) } };
    }
    // Never let one message abort the whole bulk.
    return { outcome: "failed", detail: { error: String(error) } };
  }
}
