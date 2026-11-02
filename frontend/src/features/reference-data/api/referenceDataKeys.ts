export type IssueSearchParams = {
  search: string;
  departmentId: number | null;
};

/** Query keys for reference data; each key includes every parent id and filter that changes the result. */
export const referenceDataKeys = {
  myClients: () => ["clients", "me"] as const,
  clientOffices: (clientId: number) => ["clients", clientId, "offices"] as const,
  quickIssues: (clientId: number) => ["clients", clientId, "quick-issues"] as const,
  officeFloors: (clientOfficeId: number) => ["client-offices", clientOfficeId, "floors"] as const,
  departments: () => ["departments"] as const,
  issues: (params: IssueSearchParams) => ["issues", params] as const,
};
