import type { AuthUser as LegacyAuthUser, UserRole as LegacyUserRole } from "../types";

export type ServerUserRole =
  | LegacyUserRole
  | "super_admin"
  | "order_taker"
  | "kitchen";

export type ServerAuthUser = {
  id: number;
  business_group_id: number;
  company_id: number | null;
  name: string;
  email: string;
  role: ServerUserRole;
  branch_id: number | null;
  permissions: string[];
  is_active: boolean;
};

export type AuthUser = Omit<LegacyAuthUser, "role"> & {
  business_group_id: number;
  company_id: number | null;
  permissions: string[];
  /** Real backend role. P3 uses this to select the correct portal shell. */
  server_role: ServerUserRole;
  /** Temporary P2 role used only by the pre-P3 Retail navigation shell. */
  role: LegacyUserRole;
};

export type ServerLoginResponse = {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  user: ServerAuthUser;
};

export type LoginResponse = Omit<ServerLoginResponse, "user"> & {
  user: AuthUser;
};

export function legacyShellRole(role: ServerUserRole): LegacyUserRole {
  if (role === "super_admin") return "admin";
  if (role === "order_taker" || role === "kitchen") return "staff";
  return role;
}

export function normalizeAuthUser(user: ServerAuthUser): AuthUser {
  return {
    ...user,
    server_role: user.role,
    role: legacyShellRole(user.role),
  };
}
