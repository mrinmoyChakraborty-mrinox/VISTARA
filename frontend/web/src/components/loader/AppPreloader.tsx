"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/providers/auth-provider";
import { BrandLoader } from "@/components/loader/BrandLoader";
import { cn } from "@/lib/utils";

const BOOT_KEY = "vistara-booted";
const MIN_MS = 800;
const MAX_MS = 3000;
const EXIT_MS = 620;

function lockScroll() {
  const gap = window.innerWidth - document.documentElement.clientWidth;
  document.body.style.overflow = "hidden";
  if (gap > 0) document.body.style.paddingRight = `${gap}px`;
}

function unlockScroll() {
  document.body.style.overflow = "";
  document.body.style.paddingRight = "";
}

/**
 * In-app navigation feedback: a 3px top bar plus a brief dot overlay.
 * The full aperture loader only ever appears on hard loads.
 */
function RouteProgress() {
  const pathname = usePathname();
  const [active, setActive] = useState(false);
  const [width, setWidth] = useState(0);
  const [dot, setDot] = useState(false);
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    setActive(true);
    setDot(true);
    setWidth(15);
    const t1 = window.setTimeout(() => setWidth(85), 40);
    const t2 = window.setTimeout(() => {
      setDot(false);
      setWidth(100);
    }, 250);
    const t3 = window.setTimeout(() => {
      setActive(false);
      setWidth(0);
    }, 600);
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
      window.clearTimeout(t3);
    };
  }, [pathname]);

  if (!active && !dot) return null;

  return (
    <>
      <div
        className={cn("route-bar", active && "on")}
        aria-hidden="true"
        style={{ width: `${width}%` }}
      />
      <div className={cn("route-dot", dot && "on")} aria-hidden="true">
        <span className="route-pulse" />
      </div>
    </>
  );
}

/**
 * Full-screen boot controller. Progress is real: font loading, window load,
 * and the first AuthProvider session resolution. Minimum 800ms visible,
 * hard cap 3000ms, shown once per browser session.
 */
export function AppPreloader() {
  const { loading: authLoading } = useAuth();
  const [progress, setProgress] = useState(0.12);
  const [leaving, setLeaving] = useState(false);
  const [gone, setGone] = useState(false);
  const signals = useRef({ fonts: false, load: false, auth: false });
  const authRef = useRef(authLoading);
  const start = useRef(0);
  const finished = useRef(false);

  useEffect(() => {
    authRef.current = authLoading;
  }, [authLoading]);

  // Repeat visits in the same session skip the full loader instantly.
  useEffect(() => {
    let alive = true;
    const frame = window.requestAnimationFrame(() => {
      if (!alive) return;
      try {
        if (window.sessionStorage.getItem(BOOT_KEY)) setGone(true);
      } catch {
        // sessionStorage unavailable — show the loader normally.
      }
    });
    return () => {
      alive = false;
      window.cancelAnimationFrame(frame);
    };
  }, []);

  useEffect(() => {
    if (gone) return;
    start.current = Date.now();
    lockScroll();
    let cancelled = false;

    const fonts =
      typeof document !== "undefined" &&
      "fonts" in document &&
      document.fonts
        ? document.fonts
        : null;
    if (!fonts) {
      signals.current.fonts = true;
    } else {
      void fonts.ready.then(
        () => {
          signals.current.fonts = true;
        },
        () => {
          signals.current.fonts = true;
        },
      );
    }

    const markLoad = () => {
      signals.current.load = true;
    };
    if (document.readyState === "complete") {
      signals.current.load = true;
    } else {
      window.addEventListener("load", markLoad, { once: true });
    }

    const tick = () => {
      if (cancelled || finished.current) return;
      const s = signals.current;
      if (!authRef.current) s.auth = true;
      const p = Math.min(
        1,
        0.12 + (s.fonts ? 0.33 : 0) + (s.load ? 0.3 : 0) + (s.auth ? 0.25 : 0),
      );
      const elapsed = Date.now() - start.current;
      setProgress(p);
      const ready =
        (s.fonts && s.load && s.auth && elapsed >= MIN_MS) ||
        elapsed >= MAX_MS;
      if (!ready) return;
      finished.current = true;
      setProgress(1);
      window.setTimeout(() => {
        if (cancelled) return;
        setLeaving(true);
        document.body.classList.add("boot-flash");
        window.setTimeout(() => {
          if (cancelled) return;
          document.body.classList.remove("boot-flash");
          unlockScroll();
          setGone(true);
          try {
            window.sessionStorage.setItem(BOOT_KEY, "1");
          } catch {
            // Non-fatal; the loader simply shows again next load.
          }
        }, EXIT_MS);
      }, 160);
    };

    const id = window.setInterval(tick, 100);
    tick();
    return () => {
      cancelled = true;
      window.clearInterval(id);
      window.removeEventListener("load", markLoad);
      unlockScroll();
    };
  }, [gone]);

  if (gone) return <RouteProgress />;

  return (
    <>
      <BrandLoader variant="full" progress={progress} leaving={leaving} />
      <RouteProgress />
    </>
  );
}
