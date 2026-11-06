import test from "node:test";
import assert from "node:assert/strict";

import { explainFindingEvent } from "./event-explanation.ts";

test("explains a non-credited absence with the analyzer change", () => {
  const text = explainFindingEvent({
    event_type: "absence_not_credited",
    metadata_json: {
      blocked_by: ["analyzer_not_comparable"],
      baseline: { scanner_version: "1.0", parser_version: "p1", rules_digest: "a", fingerprint_version: "fp.v2" },
      current: { scanner_version: "1.1", parser_version: "p1", rules_digest: "a", fingerprint_version: "fp.v3" },
    },
  });
  assert.match(text ?? "", /not credited/i);
  assert.match(text ?? "", /scanner version 1\.0 to 1\.1/);
  assert.match(text ?? "", /fingerprint version fp\.v2 to fp\.v3/);
  assert.doesNotMatch(text ?? "", /parser version/);
});

test("explains an unknown analyzer baseline", () => {
  const text = explainFindingEvent({
    event_type: "absence_not_credited",
    metadata_json: { blocked_by: ["analyzer_baseline_unknown"] },
  });
  assert.match(text ?? "", /no recorded analyzer/i);
});

test("describes successor and predecessor links without implying transferred decisions", () => {
  const successor = explainFindingEvent({
    event_type: "successor_linked",
    metadata_json: { linked_finding_id: "f3" },
  });
  const predecessor = explainFindingEvent({
    event_type: "predecessor_linked",
    metadata_json: { linked_finding_id: "f2" },
  });
  assert.match(successor ?? "", /successor/i);
  assert.match(successor ?? "", /not transferred/i);
  assert.match(predecessor ?? "", /legacy/i);
  assert.match(predecessor ?? "", /not transferred/i);
});

test("returns null for events with no extra explanation", () => {
  assert.equal(explainFindingEvent({ event_type: "fixed", metadata_json: null }), null);
});
