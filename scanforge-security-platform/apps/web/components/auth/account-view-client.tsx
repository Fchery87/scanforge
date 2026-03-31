"use client";

import { useEffect, useState } from "react";
import { AccountView } from "@neondatabase/auth/react";

export function AccountViewClient({ path }: { path: string }) {
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  if (!isMounted) {
    return <div className="min-h-[32rem]" aria-hidden="true" />;
  }

  return <AccountView path={path} />;
}
