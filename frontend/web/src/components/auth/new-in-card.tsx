import Link from "next/link";

/** Solid dark card teasing Find by description. Links to /#vision. */
export function NewInCard() {
  return (
    <Link href="/#vision" className="dk in" style={{ animationDelay: ".22s" }}>
      <div>
        <h2>New in</h2>
        <small>Find by description</small>
      </div>
      <div className="d">
        Discover <span>→</span>
      </div>
    </Link>
  );
}
