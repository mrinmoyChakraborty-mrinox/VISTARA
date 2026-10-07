"use client";

import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/components/providers/auth-provider";
import { getObjectHistory, listEvents } from "@/lib/apiClient";
import { isEnvConfigured } from "@/lib/env";

function useAuthed() {
  const { accessToken, configured } = useAuth();
  return isEnvConfigured() && configured && accessToken !== null;
}

export function useEventsQuery() {
  const enabled = useAuthed();
  return useQuery({
    queryKey: ["events"],
    queryFn: () => listEvents(),
    enabled,
    retry: false,
  });
}

export function useObjectHistoryQuery(name: string | null) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: ["object-history", name],
    queryFn: () => getObjectHistory(name as string),
    enabled: enabled && !!name,
    retry: false,
  });
}
