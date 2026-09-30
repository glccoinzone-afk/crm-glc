import React, { useEffect, useMemo, useState } from "react";
import api from "@/lib/glc";
import { PageHeader } from "@/components/common/GlcUI";

const STATUS_STYLE = {
  PRESENT: "bg-emerald-50 text-emerald-700",
  ABSENT: "bg-rose-50 text-rose-700",
  HALF_DAY: "bg-amber-50 text-amber-700",
  LATE: "bg-orange-50 text-orange-700",
};

export default function Attendance() {
  const [attn, setAttn] = useState([]);
  const [emps, setEmps] = useState([]);
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));

  useEffect(() => {
    api.get("/employees", { params: { limit: 200 } }).then((r) => setEmps(r.data.items || []));
  }, []);
  useEffect(() => {
    api.get("/attendance", { params: { month } }).then((r) => setAttn(r.data.items || []));
  }, [month]);

  const days = useMemo(() => {
    const [y, m] = month.split("-").map(Number);
    const last = new Date(y, m, 0).getDate();
    return Array.from({ length: last }, (_, i) => String(i + 1).padStart(2, "0"));
  }, [month]);

  const cell = (empId, day) => {
    const key = `${month}-${day}`;
    const a = attn.find((x) => x.employeeId === empId && x.date === key);
    return a?.status || null;
  };
  const cycle = ["PRESENT","ABSENT","HALF_DAY","LATE"];
  const mark = async (empId, day) => {
    const key = `${month}-${day}`;
    const cur = cell(empId, day);
    const next = cycle[(cycle.indexOf(cur) + 1) % cycle.length];
    await api.post("/attendance", { employeeId: empId, date: key, status: next });
    const r = await api.get("/attendance", { params: { month } });
    setAttn(r.data.items || []);
  };

  return (
    <div className="space-y-6">
      <PageHeader testId="attendance-page" title="Attendance" subtitle="Daily attendance grid across the team" actions={
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="h-10 px-3 rounded-lg border border-slate-200 text-[13px] bg-white" />
      }/>
      <div className="flex items-center gap-4 text-[11px] text-slate-500">
        <span className="font-medium text-slate-600">Click cell to mark:</span>
        <span className="flex items-center gap-1"><span className="w-5 h-5 rounded bg-emerald-50 text-emerald-700 text-[10px] font-bold grid place-items-center">P</span> Present</span>
        <span className="flex items-center gap-1"><span className="w-5 h-5 rounded bg-rose-50 text-rose-700 text-[10px] font-bold grid place-items-center">A</span> Absent</span>
        <span className="flex items-center gap-1"><span className="w-5 h-5 rounded bg-amber-50 text-amber-700 text-[10px] font-bold grid place-items-center">H</span> Half Day</span>
        <span className="flex items-center gap-1"><span className="w-5 h-5 rounded bg-orange-50 text-orange-700 text-[10px] font-bold grid place-items-center">L</span> Late</span>
      </div>
      <div className="bg-white rounded-2xl border border-slate-200/70 card-elev overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full text-[12px]">
            <thead className="bg-slate-50/70 sticky top-0">
              <tr>
                <th className="px-3 py-2 text-left text-[10.5px] uppercase tracking-wide text-slate-500 font-semibold sticky left-0 bg-slate-50/70 min-w-[180px]">Employee</th>
                {days.map((d) => <th key={d} className="px-2 py-2 text-center text-[10.5px] font-mono text-slate-500">{d}</th>)}
              </tr>
            </thead>
            <tbody>
              {emps.map((e) => (
                <tr key={e.id} className="border-b border-slate-50">
                  <td className="px-3 py-2 sticky left-0 bg-white">
                    <div className="font-medium text-slate-800">{e.name}</div>
                    <div className="text-[10.5px] text-slate-500 font-mono">{e.employeeId}</div>
                  </td>
                  {days.map((d) => {
                    const s = cell(e.id, d);
                    return (
                      <td key={d} className="px-1 py-1 text-center">
                        <button onClick={() => mark(e.id, d)} title={s || "Click to mark"} className="inline-block w-6 h-6 rounded-md text-[10px] font-semibold grid place-items-center cursor-pointer hover:ring-2 hover:ring-offset-1 hover:ring-[hsl(var(--primary))] transition-all ${s ? (STATUS_STYLE[s] || 'bg-slate-100 text-slate-600') : 'bg-slate-50 hover:bg-slate-100'}">
                          {s ? s[0] : ""}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
