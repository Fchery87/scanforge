export interface ActionAvailabilityInput {
  hasSelection: boolean;
  isLoading: boolean;
  hasError: boolean;
  userRole?: string;
  integrationConnected?: boolean;
}

export function deriveActionAvailability(input: ActionAvailabilityInput): {
  canAct: boolean;
  reason?: string;
} {
  if (input.isLoading) {
    return { canAct: false, reason: "Loading" };
  }
  if (input.hasError) {
    return { canAct: false, reason: "Error state" };
  }
  if (input.hasSelection && input.userRole !== "owner" && input.userRole !== "admin") {
    return { canAct: false, reason: "Insufficient permissions" };
  }
  if (input.integrationConnected === false) {
    return { canAct: false, reason: "Integration not connected" };
  }
  return { canAct: true };
}

export function isDestructiveActionAllowed(input: {
  userRole?: string;
  isLastOwner: boolean;
}): { allowed: boolean; reason?: string } {
  if (input.userRole !== "owner" && input.userRole !== "admin") {
    return { allowed: false, reason: "Insufficient permissions" };
  }
  if (input.isLastOwner) {
    return { allowed: false, reason: "Cannot remove the last owner" };
  }
  return { allowed: true };
}

export function isUnavailableAction(input: {
  integrationConnected?: boolean;
}): { unavailable: boolean; reason?: string } {
  if (input.integrationConnected === false) {
    return { unavailable: true, reason: "Integration not connected" };
  }
  return { unavailable: false };
}
