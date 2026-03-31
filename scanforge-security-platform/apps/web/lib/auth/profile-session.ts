export type ProfileAuthState = "pending" | "authenticated" | "unauthenticated";

export function resolveProfileAuthState(args: {
  isSessionPending: boolean;
  hasSession: boolean;
}): ProfileAuthState {
  if (args.isSessionPending) {
    return "pending";
  }

  return args.hasSession ? "authenticated" : "unauthenticated";
}
