import test from "node:test";
import assert from "node:assert/strict";

import {
  scanForgeBodyClassName,
  scanForgeMetaThemeColor,
  scanForgeMotion,
  scanForgeRadii,
  scanForgeTokens,
} from "./design-system.ts";

test("defines the field palette used by the operator shell", () => {
  assert.deepEqual(
    {
      canvas: scanForgeTokens.canvas,
      panel: scanForgeTokens.panel,
      elevated: scanForgeTokens.elevated,
      border: scanForgeTokens.border,
      primaryText: scanForgeTokens.textPrimary,
      signal: scanForgeTokens.brandPrimary,
    },
    {
      canvas: "#101210",
      panel: "#1c221e",
      elevated: "#171b18",
      border: "#2a332c",
      primaryText: "#e7eee6",
      signal: "#d45a38",
    }
  );
});

test("keeps the body classes on the document without decorative overlays", () => {
  assert.match(scanForgeBodyClassName, /\bmin-h-screen\b/);
  assert.match(scanForgeBodyClassName, /\bbg-background\b/);
  assert.match(scanForgeBodyClassName, /\btext-text-primary\b/);
  assert.doesNotMatch(scanForgeBodyClassName, /scanforge-noise/);
  assert.doesNotMatch(scanForgeBodyClassName, /scanforge-vignette/);
});

test("exposes short motion and tight radii for controls", () => {
  assert.deepEqual(scanForgeMotion, {
    fast: "120ms",
    base: "160ms",
    slow: "220ms",
    ease: "cubic-bezier(0.2, 0, 0, 1)",
  });

  assert.deepEqual(scanForgeRadii, {
    sm: "4px",
    md: "6px",
    lg: "8px",
    xl: "10px",
  });
});

test("sets the theme color to the field canvas", () => {
  assert.equal(scanForgeMetaThemeColor, "#101210");
});
