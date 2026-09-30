import React, { createContext, useContext, useState } from "react";

const MobileNavCtx = createContext(null);

export function MobileNavProvider({ children }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const openMobile = () => setMobileOpen(true);
  const closeMobile = () => setMobileOpen(false);
  return (
    <MobileNavCtx.Provider value={{ mobileOpen, openMobile, closeMobile }}>
      {children}
    </MobileNavCtx.Provider>
  );
}

export const useMobileNav = () => useContext(MobileNavCtx);
