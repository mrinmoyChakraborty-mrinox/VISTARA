"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { VistaraMark } from "@/components/brand/vistara-mark";
import { useAuth } from "@/components/providers/auth-provider";
import { getSupabaseClient } from "@/lib/supabaseClient";

const GOOGLE_ENABLED =
  typeof process !== "undefined" &&
  process.env.NEXT_PUBLIC_ENABLE_GOOGLE === "true";

export function AuthCard({
  mode,
  next,
  oauthError,
}: {
  mode: "login" | "signup";
  next: string;
  oauthError: string | null;
}) {
  const router = useRouter();
  const { user, loading, signIn, signUp, configured, configError } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState<string | null>(
    oauthError ? "Google sign-in failed. Try email instead." : null,
  );
  const [errKey, setErrKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [go, setGo] = useState(false);
  const [knob, setKnob] = useState<"arrow" | "spinner" | "check">("arrow");
  const [ripples, setRipples] = useState(0);
  const [confirmSent, setConfirmSent] = useState(false);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const busyRef = useRef(false);

  useEffect(() => {
    if (!loading && user) router.replace(next);
  }, [loading, user, router, next]);

  useEffect(
    () => () => {
      timers.current.forEach(clearTimeout);
    },
    [],
  );

  const showErr = (message: string) => {
    setError(message);
    setErrKey((k) => k + 1);
  };

  const fail = (message: string) => {
    showErr(message);
    setBusy(false);
    setGo(false);
    setKnob("arrow");
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setError(null);
    if (!configured) {
      fail(configError ?? "Auth is not configured.");
      return;
    }
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
      showErr("Enter a valid e-mail address.");
      return;
    }
    if (password.length < 6) {
      showErr("Password must be at least 6 characters.");
      return;
    }
    if (mode === "signup" && password !== confirm) {
      showErr("Passwords do not match.");
      return;
    }
    busyRef.current = true;
    setBusy(true);
    setGo(true);
    setRipples((r) => r + 1);
    timers.current.push(
      setTimeout(() => {
        setKnob("spinner");
        void run();
      }, 450),
    );
  };

  const run = async () => {
    try {
      if (mode === "login") {
        const { error: authError } = await signIn(email.trim(), password);
        if (authError) {
          fail(friendlyError(authError));
          return;
        }
      } else {
        const res = await signUp(email.trim(), password);
        if (res.error) {
          fail(friendlyError(res.error));
          return;
        }
        if (res.needsConfirmation) {
          setKnob("check");
          timers.current.push(setTimeout(() => setConfirmSent(true), 700));
          return;
        }
      }
      setKnob("check");
      // The authed effect above performs the redirect.
    } catch {
      fail("Could not reach the auth service. Check your connection and retry.");
    }
  };

  const google = async () => {
    if (!GOOGLE_ENABLED) {
      showErr("Google sign-in is not connected in this preview.");
      return;
    }
    setError(null);
    try {
      const supabase = getSupabaseClient();
      const { error: authError } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: `${window.location.origin}/login?next=${encodeURIComponent(next)}`,
        },
      });
      if (authError) showErr(friendlyError(authError.message));
    } catch {
      showErr("Google sign-in is unavailable right now.");
    }
  };

  if (confirmSent) {
    return (
      <form className="glass login in" noValidate style={{ animationDelay: ".1s" }}>
        <div className="row">
          <span className="small logo" style={{ fontSize: "1rem" }}>
            <VistaraMark size={20} />
            Vistara
          </span>
          <Link className="link" href="/login">
            Log in
          </Link>
        </div>
        <h1>Check your email.</h1>
        <p className="sub">
          We sent a confirmation link to {email}. Open it, then come back and
          log in.
        </p>
        <Link className="g" href="/login" style={{ alignSelf: "start" }}>
          <i>→</i>Go to log in
        </Link>
        <div className="foot" style={{ marginTop: 14 }}>
          Please keep your session secure.
        </div>
      </form>
    );
  }

  return (
    <form
      className={`glass login in${mode === "signup" ? " su" : ""}`}
      noValidate
      style={{ animationDelay: ".1s" }}
      onSubmit={onSubmit}
    >
      <div className="row">
        <span className="small logo" style={{ fontSize: "1rem" }}>
          <VistaraMark size={20} />
          Vistara
        </span>
        <Link className="link" href={mode === "login" ? "/signup" : "/login"}>
          {mode === "login" ? "Sign up" : "Log in"}
        </Link>
      </div>

      <div className="row" style={{ margin: "22px 0 4px", alignItems: "flex-end" }}>
        <h1>{mode === "login" ? "Log in" : "Sign up"}</h1>
        <button type="button" className="g" onClick={google} aria-label="Continue with Google">
          <i>G</i>Google
        </button>
      </div>
      <p className="sub">
        {mode === "login"
          ? "Ask your camera what happened."
          : "Your first memory takes two minutes."}
      </p>

      <div className="f">
        <span className="ic" aria-hidden="true">
          @
        </span>
        <label style={{ position: "absolute", left: -9999 }} htmlFor={mode === "login" ? "login-email" : "signup-email"}>
          Email
        </label>
        <input
          id={mode === "login" ? "login-email" : "signup-email"}
          type="email"
          placeholder="e-mail address"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>

      <div className="f">
        <span className="ic" aria-hidden="true">
          🔑
        </span>
        <label style={{ position: "absolute", left: -9999 }} htmlFor={mode === "login" ? "login-password" : "signup-password"}>
          Password
        </label>
        <input
          id={mode === "login" ? "login-password" : "signup-password"}
          type={showPw ? "text" : "password"}
          placeholder="password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button
          type="button"
          className="mini"
          aria-pressed={showPw}
          onClick={() => setShowPw((v) => !v)}
        >
          {showPw ? "Hide" : "Show"}
        </button>
      </div>

      <div className="f confirm">
        <span className="ic" aria-hidden="true">
          🔑
        </span>
        <label style={{ position: "absolute", left: -9999 }} htmlFor="signup-confirm">
          Confirm password
        </label>
        <input
          id="signup-confirm"
          type={showPw ? "text" : "password"}
          placeholder="confirm password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
      </div>

      <div
        key={errKey}
        className={error ? "err show" : "err"}
        role="alert"
        aria-live="polite"
      >
        {error}
      </div>

      <div className="act">
        <p>
          Your camera preview and change detection run in your browser. Only
          gated, downscaled frames are sent. Evidence is returned only to you.{" "}
          <Link href="/#privacy">Learn more</Link>
        </p>
        <button
          className={go ? "sw go" : "sw"}
          type="submit"
          disabled={busy}
          aria-label={mode === "login" ? "Log in" : "Create account"}
        >
          <span className="k" aria-hidden="true">
            {knob === "spinner" ? <span className="sp" /> : knob === "check" ? "✓" : "→"}
          </span>
          {ripples > 0 && (
            <span
              key={ripples}
              className="rp"
              aria-hidden="true"
              style={{ left: 38, top: 14 }}
            />
          )}
        </button>
      </div>
      <div className="foot">Please keep your session secure.</div>
    </form>
  );
}

/**
 * Reads ?next= and ?error= on the client and renders the real form. Must be
 * rendered inside a Suspense boundary with a styled fallback so the scene,
 * cards, and skeleton prerender statically.
 */
export function AuthCardHost({ mode }: { mode: "login" | "signup" }) {
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/dashboard";
  const oauthError = searchParams.get("error");
  return <AuthCard mode={mode} next={next} oauthError={oauthError} />;
}

function friendlyError(message: string): string {
  const lower = message.toLowerCase();
  if (lower.includes("invalid login") || lower.includes("invalid credentials")) {
    return "Invalid email or password. Try again.";
  }
  if (lower.includes("confirm") || lower.includes("not confirmed") || lower.includes("verify")) {
    return "This email is not confirmed yet — check your inbox for the link.";
  }
  if (lower.includes("network") || lower.includes("fetch") || lower.includes("failed")) {
    return "Network error. Check your connection and retry.";
  }
  return message;
}
