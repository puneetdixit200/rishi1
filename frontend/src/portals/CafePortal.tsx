import type { AuthUser } from "../auth/types";
import { allowedCafeSections } from "../portalRouting";
import { PortalFrame } from "./PortalFrame";

const LABELS: Record<string, string> = {
  dashboard: "Dashboard",
  orders: "Orders",
  pos: "POS",
  tables: "Tables",
  menu: "Menu",
  billing: "Billing",
  reports: "Reports",
  staff: "Staff",
  settings: "Settings",
  kitchen: "Kitchen",
};

type CafePortalProps = {
  user: AuthUser;
  pathname: string;
  onNavigate: (path: string) => void;
  onLogout: () => void;
};

export function CafePortal({ user, pathname, onNavigate, onLogout }: CafePortalProps) {
  const sections = user.server_role === "super_admin"
    ? ["dashboard", "orders", "pos", "tables", "menu", "billing", "reports", "staff", "settings", "kitchen"]
    : allowedCafeSections(user.server_role);
  const requested = pathname.split("/").filter(Boolean)[1] ?? sections[0] ?? "dashboard";
  const active = sections.includes(requested) ? requested : sections[0] ?? "dashboard";

  return (
    <PortalFrame
      title="Kalpvrik Cafe"
      subtitle="Cafe operations portal"
      user={user}
      items={sections.map((key) => ({ key, label: LABELS[key] ?? key }))}
      activeKey={active}
      onNavigate={(key) => onNavigate(`/cafe/${key}`)}
      onLogout={onLogout}
    >
      <section className="page-stack">
        <div className="page-header">
          <div>
            <p className="eyebrow">Cafe workspace</p>
            <h2>{LABELS[active]}</h2>
            <p className="page-description">
              This P3 shell is isolated to the Cafe venture. Operational menu, table and QR data arrives in P5.
            </p>
          </div>
        </div>
        <article className="panel wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Access scope</p>
              <h3>{user.company_name ?? "Selected Cafe venture"}</h3>
            </div>
          </div>
          <p className="page-description">
            Role: {user.server_role}. Company and branch authorization is enforced by the backend P2 scope boundary.
          </p>
        </article>
      </section>
    </PortalFrame>
  );
}
