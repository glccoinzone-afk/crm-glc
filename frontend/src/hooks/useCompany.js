import { useEffect, useState } from "react";
import api from "@/lib/glc";

// GSTIN / state / GST defaults come from the server (COMPANY_GSTIN), never hard-coded in screens.
let cached = null;
let inflight = null;

export function useCompany() {
  const [company, setCompany] = useState(cached);
  useEffect(() => {
    if (cached) return;
    inflight = inflight || api.get("/finance/company").then((r) => (cached = r.data)).catch(() => null);
    inflight.then((c) => c && setCompany(c));
  }, []);
  return company;
}
