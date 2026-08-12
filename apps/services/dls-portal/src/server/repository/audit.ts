import "server-only";

import type { AuditEntry } from "@/lib/types";
import { asDate, audit, objectId } from "@/server/repository/helpers";

/** Audit trail for one message, oldest first. Null when the id is unparseable. */
export async function auditFor(messageId: string): Promise<AuditEntry[] | null> {
  const oid = objectId(messageId);
  if (!oid) return null;
  const docs = await audit().find({ messageId: oid }).sort({ at: 1 }).toArray();
  return docs.map((doc) => ({
    id: String(doc._id),
    action: doc.action,
    actor: doc.actor,
    at: asDate(doc.at) ?? "",
    bulkId: doc.bulkId ?? null,
    result: doc.result,
    error: doc.error ?? null,
    detail: doc.detail ?? {},
  }));
}
