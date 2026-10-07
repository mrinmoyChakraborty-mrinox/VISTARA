"use client";

import { useEffect, useState } from "react";

import {
  getEmbeddingState,
  queueIndexing,
  reloadEmbeddingModel,
  subscribeEmbedding,
  type IndexStatus,
} from "@/lib/embeddingQueue";
import type { Memory } from "@/types/domain";

/** Live background-indexing status for one memory. */
export function useIndexingStatus(memoryId: string | null): IndexStatus | null {
  const [status, setStatus] = useState<IndexStatus | null>(null);

  useEffect(() => {
    if (!memoryId) return;
    return subscribeEmbedding((state) => {
      setStatus(state.statusById[memoryId] ?? null);
    });
  }, [memoryId]);

  return status;
}

/** Model capability/progress for the settings page. */
export function useEmbeddingStats() {
  const [stats, setStats] = useState(getEmbeddingState);

  useEffect(() => subscribeEmbedding(setStats), []);

  return { ...stats, reload: reloadEmbeddingModel, index: queueIndexing };
}

export type { Memory };
