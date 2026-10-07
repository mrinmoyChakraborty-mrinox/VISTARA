"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";

import { VistaraMark } from "@/components/brand/vistara-mark";
import { ThemeToggle } from "@/components/landing/theme-toggle";
import { useAuth } from "@/components/providers/auth-provider";

/** Glass pill topbar in the landing-nav style for authenticated pages. */
export function AppTopbar() {
  const { user, signOut } = useAuth();
  const router = useRouter();

  const onSignOut = async () => {
    await signOut();
    router.push("/login");
  };

  return (
    <nav aria-label="Application">
      <Link className="logo" href="/" aria-label="Vistara home">
        <VistaraMark size={28} />
        Vistara
      </Link>
      <div className="links">
        <a href="/cameras">Cameras</a>
      </div>
      <div className="right">
        {user?.email && (
          <span
            className="mono mute"
            style={{ maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis" }}
            title={user.email}
          >
            {user.email}
          </span>
        )}
        <ThemeToggle />
        <button
          type="button"
          className="btn"
          onClick={onSignOut}
          aria-label="Log out"
          style={{ padding: "8px 16px", fontSize: ".85rem" }}
        >
          <LogOut size={15} aria-hidden="true" />
          Log out
        </button>
      </div>
    </nav>
  );
}
