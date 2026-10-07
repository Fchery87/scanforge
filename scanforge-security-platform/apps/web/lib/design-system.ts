export const scanForgeTokens = {
  canvas: "#101210",
  elevated: "#171b18",
  panel: "#1c221e",
  surfaceSubtle: "#232a25",
  border: "#2a332c",
  borderStrong: "#3c4940",
  textPrimary: "#e7eee6",
  textSecondary: "#b7c2b6",
  textMuted: "#8e9b90",
  brandPrimary: "#d45a38",
  brandSecondary: "#8e9b90",
  brandAccent: "#d45a38",
  success: "#7d9a62",
  warning: "#c6a15a",
  danger: "#d45a38",
  info: "#8e9b90",
  severityCritical: "#d45a38",
  severityHigh: "#e08a3c",
  severityMedium: "#c6a15a",
  severityLow: "#7d9a62",
  severityInfo: "#8e9b90",
} as const;

export const scanForgeMotion = {
  fast: "120ms",
  base: "160ms",
  slow: "220ms",
  ease: "cubic-bezier(0.2, 0, 0, 1)",
} as const;

export const scanForgeRadii = {
  sm: "4px",
  md: "6px",
  lg: "8px",
  xl: "10px",
} as const;

export const scanForgeMetaThemeColor = scanForgeTokens.canvas;

export const scanForgeBodyClassName = [
  "min-h-screen",
  "bg-background",
  "text-text-primary",
  "antialiased",
].join(" ");
