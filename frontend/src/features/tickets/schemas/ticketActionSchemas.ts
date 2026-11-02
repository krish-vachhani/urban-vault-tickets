import { z } from "zod";

/** Matches the backend's limit for free-text fields (README-ticket-actions-api §13a). */
export const MAX_FREE_TEXT_LENGTH = 5000;

const freeText = (fieldLabel: string) =>
  z
    .string()
    .trim()
    .min(1, `${fieldLabel} is required.`)
    .max(MAX_FREE_TEXT_LENGTH, `${fieldLabel} must be at most ${MAX_FREE_TEXT_LENGTH} characters.`);

export const assignWorkerSchema = z.object({
  workerId: z.number({ error: "Select a worker." }),
});
export type AssignWorkerFormValues = z.infer<typeof assignWorkerSchema>;

export const changeDepartmentSchema = z.object({
  departmentId: z.number({ error: "Select a department." }),
  forwardingNote: freeText("A forwarding note"),
});
export type ChangeDepartmentFormValues = z.infer<typeof changeDepartmentSchema>;

export const assessmentSchema = z.object({
  outcome: z.enum(["FULLY_RESOLVED", "PARTIALLY_RESOLVED", "CHANGE_REQUESTED"], {
    error: "Choose one of the assessment options.",
  }),
});
export type AssessmentFormValues = z.infer<typeof assessmentSchema>;

export const commentSchema = z.object({
  body: freeText("A comment"),
});
export type CommentFormValues = z.infer<typeof commentSchema>;
