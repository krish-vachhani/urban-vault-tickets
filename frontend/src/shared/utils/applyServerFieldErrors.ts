import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

import { NON_FIELD_ERRORS_KEY, type ApiErrorInfo } from "../api/apiError";

const VALIDATION_ERROR_CODE = "VALIDATION_ERROR";

/**
 * Shows backend validation errors next to the form fields they belong to.
 *
 * `fieldNames` maps an API field (e.g. `issue_ids`) to the form field that
 * displays it (e.g. `issues`). Returns the message for anything that has no
 * field to sit next to (object-level errors, permission and conflict errors),
 * or null when every error was attached to a field.
 */
export function applyServerFieldErrors<Values extends FieldValues>(
  apiError: ApiErrorInfo,
  setError: UseFormSetError<Values>,
  fieldNames: Record<string, Path<Values>>,
): string | null {
  if (apiError.code !== VALIDATION_ERROR_CODE) {
    return apiError.message;
  }

  const formLevelMessages: string[] = [];
  let hasFieldError = false;

  for (const [apiField, messages] of Object.entries(apiError.details)) {
    const formField = fieldNames[apiField];
    if (formField && apiField !== NON_FIELD_ERRORS_KEY) {
      setError(formField, { type: "server", message: messages.join(" ") });
      hasFieldError = true;
    } else {
      formLevelMessages.push(...messages);
    }
  }

  if (formLevelMessages.length > 0) {
    return formLevelMessages.join(" ");
  }
  return hasFieldError ? null : apiError.message;
}
