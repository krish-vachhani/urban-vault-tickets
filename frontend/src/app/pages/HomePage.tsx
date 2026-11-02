import Typography from "@mui/material/Typography";

import { ApiHealthIndicator } from "../../shared/components/ApiHealthIndicator";

/** Placeholder start page for the project scaffold; replaced by the ticket list later. */
export function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-start gap-4 p-6">
      <Typography component="h1" variant="h4">
        Urban Vault Tickets
      </Typography>
      <Typography color="text.secondary">Project scaffold is running.</Typography>
      <ApiHealthIndicator />
    </main>
  );
}
