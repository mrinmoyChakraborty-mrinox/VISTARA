"use client";

import { useEffect, useRef, useState } from "react";

import { fetchEvidenceBlob } from "@/lib/apiClient";

/**
 * Blob URL for one evidence record. Uses the signed Evidence.url directly
 * when present; otherwise fetches with the bearer token. Revokes object URLs
 * on unmount or when the id changes. Parents should key by evidence id so a
 * new record never flashes a stale thumbnail.
 */
export function useEvidenceBlobUrl(
  evidenceId: string | null,
  directUrl?: string,
): string | null {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const revokeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (directUrl || !evidenceId) return;
    let cancelled = false;
    revokeRef.current?.();
    revokeRef.current = null;
    fetchEvidenceBlob(evidenceId)
      .then(({ url, revoke }) => {
        if (cancelled) {
          revoke();
          return;
        }
        revokeRef.current = revoke;
        setBlobUrl(url);
      })
      .catch(() => {
        if (!cancelled) setBlobUrl(null);
      });
    return () => {
      cancelled = true;
    };
  }, [evidenceId, directUrl]);

  useEffect(
    () => () => {
      revokeRef.current?.();
      revokeRef.current = null;
    },
    [],
  );

  return directUrl ?? blobUrl;
}
