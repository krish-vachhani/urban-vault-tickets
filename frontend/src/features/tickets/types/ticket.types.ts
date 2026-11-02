import type { IdName, UserSummary } from "../../../shared/types/api.types";

export type WorkflowStage =
  | "PENDING_TECHNICIAN_ASSIGNMENT"
  | "PENDING_TECHNICIAN_ASSESSMENT"
  | "PENDING_DEPARTMENT_POC_REVIEW";

export type TicketStatus = "OPEN" | "TECHNICIAN_CLOSED" | "CLOSED";

export type AssessmentOutcome = "FULLY_RESOLVED" | "PARTIALLY_RESOLVED" | "CHANGE_REQUESTED";

export type TicketTab = "open" | "closed";

export type TicketOrdering = "created_at" | "-created_at";

/** A ticket card in the listing. */
export type TicketSummary = {
  id: number;
  ticket_number: string;
  client: IdName;
  client_office: IdName;
  issues: IdName[];
  floors: IdName[];
  workflow_stage: WorkflowStage;
  status: TicketStatus;
  created_by: UserSummary;
  created_at: string;
  current_department: IdName;
  current_assignees: UserSummary[];
  action_required: boolean;
};

/** What the backend says the signed-in user may do; used only to decide which controls to render. */
export type AvailableActions = {
  can_assign_worker: boolean;
  can_change_department: boolean;
  can_submit_assessment: boolean;
  can_mark_resolved: boolean;
  can_comment: boolean;
};

export type TicketAssessment = {
  outcome: AssessmentOutcome;
  submitted_by: UserSummary;
  submitted_at: string;
};

export type TicketDetail = TicketSummary & {
  description: string;
  origin_department: IdName;
  closed_by: UserSummary | null;
  closed_at: string | null;
  current_poc: UserSummary | null;
  current_worker: UserSummary | null;
  assessment: TicketAssessment | null;
  available_actions: AvailableActions;
};

export type WorkflowStageOption = {
  value: WorkflowStage;
  label: string;
};

/** Values for the listing's filter drop-downs, taken from the tickets the user can see. */
export type TicketFilterOptions = {
  clients: IdName[];
  departments: IdName[];
  facility_managers: IdName[];
  workflow_stages: WorkflowStageOption[];
};

/** Everything that selects one page of the ticket list. Optional values mean "no filter". */
export type TicketListParams = {
  tab: TicketTab;
  page: number;
  pageSize: number;
  search?: string;
  clientId?: number;
  departmentId?: number;
  facilityManagerId?: number;
  workflowStage?: WorkflowStage;
  ordering: TicketOrdering;
};

export type CreateTicketPayload = {
  client_office_id: number;
  issue_ids: number[];
  floor_ids?: number[];
  description?: string;
};

export type ActivityFilter = "ALL" | "ACTIONS" | "COMMENTS";

export type ActivityChange = {
  field: string;
  from: string;
  to: string;
};

/** One entry of the Activity feed: an action on the ticket or a comment. */
export type ActivityItem = {
  id: string;
  type: "ACTION" | "COMMENT";
  event_type: string | null;
  /** Null for events the system performed. */
  actor: UserSummary | null;
  description: string;
  change: ActivityChange | null;
  note: string | null;
  created_at: string;
};

export type AssignWorkerResult = {
  message: string;
  ticket_id: number;
  workflow_stage: WorkflowStage;
  worker: UserSummary;
};

export type ChangeDepartmentResult = {
  ticket_id: number;
  current_department: IdName;
  workflow_stage: WorkflowStage;
  status: TicketStatus;
};

export type SubmitAssessmentResult = {
  ticket_id: number;
  outcome: AssessmentOutcome;
  workflow_stage: WorkflowStage;
  status: TicketStatus;
};

export type MarkResolvedResult = {
  ticket_id: number;
  workflow_stage: WorkflowStage;
  status: TicketStatus;
  closed_by: UserSummary;
  closed_at: string;
};
