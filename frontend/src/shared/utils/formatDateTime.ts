const DATE_TIME_FORMAT_OPTIONS: Intl.DateTimeFormatOptions = {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: true,
};

function findPart(parts: Intl.DateTimeFormatPart[], type: Intl.DateTimeFormatPartTypes): string {
  return parts.find((part) => part.type === type)?.value ?? "";
}

/** Formats an ISO timestamp in the browser's local time as `27-Oct-2025 11:40 AM` (README-frontend-architecture §14). */
export function formatDateTime(isoTimestamp: string): string {
  const parts = new Intl.DateTimeFormat("en-GB", DATE_TIME_FORMAT_OPTIONS).formatToParts(new Date(isoTimestamp));
  const day = findPart(parts, "day");
  const month = findPart(parts, "month");
  const year = findPart(parts, "year");
  const hour = findPart(parts, "hour");
  const minute = findPart(parts, "minute");
  const dayPeriod = findPart(parts, "dayPeriod").toUpperCase();
  return `${day}-${month}-${year} ${hour}:${minute} ${dayPeriod}`;
}
