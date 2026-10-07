import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthCardHost } from "@/components/auth/auth-card";
import { AuthFormSkeleton } from "@/components/auth/auth-skeleton";
import { DateCard } from "@/components/auth/date-card";
import { NewInCard } from "@/components/auth/new-in-card";

export const metadata: Metadata = { title: "Vistara — Log in" };

export default function LoginPage() {
  return (
    <>
      <div className="col">
        <Suspense fallback={<AuthFormSkeleton />}>
          <AuthCardHost mode="login" />
        </Suspense>
        <NewInCard />
      </div>
      <DateCard variant="login" />
    </>
  );
}
