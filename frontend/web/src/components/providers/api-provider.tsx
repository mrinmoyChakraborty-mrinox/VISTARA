"use client";

import { useMemo } from "react";

import {
  createCamera,
  deleteCamera,
  getHealth,
  getMemory,
  getObjectHistory,
  listCameras,
  listEvents,
  listMemories,
  postChat,
  postEmbedding,
  startCamera,
  stopCamera,
  fetchEvidenceBlob,
} from "@/lib/apiClient";

/**
 * Hook-based API provider: every protected call goes through apiFetch, which
 * injects the bearer token. Never hand-roll headers in a component.
 */
export function useApi() {
  return useMemo(
    () => ({
      getHealth,
      listCameras,
      createCamera,
      deleteCamera,
      startCamera,
      stopCamera,
      listMemories,
      getMemory,
      postEmbedding,
      getObjectHistory,
      listEvents,
      postChat,
      fetchEvidenceBlob,
    }),
    [],
  );
}

export type Api = ReturnType<typeof useApi>;
