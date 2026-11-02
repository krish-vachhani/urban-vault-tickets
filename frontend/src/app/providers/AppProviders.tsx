import CssBaseline from "@mui/material/CssBaseline";
import GlobalStyles from "@mui/material/GlobalStyles";
import { StyledEngineProvider, ThemeProvider } from "@mui/material/styles";
import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { appTheme } from "../../shared/theme/theme";

type AppProvidersProps = {
  queryClient: QueryClient;
  children: ReactNode;
};

/**
 * Application-wide providers. The QueryClient is passed in so tests can supply
 * a fresh client per test. Routing is added by the caller (BrowserRouter in the
 * app, MemoryRouter in tests).
 */
export function AppProviders({ queryClient, children }: AppProvidersProps) {
  return (
    <StyledEngineProvider enableCssLayer>
      <GlobalStyles styles="@layer theme, base, mui, components, utilities;" />
      <ThemeProvider theme={appTheme}>
        <CssBaseline />
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      </ThemeProvider>
    </StyledEngineProvider>
  );
}
