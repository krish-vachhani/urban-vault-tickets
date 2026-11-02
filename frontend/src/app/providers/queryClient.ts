import { QueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";

/** Retry a failed read at most this many times, and only for transient failures. */
const MAX_QUERY_RETRIES = 2;
/** How long fetched data is treated as fresh before a background refetch. */
const DEFAULT_STALE_TIME_MS = 30_000;
const FIRST_SERVER_ERROR_STATUS = 500;

/**
 * Only network failures and 5xx responses are worth retrying. Authentication,
 * permission, not-found, conflict, and validation errors (4xx) will not change
 * on retry (README-frontend-architecture §9).
 */
export function isTransientRequestError(error: unknown): boolean {
  if (!isAxiosError(error)) {
    return false;
  }
  const responseStatus = error.response?.status;
  const isNetworkFailure = responseStatus === undefined;
  return isNetworkFailure || responseStatus >= FIRST_SERVER_ERROR_STATUS;
}

export function createAppQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: DEFAULT_STALE_TIME_MS,
        retry: (failureCount, error) => failureCount < MAX_QUERY_RETRIES && isTransientRequestError(error),
        refetchOnWindowFocus: false,
      },
      mutations: {
        // Business actions are not idempotent; never repeat them automatically.
        retry: false,
      },
    },
  });
}
