// Browser-exposed environment. Only NEXT_PUBLIC_* variables may reach the
// browser. Server-only secrets (GROQ_API_KEY, SUPABASE_SERVICE_ROLE_KEY) must
// never appear here, in any client bundle, log, or commit.

export interface PublicEnv {
  supabaseUrl: string;
  supabaseAnonKey: string;
  backendUrl: string;
  wsUrl: string;
}

const REQUIRED: { key: keyof PublicEnv; name: string }[] = [
  { key: "supabaseUrl", name: "NEXT_PUBLIC_SUPABASE_URL" },
  { key: "supabaseAnonKey", name: "NEXT_PUBLIC_SUPABASE_ANON_KEY" },
  { key: "backendUrl", name: "NEXT_PUBLIC_BACKEND_URL" },
  { key: "wsUrl", name: "NEXT_PUBLIC_WS_URL" },
];

function readRaw(): Record<string, string | undefined> {
  return {
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL,
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL,
  };
}

/** True when every required public variable is present. Safe to call anywhere. */
export function isEnvConfigured(): boolean {
  const raw = readRaw();
  return REQUIRED.every(({ name }) => (raw[name] ?? "").trim().length > 0);
}

/** Names of the missing required public variables, if any. */
export function missingEnvVars(): string[] {
  const raw = readRaw();
  return REQUIRED.filter(({ name }) => (raw[name] ?? "").trim().length === 0).map(
    ({ name }) => name,
  );
}

/**
 * Validated public env. Throws a descriptive error when a variable is
 * missing. Call only from client-side effects and event handlers so static
 * prerendering never depends on backend configuration.
 */
export function getEnv(): PublicEnv {
  const missing = missingEnvVars();
  if (missing.length > 0) {
    throw new Error(
      `Missing required environment variables: ${missing.join(", ")}. ` +
        "Copy them from the deployment settings; the backend stays unreachable until then.",
    );
  }
  const raw = readRaw();
  return {
    supabaseUrl: raw.NEXT_PUBLIC_SUPABASE_URL!.replace(/\/$/, ""),
    supabaseAnonKey: raw.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    backendUrl: raw.NEXT_PUBLIC_BACKEND_URL!.replace(/\/$/, ""),
    wsUrl: raw.NEXT_PUBLIC_WS_URL!.replace(/\/$/, ""),
  };
}
