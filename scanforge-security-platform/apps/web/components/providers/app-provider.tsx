"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { NeonAuthUIProvider } from "@neondatabase/auth/react";

import { authClient } from "@/lib/auth/client";

import { ThemeProvider } from "./theme-provider";
import { Toaster } from "../ui/toaster";

export function AppProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  return (
    <ThemeProvider>
      <NeonAuthUIProvider
        authClient={authClient as never}
        navigate={router.push}
        replace={router.replace}
        onSessionChange={router.refresh}
        Link={Link}
      >
        {children}
        <Toaster />
      </NeonAuthUIProvider>
    </ThemeProvider>
  );
}
