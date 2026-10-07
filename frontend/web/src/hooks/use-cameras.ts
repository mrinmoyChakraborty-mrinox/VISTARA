"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { useAuth } from "@/components/providers/auth-provider";
import {
  createCamera,
  deleteCamera,
  listCameras,
  listMemories,
  startCamera,
  stopCamera,
  type ApiError,
} from "@/lib/apiClient";
import { isEnvConfigured } from "@/lib/env";

function useAuthed() {
  const { accessToken, configured } = useAuth();
  return isEnvConfigured() && configured && accessToken !== null;
}

function errorMessage(err: unknown, fallback: string): string {
  if (typeof err === "object" && err !== null && "message" in err) {
    return String((err as ApiError).message || fallback);
  }
  return fallback;
}

export function useCamerasQuery() {
  const enabled = useAuthed();
  return useQuery({
    queryKey: ["cameras"],
    queryFn: listCameras,
    enabled,
    retry: false,
  });
}

export function useMemoriesQuery() {
  const enabled = useAuthed();
  return useQuery({
    queryKey: ["memories"],
    queryFn: () => listMemories(),
    enabled,
    retry: false,
  });
}

export function useCreateCamera() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; source_type: "browser" }) =>
      createCamera(body),
    onSuccess: (camera) => {
      void queryClient.invalidateQueries({ queryKey: ["cameras"] });
      toast.success("Camera added", { description: camera.name });
    },
    onError: (err) => {
      toast.error("Could not add the camera", {
        description: errorMessage(err, "Check the backend and retry."),
      });
    },
  });
}

export function useDeleteCamera() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteCamera(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["cameras"] });
      toast.success("Camera deleted");
    },
    onError: (err) => {
      toast.error("Could not delete the camera", {
        description: errorMessage(err, "Check the backend and retry."),
      });
    },
  });
}

export function useStartCamera() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => startCamera(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["cameras"] });
    },
    onError: (err) => {
      toast.error("Could not start the camera session", {
        description: errorMessage(err, "Check the backend and retry."),
      });
    },
  });
}

export function useStopCamera() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => stopCamera(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["cameras"] });
    },
    onError: (err) => {
      toast.error("Could not stop the camera session", {
        description: errorMessage(err, "Check the backend and retry."),
      });
    },
  });
}
