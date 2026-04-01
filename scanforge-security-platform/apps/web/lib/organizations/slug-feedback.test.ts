import test from "node:test";
import assert from "node:assert/strict";

import { getSlugAdjustmentNotice, getSlugPreviewMessage } from "./slug-feedback.ts";

test("returns no notice when the requested slug is preserved", () => {
  assert.equal(getSlugAdjustmentNotice("studio-eighty7", "studio-eighty7"), null);
});

test("returns a notice when the saved slug is auto-adjusted", () => {
  assert.equal(
    getSlugAdjustmentNotice("studio-eighty7", "studio-eighty7-2"),
    'Requested slug "studio-eighty7" was already taken, so ScanForge saved this organization as "studio-eighty7-2".'
  );
});

test("returns an availability message when the slug is open", () => {
  assert.equal(
    getSlugPreviewMessage("studio-eighty7", "studio-eighty7"),
    'This organization should be created as "studio-eighty7".'
  );
});

test("returns a fallback message when the slug would be adjusted", () => {
  assert.equal(
    getSlugPreviewMessage("studio-eighty7", "studio-eighty7-3"),
    'This slug is already taken. If you create the organization now, ScanForge will likely save it as "studio-eighty7-3".'
  );
});
