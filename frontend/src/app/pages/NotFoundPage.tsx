import Button from "@mui/material/Button";
import Typography from "@mui/material/Typography";
import { Link as RouterLink } from "react-router";

export function NotFoundPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-start gap-4 p-6">
      <Typography component="h1" variant="h4">
        Page not found
      </Typography>
      <Button component={RouterLink} to="/" variant="contained">
        Go to the start page
      </Button>
    </main>
  );
}
