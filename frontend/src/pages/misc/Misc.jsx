import React, { useEffect, useState } from "react";
import { Plus, FolderKanban, LifeBuoy, FileArchive, ScrollText } from "lucide-react";
import { motion } from "framer-motion";
import api, { fmtDate, fmtInr } from "@/lib/glc";
import { PageHeader, DataGrid, StatusBadge, EmptyState } from "@/components/common/GlcUI";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Field, SelectField } from "@/pages/crm/Leads";

// ---------- Projects ----------
export function Projects() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.get("/projects").then((r) => setRows(r.data.items || [])).finally(() => setLoading(false)); }, []);
  const columns = [
    { key: "name", header: "Project", render: (r) => <span className="font-medium">{r.name}</span> },
    { key: "status", header: "Status", render: (r) => <StatusBadge value={r.status} /> },
    { key: "budget", header: "Budget", mono: true, align: "right", render: (r) => fmtInr(r.budget) },
    { key: "startDate", header: "Start", render: (r) => fmtDate(r.startDate) },
    { key: "endDate", header: "End", render: (r) => fmtDate(r.endDate) },
  ];
  return (
    <div className="space-y-6">
      <PageHeader testId="projects-page" title="Projects" subtitle="Cross-vertical initiatives with budgets and timelines" />
      {(!loading && rows.length === 0) ? <EmptyState icon={FolderKanban} title="No projects yet" /> : <DataGrid columns={columns} rows={rows} loading={loading} testId="projects-grid" />}
    </div>
  );
}

