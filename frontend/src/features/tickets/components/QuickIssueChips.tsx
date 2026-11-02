import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";

import type { QuickIssue } from "../../reference-data/types/referenceData.types";
import type { IssueOption } from "../schemas/createTicketSchema";

type QuickIssueChipsProps = {
  quickIssues: QuickIssue[];
  selectedIssues: IssueOption[];
  onSelectIssue: (issue: IssueOption) => void;
};

/** "Quick Issues - tap to autofill": the Client's most frequent Issues as one-tap choices. */
export function QuickIssueChips({ quickIssues, selectedIssues, onSelectIssue }: QuickIssueChipsProps) {
  if (quickIssues.length === 0) {
    return null;
  }
  const selectedDepartmentId = selectedIssues[0]?.departmentId;

  return (
    <div className="flex flex-col gap-2">
      <Typography id="quick-issues-heading" variant="body2" color="text.secondary">
        Quick Issues - tap to autofill
      </Typography>
      <div role="group" aria-labelledby="quick-issues-heading" className="flex flex-wrap gap-2">
        {quickIssues.map((quickIssue) => {
          const isSelected = selectedIssues.some((issue) => issue.id === quickIssue.id);
          // A ticket's Issues must all belong to one Department.
          const isOtherDepartment =
            selectedDepartmentId !== undefined && quickIssue.department_id !== selectedDepartmentId;

          return (
            <Chip
              key={quickIssue.id}
              label={quickIssue.name}
              color={isSelected ? "primary" : "default"}
              variant={isSelected ? "filled" : "outlined"}
              disabled={isOtherDepartment}
              onClick={
                isSelected
                  ? undefined
                  : () =>
                      onSelectIssue({
                        id: quickIssue.id,
                        name: quickIssue.name,
                        departmentId: quickIssue.department_id,
                      })
              }
            />
          );
        })}
      </div>
    </div>
  );
}
