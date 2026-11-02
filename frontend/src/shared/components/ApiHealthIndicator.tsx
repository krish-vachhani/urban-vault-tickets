import Chip from "@mui/material/Chip";
import { useQuery } from "@tanstack/react-query";

import { getApiHealth, healthQueryKey } from "../api/healthApi";

/** Small status chip showing whether the React app can reach the Django API. */
export function ApiHealthIndicator() {
  const healthQuery = useQuery({ queryKey: healthQueryKey, queryFn: getApiHealth });

  if (healthQuery.isPending) {
    return <Chip label="Checking API…" variant="outlined" />;
  }
  if (healthQuery.isError || healthQuery.data.status !== "ok") {
    return <Chip label="API unavailable" color="error" />;
  }
  return <Chip label="API connected" color="success" />;
}
