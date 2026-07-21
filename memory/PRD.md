# GLC Zone CRM + ERP — Product Requirements Document

## Original Problem Statement
Build a world-class enterprise CRM + ERP web application for GLC Zone based on the attached PRD. Follow every functional requirement in the document exactly, but redesign the entire experience with a premium modern light-mode SaaS interface. The UI should feel like a combination of Linear, Stripe Dashboard, Notion, Odoo 18, Zoho One, Salesforce Lightning, and Microsoft Dynamics 365 while maintaining its own identity. Use React 18 + Tailwind + shadcn/ui + Framer Motion + Lucide + charts (ApexCharts spec → Recharts implementation). Premium light-mode SaaS with soft white backgrounds, rounded 16–20px cards, subtle shadows, spacious layouts, smooth animations, skeleton loaders, floating sidebar, sticky topbar, advanced datagrids, dashboards, Kanban, timeline, customer 360, premium forms, glass only where appropriate. All 13 modules from the PRD.

## User Personas
- **Super Admin (Bishwajeet)** — cross-vertical control, financial oversight.
- **Admin (Riddhi)** — day-to-day operations, master data.
- **Manager (Dev)** — engineering / project management, task oversight.
- **Support Executive (Danish)** — helpdesk, QA.
- **Sales, Accounts, HR, Delivery** roles (seeded as employees) — future logins.

## Core Requirements (from PRD — implemented)
- 13 modules: Dashboard, CRM (Leads/Customers/Pipeline/Quotations), Sales (Orders/Invoices/Payments), Inventory (Products/Stock), Purchase (Suppliers/POs), Delivery, HR (Employees/Attendance/Leaves/Payroll), Finance (Chart of Accounts/Journal/GST/Expenses/P&L), Projects, Tasks, Support Tickets, Documents, Audit Log, Settings.
- India-first: GST (CGST/SGST/IGST), HSN codes, PAN/GSTIN capture, INR formatting.
- 8 verticals with functional switcher: GLC Fresh, GLC Store, GLC Garden, GLC Hardwares, Dhani Jewellers, India Mandi, GLC Property, GLC Legal.
- JWT auth, 4 seeded PRD users (all `Admin@123`).

## Architecture
- **Backend**: FastAPI + Motor (MongoDB), UUID string IDs, JWT (HS256), bcrypt.
- **Frontend**: React (CRA) + Tailwind + shadcn/ui + Framer Motion + Recharts + sonner.
- **Design tokens**: Obsidian Pine `#064E3B` + Terracotta accent `#EA580C`, Satoshi + IBM Plex Mono, 16–20px rounded, subtle shadows, glass topbar.

## What's Been Implemented (Feb 2026)
- **Backend (server.py + seed.py)**: 60+ endpoints across 13 modules, JWT auth, dashboard aggregator, quote→order→invoice→payment flow, PO→stock increment on RECEIVED, payroll with PF/ESI/TDS, GSTR-1 summary, journal balanced-entry check, activity/audit logging.
- **Rich seed data**: 4 users, 8 verticals, 14 products, 8 customers, 12 leads, 12 deals, 18 orders + auto-invoices with mixed paid/partial/unpaid, 12 employees, 7-day attendance, 6 leave requests, 5 suppliers, 15-entry CoA, 6 expenses, 10 deliveries, 3 projects, 12 tasks, 6 tickets, 4 documents, 5 notifications.
- **Frontend**: Floating sidebar + sticky glass topbar + vertical switcher + notifications drawer + profile menu. Executive dashboard with 10 KPI cards, revenue area chart, sales-by-vertical donut, lead funnel bar chart, recent orders table, low-stock alerts, pending approvals. Full pages for all 13 modules with premium data grids, Kanban (Pipeline, Tasks, Deliveries), Customer 360 with tabs (orders/invoices/payments/tickets), invoice preview modal, quotation builder with GST calc, attendance matrix grid, payroll generator, GST reports.
- **Testing**: Backend 38/38 passed. Frontend E2E verified across all modules; two useEffect Promise-cleanup bugs fixed by testing agent (Pipeline, Deliveries).

## Not Yet Implemented / Backlog
- **P1**
  - PDF export for invoices, quotations, payroll slips, GSTR-1 (currently HTML preview only).
  - Global command palette (⌘K) with search across leads/customers/orders.
  - File upload for documents (currently just metadata + placeholder link).
  - Role-based permissions matrix (all seeded users currently act as Admin).
  - Lead activity timeline UI (backend supports; UI shows only summary).
- **P2**
  - Real-time notifications via WebSocket.
  - Recruitment pipeline, assets tracker.
  - Balance sheet + trial balance from journal.
  - Timesheets, Gantt view on projects.
  - E-invoicing (IRN/QR code via GST portal).
  - WhatsApp / Email dispatch for invoices, OTP.

## Test Credentials
Stored at `/app/memory/test_credentials.md`. All seeded users use password `Admin@123`.

## Deployment Notes
- Backend service `backend` (supervisor) on `0.0.0.0:8001` with `/api` prefix.
- Frontend uses `REACT_APP_BACKEND_URL` and `/api` routing.
- MongoDB via `MONGO_URL` + `DB_NAME` (never hardcoded).
- Seed is idempotent (runs on startup, skips if collections already populated).
