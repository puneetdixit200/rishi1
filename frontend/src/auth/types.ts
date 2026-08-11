export type UserRole =
  | "super_admin"
  | "admin"
  | "store_manager"
  | "staff"
  | "order_taker"
  | "kitchen"
  | "analyst";

export type AuthUser = {
  id: number;
  business_group_id: number;
  company_id: number | null;
  name: string;
  email: string;
  role: UserRole;
  branch_id: number | null;
  permissions: string[];
  is_active: boolean;
};

export type LoginResponse = {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  user: AuthUser;
};
