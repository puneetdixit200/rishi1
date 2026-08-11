import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");

const entryShim = read("src/App.ts");
const portalRoot = read("src/PortalRoot.tsx");
const routing = read("src/portalRouting.ts");
const cafePortal = read("src/portals/CafePortal.tsx");
const superPortal = read("src/portals/SuperAdminPortal.tsx");

const assertions = [
  [entryShim.includes('export { default } from "./PortalRoot"'), "extensionless App entry must route to PortalRoot"],
  [portalRoot.includes('import("./App.tsx")'), "PortalRoot must preserve the original Retail App.tsx"],
  [routing.includes('"super-admin"') && routing.includes('"retail"') && routing.includes('"cafe"'), "all authenticated portal kinds must exist"],
  [routing.includes('user.company_business_type === "cafe"'), "Cafe portal selection must derive from server venture type"],
  [routing.includes('portal === "super-admin"') && routing.includes("return false"), "normal users must be blocked from Super Admin portal"],
  [routing.includes('user.company_business_type === "retail"'), "Retail portal access must derive from server venture type"],
  [routing.includes('role === "kitchen"') && routing.includes('["kitchen"]'), "Kitchen role must have preparation-only navigation"],
  [routing.includes('role === "order_taker"') && routing.includes('["orders"]'), "Order Taker must have order-only navigation"],
  [portalRoot.includes('/^\\/order\\/([^/]+)$/'), "public QR route must remain separate from authenticated portals"],
  [portalRoot.includes("Table ordering is not active yet"), "P3 must not activate public QR ordering"],
  [cafePortal.includes("P5"), "Cafe placeholders must defer operational menu/table/QR work to P5"],
  [superPortal.includes("activeVentureStorage.set"), "Super Admin venture selector must set explicit backend venture scope"],
];

for (const [passed, message] of assertions) {
  if (!passed) {
    console.error(`Portal verification failed: ${message}`);
    process.exit(1);
  }
}

console.log(`Portal verification passed: ${assertions.length} checks.`);
