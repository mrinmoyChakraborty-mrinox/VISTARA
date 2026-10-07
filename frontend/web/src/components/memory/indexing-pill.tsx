"use client";

import { Loader2, RotateCcw } from "lucide-react";

import { queueIndexing } from "@/lib/embeddingQueue";
import { useIndexingStatus } from "@/hooks/use-embedding";
import type { Memory } from "@/types/domain";

/**
 * Background-indexing pill. Shown until the embedding POST resolves; a retry
 * pill appears on failure. Memory display never waits for it.
 */
export function IndexingPill({ memory }: { memory: Memory }) {
  const status = useIndexingStatus(memory.id);

  if (status === "error") {
    return (
      <button
        type="button"
        className="schip"
        onClick={() => void queueIndexing(memory)}
        style={{ cursor: "pointer", color: "#c4572f" }}
        aria-label="Retry search indexing for this memory"
      >
        <RotateCcw size={12} aria-hidden="true" />
        Retry indexing
      </button>
    );
  }

  if (status !== "indexing") return null;

  return (
    <span className="schip">
      <Loader2 size={12} className="animate-spin" aria-hidden="true" />
      Indexing…
    </span>
  );
}
