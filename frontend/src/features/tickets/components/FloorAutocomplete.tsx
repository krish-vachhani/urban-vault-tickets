import Autocomplete from "@mui/material/Autocomplete";
import TextField from "@mui/material/TextField";

import type { Floor } from "../../reference-data/types/referenceData.types";

type FloorAutocompleteProps = {
  floors: Floor[];
  selectedFloorIds: number[];
  onChange: (floorIds: number[]) => void;
  errorMessage?: string;
};

/** Multi-select of the Office's Floors, shown only when the Office has more than one. */
export function FloorAutocomplete({ floors, selectedFloorIds, onChange, errorMessage }: FloorAutocompleteProps) {
  const selectedFloors = floors.filter((floor) => selectedFloorIds.includes(floor.id));

  return (
    <Autocomplete
      multiple
      disableCloseOnSelect
      options={floors}
      value={selectedFloors}
      onChange={(_event, newFloors) => onChange(newFloors.map((floor) => floor.id))}
      getOptionLabel={(floor) => floor.name}
      isOptionEqualToValue={(option, value) => option.id === value.id}
      renderInput={(inputProps) => (
        <TextField
          {...inputProps}
          label="Floor(s)"
          required
          error={errorMessage !== undefined}
          helperText={errorMessage ?? "This office has multiple floors - please select where the issue is."}
        />
      )}
    />
  );
}
