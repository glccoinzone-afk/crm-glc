"""GST + accounting rules for the GLC Zone CRM.

Everything in here is pure Python (no database, no web framework) so it can be unit tested on its own;
server.py wires these helpers into the API. Amounts are rupees, rounded to 2 decimals per invoice line.

Please have a chartered accountant review the defaults marked "CA:" before relying on the returns.
"""
import os
import re
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------- states
STATE_CODES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh", "05": "Uttarakhand",
    "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
    "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur", "15": "Mizoram", "16": "Tripura",
    "17": "Meghalaya", "18": "Assam", "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
    "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat", "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra", "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
    "34": "Puducherry", "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh",
    "38": "Ladakh", "97": "Other Territory",
}
_STATE_ALIASES = {
    "an": "35", "ap": "37", "ar": "12", "as": "18", "br": "10", "ch": "04", "cg": "22", "dn": "26", "dd": "26",
    "dh": "26", "dl": "07", "ga": "30", "gj": "24", "hr": "06", "hp": "02", "jk": "01", "jh": "20", "ka": "29",
    "kl": "32", "la": "38", "ld": "31", "mp": "23", "mh": "27", "mn": "14", "ml": "17", "mz": "15", "nl": "13",
    "od": "21", "or": "21", "py": "34", "pb": "03", "rj": "08", "sk": "11", "tn": "33", "ts": "36", "tg": "36",
    "tr": "16", "up": "09", "uk": "05", "ut": "05", "wb": "19", "orissa": "21", "pondicherry": "34",
    "new delhi": "07", "uttaranchal": "05", "jammu & kashmir": "01",
}
_NAME_TO_CODE = {re.sub(r"[^a-z ]", "", n.lower().replace("&", "and")): c for c, n in STATE_CODES.items()}

COMPANY_GSTIN = os.environ.get("COMPANY_GSTIN", "10FZTPA0354J1ZJ").strip().upper()
COMPANY_STATE_CODE = COMPANY_GSTIN[:2] if len(COMPANY_GSTIN) >= 2 else "10"

# CA: delivery/shipping charged to the customer is treated as a taxable service, GST-inclusive.
DELIVERY_SAC = os.environ.get("DELIVERY_SAC", "996812")
DELIVERY_GST_RATE = float(os.environ.get("DELIVERY_GST_RATE", "18"))
DELIVERY_TAX_INCLUSIVE = os.environ.get("DELIVERY_TAX_INCLUSIVE", "1") not in ("0", "false", "False")


def state_code(text: Any) -> Optional[str]:
    """'Bihar' / 'BR' / '10' -> '10'. None when unknown or empty."""
    if text is None:
        return None
    t = str(text).strip().lower()
    if not t:
        return None
    if t.isdigit() and len(t) <= 2 and t.zfill(2) in STATE_CODES:
        return t.zfill(2)
    if t in _STATE_ALIASES:
        return _STATE_ALIASES[t]
    return _NAME_TO_CODE.get(re.sub(r"[^a-z ]", "", t.replace("&", "and")).strip())


def gstin_checksum(gstin14: str) -> str:
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    total = 0
    for i, c in enumerate(gstin14):
        v = chars.index(c) * (1 if i % 2 == 0 else 2)
        total += v // 36 + v % 36
    return chars[(36 - total % 36) % 36]


_GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def valid_gstin(gstin: Any) -> bool:
    g = str(gstin or "").strip().upper()
    if not _GSTIN_RE.match(g) or g[:2] not in STATE_CODES:
        return False
    return gstin_checksum(g[:14]) == g[14]


def place_of_supply(customer_gstin: Any = None, customer_state: Any = None, company_state: Optional[str] = None) -> str:
    """State code the supply is made to. Registered buyer: first 2 digits of the GSTIN; otherwise the state given;
    unknown -> the company's own state (treated as intra-state, the normal case for a local marketplace)."""
    g = str(customer_gstin or "").strip().upper()
    if valid_gstin(g):
        return g[:2]
    return state_code(customer_state) or (company_state or COMPANY_STATE_CODE)


def is_intra_state(customer_gstin: Any = None, customer_state: Any = None, company_state: Optional[str] = None) -> bool:
    return place_of_supply(customer_gstin, customer_state, company_state) == (company_state or COMPANY_STATE_CODE)


# ---------------------------------------------------------------- tax maths
def _r(x: float) -> float:
    return round(float(x) + 0.0, 2)


