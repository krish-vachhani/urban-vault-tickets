import type { AssessmentOutcome, WorkflowStage } from "./ticket.types";

/** Display labels from README-ticket-lifecycle §2 and §4. */
export const WORKFLOW_STAGE_LABELS: Record<WorkflowStage, string> = {
  PENDING_TECHNICIAN_ASSIGNMENT: "Pending Technician Assignment",
  PENDING_TECHNICIAN_ASSESSMENT: "Pending Technician Assessment",
  PENDING_DEPARTMENT_POC_REVIEW: "Pending Department POC Review",
};

export const ASSESSMENT_OUTCOME_LABELS: Record<AssessmentOutcome, string> = {
  FULLY_RESOLVED: "Mark Fully Resolved",
  PARTIALLY_RESOLVED: "Mark Partially Resolved",
  CHANGE_REQUESTED: "Suggest Department/Worker Change",
};

/** Wireframe wording shown next to each assessment option. */
export const ASSESSMENT_OUTCOME_DESCRIPTIONS: Record<AssessmentOutcome, string> = {
  FULLY_RESOLVED: "The issue has been fully resolved; no further action is needed.",
  PARTIALLY_RESOLVED: "I resolved my part, but another Department or Worker's scope is involved.",
  CHANGE_REQUESTED: "The issue is outside my scope and should go to the correct Department or Worker.",
};
