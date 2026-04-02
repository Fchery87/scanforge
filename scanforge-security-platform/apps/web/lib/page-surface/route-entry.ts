export interface HomeRouteInput {
  hasSession: boolean;
  hasOrg?: boolean;
  defaultOrgId?: string;
}

export function resolveHomeRoute(input: HomeRouteInput): string {
  if (!input.hasSession) return "/auth/sign-in";
  if (input.defaultOrgId) return `/dashboard/${input.defaultOrgId}`;
  return "/dashboard";
}