// ---------- Tasks Kanban ----------
const TASK_STAGES = [
  { key: "TODO", label: "To Do" },
  { key: "IN_PROGRESS", label: "In Progress" },
  { key: "REVIEW", label: "Review" },
  { key: "DONE", label: "Done" },
];
export function Tasks() {
  const [rows, setRows] = useState([]);
  const [projects, setProjects] = useState([]);
  const [dragged, setDragged] = useState(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", projectId: "", priority: "MEDIUM", status: "TODO", assignedToName: "" });

  const load = () => api.get("/tasks").then((r) => setRows(r.data.items || []));
  useEffect(() => { load(); api.get("/projects").then((r) => setProjects(r.data.items || [])); }, []);

  const move = async (t, status) => {
    if (t.status === status) return;
    await api.put(`/tasks/${t.id}`, { status });
    setRows((prev) => prev.map((x) => (x.id === t.id ? { ...x, status } : x)));
  };
  const save = async () => {
    const p = projects.find((x) => x.id === form.projectId);
    await api.post("/tasks", { ...form, projectName: p?.name });
    toast.success("Task added"); setOpen(false); load();
  };

  return (
    <div className="space-y-6">
      <PageHeader testId="tasks-page" title="Tasks" subtitle="Kanban board of team tasks across projects" actions={
        <button data-testid="new-task-btn" onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12.5px] font-medium bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary))]/90">
          <Plus size={14} /> New Task
        </button>
      }/>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {TASK_STAGES.map((s) => (
          <div
            key={s.key}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => dragged && move(dragged, s.key)}
            className="kanban-col p-3"
          >
            <div className="flex items-center justify-between px-1 mb-3">
              <div className="text-[13px] font-semibold text-slate-800">{s.label}</div>
              <span className="text-[11px] font-mono text-slate-500 bg-white px-1.5 py-0.5 rounded">{rows.filter((r) => r.status === s.key).length}</span>
            </div>
            <div className="space-y-2">
              {rows.filter((r) => r.status === s.key).map((t) => (
                <motion.div key={t.id} layout draggable onDragStart={() => setDragged(t)} onDragEnd={() => setDragged(null)}
                  className="bg-white rounded-xl border border-slate-200 p-3 cursor-grab hover:shadow-md hover:-translate-y-0.5 transition-transform"
                  data-testid={`task-${t.id}`}>
                  <div className="flex items-center justify-between">
                    <StatusBadge value={t.priority} />
                    <div className="text-[10.5px] text-slate-400">{fmtDate(t.dueDate)}</div>
                  </div>
                  <div className="text-[13.5px] font-medium text-slate-900 mt-2">{t.title}</div>
                  <div className="text-[11.5px] text-slate-500 mt-1">{t.projectName || "—"}</div>
                  {t.assignedToName && <div className="text-[11px] text-slate-400 mt-1">→ {t.assignedToName}</div>}
                </motion.div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md rounded-2xl">
          <DialogHeader><DialogTitle>New Task</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Field label="Title*" v={form.title} on={(v) => setForm({ ...form, title: v })} tid="task-title" />
            <label className="text-[11.5px] font-medium text-slate-600">Project
              <select value={form.projectId} onChange={(e) => setForm({ ...form, projectId: e.target.value })} className="mt-1 w-full h-10 px-3 rounded-lg border border-slate-200 text-[13px] bg-white">
                <option value="">—</option>
                {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
            <div className="grid grid-cols-2 gap-3">
              <SelectField label="Priority" v={form.priority} on={(v) => setForm({ ...form, priority: v })} opts={["LOW", "MEDIUM", "HIGH", "URGENT"]} />
              <SelectField label="Status" v={form.status} on={(v) => setForm({ ...form, status: v })} opts={["TODO", "IN_PROGRESS", "REVIEW", "DONE"]} />
            </div>
            <Field label="Assignee" v={form.assignedToName} on={(v) => setForm({ ...form, assignedToName: v })} />
          </div>
          <DialogFooter>
            <button onClick={() => setOpen(false)} className="px-3 py-2 rounded-lg text-[13px] text-slate-600 hover:bg-slate-100">Cancel</button>
            <button data-testid="save-task" onClick={save} className="px-3 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px]">Create</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---------- Tickets ----------
export function Tickets() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const load = () => { setLoading(true); api.get("/tickets").then((r) => setRows(r.data.items || [])).finally(() => setLoading(false)); };
  useEffect(load, []);
  const act = async (r, status) => { await api.put(`/tickets/${r.id}`, { status }); toast.success(status); load(); };

  const columns = [
    { key: "ticketNo", header: "Ticket", mono: true, render: (r) => <span className="font-medium">{r.ticketNo}</span> },
    { key: "subject", header: "Subject" },
    { key: "customerName", header: "Customer" },
    { key: "priority", header: "Priority", render: (r) => <StatusBadge value={r.priority} /> },
    { key: "status", header: "Status", render: (r) => <StatusBadge value={r.status} /> },
    { key: "assignedTo", header: "Assigned" },
    { key: "actions", header: "", align: "right", render: (r) => (
        <select onChange={(e) => act(r, e.target.value)} defaultValue={r.status} className="text-[11.5px] px-2 py-1 rounded-md border border-slate-200 bg-white">
          {["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      )
    },
  ];
  return (
    <div className="space-y-6">
      <PageHeader testId="tickets-page" title="Support Tickets" subtitle="Customer support desk with SLA-driven prioritisation" />
      {(!loading && rows.length === 0) ? <EmptyState icon={LifeBuoy} title="No tickets yet" /> : <DataGrid columns={columns} rows={rows} loading={loading} testId="tickets-grid" />}
    </div>
  );
}

// ---------- Documents ----------
export function Documents() {
  const [rows, setRows] = useState([]);
  useEffect(() => { api.get("/documents").then((r) => setRows(r.data.items || [])); }, []);

  const CAT_STYLE = { LEGAL: "bg-rose-50 text-rose-700", HR: "bg-emerald-50 text-emerald-700", FINANCE: "bg-amber-50 text-amber-700", VENDOR: "bg-blue-50 text-blue-700", GENERAL: "bg-slate-100 text-slate-700" };

  return (
    <div className="space-y-6">
      <PageHeader testId="documents-page" title="Document Vault" subtitle="Centralised business documents with categories" />
      {rows.length === 0 ? <EmptyState icon={FileArchive} title="No documents yet" /> : (
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
          {rows.map((d) => (
            <div key={d.id} className="bg-white rounded-2xl border border-slate-200/70 card-elev p-4 hover:-translate-y-0.5 transition-transform">
              <div className="w-10 h-10 rounded-lg bg-slate-100 grid place-items-center text-slate-500 mb-3">
                <FileArchive size={18} />
              </div>
              <div className="text-[13.5px] font-medium text-slate-900 truncate">{d.name}</div>
              <div className="text-[11px] text-slate-500 mt-0.5">{d.uploadedBy} · {fmtDate(d.createdAt)}</div>
              <div className="mt-3"><span className={`inline-block text-[10.5px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full ${CAT_STYLE[d.category] || CAT_STYLE.GENERAL}`}>{d.category}</span></div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------- Audit Log ----------
export function AuditLog() {
  const [rows, setRows] = useState([]);
  useEffect(() => { api.get("/audit").then((r) => setRows(r.data.items || [])); }, []);
  const columns = [
    { key: "createdAt", header: "Time", render: (r) => fmtDate(r.createdAt) },
    { key: "userId", header: "User", mono: true, render: (r) => (r.userId || "").slice(0, 8) },
    { key: "module", header: "Module" },
    { key: "action", header: "Action" },
    { key: "entityId", header: "Entity", mono: true, render: (r) => (r.entityId || "—").slice(0, 8) },
  ];
  return (
    <div className="space-y-6">
      <PageHeader testId="audit-page" title="Audit Log" subtitle="System-wide activity trail for accountability" />
      <DataGrid columns={columns} rows={rows} testId="audit-grid" empty="No audit entries." />
    </div>
  );
}

// ---------- Settings ----------
export function Settings() {
  const [c, setC] = useState({});
  const [users, setUsers] = useState([]);
  useEffect(() => {
    api.get("/settings/company").then((r) => setC(r.data || {}));
    api.get("/users").then((r) => setUsers(r.data.items || []));
  }, []);
  const save = async () => { await api.put("/settings/company", c); toast.success("Company profile saved"); };

  return (
    <div className="space-y-6">
      <PageHeader testId="settings-page" title="Settings" subtitle="Company profile, users and role permissions" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl border border-slate-200/70 card-elev p-6">
          <div className="text-[14px] font-semibold text-slate-900 mb-4">Company Profile</div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Name" v={c.name} on={(v) => setC({ ...c, name: v })} />
            <Field label="GSTIN" v={c.gst} on={(v) => setC({ ...c, gst: v })} />
            <Field label="PAN" v={c.pan} on={(v) => setC({ ...c, pan: v })} />
            <Field label="Email" v={c.email} on={(v) => setC({ ...c, email: v })} />
            <Field label="Phone" v={c.phone} on={(v) => setC({ ...c, phone: v })} />
            <Field label="Website" v={c.website} on={(v) => setC({ ...c, website: v })} />
          </div>
          <div className="mt-3">
            <Field label="Address" v={c.address} on={(v) => setC({ ...c, address: v })} />
          </div>
          <div className="mt-4">
            <button data-testid="save-company" onClick={save} className="px-3 py-2 rounded-lg bg-[hsl(var(--primary))] text-white text-[13px]">Save Company Profile</button>
          </div>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200/70 card-elev p-6">
          <div className="text-[14px] font-semibold text-slate-900 mb-4">Users & Roles</div>
          <div className="divide-y divide-slate-100">
            {users.map((u) => (
              <div key={u.id} className="py-3 flex items-center justify-between">
                <div>
                  <div className="text-[13.5px] font-medium text-slate-900">{u.name}</div>
                  <div className="text-[11.5px] text-slate-500">{u.email}</div>
                </div>
                <StatusBadge value={u.role?.toUpperCase().replace(/\s+/g, "_")} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
