import Autocomplete from "@mui/material/Autocomplete";
import TextField from "@mui/material/TextField";
import { useState } from "react";

import { useIssueSearch } from "../../reference-data/hooks/useReferenceData";
import type { IssueOption } from "../schemas/createTicketSchema";

type IssueAutocompleteProps = {
  selectedIssues: IssueOption[];
  onChange: (issues: IssueOption[]) => void;
  errorMessage?: string;
};

/** Searchable multi-select of Issues. Once one is chosen, the search is limited to its Department. */
export function IssueAutocomplete({ selectedIssues, onChange, errorMessage }: IssueAutocompleteProps) {
  const [searchText, setSearchText] = useState("");
  const departmentId = selectedIssues[0]?.departmentId ?? null;
  const issueSearchQuery = useIssueSearch({ search: searchText, departmentId });

  const foundIssues: IssueOption[] = (issueSearchQuery.data ?? []).map((issue) => ({
    id: issue.id,
    name: issue.name,
    departmentId: issue.department.id,
  }));
  // Selected Issues stay in the option list even when the current search no longer returns them.
  const unselectedFoundIssues = foundIssues.filter((found) => !selectedIssues.some((chosen) => chosen.id === found.id));
  const options = [...selectedIssues, ...unselectedFoundIssues];

  return (
    <Autocomplete
      multiple
      disableCloseOnSelect
      options={options}
      value={selectedIssues}
      onChange={(_event, newIssues) => onChange(newIssues)}
      inputValue={searchText}
      onInputChange={(_event, newSearchText) => setSearchText(newSearchText)}
      // The server already filtered by the search text.
      filterOptions={(allOptions) => allOptions}
      getOptionLabel={(issue) => issue.name}
      // Until the Department-restricted search returns, earlier options must not be selectable.
      getOptionDisabled={(issue) => departmentId !== null && issue.departmentId !== departmentId}
      isOptionEqualToValue={(option, value) => option.id === value.id}
      loading={issueSearchQuery.isFetching}
      noOptionsText={issueSearchQuery.isError ? "Could not search issues." : "No matching issues."}
      renderInput={(inputProps) => (
        <TextField
          {...inputProps}
          label="Issue(s)"
          placeholder="Type or search issue"
          required
          error={errorMessage !== undefined}
          helperText={errorMessage}
        />
      )}
    />
  );
}
