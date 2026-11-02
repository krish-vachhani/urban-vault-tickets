import { isAxiosError } from "axios";

/** Field name → validation messages, as in the API error envelope (README-api-conventions §2). */
export type ApiErrorDetails = Record<string, string[]>;

export type ApiErrorInfo = {
  /** HTTP status, or null when the server could not be reached. */
  status: number | null;
  /** Stable machine-readable code; branch on this, never on `message`. */
  code: string;
  message: string;
  details: ApiErrorDetails;
};

export const NON_FIELD_ERRORS_KEY = "non_field_errors";

const NETWORK_ERROR_CODE = "NETWORK_ERROR";
const UNEXPECTED_ERROR_CODE = "UNEXPECTED_ERROR";
const NETWORK_ERROR_MESSAGE = "Cannot reach the server. Check your connection and try again.";
const UNEXPECTED_ERROR_MESSAGE = "Something went wrong. Please try again.";

function readDetails(rawDetails: unknown): ApiErrorDetails {
  if (typeof rawDetails !== "object" || rawDetails === null) {
    return {};
  }
  const details: ApiErrorDetails = {};
  for (const [field, messages] of Object.entries(rawDetails)) {
    if (Array.isArray(messages)) {
      details[field] = messages.filter((message): message is string => typeof message === "string");
    }
  }
  return details;
}

/** Turns any thrown value into the error envelope's fields so screens render errors one way. */
export function parseApiError(error: unknown): ApiErrorInfo {
  if (!isAxiosError(error)) {
    return { status: null, code: UNEXPECTED_ERROR_CODE, message: UNEXPECTED_ERROR_MESSAGE, details: {} };
  }
  if (!error.response) {
    return { status: null, code: NETWORK_ERROR_CODE, message: NETWORK_ERROR_MESSAGE, details: {} };
  }

  const status = error.response.status;
  const envelope: unknown = error.response.data?.error;
  if (typeof envelope === "object" && envelope !== null && "code" in envelope && "message" in envelope) {
    return {
      status,
      code: String(envelope.code),
      message: String(envelope.message),
      details: "details" in envelope ? readDetails(envelope.details) : {},
    };
  }
  return { status, code: UNEXPECTED_ERROR_CODE, message: UNEXPECTED_ERROR_MESSAGE, details: {} };
}
