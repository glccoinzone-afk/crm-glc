import React, { useEffect, useState } from "react";
import { Truck } from "lucide-react";
import api, { fmtDate } from "@/lib/glc";
import { PageHeader, EmptyState, StatusBadge } from "@/components/common/GlcUI";
import { toast } from "sonner";

const LANES = [
  { key: "PENDING", label: "Pending" },
  { key: "ASSIGNED", label: "Assigned" },
  { key: "IN_TRANSIT", label: "In Transit" },
  { key: "DELIVERED", label: "Delivered" },
];

export default function Deliveries() {
  const [rows, setRows] = useState([]);
  const load = () => api.get("/deliveries").then((r) => setRows(r.data.items || []));
  useEffect(load, []);

  const move = async (d, status) => {
    await api.put(`/deliveries/${d.id}`, { status });
    toast.success(`Moved to ${status.replace("_", " ")}`);
    load();
  };

  const byLane = (l) => rows.filter((d) => d.status === l);

  return (
    <div className="space-y-6">
      <PageHeader testId="deliveries-page" title="Deliveries" subtitle="Assign, track, and verify OTP-based deliveries in real time" />
      {rows.length === 0 ? (
        <EmptyState icon={Truck} title="No deliveries yet" description="Deliveries appear automatically for shipped orders." />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4" data-testid="deliveries-board">
          {LANES.map((lane) => (
            <div key={lane.key} className="kanban-col p-3">
              <div className="flex items-center justify-between px-1 mb-3">
                <div className="text-[13px] font-semibold text-slate-800">{lane.label}</div>
                <span className="text-[11px] font-mono text-slate-500 bg-white px-1.5 py-0.5 rounded">{byLane(lane.key).length}</span>
              </div>
              <div className="space-y-2">
                {byLane(lane.key).map((d) => (
                  <div key={d.id} data-testid={`delivery-${d.id}`} className="bg-white rounded-xl border border-slate-200 p-3">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="text-[13px] font-medium text-slate-900">{d.orderNo}</div>
                        <div className="text-[11.5px] text-slate-500 mt-0.5">{d.customerName}</div>
                      </div>
                      <StatusBadge value={d.status} />
                    </div>
                    <div className="text-[11.5px] text-slate-600 mt-2">{d.address}</div>
                    <div className="flex items-center justify-between mt-3">
                      <div className="text-[11px] font-mono text-slate-500">OTP {d.otp}</div>
                      <select onChange={(e) => move(d, e.target.value)} defaultValue="" className="text-[11.5px] px-2 py-1 rounded-md border border-slate-200 bg-white">
                        <option value="" disabled>Move…</option>
                        {LANES.map((l) => <option key={l.key} value={l.key}>{l.label}</option>)}
                      </select>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
