import { describe, expect, it } from "vitest";

import { formatDateTime } from "./formatDateTime";

describe("formatDateTime", () => {
  it("formats a morning timestamp like the wireframe, in local time", () => {
    // Built from local-time parts so the expectation holds in any time zone.
    const localMorning = new Date(2025, 9, 27, 11, 40).toISOString();
    expect(formatDateTime(localMorning)).toBe("27-Oct-2025 11:40 AM");
  });

  it("formats an afternoon timestamp with PM", () => {
    const localAfternoon = new Date(2025, 10, 2, 14, 5).toISOString();
    expect(formatDateTime(localAfternoon)).toBe("02-Nov-2025 02:05 PM");
  });
});
