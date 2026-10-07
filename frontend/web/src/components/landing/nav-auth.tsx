"use client";

import { useAuth } from "@/components/providers/auth-provider";

/** Nav auth state: "Log in" when logged out, "Open dashboard" when in. */
export function NavAuth() {
  const { user, loading } = useAuth();

  if (loading || !user) {
    if (loading) return null;
    return (
      <a
        href="/login"
        style={{ fontSize: ".9rem", color: "var(--mute)", padding: "8px 4px" }}
      >
        Log in
      </a>
    );
  }

  return (
    <a
      href="/dashboard"
      style={{ fontSize: ".9rem", color: "var(--mute)", padding: "8px 4px" }}
    >
      Open dashboard
    </a>
  );
}
