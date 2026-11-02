import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";

import { parseApiError } from "../api/apiError";

type ErrorMessageProps = {
  /** Anything thrown by an API call. */
  error: unknown;
  /** Shown in front of the server's message, e.g. "Could not load tickets." */
  title: string;
  onRetry?: () => void;
};

/** An error alert for a failed request: what failed, why, and an optional Retry button. */
export function ErrorMessage({ error, title, onRetry }: ErrorMessageProps) {
  const { message } = parseApiError(error);

  return (
    <Alert
      severity="error"
      action={
        onRetry ? (
          <Button color="inherit" size="small" onClick={onRetry}>
            Retry
          </Button>
        ) : undefined
      }
    >
      <strong>{title}</strong> {message}
    </Alert>
  );
}
