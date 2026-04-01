export const scanForgeTokens = {
  canvas: "#141414",
  elevated: "#1b1b1a",
  panel: "#22211f",
  surfaceSubtle: "#2a2825",
  border: "#3a3631",
  borderStrong: "#514a42",
  textPrimary: "#f3eee7",
  textSecondary: "#c9c0b4",
  textMuted: "#978d82",
  brandPrimary: "#b66a2c",
  brandSecondary: "#6f7c63",
  brandAccent: "#d6a14a",
  success: "#6e8b5d",
  warning: "#c8a33a",
  danger: "#c24a3a",
  info: "#7f8f98",
  severityCritical: "#c24a3a",
  severityHigh: "#d9742f",
  severityMedium: "#c8a33a",
  severityLow: "#6e8b5d",
  severityInfo: "#7f8f98",
} as const;

export const scanForgeMotion = {
  fast: "160ms",
  base: "220ms",
  slow: "320ms",
  ease: "cubic-bezier(0.22, 1, 0.36, 1)",
} as const;

export const scanForgeRadii = {
  sm: "4px",
  md: "8px",
  lg: "12px",
  xl: "18px",
} as const;

export const scanForgeMetaThemeColor = scanForgeTokens.canvas;

export const scanForgeBodyClassName = [
  "min-h-screen",
  "bg-background",
  "text-text-primary",
  "antialiased",
  "scanforge-noise",
  "scanforge-vignette",
].join(" ");
