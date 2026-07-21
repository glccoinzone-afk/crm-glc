import React from "react";
import Sidebar from "@/components/Layout/Sidebar";
import Topbar from "@/components/Layout/Topbar";

export default function AppLayout({ children }) {
  return (
    <div className="min-h-screen bg-[hsl(var(--background))]">
      <Sidebar />
      <div className="lg:pl-[288px]">
        <Topbar />
        <main className="glc-page">{children}</main>
      </div>
    </div>
  );
}
