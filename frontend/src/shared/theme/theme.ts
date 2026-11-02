import { createTheme } from "@mui/material/styles";

/** Shared MUI theme: colours, typography, and component defaults. */
export const appTheme = createTheme({
  palette: {
    primary: { main: "#1f4e79" },
    success: { main: "#2e7d32" },
    error: { main: "#c62828" },
    background: { default: "#f5f5f5" },
  },
  shape: { borderRadius: 8 },
  components: {
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: { root: { textTransform: "none" } },
    },
  },
});
