import { z } from "zod";

import type { CreateTicketPayload } from "../types/ticket.types";
import { MAX_FREE_TEXT_LENGTH } from "./ticketActionSchemas";

/** An Issue as the form holds it. `departmentId` drives the one-Department-per-ticket rule. */
const issueOptionSchema = z.object({
  id: z.number(),
  name: z.string(),
  departmentId: z.number(),
});
export type IssueOption = z.infer<typeof issueOptionSchema>;

type TicketFormRules = {
  /** Facility Managers and Department POCs must describe the issue; Clients may leave it blank. */
  isDescriptionRequired: boolean;
  /** True when the chosen Office has several Floors, so the user must pick which are affected. */
  isFloorSelectionRequired: boolean;
};

/** Client-side validation for instant feedback. The API repeats every rule and stays authoritative. */
export function createTicketFormSchema({ isDescriptionRequired, isFloorSelectionRequired }: TicketFormRules) {
  return z
    .object({
      clientId: z.number({ error: "Select a client." }),
      clientOfficeId: z.number({ error: "Select an office." }),
      floorIds: z.array(z.number()),
      issues: z.array(issueOptionSchema).min(1, "Select at least one issue."),
      description: z.string().max(MAX_FREE_TEXT_LENGTH, `Description must be at most ${MAX_FREE_TEXT_LENGTH} characters.`),
    })
    .superRefine((values, context) => {
      if (isFloorSelectionRequired && values.floorIds.length === 0) {
        context.addIssue({ code: "custom", path: ["floorIds"], message: "Select at least one floor." });
      }
      if (isDescriptionRequired && values.description.trim() === "") {
        context.addIssue({ code: "custom", path: ["description"], message: "Describe the issue." });
      }
    });
}

export type TicketFormValues = z.infer<ReturnType<typeof createTicketFormSchema>>;

/**
 * The request body for POST /tickets/. The Client is not sent (the API derives it from the Office).
 * Floor ids are sent only when the user chose them; with one Floor the API attaches it automatically,
 * and with none it rejects any Floor ids.
 */
export function buildCreateTicketPayload(values: TicketFormValues, includeFloors: boolean): CreateTicketPayload {
  const trimmedDescription = values.description.trim();
  return {
    client_office_id: values.clientOfficeId,
    issue_ids: values.issues.map((issue) => issue.id),
    ...(includeFloors && { floor_ids: values.floorIds }),
    ...(trimmedDescription !== "" && { description: trimmedDescription }),
  };
}
