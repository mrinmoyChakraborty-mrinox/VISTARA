import Link from "next/link";
import type { ReactNode } from "react";

import { TabletopScene } from "@/components/auth/tabletop-scene";
import { ThemeToggle } from "@/components/landing/theme-toggle";

/**
 * Auth route-group layout. The tabletop scene stays mounted across /login
 * and /signup; only the cards swap.
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="auth2">
      <TabletopScene />
      <div className="top">
        <Link className="logo" href="/" aria-label="Vistara home">
          <b />
          Vistara
        </Link>
        <ThemeToggle />
      </div>
      <main>
        <div className="collage">{children}</div>
      </main>
    </div>
  );
}
