import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";
import { useController, type Control, type FieldPath, type FieldValues } from "react-hook-form";

import type { IdName } from "../types/api.types";

type FormSelectFieldProps<Values extends FieldValues> = {
  name: FieldPath<Values>;
  control: Control<Values>;
  label: string;
  options: IdName[];
  disabled?: boolean;
  helperText?: string;
  onValueChange?: (selectedId: number | null) => void;
};

/** A Material UI drop-down wired to React Hook Form. The form value is the selected id, or null. */
export function FormSelectField<Values extends FieldValues>({
  name,
  control,
  label,
  options,
  disabled,
  helperText,
  onValueChange,
}: FormSelectFieldProps<Values>) {
  const { field, fieldState } = useController({ name, control });

  function handleChange(rawValue: string) {
    const selectedId = rawValue === "" ? null : Number(rawValue);
    field.onChange(selectedId);
    onValueChange?.(selectedId);
  }

  return (
    <TextField
      select
      fullWidth
      label={label}
      name={field.name}
      value={field.value ?? ""}
      onChange={(event) => handleChange(event.target.value)}
      onBlur={field.onBlur}
      inputRef={field.ref}
      disabled={disabled}
      error={fieldState.invalid}
      helperText={fieldState.error?.message ?? helperText}
    >
      {options.map((option) => (
        <MenuItem key={option.id} value={option.id}>
          {option.name}
        </MenuItem>
      ))}
    </TextField>
  );
}
