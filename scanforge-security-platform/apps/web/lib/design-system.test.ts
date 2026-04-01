import test from "node:test";
import assert from "node:assert/strict";

import {
  scanForgeBodyClassName,
  scanForgeMetaThemeColor,
  scanForgeMotion,
  scanForgeRadii,
  scanForgeTokens,
} from "./design-system.ts";

test("defines the editorial-industrial surface palette for the app shell", () => {
  assert.deepEqual(
    {
      canvas: scanForgeTokens.canvas,
      panel: scanForgeTokens.panel,
      elevated: scanForgeTokens.elevated,
      border: scanForgeTokens.border,
      primaryText: scanForgeTokens.textPrimary,
      accent: scanForgeTokens.brandPrimary,
    },
    {
      canvas: "#141414",
      panel: "#22211f",
      elevated: "#1b1b1a",
      border: "#3a3631",
      primaryText: "#f3eee7",
      accent: "#b66a2c",
    }
  );
});

test("keeps the body shell classes aligned with the new visual direction", () => {
  assert.match(scanForgeBodyClassName, /\bmin-h-screen\b/);
  assert.match(scanForgeBodyClassName, /\bbg-background\b/);
  assert.match(scanForgeBodyClassName, /\btext-text-primary\b/);
  assert.match(scanForgeBodyClassName, /\bscanforge-noise\b/);
  assert.match(scanForgeBodyClassName, /\bscanforge-vignette\b/);
});

test("exposes shared motion and radius tokens for page-level reuse", () => {
  assert.deepEqual(scanForgeMotion, {
    fast: "160ms",
    base: "220ms",
    slow: "320ms",
    ease: "cubic-bezier(0.22, 1, 0.36, 1)",
  });

  assert.deepEqual(scanForgeRadii, {
    sm: "4px",
    md: "8px",
    lg: "12px",
    xl: "18px",
  });
});

test("sets a theme color that matches the darker application canvas", () => {
  assert.equal(scanForgeMetaThemeColor, "#141414");
});
