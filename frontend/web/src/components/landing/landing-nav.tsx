import { NAV_LINKS } from "@/lib/landing-data";
import { ShimmerButton } from "@/components/ui-fx/shimmer-button";
import { NavAuth } from "@/components/landing/nav-auth";
import { ThemeToggle } from "@/components/landing/theme-toggle";

export function LandingNav() {
  return (
    <nav>
      <a className="logo" href="#top">
        <b />
        Vistara
      </a>
      <div className="links">
        {NAV_LINKS.map((link) => (
          <a key={link.href} href={link.href}>
            {link.label}
          </a>
        ))}
      </div>
      <div className="right">
        <NavAuth />
        <ThemeToggle />
        <ShimmerButton href="#rewind">Try the demo</ShimmerButton>
      </div>
    </nav>
  );
}