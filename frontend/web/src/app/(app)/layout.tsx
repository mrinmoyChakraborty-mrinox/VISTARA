"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { AuroraBackground } from "@/components/landing/aurora-background";
import { AppTopbar } from "@/components/app/app-topbar";
import { StatusBar } from "@/components/app/status-bar";
import { useAuth } from "@/components/providers/auth-provider";

function ShellSkeleton() {
  return (
    <div className="app-skel" role="status" aria-label="Loading application">
      <div className="skel" style={{ height: 54, borderRadius: 999 }} />
      <div className="skel" style={{ height: 26 }} />
      <div className="skel" style={{ height: 220, borderRadius: 24 }} />
    </div>
  );
}

/**
 * Guarded shell for authenticated pages. Without a session, redirects to
 * /login?next=<path>. Shows backend health, socket, and processing state.
 */
export default function AppLayout({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [loading, user, router, pathname]);

  return (
    <>
      <AuroraBackground />
      <AppTopbar />
      <StatusBar />
      <main className="wrap" style={{ paddingTop: 28, paddingBottom: 72 }}>
        {loading || !user ? <ShellSkeleton /> : children}
      </main>
    </>
  );
}
