export function getSlugAdjustmentNotice(requestedSlug: string, actualSlug: string): string | null {
  if (!requestedSlug || !actualSlug || requestedSlug === actualSlug) {
    return null;
  }

  return `Requested slug "${requestedSlug}" was already taken, so ScanForge saved this organization as "${actualSlug}".`;
}

export function getSlugPreviewMessage(requestedSlug: string, availableSlug: string): string | null {
  if (!requestedSlug || !availableSlug) {
    return null;
  }

  if (requestedSlug === availableSlug) {
    return `This organization should be created as "${availableSlug}".`;
  }

  return `This slug is already taken. If you create the organization now, ScanForge will likely save it as "${availableSlug}".`;
}
