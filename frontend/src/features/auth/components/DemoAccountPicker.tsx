import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";

import { DEMO_ACCOUNTS } from "../demoAccounts";

type DemoAccountPickerProps = {
  onSelectEmail: (email: string) => void;
};

/** Development-only: pre-fills the email field with a seeded account. It does not sign anyone in. */
export function DemoAccountPicker({ onSelectEmail }: DemoAccountPickerProps) {
  return (
    <TextField
      select
      fullWidth
      label="Demo account (development only)"
      helperText="Fills in the email. Enter the demo password to sign in."
      value=""
      onChange={(event) => onSelectEmail(event.target.value)}
    >
      {DEMO_ACCOUNTS.map((account) => (
        <MenuItem key={account.email} value={account.email}>
          {account.name} — {account.roleLabel}
        </MenuItem>
      ))}
    </TextField>
  );
}
