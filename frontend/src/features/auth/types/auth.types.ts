import type { IdName, UserRole } from "../../../shared/types/api.types";

/** The signed-in user's profile from GET /auth/me/. */
export type CurrentUser = {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  role_label: string;
  department: IdName | null;
  clients: IdName[];
};

export type LoginCredentials = {
  email: string;
  password: string;
};

export type LoginResponse = {
  access: string;
};
