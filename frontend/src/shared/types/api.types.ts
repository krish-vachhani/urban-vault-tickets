export type IdName = {
  id: number;
  name: string;
};

export type UserRole = "CLIENT" | "FACILITY_MANAGER" | "DEPARTMENT_POC" | "WORKER";

/** A person as the API describes them in tickets, activity, and assignee lists. */
export type UserSummary = {
  id: number;
  name: string;
  role: UserRole;
  role_label: string;
};

/** Page-number paginated collection (README-api-conventions §5). */
export type PaginatedResponse<Item> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: Item[];
};

/** Small unpaginated reference-data collection (README-api-conventions §5). */
export type ResultsResponse<Item> = {
  results: Item[];
};
