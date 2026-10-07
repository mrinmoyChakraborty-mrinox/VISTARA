// Supabase JS client — auth only (live mode). In local demo mode there is no
// Supabase project: the backend accepts local demo credentials and the
// token lives in localStorage, never in a server bundle.
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

import { getEnv, getVistaMode, isEnvConfigured } from "@/lib/env";

const LOCAL_TOKEN_KEY = "vistara:local-token";
export const LOCAL_DEMO_TOKEN = "demo-token";

let client: SupabaseClient | null = null;

/**
 * Lazily-created Supabase client. Call only from client-side effects and
 * event handlers so prerendering never requires env configuration.
 */
export function getSupabaseClient(): SupabaseClient {
  if (client) return client;
  const env = getEnv();
  client = createClient(env.supabaseUrl, env.supabaseAnonKey);
  return client;
}

/** Current access token, or null when there is no session. Kept in memory. */
export async function getAccessToken(): Promise<string | null> {
  if (getVistaMode() === "local") return getLocalToken();
  const supabase = getSupabaseClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

/** Local demo credential (local mode only). Persisted across reloads. */
export function getLocalToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(LOCAL_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setLocalToken(token: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (token) window.localStorage.setItem(LOCAL_TOKEN_KEY, token);
    else window.localStorage.removeItem(LOCAL_TOKEN_KEY);
  } catch {
    // Storage is best-effort (private mode, quotas).
  }
}

/** True when local mode is configured enough to reach the backend. */
export function isLocalConfigured(): boolean {
  return getVistaMode() === "local" && isEnvConfigured();
}
