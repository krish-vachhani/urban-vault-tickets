/**
 * Development-only convenience for the login screen: the seeded accounts from
 * README-seed-data §4, primary demo accounts first. Choosing one only pre-fills
 * the email; the user still signs in with the real password through the normal
 * login endpoint.
 */
export type DemoAccount = {
  name: string;
  email: string;
  roleLabel: string;
};

export const DEMO_ACCOUNTS: DemoAccount[] = [
  { name: "Chaitanya M", email: "chaitanya.m@urbanvault.test", roleLabel: "Client POC" },
  { name: "Chandan S", email: "chandan.s@urbanvault.test", roleLabel: "Facility Manager" },
  { name: "Dhananjaya Murthy", email: "dhananjaya.m@urbanvault.test", roleLabel: "Technical Manager" },
  { name: "Prakash Kumar", email: "prakash.k@urbanvault.test", roleLabel: "Technician" },
  { name: "Priya R", email: "priya.r@urbanvault.test", roleLabel: "Client POC (Harness, Acme)" },
  { name: "Neha K", email: "neha.k@urbanvault.test", roleLabel: "Client POC (Acme)" },
  { name: "Meera J", email: "meera.j@urbanvault.test", roleLabel: "Facility Manager" },
  { name: "Abdul", email: "abdul@urbanvault.test", roleLabel: "IT Manager" },
  { name: "Lakshmi N", email: "lakshmi.n@urbanvault.test", roleLabel: "Housekeeping Manager" },
  { name: "Suresh B", email: "suresh.b@urbanvault.test", roleLabel: "Electrical Manager" },
  { name: "Ravi T", email: "ravi.t@urbanvault.test", roleLabel: "Technician (Technical)" },
  { name: "Imran S", email: "imran.s@urbanvault.test", roleLabel: "Technician (IT)" },
  { name: "Kavya P", email: "kavya.p@urbanvault.test", roleLabel: "Technician (Housekeeping)" },
  { name: "Manoj E", email: "manoj.e@urbanvault.test", roleLabel: "Technician (Electrical)" },
];

/** The picker is shown only when the development flag is switched on (README-authentication §8). */
export function isDemoAccountPickerEnabled(): boolean {
  return import.meta.env.VITE_ENABLE_DEMO_ACCOUNTS === "true";
}
