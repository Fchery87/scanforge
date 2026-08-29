import { test } from "vitest";
import assert from "node:assert/strict";

import { summarizeNotificationGroups } from "./groups.ts";

test("groups unread finding notifications by type", () => {
  const groups = summarizeNotificationGroups([
    { id: "1", notification_type: "finding", is_read: false },
    { id: "2", notification_type: "finding", is_read: false },
  ]);

  assert.equal(groups[0]?.count, 2);
});
