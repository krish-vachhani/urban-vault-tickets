import { describe, expect, it } from "vitest";

import { countActiveFilters, parseTicketListParams, toSearchParams } from "./ticketListParams";

describe("ticket list URL state", () => {
  it("uses the defaults for an empty URL", () => {
    expect(parseTicketListParams(new URLSearchParams())).toEqual({
      tab: "open",
      page: 1,
      pageSize: 10,
      search: undefined,
      clientId: undefined,
      departmentId: undefined,
      facilityManagerId: undefined,
      workflowStage: undefined,
      ordering: "-created_at",
    });
  });

  it("reads every parameter from the URL", () => {
    const params = parseTicketListParams(
      new URLSearchParams(
        "tab=closed&page=3&search=AC&client_id=1&department_id=2&facility_manager_id=5&workflow_stage=PENDING_TECHNICIAN_ASSESSMENT&ordering=created_at",
      ),
    );

    expect(params).toMatchObject({
      tab: "closed",
      page: 3,
      search: "AC",
      clientId: 1,
      departmentId: 2,
      facilityManagerId: 5,
      workflowStage: "PENDING_TECHNICIAN_ASSESSMENT",
      ordering: "created_at",
    });
    expect(countActiveFilters(params)).toBe(4);
  });

  it("ignores values the API would reject", () => {
    const params = parseTicketListParams(
      new URLSearchParams("tab=archived&page=0&client_id=abc&workflow_stage=NOPE&ordering=title"),
    );

    expect(params).toMatchObject({ tab: "open", page: 1, clientId: undefined, workflowStage: undefined, ordering: "-created_at" });
  });

  it("writes only non-default values back to the URL", () => {
    const params = parseTicketListParams(new URLSearchParams("tab=closed&page=2&search=lift"));

    expect(toSearchParams(params).toString()).toBe("tab=closed&page=2&search=lift");
    expect(toSearchParams(parseTicketListParams(new URLSearchParams())).toString()).toBe("");
  });
});
