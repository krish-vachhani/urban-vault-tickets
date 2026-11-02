import TextField, { type TextFieldProps } from "@mui/material/TextField";
import { useController, type Control, type FieldPath, type FieldValues } from "react-hook-form";

type FormTextFieldProps<Values extends FieldValues> = Omit<
  TextFieldProps,
  "name" | "value" | "onChange" | "onBlur" | "error" | "inputRef"
> & {
  name: FieldPath<Values>;
  control: Control<Values>;
};

/** A Material UI text field wired to React Hook Form, showing the field's validation message. */
export function FormTextField<Values extends FieldValues>({
  name,
  control,
  helperText,
  ...textFieldProps
}: FormTextFieldProps<Values>) {
  const { field, fieldState } = useController({ name, control });

  return (
    <TextField
      {...textFieldProps}
      name={field.name}
      value={field.value ?? ""}
      onChange={field.onChange}
      onBlur={field.onBlur}
      inputRef={field.ref}
      error={fieldState.invalid}
      helperText={fieldState.error?.message ?? helperText}
      fullWidth
    />
  );
}
