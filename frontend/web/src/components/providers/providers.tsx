"use client";

import type { ReactNode } from "react";

import { AuthProvider } from "@/components/providers/auth-provider";
import { CameraProvider } from "@/components/providers/camera-provider";
import { ChatProvider } from "@/components/providers/chat-provider";
import { QueryProvider } from "@/components/providers/query-provider";
import { Toaster } from "@/components/ui/sonner";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryProvider>
      <AuthProvider>
        <CameraProvider>
          <ChatProvider>
            {children}
            <Toaster />
          </ChatProvider>
        </CameraProvider>
      </AuthProvider>
    </QueryProvider>
  );
}
