"use client";

import { useParams } from "next/navigation";

import { MessageDetailPanel } from "@/components/MessageDetailPanel";

/**
 * Standalone message page — a direct link (History, a pasted URL, back
 * button) lands here. From the Overview grid a click opens the same content
 * in a slide-over instead (see `MessageDetailPanel` and `Overview`'s own
 * `message` query param); this route stays so every message keeps a
 * shareable, bookmarkable URL of its own.
 */
export default function MessagePage() {
  const { id } = useParams<{ id: string }>();

  return (
    <div className="mx-auto max-w-md space-y-5">
      <MessageDetailPanel id={id} />
    </div>
  );
}
