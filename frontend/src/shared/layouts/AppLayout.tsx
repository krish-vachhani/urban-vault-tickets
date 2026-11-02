import AppBar from "@mui/material/AppBar";
import Button from "@mui/material/Button";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import { Link as RouterLink, Outlet, useNavigate } from "react-router";

import { useAuth } from "../../features/auth/hooks/useAuth";

/** Header (brand, who is signed in, sign out) around every signed-in screen. */
export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function signOut() {
    await logout();
    void navigate("/login", { replace: true });
  }

  return (
    <>
      <AppBar position="static" component="header">
        <Toolbar className="flex-wrap gap-x-4 gap-y-1">
          <Typography
            component={RouterLink}
            to="/tickets"
            variant="h6"
            className="grow text-inherit no-underline"
            color="inherit"
          >
            Urban Vault Tickets
          </Typography>
          {user && (
            <Typography variant="body2" component="p">
              {user.name} ({user.role_label})
            </Typography>
          )}
          <Button color="inherit" onClick={() => void signOut()}>
            Sign out
          </Button>
        </Toolbar>
      </AppBar>
      <main className="mx-auto w-full max-w-4xl p-3 sm:p-6">
        <Outlet />
      </main>
    </>
  );
}
