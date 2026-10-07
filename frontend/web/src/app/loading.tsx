import { BrandLoader } from "@/components/loader/BrandLoader";

/** Route-level Suspense fallback: the lighter inline loader. */
export default function Loading() {
  return (
    <main
      className="wrap"
      style={{ display: "grid", placeItems: "center", minHeight: "62vh" }}
    >
      <BrandLoader variant="inline" />
    </main>
  );
}
