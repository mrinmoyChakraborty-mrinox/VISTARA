import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthCardHost } from "@/components/auth/auth-card";
import { AuthFormSkeleton } from "@/components/auth/auth-skeleton";
import { DateCard } from "@/components/auth/date-card";
import { NewInCard } from "@/components/auth/new-in-card";

export const metadata: Metadata = { title: "Vistara — Sign up" };

export default function SignupPage() {
  return (
    <>
      <div className="col">
        <Suspense fallback={<AuthFormSkeleton />}>
          <AuthCardHost mode="signup" />
        </Suspense>
        <NewInCard />
      </div>
      <DateCard variant="signup" />
    </>
  );
}
