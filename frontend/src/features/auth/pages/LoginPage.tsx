import { zodResolver } from "@hookform/resolvers/zod";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useLocation, useNavigate } from "react-router";
import { z } from "zod";

import { parseApiError } from "../../../shared/api/apiError";
import { ApiHealthIndicator } from "../../../shared/components/ApiHealthIndicator";
import { FormTextField } from "../../../shared/components/FormTextField";
import { LoadingIndicator } from "../../../shared/components/LoadingIndicator";
import { DemoAccountPicker } from "../components/DemoAccountPicker";
import { isDemoAccountPickerEnabled } from "../demoAccounts";
import { useAuth } from "../hooks/useAuth";

const loginSchema = z.object({
  email: z.email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});

type LoginFormValues = z.infer<typeof loginSchema>;

const DEFAULT_LANDING_PATH = "/tickets";

export function LoginPage() {
  const { status, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [loginErrorMessage, setLoginErrorMessage] = useState<string | null>(null);

  const { control, handleSubmit, setValue, formState } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  // Where the visitor was headed before being sent here, or the ticket list.
  const destination: string = location.state?.from?.pathname
    ? `${location.state.from.pathname}${location.state.from.search ?? ""}`
    : DEFAULT_LANDING_PATH;

  if (status === "loading") {
    return <LoadingIndicator label="Restoring your session" />;
  }
  if (status === "authenticated") {
    return <Navigate to={destination} replace />;
  }

  async function submitLogin(values: LoginFormValues) {
    setLoginErrorMessage(null);
    try {
      await login(values);
      void navigate(destination, { replace: true });
    } catch (error) {
      setLoginErrorMessage(parseApiError(error).message);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-4 p-4">
      <Paper className="flex flex-col gap-4 p-6" component="section" aria-labelledby="login-heading">
        <Typography id="login-heading" component="h1" variant="h5">
          Sign in to Urban Vault Tickets
        </Typography>

        {loginErrorMessage && <Alert severity="error">{loginErrorMessage}</Alert>}

        <form className="flex flex-col gap-4" noValidate onSubmit={(event) => void handleSubmit(submitLogin)(event)}>
          {isDemoAccountPickerEnabled() && (
            <DemoAccountPicker onSelectEmail={(email) => setValue("email", email, { shouldValidate: true })} />
          )}
          <FormTextField control={control} name="email" label="Email" type="email" autoComplete="username" />
          <FormTextField
            control={control}
            name="password"
            label="Password"
            type="password"
            autoComplete="current-password"
          />
          <Button type="submit" variant="contained" size="large" disabled={formState.isSubmitting}>
            {formState.isSubmitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </Paper>
      <div className="flex justify-center">
        <ApiHealthIndicator />
      </div>
    </main>
  );
}
