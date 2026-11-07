"use client";

import { useEffect, useState } from "react";
import { AuthView } from "@neondatabase/auth/react";
import { safeAuthDestination } from "@/lib/auth/destination";

export function AuthViewClient({ path }: { path: string }) {
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  if (!isMounted) {
    return <div className="min-h-[28rem]" aria-hidden="true" />;
  }

  return <AuthView path={path} redirectTo={safeAuthDestination(new URLSearchParams(window.location.search).get("redirectTo"))} />;
}
