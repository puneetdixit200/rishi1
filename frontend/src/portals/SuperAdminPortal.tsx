import { useEffect, useState } from "react";

import { activeVentureStorage, apiRequest } from "../api/client";
import type { AuthUser, BusinessType } from "../auth/types";
import { PortalFrame } from "./PortalFrame";

type Venture = {
  id: number;
  business_group_id: number;
  business_type: BusinessType;
  slug: string;
  code: string;
  name: string;
  legal_name: string;
  trade_name: string | null;
  is_active: boolean;
};

type VentureUser = {
  id: number;
  company_id: number | null;
  branch_id: number | null;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
};

type SuperAdminPortalProps = {
  user: AuthUser;
  token: string;
  pathname: string;
  onNavigate: (path: string) => void;
  onLogout: () => void;
};

export function SuperAdminPortal({ user, token, pathname, onNavigate, onLogout }: SuperAdminPortalProps) {
  const active = pathname.includes("/users") ? "users" : "ventures";
  const [ventures, setVentures] = useState<Venture[]>([]);
  const [users, setUsers] = useState<VentureUser[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    activeVentureStorage.clear();
    void apiRequest<Venture[]>("/ventures", {}, token)
      .then(setVentures)
      .catch((err: Error) => setError(err.message));
  }, [token]);

  useEffect(() => {
    if (active !== "users") return;
    void apiRequest<VentureUser[]>("/venture-users", {}, token)
      .then(setUsers)
      .catch((err: Error) => setError(err.message));
  }, [active, token]);

  const enterVenture = (venture: Venture) => {
    activeVentureStorage.set(venture.id);
    onNavigate(venture.business_type === "cafe" ? "/cafe/dashboard" : "/retail/overview");
  };

  return (
    <PortalFrame
      title="Super Admin"
      subtitle="Business group control plane"
      user={user}
      items={[{ key: "ventures", label: "Ventures" }, { key: "users", label: "Users" }]}
      activeKey={active}
      onNavigate={(key) => onNavigate(`/super-admin/${key}`)}
      onLogout={onLogout}
    >
      <section className="page-stack">
        <div className="page-header">
          <div>
            <p className="eyebrow">All Ventures</p>
            <h2>{active === "users" ? "Venture Users" : "Venture Selector"}</h2>
            <p className="page-description">Only Super Admin receives this global business-group view.</p>
          </div>
        </div>
        {error ? <article className="panel"><p>{error}</p></article> : null}
        {active === "ventures" ? (
          <section className="content-grid">
            {ventures.map((venture) => (
              <article className="panel" key={venture.id}>
                <p className="eyebrow">{venture.business_type}</p>
                <h3>{venture.name}</h3>
                <p className="page-description">{venture.legal_name}</p>
                <button className="logout-button" type="button" onClick={() => enterVenture(venture)}>
                  Open {venture.business_type === "cafe" ? "Cafe" : "Retail"} portal
                </button>
              </article>
            ))}
          </section>
        ) : (
          <article className="panel wide">
            <div className="panel-header"><h3>Business group users</h3></div>
            <div className="data-table-shell">
              <table>
                <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Company</th><th>Status</th></tr></thead>
                <tbody>
                  {users.map((item) => (
                    <tr key={item.id}>
                      <td>{item.name}</td><td>{item.email}</td><td>{item.role}</td>
                      <td>{item.company_id ?? "All"}</td><td>{item.is_active ? "Active" : "Inactive"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        )}
      </section>
    </PortalFrame>
  );
}
