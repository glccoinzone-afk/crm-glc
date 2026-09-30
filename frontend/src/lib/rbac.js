export function canAccess(role, moduleKey, userModules) {
  const perms = Array.isArray(userModules) ? userModules : ["dashboard"];
  if (perms.includes("*")) return true;
  const parts = moduleKey.split(".");
  for (let i = parts.length; i > 0; i--) {
    const p = parts.slice(0, i).join(".");
    if (perms.includes(p)) return true;
  }
  return false;
}
