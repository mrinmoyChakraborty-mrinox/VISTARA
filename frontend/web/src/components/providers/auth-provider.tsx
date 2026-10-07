"use client";

import type { Session, User } from "@supabase/supabase-js";
import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { UNAUTHORIZED_EVENT } from "@/lib/apiClient";
import { isEnvConfigured, missingEnvVars } from "@/lib/env";
import { getSupabaseClient } from "@/lib/supabaseClient";

interface AuthContextValue {
  user: User | null;
  session: Session | null;
  /** Access token, kept in memory and mirrored from the session. */
  accessToken: string | null;
  loading: boolean;
  configured: boolean;
  configError: string | null;
  signIn: (email: string, password: string) => Promise<{ error: string | null }>;
  signUp: (
    email: string,
    password: string,
  ) => Promise<{ error: string | null; needsConfirmation: boolean }>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [configured, setConfigured] = useState(true);
  const [configError, setConfigError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let subscription: { unsubscribe: () => void } | null = null;
    async function init() {
      if (!isEnvConfigured()) {
        if (cancelled) return;
        setConfigured(false);
        setConfigError(
          `Missing ${missingEnvVars().join(", ")}. The app shell renders, but auth and the backend stay unavailable.`,
        );
        setLoading(false);
        return;
      }
      const supabase = getSupabaseClient();
      try {
        const { data } = await supabase.auth.getSession();
        if (cancelled) return;
        setSession(data.session);
        setUser(data.session?.user ?? null);
        setAccessToken(data.session?.access_token ?? null);
        setLoading(false);
      } catch {
        if (!cancelled) setLoading(false);
      }
      if (cancelled) return;
      const { data } = supabase.auth.onAuthStateChange((_event, next) => {
        setSession(next);
        setUser(next?.user ?? null);
        setAccessToken(next?.access_token ?? null);
      });
      subscription = data.subscription;
    }
    void init();
    return () => {
      cancelled = true;
      subscription?.unsubscribe();
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const supabase = getSupabaseClient();
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    return { error: error?.message ?? null };
  }, []);

  const signUp = useCallback(async (email: string, password: string) => {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase.auth.signUp({ email, password });
    return {
      error: error?.message ?? null,
      needsConfirmation: !error && !data.session,
    };
  }, []);

  const signOut = useCallback(async () => {
    try {
      await getSupabaseClient().auth.signOut();
    } finally {
      setSession(null);
      setUser(null);
      setAccessToken(null);
    }
  }, []);

  // API layer signals unrecoverable 401s here; bounce back to /login.
  useEffect(() => {
    const onUnauthorized = (event: Event) => {
      const next =
        event instanceof CustomEvent && typeof event.detail === "string"
          ? event.detail
          : "/cameras";
      router.replace(`/login?next=${encodeURIComponent(next)}`);
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, [router]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      session,
      accessToken,
      loading,
      configured,
      configError,
      signIn,
      signUp,
      signOut,
    }),
    [user, session, accessToken, loading, configured, configError, signIn, signUp, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
