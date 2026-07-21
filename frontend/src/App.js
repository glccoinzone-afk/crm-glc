import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth, VerticalProvider } from "@/context/AuthContext";
import AppLayout from "@/components/Layout/AppLayout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Leads from "@/pages/crm/Leads";
import Customers from "@/pages/crm/Customers";
import Customer360 from "@/pages/crm/Customer360";
import Pipeline from "@/pages/crm/Pipeline";
import Quotations from "@/pages/crm/Quotations";
import Orders from "@/pages/sales/Orders";
import Invoices from "@/pages/sales/Invoices";
import Products from "@/pages/inventory/Products";
import Stock from "@/pages/inventory/Stock";
import Suppliers from "@/pages/purchase/Suppliers";
import PurchaseOrders from "@/pages/purchase/PurchaseOrders";
import Deliveries from "@/pages/delivery/Deliveries";
import Employees from "@/pages/hr/Employees";
import Attendance from "@/pages/hr/Attendance";
import Leaves from "@/pages/hr/Leaves";
import Payroll from "@/pages/hr/Payroll";
import { ChartOfAccounts, Journal, GstReports, Expenses } from "@/pages/finance/Finance";
import { Projects, Tasks, Tickets, Documents, AuditLog, Settings } from "@/pages/misc/Misc";
import { Toaster } from "sonner";
import { Loader2 } from "lucide-react";

function Guard({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="min-h-screen grid place-items-center"><Loader2 className="animate-spin text-[hsl(var(--primary))]" /></div>;
  }
  if (!user) return <Navigate to="/login" replace />;
  return <AppLayout>{children}</AppLayout>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Guard><Dashboard /></Guard>} />
      <Route path="/crm/leads" element={<Guard><Leads /></Guard>} />
      <Route path="/crm/customers" element={<Guard><Customers /></Guard>} />
      <Route path="/crm/customers/:id" element={<Guard><Customer360 /></Guard>} />
      <Route path="/crm/pipeline" element={<Guard><Pipeline /></Guard>} />
      <Route path="/crm/quotations" element={<Guard><Quotations /></Guard>} />
      <Route path="/sales/orders" element={<Guard><Orders /></Guard>} />
      <Route path="/sales/invoices" element={<Guard><Invoices /></Guard>} />
      <Route path="/inventory/products" element={<Guard><Products /></Guard>} />
      <Route path="/inventory/stock" element={<Guard><Stock /></Guard>} />
      <Route path="/purchase/suppliers" element={<Guard><Suppliers /></Guard>} />
      <Route path="/purchase/orders" element={<Guard><PurchaseOrders /></Guard>} />
      <Route path="/delivery" element={<Guard><Deliveries /></Guard>} />
      <Route path="/hr/employees" element={<Guard><Employees /></Guard>} />
      <Route path="/hr/attendance" element={<Guard><Attendance /></Guard>} />
      <Route path="/hr/leaves" element={<Guard><Leaves /></Guard>} />
      <Route path="/hr/payroll" element={<Guard><Payroll /></Guard>} />
      <Route path="/finance/accounts" element={<Guard><ChartOfAccounts /></Guard>} />
      <Route path="/finance/journal" element={<Guard><Journal /></Guard>} />
      <Route path="/finance/gst" element={<Guard><GstReports /></Guard>} />
      <Route path="/finance/expenses" element={<Guard><Expenses /></Guard>} />
      <Route path="/projects" element={<Guard><Projects /></Guard>} />
      <Route path="/tasks" element={<Guard><Tasks /></Guard>} />
      <Route path="/tickets" element={<Guard><Tickets /></Guard>} />
      <Route path="/documents" element={<Guard><Documents /></Guard>} />
      <Route path="/audit" element={<Guard><AuditLog /></Guard>} />
      <Route path="/settings" element={<Guard><Settings /></Guard>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <VerticalProvider>
          <AppRoutes />
          <Toaster position="bottom-right" richColors closeButton />
        </VerticalProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
