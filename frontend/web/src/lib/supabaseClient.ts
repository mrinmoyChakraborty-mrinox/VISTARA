// Supabase JS client — auth only. The client never calls Supabase database or
// storage APIs for memories, cameras, evidence, or chat.
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

import { getEnv } from "@/lib/env";

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
  const supabase = getSupabaseClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}
