import { test } from "vitest";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";


test("proxy does not log request cookies or emit debug console logs", () => {
  const source = readFileSync("proxy.ts", "utf8");

  assert.doesNotMatch(source, /request\.headers\.get\(['"]cookie['"]\)/);
  assert.doesNotMatch(source, /console\.log\(/);
});
