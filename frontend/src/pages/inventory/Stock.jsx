import React, { useEffect, useState } from "react";
import { Warehouse, TriangleAlert } from "lucide-react";
import api from "@/lib/glc";
import { PageHeader, DataGrid, StatCard } from "@/components/common/GlcUI";

export default function Stock() {
  const [items, setItems] = useState([]);
  const [low, setLow] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.get("/inventory/stock"), api.get("/inventory/low-stock")]).then(([a, b]) => {
      setItems(a.data.items || []); setLow(b.data.items || []);
    }).finally(() => setLoading(false));
  }, []);

  const totalUnits = items.reduce((s, i) => s + (i.qty || 0), 0);
  const totalValue = items.reduce((s, i) => s + (i.qty || 0) * (i.product?.buyingPrice || 0), 0);

  const columns = [
    { key: "sku", header: "SKU", mono: true, render: (r) => r.product?.sku || "—" },
    { key: "name", header: "Product", render: (r) => r.product?.name || "—" },
    { key: "category", header: "Category", render: (r) => r.product?.category || "—" },
    { key: "warehouse", header: "Warehouse", render: (r) => r.warehouse?.name || "—" },
    { key: "qty", header: "Qty", mono: true, align: "right", render: (r) => (
        <span className={r.qty <= (r.product?.minStock || 5) ? "text-rose-600 font-medium" : "text-slate-800"}>{r.qty}</span>
      )
    },
    { key: "value", header: "Value", mono: true, align: "right", render: (r) => "₹" + Number((r.qty || 0) * (r.product?.buyingPrice || 0)).toLocaleString("en-IN") },
  ];

  return (
    <div className="space-y-6">
      <PageHeader testId="stock-page" title="Stock Overview" subtitle="Warehouse-wise stock levels across products" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total SKUs" value={items.length} icon={Warehouse} tone="primary" />
        <StatCard label="Total Units" value={totalUnits} icon={Warehouse} tone="accent" />
        <StatCard label="Inventory Value" value={"₹" + Number(totalValue).toLocaleString("en-IN")} icon={Warehouse} tone="success" />
        <StatCard label="Low Stock" value={low.length} icon={TriangleAlert} tone="danger" />
      </div>
      <DataGrid columns={columns} rows={items} loading={loading} testId="stock-grid" />
    </div>
  );
}