def split_line(item: Dict[str, Any], intra: bool) -> Dict[str, Any]:
    """Tax for one invoice line. item: qty, rate (unit price), discount (%), discountAmount (rupees),
    gstRate (%), taxInclusive (unit price already contains the tax)."""
    qty = float(item.get("qty") or 0)
    rate = float(item.get("rate") or 0)
    gst_rate = float(item.get("gstRate") or 0)
    gross = qty * rate
    disc = gross * float(item.get("discount") or 0) / 100.0 + float(item.get("discountAmount") or 0)
    net = max(gross - disc, 0.0)
    if item.get("taxInclusive") and gst_rate > 0:
        taxable = net / (1 + gst_rate / 100.0)
    else:
        taxable = net
    taxable = _r(taxable)
    tax = _r(net - taxable) if item.get("taxInclusive") and gst_rate > 0 else _r(taxable * gst_rate / 100.0)
    if intra:
        cgst = _r(tax / 2)
        sgst = _r(tax - cgst)
        igst = 0.0
    else:
        cgst = sgst = 0.0
        igst = tax
    return {
        "name": item.get("name", ""), "hsn": item.get("hsn", ""), "qty": qty, "rate": rate, "gstRate": gst_rate,
        "taxInclusive": bool(item.get("taxInclusive")), "isDelivery": bool(item.get("isDelivery")),
        "productId": item.get("productId"),
        "discount": float(item.get("discount") or 0), "discountAmount": float(item.get("discountAmount") or 0),
        "taxable": taxable, "cgst": cgst, "sgst": sgst, "igst": igst, "tax": _r(cgst + sgst + igst),
        "total": _r(taxable + cgst + sgst + igst),
    }


def calc_gst(items: List[Dict[str, Any]], intra_state: bool = True, round_off: bool = False) -> Dict[str, Any]:
    """Same keys as the old calc_gst (subtotal/cgst/sgst/igst/total) plus per-line detail in `lines`."""
    lines = [split_line(i, intra_state) for i in items]
    subtotal = _r(sum(l["taxable"] for l in lines))
    cgst = _r(sum(l["cgst"] for l in lines))
    sgst = _r(sum(l["sgst"] for l in lines))
    igst = _r(sum(l["igst"] for l in lines))
    total = _r(subtotal + cgst + sgst + igst)
    rounding = 0.0
    if round_off:
        rounding = _r(round(total) - total)
        total = _r(total + rounding)
    return {"subtotal": subtotal, "cgst": cgst, "sgst": sgst, "igst": igst, "total": total, "roundOff": rounding, "lines": lines}


def delivery_item(amount: float) -> Optional[Dict[str, Any]]:
    amount = float(amount or 0)
    if amount <= 0:
        return None
    return {"name": "Delivery charges", "hsn": DELIVERY_SAC, "qty": 1, "rate": amount, "gstRate": DELIVERY_GST_RATE,
            "taxInclusive": DELIVERY_TAX_INCLUSIVE, "isDelivery": True}


