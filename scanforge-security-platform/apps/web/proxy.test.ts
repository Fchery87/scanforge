import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

test("proxy does not log request cookies or emit debug console logs", () => {
  const source = readFileSync(new URL("./proxy.ts", import.meta.url), "utf8");

  assert.doesNotMatch(source, /request\.headers\.get\(['"]cookie['"]\)/);
  assert.doesNotMatch(source, /console\.log\(/);
});
