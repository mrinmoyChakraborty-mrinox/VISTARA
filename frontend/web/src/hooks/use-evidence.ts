"use client";

import { useEffect, useRef, useState } from "react";

import { fetchEvidenceBlob } from "@/lib/apiClient";

/**
 * Blob URL for one evidence record. Uses the signed Evidence.url directly
 * when present; otherwise fetches with the bearer token. Revokes object URLs
 * on unmount or when the id changes. Parents should key by evidence id so a
 * new record never flashes a stale thumbnail.
 *
 * `unavailable` is true when the backend honestly has no servable file
 * (local/offline metadata fallback, 404, or 403) — render an "unavailable"
 * state, not a loader. `url === null && !unavailable` means still loading.
 */
export function useEvidenceBlobUrl(
  evidenceId: string | null,
  directUrl?: string,
): { url: string | null; unavailable: boolean } {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const revokeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (directUrl || !evidenceId) return;
    let cancelled = false;
    revokeRef.current?.();
    revokeRef.current = null;
    setBlobUrl(null);
    setUnavailable(false);
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
        if (!cancelled) setUnavailable(true);
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

  if (directUrl) return { url: directUrl, unavailable: false };
  return { url: blobUrl, unavailable };
}
