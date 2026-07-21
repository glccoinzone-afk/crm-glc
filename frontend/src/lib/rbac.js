// Role-based module permissions (mirrors backend ROLE_PERMS).
export const ROLE_MODULES = {
  "Super Admin": ["*"],
  "Admin": ["*"],
  "Manager": ["dashboard", "crm", "sales", "inventory", "purchase", "delivery", "projects", "tasks", "tickets", "documents", "settings", "ocm"],
  "Support Executive": ["dashboard", "crm.customers", "tickets", "documents", "ocm.inbox", "ocm.contacts"],
  "Sales": ["dashboard", "crm", "sales", "inventory.products", "delivery", "documents", "ocm"],
  "Accounts": ["dashboard", "sales.invoices", "finance", "purchase", "documents", "hr.payroll"],
  "HR": ["dashboard", "hr", "documents"],
};

export function canAccess(role, moduleKey) {
  const perms = ROLE_MODULES[role] || ROLE_MODULES["Admin"];
  if (perms.includes("*")) return true;
  // Exact or parent match: "sales.invoices" allowed if "sales" or "sales.invoices" is in perms
  const parts = moduleKey.split(".");
  for (let i = parts.length; i > 0; i--) {
    const p = parts.slice(0, i).join(".");
    if (perms.includes(p)) return true;
  }
  return false;
}