def items_from_glczone(order: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Invoice items from a website order (sales_orders doc filled by the order-event webhook).

    Website lines carry price, quantity, tax_percent, tax_amount, sub_total (what the customer paid for the line),
    discounted_price and hsn. Tax is treated as included in the price unless the line total equals price + tax."""
    out: List[Dict[str, Any]] = []
    for it in order.get("glczoneItems") or []:
        if str(it.get("status", "")).lower() in ("cancelled", "returned"):
            continue
        qty = float(it.get("quantity") or it.get("qty") or 1)
        unit = float(it.get("discounted_price") or it.get("price") or 0)
        rate_pct = float(it.get("tax_percent") or 0)
        tax_amt = float(it.get("tax_amount") or 0)
        line_paid = it.get("sub_total")
        inclusive = True
        if rate_pct > 0 and tax_amt > 0 and line_paid is not None:
            # exclusive pricing: the customer paid price*qty + tax
            inclusive = not (abs(float(line_paid) - (unit * qty + tax_amt)) < 0.05)
        out.append({"name": it.get("name", ""), "hsn": it.get("hsn", "") or "", "qty": qty, "rate": unit,
                    "gstRate": rate_pct, "taxInclusive": inclusive if rate_pct > 0 else False})
    d = delivery_item(order.get("deliveryCharge"))
    if d:
        out.append(d)
    return out


# ---------------------------------------------------------------- numbering
def fy_start_year(d: Optional[date] = None) -> int:
    d = d or date.today()
    return d.year if d.month >= 4 else d.year - 1


def fy_short(d: Optional[date] = None) -> str:
    y = fy_start_year(d)
    return f"{y % 100:02d}-{(y + 1) % 100:02d}"


def fy_label(d: Optional[date] = None) -> str:
    y = fy_start_year(d)
    return f"{y}-{(y + 1) % 100:02d}"


def doc_number(prefix: str, seq: int, d: Optional[date] = None) -> str:
    """INV/26-27/00001 (max 16 chars, as GST rule 46 requires)."""
    return f"{prefix}/{fy_short(d)}/{seq:05d}"


def counter_key(prefix: str, d: Optional[date] = None) -> str:
    return f"{prefix}:{fy_label(d)}"


# ---------------------------------------------------------------- chart of accounts + journals
# code -> (name, type)
REQUIRED_ACCOUNTS = {
    "1100": ("Cash", "ASSET"), "1200": ("Bank", "ASSET"), "1300": ("Accounts Receivable", "ASSET"),
    "1400": ("Inventory", "ASSET"),
    "1500": ("Input CGST", "ASSET"), "1510": ("Input SGST", "ASSET"), "1520": ("Input IGST", "ASSET"),
    "2100": ("Accounts Payable", "LIABILITY"),
    "2210": ("Output CGST", "LIABILITY"), "2220": ("Output SGST", "LIABILITY"), "2230": ("Output IGST", "LIABILITY"),
    "4100": ("Sales Revenue", "INCOME"), "4300": ("Delivery Income", "INCOME"), "4400": ("Sales Returns", "INCOME"),
    "5900": ("Round Off", "EXPENSE"),
}
DEBIT_NORMAL = ("ASSET", "EXPENSE")


def _entries(pairs: Iterable[Tuple[str, float, float]]) -> List[Dict[str, Any]]:
    return [{"accountCode": c, "debit": _r(d), "credit": _r(cr)} for c, d, cr in pairs if abs(d) > 0.004 or abs(cr) > 0.004]


def journal_for_invoice(inv: Dict[str, Any]) -> List[Dict[str, Any]]:
    goods = _r(sum(l["taxable"] for l in inv.get("lines", []) if not l.get("isDelivery")))
    deliv = _r(sum(l["taxable"] for l in inv.get("lines", []) if l.get("isDelivery")))
    rounding = float(inv.get("roundOff") or 0)
    return _entries([
        ("1300", inv["total"], 0),
        ("4100", 0, goods), ("4300", 0, deliv),
        ("2210", 0, inv.get("cgst", 0)), ("2220", 0, inv.get("sgst", 0)), ("2230", 0, inv.get("igst", 0)),
        ("5900", max(-rounding, 0), max(rounding, 0)),
    ])


def journal_for_credit_note(cn: Dict[str, Any]) -> List[Dict[str, Any]]:
    goods = _r(sum(l["taxable"] for l in cn.get("lines", []) if not l.get("isDelivery")))
    deliv = _r(sum(l["taxable"] for l in cn.get("lines", []) if l.get("isDelivery")))
    rounding = float(cn.get("roundOff") or 0)
    return _entries([
        ("4400", goods, 0), ("4300", deliv, 0),
        ("2210", cn.get("cgst", 0), 0), ("2220", cn.get("sgst", 0), 0), ("2230", cn.get("igst", 0), 0),
        ("5900", max(rounding, 0), max(-rounding, 0)),
        ("1300", 0, cn["total"]),
    ])


def journal_for_payment(amount: float, method: str) -> List[Dict[str, Any]]:
    cash = str(method or "").upper() == "CASH"
    return _entries([("1100" if cash else "1200", amount, 0), ("1300", 0, amount)])


def journal_for_purchase(po: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Goods received: inventory + input GST (claimable only when the supplier has a valid GSTIN)."""
    itc = bool(po.get("itcEligible", True))
    taxable = _r(po.get("subtotal", 0))
    cg, sg, ig = po.get("cgst", 0), po.get("sgst", 0), po.get("igst", 0)
    if itc:
        return _entries([("1400", taxable, 0), ("1500", cg, 0), ("1510", sg, 0), ("1520", ig, 0), ("2100", 0, po["total"])])
    return _entries([("1400", po["total"], 0), ("2100", 0, po["total"])])


def check_balanced(entries: List[Dict[str, Any]]) -> bool:
    return abs(sum(e["debit"] for e in entries) - sum(e["credit"] for e in entries)) < 0.01


def trial_balance(accounts: List[Dict[str, Any]], journals: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_id = {a["id"]: a for a in accounts}
    dr: Dict[str, float] = defaultdict(float)
    cr: Dict[str, float] = defaultdict(float)
    for j in journals:
        for e in j.get("entries", []):
            aid = e.get("accountId")
            if aid in by_id:
                dr[aid] += float(e.get("debit") or 0)
                cr[aid] += float(e.get("credit") or 0)
    rows = []
    for a in sorted(accounts, key=lambda x: x.get("code", "")):
        d, c = _r(dr[a["id"]]), _r(cr[a["id"]])
        net = _r(d - c) if a.get("type") in DEBIT_NORMAL else _r(c - d)
        rows.append({"id": a["id"], "code": a.get("code"), "name": a.get("name"), "type": a.get("type"),
                     "debit": d, "credit": c, "balance": net})
    td, tc = _r(sum(r["debit"] for r in rows)), _r(sum(r["credit"] for r in rows))
    return {"rows": rows, "totalDebit": td, "totalCredit": tc, "balanced": abs(td - tc) < 0.01}


def ledger(account: Dict[str, Any], journals: List[Dict[str, Any]]) -> Dict[str, Any]:
    sign = 1 if account.get("type") in DEBIT_NORMAL else -1
    entries, running = [], 0.0
    for j in sorted(journals, key=lambda x: (str(x.get("date", "")), str(x.get("createdAt", "")))):
        for e in j.get("entries", []):
            if e.get("accountId") == account["id"]:
                d, c = float(e.get("debit") or 0), float(e.get("credit") or 0)
                running = _r(running + sign * (d - c))
                entries.append({"date": j.get("date"), "narration": j.get("narration"), "refType": j.get("refType"),
                                "refId": j.get("refId"), "debit": _r(d), "credit": _r(c), "balance": running})
    return {"account": {"id": account["id"], "code": account.get("code"), "name": account.get("name"), "type": account.get("type")},
            "entries": entries, "closing": running}


# ---------------------------------------------------------------- reports
def ensure_lines(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Per-line GST detail; rebuilt from items for documents created before `lines` existed."""
    if doc.get("lines"):
        return doc["lines"]
    intra = is_intra_state(doc.get("customerGst"), doc.get("customerState"))
    items = doc.get("items") or []
    if not items:
        return []
    fixed = []
    for it in items:
        it = dict(it)
        it.setdefault("rate", it.get("price", 0))
        it.setdefault("gstRate", it.get("gst", 0))
        fixed.append(it)
    return calc_gst(fixed, intra)["lines"]


def _pos_label(code: str) -> str:
    return f"{code}-{STATE_CODES.get(code, '')}"


def gstr1(invoices: List[Dict[str, Any]], credit_notes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """GSTR-1 style summary (B2B, B2C large, B2C small, credit notes, HSN, documents issued)."""
    b2b, b2cl, cdn = [], [], []
    b2cs: Dict[Tuple[str, float], Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    hsn: Dict[Tuple[str, float], Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    def add_hsn(lines, sign):
        for l in lines:
            k = (l.get("hsn") or "NA", float(l.get("gstRate") or 0))
            h = hsn[k]
            h["qty"] += sign * float(l.get("qty") or 0)
            h["taxable"] += sign * l["taxable"]
            h["cgst"] += sign * l["cgst"]
            h["sgst"] += sign * l["sgst"]
            h["igst"] += sign * l["igst"]

    for inv in invoices:
        if inv.get("status") == "CANCELLED":
            continue
        lines = ensure_lines(inv)
        gstin = str(inv.get("customerGst") or "").strip().upper()
        pos = place_of_supply(gstin, inv.get("customerState"))
        add_hsn(lines, 1)
        if valid_gstin(gstin):
            b2b.append({"gstin": gstin, "invoiceNo": inv.get("invoiceNo"), "date": str(inv.get("invoiceDate", ""))[:10],
                        "value": inv.get("total", 0), "pos": _pos_label(pos), "taxable": inv.get("subtotal", 0),
                        "cgst": inv.get("cgst", 0), "sgst": inv.get("sgst", 0), "igst": inv.get("igst", 0)})
        elif pos != COMPANY_STATE_CODE and float(inv.get("total") or 0) > 250000:
            b2cl.append({"invoiceNo": inv.get("invoiceNo"), "date": str(inv.get("invoiceDate", ""))[:10],
                         "value": inv.get("total", 0), "pos": _pos_label(pos), "taxable": inv.get("subtotal", 0),
                         "igst": inv.get("igst", 0)})
        else:
            for l in lines:
                row = b2cs[(pos, float(l.get("gstRate") or 0))]
                row["taxable"] += l["taxable"]
                row["cgst"] += l["cgst"]
                row["sgst"] += l["sgst"]
                row["igst"] += l["igst"]

    for cn in credit_notes:
        lines = ensure_lines(cn)
        gstin = str(cn.get("customerGst") or "").strip().upper()
        add_hsn(lines, -1)
        cdn.append({"noteNo": cn.get("noteNo"), "date": str(cn.get("noteDate", ""))[:10], "invoiceNo": cn.get("invoiceNo"),
                    "type": "registered" if valid_gstin(gstin) else "unregistered", "gstin": gstin if valid_gstin(gstin) else "",
                    "value": cn.get("total", 0), "taxable": cn.get("subtotal", 0),
                    "cgst": cn.get("cgst", 0), "sgst": cn.get("sgst", 0), "igst": cn.get("igst", 0)})

    def rows(d, keyname):
        out = []
        for k, v in sorted(d.items()):
            r = {keyname[0]: k[0], keyname[1]: k[1]}
            r.update({m: _r(x) for m, x in v.items()})
            out.append(r)
        return out

    nums = sorted(str(i.get("invoiceNo", "")) for i in invoices if i.get("invoiceNo"))
    live = [i for i in invoices if i.get("status") != "CANCELLED"]
    tot = {
        "taxable": _r(sum(float(i.get("subtotal") or 0) for i in live) - sum(float(c.get("subtotal") or 0) for c in credit_notes)),
        "cgst": _r(sum(float(i.get("cgst") or 0) for i in live) - sum(float(c.get("cgst") or 0) for c in credit_notes)),
        "sgst": _r(sum(float(i.get("sgst") or 0) for i in live) - sum(float(c.get("sgst") or 0) for c in credit_notes)),
        "igst": _r(sum(float(i.get("igst") or 0) for i in live) - sum(float(c.get("igst") or 0) for c in credit_notes)),
    }
    return {
        "b2b": b2b, "b2cl": b2cl,
        "b2cs": [{"pos": _pos_label(r["pos"]), **{k: v for k, v in r.items() if k != "pos"}} for r in rows(b2cs, ("pos", "rate"))],
        "cdn": cdn,
        "hsn": [{"hsn": r["hsn"], "rate": r["rate"], **{k: v for k, v in r.items() if k not in ("hsn", "rate")}} for r in rows(hsn, ("hsn", "rate"))],
        "documents": {"invoices": len(invoices), "cancelled": len(invoices) - len(live), "from": nums[0] if nums else None,
                      "to": nums[-1] if nums else None, "creditNotes": len(credit_notes)},
        "totals": tot,
    }


def gstr3b(invoices: List[Dict[str, Any]], credit_notes: List[Dict[str, Any]], purchases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """GSTR-3B style: outward supplies, eligible ITC, and tax payable after utilising credit
    (IGST credit pays IGST, then CGST, then SGST; CGST credit pays CGST then IGST; SGST credit pays SGST then IGST)."""
    live = [i for i in invoices if i.get("status") != "CANCELLED"]
    taxable = nil = 0.0
    out = {"cgst": 0.0, "sgst": 0.0, "igst": 0.0}
    for doc, sign in [(i, 1) for i in live] + [(c, -1) for c in credit_notes]:
        for l in ensure_lines(doc):
            if float(l.get("gstRate") or 0) > 0:
                taxable += sign * l["taxable"]
            else:
                nil += sign * l["taxable"]
            for h in out:
                out[h] += sign * l[h]
    itc = {"cgst": 0.0, "sgst": 0.0, "igst": 0.0}
    itc_docs = 0
    for p in purchases:
        if p.get("status") != "RECEIVED" or not p.get("itcEligible", valid_gstin(p.get("supplierGst"))):
            continue
        itc_docs += 1
        for h in itc:
            itc[h] += float(p.get(h) or 0)
    out = {k: _r(v) for k, v in out.items()}
    itc = {k: _r(v) for k, v in itc.items()}

    pay, credit = dict(out), dict(itc)
    used = defaultdict(float)

    def use(credit_head, pay_head):
        amt = min(credit[credit_head], pay[pay_head])
        if amt > 0:
            credit[credit_head] = _r(credit[credit_head] - amt)
            pay[pay_head] = _r(pay[pay_head] - amt)
            used[f"{credit_head}->{pay_head}"] = _r(amt)

    for pay_head in ("igst", "cgst", "sgst"):
        use("igst", pay_head)
    use("cgst", "cgst"); use("cgst", "igst")
    use("sgst", "sgst"); use("sgst", "igst")
    return {
        "outward": {"taxableValue": _r(taxable), "nilRatedValue": _r(nil), **out},
        "itcAvailable": itc, "itcDocuments": itc_docs, "utilised": dict(used),
        "netPayableCash": {**pay, "total": _r(sum(pay.values()))},
        "itcCarriedForward": {**credit, "total": _r(sum(credit.values()))},
    }


def receivables_ageing(invoices: List[Dict[str, Any]], today: Optional[date] = None) -> Dict[str, Any]:
    today = today or date.today()
    buckets = ["notDue", "1-30", "31-60", "61-90", "90+"]
    per: Dict[str, Dict[str, float]] = defaultdict(lambda: {b: 0.0 for b in buckets})
    tot = {b: 0.0 for b in buckets}
    for inv in invoices:
        if inv.get("status") in ("CANCELLED", "PAID"):
            continue
        due = float(inv.get("dueAmount") or 0)
        if due <= 0.005:
            continue
        try:
            dd = datetime.fromisoformat(str(inv.get("dueDate"))[:19]).date()
        except Exception:
            dd = today
        days = (today - dd).days
        b = "notDue" if days <= 0 else "1-30" if days <= 30 else "31-60" if days <= 60 else "61-90" if days <= 90 else "90+"
        name = inv.get("customerName") or "Unknown"
        per[name][b] += due
        tot[b] += due
    rows = [{"customer": n, **{b: _r(v[b]) for b in buckets}, "total": _r(sum(v.values()))} for n, v in per.items()]
    rows.sort(key=lambda r: -r["total"])
    return {"buckets": buckets, "rows": rows, "totals": {**{b: _r(v) for b, v in tot.items()}, "total": _r(sum(tot.values()))}}


def credit_note_items(invoice: Dict[str, Any], picks: Optional[List[Dict[str, Any]]] = None, include_delivery: bool = False) -> List[Dict[str, Any]]:
    """Items for a credit note against `invoice`. picks=[{index, qty}] for a partial return; None = everything.
    Rates, discounts and tax mode are copied from the invoice so the tax reverses exactly."""
    lines = ensure_lines(invoice)
    items = invoice.get("items") or []
    out = []
    if picks is None:
        for l in lines:
            if l.get("isDelivery") and not include_delivery:
                continue
            out.append({"name": l["name"], "hsn": l.get("hsn", ""), "qty": l["qty"], "rate": l["rate"],
                        "gstRate": l["gstRate"], "taxInclusive": l.get("taxInclusive", False), "isDelivery": l.get("isDelivery", False),
                        "productId": l.get("productId"), "discount": l.get("discount", 0),
                        "discountAmount": l.get("discountAmount", 0)})
        return out
    for p in picks:
        idx, qty = int(p.get("index", -1)), float(p.get("qty") or 0)
        if idx < 0 or idx >= len(lines) or qty <= 0:
            raise ValueError("bad item pick")
        l = lines[idx]
        if qty > l["qty"] + 1e-9:
            raise ValueError(f"cannot credit {qty} of '{l['name']}' (invoiced {l['qty']})")
        out.append({"name": l["name"], "hsn": l.get("hsn", ""), "qty": qty, "rate": l["rate"], "gstRate": l["gstRate"],
                    "taxInclusive": l.get("taxInclusive", False), "isDelivery": l.get("isDelivery", False),
                    "productId": l.get("productId"), "discount": l.get("discount", 0),
                    "discountAmount": (l.get("discountAmount", 0) or 0) * qty / (l["qty"] or 1)})
    return out
