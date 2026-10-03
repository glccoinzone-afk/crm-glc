"""GLC Zone CRM + ERP - Backend (FastAPI + MongoDB)."""
from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta, date
import os
import re
import json
import uuid
import asyncio
import logging
import bcrypt
import jwt as pyjwt
import requests
from pathlib import Path
from fastapi import UploadFile, File, Response, Header
from pymongo import ReturnDocument
import glc_finance as gf

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ.get("JWT_SECRET", "glc-zone-supersecret-dev-only-change-in-prod")
JWT_ALGO = "HS256"
JWT_EXPIRES_MIN = 60 * 24 * 7
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
STORAGE_APP_NAME = os.environ.get("STORAGE_APP_NAME", "glczone")
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
_storage_key: Optional[str] = None


def init_storage() -> Optional[str]:
    global _storage_key
    if _storage_key or not EMERGENT_LLM_KEY:
        return _storage_key
    try:
        r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_LLM_KEY}, timeout=15)
        r.raise_for_status()
        _storage_key = r.json().get("storage_key")
        return _storage_key
    except Exception as e:
        logging.getLogger("glc").exception(f"Storage init failed: {e}")
        return None


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    if not key:
        raise HTTPException(500, "Storage not initialized")
    r = requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    r.raise_for_status()
    return r.json()


def get_object(path: str):
    key = init_storage()
    if not key:
        raise HTTPException(500, "Storage not initialized")
    r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="GLC Zone CRM+ERP", version="1.0.0")
api = APIRouter(prefix="/api")
bearer = HTTPBearer(auto_error=False)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("glc")


# ---------- helpers ----------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid() -> str:
    return str(uuid.uuid4())


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_pw(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), h.encode())
    except Exception:
        return False


def make_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRES_MIN)).timestamp()),
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


async def current_user(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> Dict[str, Any]:
    if not cred:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = pyjwt.decode(cred.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


FINANCE_ROLES = ("Super Admin", "Admin", "Accounts", "Finance Staff")


async def finance_user(user=Depends(current_user)) -> Dict[str, Any]:
    if user.get("role") not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Finance access required")
    return user


def clean(doc: Optional[dict]) -> Optional[dict]:
    if not doc:
        return doc
    doc.pop("_id", None)
    doc.pop("password", None)
    return doc


def cleans(docs: List[dict]) -> List[dict]:
    return [clean(d) for d in docs]


async def log_activity(user_id: str, module: str, action: str, entity_id: Optional[str] = None, meta: Optional[dict] = None):
    await db.audit_logs.insert_one({
        "id": uid(),
        "userId": user_id,
        "module": module,
        "action": action,
        "entityId": entity_id,
        "meta": meta or {},
        "createdAt": now_iso(),
    })


# ---------- Auth ----------
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    avatar: Optional[str] = None
    department: Optional[str] = None
    isActive: bool = True


@api.post("/auth/login")
async def auth_login(data: LoginIn):
    u = await db.users.find_one({"email": data.email.lower()})
    if not u or not verify_pw(data.password, u.get("password", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not u.get("isActive", True):
        raise HTTPException(status_code=403, detail="Account disabled")
    if u.get("twofa_enabled") and u.get("totp_secret"):
        temp_token = make_token(u["id"], u["email"], u.get("role", "Admin"))
        return {"requires_2fa": True, "temp_token": temp_token}
    token = make_token(u["id"], u["email"], u.get("role", "Admin"))
    await log_activity(u["id"], "auth", "login")
    return {"token": token, "user": clean(u)}


@api.get("/auth/me")
async def auth_me(user=Depends(current_user)):
    return user


class EmployeeLoginIn(BaseModel):
    employee_code: str
    pin: str


@api.post("/auth/employee-login")
async def auth_employee_login(data: EmployeeLoginIn):
    try:
        resp = requests.post(
            "https://glczone.in/api/crm/verify-employee",
            json={"employee_code": data.employee_code, "pin": data.pin},
            timeout=10,
        )
    except Exception:
        raise HTTPException(503, "Could not reach verification service. Try again.")

    if resp.status_code == 429:
        raise HTTPException(429, "Too many attempts. Please wait a minute and try again.")

    body = resp.json() if resp.content else {}
    if resp.status_code != 200 or not body.get("valid"):
        raise HTTPException(401, body.get("message", "Invalid Employee ID or PIN"))

    role = body["role"]
    name = body.get("name", "Employee")
    employee_code = data.employee_code

    u = await db.users.find_one({"$or": [{"employee_code": employee_code}, {"employeeCode": employee_code}]})
    if u:
        if not u.get("isActive", True):
            raise HTTPException(403, "This account is disabled")
        await db.users.update_one({"employee_code": employee_code}, {"$set": {"role": role, "name": name}})
        u["role"] = role
        u["name"] = name
    else:
        u = {
            "id": uid(),
            "employee_code": employee_code,
            "name": name,
            "email": f"{employee_code.lower()}@glczone.internal",
            "password": hash_pw(uid()),
            "role": role,
            "avatar": f"https://api.dicebear.com/7.x/initials/svg?seed={name.replace(' ', '')[:2]}",
            "department": "Operations",
            "isActive": True,
            "createdAt": now_iso(),
        }
        await db.users.insert_one(dict(u))

    if u.get("twofa_enabled") and u.get("totp_secret"):
        temp_token = make_token(u["id"], u["email"], role)
        return {"requires_2fa": True, "temp_token": temp_token}
    token = make_token(u["id"], u["email"], role)
    await log_activity(u["id"], "auth", "employee_login")
    return {"token": token, "user": clean(u)}


import hmac
import httpx
import hashlib

CRM_SSO_SECRET = os.environ.get("CRM_SSO_SECRET", "")


@api.get("/auth/sso")
async def auth_sso(role: str, employee_code: str, name: str, exp: str, sig: str):
    if not CRM_SSO_SECRET:
        raise HTTPException(500, "SSO not configured")
    payload_str = f"{role}|{employee_code}|{name}|{exp}"
    expected_sig = hmac.new(CRM_SSO_SECRET.encode(), payload_str.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, sig):
        raise HTTPException(401, "Invalid SSO signature")
    if int(exp) < int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(401, "SSO link expired")
    valid_sso_roles = (
        "Super Admin", "Admin", "Manager", "Catalog Manager", "Logistics Manager",
        "Warehouse Manager", "Seller Relations Manager", "Telecaller",
        "Finance Staff", "Marketing Manager", "System Admin",
        "Support Executive", "Sales", "HR", "Accounts",
    )
    if role not in valid_sso_roles:
        raise HTTPException(403, "Role not permitted")

    u = await db.users.find_one({"$or": [{"employee_code": employee_code}, {"employeeCode": employee_code}]})
    if u:
        if not u.get("isActive", True):
            raise HTTPException(403, "This account is disabled")
        await db.users.update_one({"employee_code": employee_code}, {"$set": {"role": role, "name": name}})
        u["role"] = role
        u["name"] = name
    else:
        u = {
            "id": uid(),
            "employee_code": employee_code,
            "name": name,
            "email": f"{employee_code.lower()}@glczone.internal",
            "password": hash_pw(uid()),
            "role": role,
            "avatar": f"https://api.dicebear.com/7.x/initials/svg?seed={name.replace(' ', '')[:2]}",
            "department": "Operations",
            "isActive": True,
            "createdAt": now_iso(),
        }
        await db.users.insert_one(dict(u))

    token = make_token(u["id"], u["email"], role)
    await log_activity(u["id"], "auth", "sso_login")

    from fastapi.responses import HTMLResponse
    html = f"""<!DOCTYPE html><html><body>
<script>
localStorage.setItem('glc_token', '{token}');
localStorage.removeItem('glc_user');
window.location.href = '/crm/';
</script>
Redirecting...
</body></html>"""
    return HTMLResponse(content=html)


class UserNameUpdateIn(BaseModel):
    name: str


@api.put("/users/{user_id}/name")
async def update_user_name(user_id: str, data: UserNameUpdateIn, user=Depends(current_user)):
    if user.get("role") != "Super Admin":
        raise HTTPException(403, "Only Super Admin can rename a role seat")
    result = await db.users.update_one({"id": user_id}, {"$set": {"name": data.name}})
    if result.matched_count == 0:
        raise HTTPException(404, "User not found")
    await log_activity(user["id"], "users", "rename", user_id, {"newName": data.name})
    return {"ok": True, "name": data.name}


# ---------- Generic helpers for CRUD collections ----------
async def paginate(collection, filt: dict, page: int = 1, limit: int = 50, sort_field: str = "createdAt", sort_dir: int = -1, search_fields: Optional[List[str]] = None, q: Optional[str] = None):
    if q and search_fields:
        filt = {**filt, "$or": [{f: {"$regex": q, "$options": "i"}} for f in search_fields]}
    total = await collection.count_documents(filt)
    cursor = collection.find(filt, {"_id": 0}).sort(sort_field, sort_dir).skip((page - 1) * limit).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


# =========================================================
# CRM: Leads, Customers, Pipeline, Quotations
# =========================================================
class LeadIn(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    source: str = "MANUAL"
    status: str = "NEW"
    score: int = 0
    value: float = 0
    assignedTo: Optional[str] = None
    followUpDate: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = []
    vertical: Optional[str] = None


@api.get("/leads")
async def list_leads(page: int = 1, limit: int = 50, q: Optional[str] = None, status_: Optional[str] = Query(None, alias="status"), vertical: Optional[str] = None, user=Depends(current_user)):
    filt = {}
    if status_:
        filt["status"] = status_
    if vertical:
        filt["vertical"] = vertical
    return await paginate(db.leads, filt, page, limit, search_fields=["name", "email", "phone", "company"], q=q)


@api.post("/leads")
async def create_lead(data: LeadIn, user=Depends(current_user)):
    doc = {**data.model_dump(), "id": uid(), "createdAt": now_iso(), "updatedAt": now_iso(), "activities": []}
    await db.leads.insert_one(doc)
    await log_activity(user["id"], "leads", "create", doc["id"], {"name": doc["name"]})
    return clean(doc)


@api.get("/leads/{lead_id}")
async def get_lead(lead_id: str, user=Depends(current_user)):
    d = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Not found")
    return d


@api.put("/leads/{lead_id}")
async def update_lead(lead_id: str, data: LeadIn, user=Depends(current_user)):
    upd = {**data.model_dump(), "updatedAt": now_iso()}
    r = await db.leads.update_one({"id": lead_id}, {"$set": upd})
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    await log_activity(user["id"], "leads", "update", lead_id)
    d = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    return d


@api.delete("/leads/{lead_id}")
async def delete_lead(lead_id: str, user=Depends(current_user)):
    await db.leads.delete_one({"id": lead_id})
    await log_activity(user["id"], "leads", "delete", lead_id)
    return {"ok": True}


@api.post("/leads/{lead_id}/activity")
async def add_lead_activity(lead_id: str, body: Dict[str, Any], user=Depends(current_user)):
    entry = {"id": uid(), "type": body.get("type", "note"), "text": body.get("text", ""), "by": user.get("name"), "at": now_iso()}
    await db.leads.update_one({"id": lead_id}, {"$push": {"activities": entry}, "$set": {"updatedAt": now_iso()}})
    return entry


@api.post("/leads/{lead_id}/convert")
async def convert_lead(lead_id: str, user=Depends(current_user)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "Not found")
    cust = {
        "id": uid(),
        "name": lead.get("name"),
        "email": lead.get("email"),
        "phone": lead.get("phone"),
        "company": lead.get("company"),
        "type": "RETAIL",
        "vertical": lead.get("vertical"),
        "gst": "",
        "pan": "",
        "creditLimit": 0,
        "outstanding": 0,
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
        "convertedFromLead": lead_id,
    }
    await db.customers.insert_one(cust)
    await db.leads.update_one({"id": lead_id}, {"$set": {"status": "WON", "convertedCustomerId": cust["id"]}})
    await log_activity(user["id"], "leads", "convert", lead_id, {"customerId": cust["id"]})
    return clean(cust)


class CustomerIn(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    gst: Optional[str] = None
    pan: Optional[str] = None
    type: str = "RETAIL"
    vertical: Optional[str] = None
    creditLimit: float = 0
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    tags: List[str] = []


@api.get("/customers")
async def list_customers(page: int = 1, limit: int = 50, q: Optional[str] = None, vertical: Optional[str] = None, user=Depends(current_user)):
    filt = {}
    if vertical:
        filt["vertical"] = vertical
    return await paginate(db.customers, filt, page, limit, search_fields=["name", "email", "phone", "company", "gst"], q=q)


@api.post("/customers")
async def create_customer(data: CustomerIn, user=Depends(current_user)):
    doc = {**data.model_dump(), "id": uid(), "createdAt": now_iso(), "updatedAt": now_iso(), "outstanding": 0}
    await db.customers.insert_one(doc)
    await log_activity(user["id"], "customers", "create", doc["id"])
    return clean(doc)


@api.get("/customers/{cid}")
async def get_customer(cid: str, user=Depends(current_user)):
    d = await db.customers.find_one({"id": cid}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Not found")
    orders = await db.sales_orders.find({"customerId": cid}, {"_id": 0}).sort("createdAt", -1).to_list(50)
    invoices = await db.invoices.find({"customerId": cid}, {"_id": 0}).sort("createdAt", -1).to_list(50)
    payments = await db.payments.find({"customerId": cid}, {"_id": 0}).sort("createdAt", -1).to_list(50)
    tickets = await db.tickets.find({"customerId": cid}, {"_id": 0}).sort("createdAt", -1).to_list(20)
    return {"customer": d, "orders": orders, "invoices": invoices, "payments": payments, "tickets": tickets}


@api.put("/customers/{cid}")
async def update_customer(cid: str, data: CustomerIn, user=Depends(current_user)):
    r = await db.customers.update_one({"id": cid}, {"$set": {**data.model_dump(), "updatedAt": now_iso()}})
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    d = await db.customers.find_one({"id": cid}, {"_id": 0})
    return d


@api.delete("/customers/{cid}")
async def delete_customer(cid: str, user=Depends(current_user)):
    await db.customers.delete_one({"id": cid})
    return {"ok": True}


# Pipeline (deals)
class DealIn(BaseModel):
    title: str
    customerId: Optional[str] = None
    customerName: Optional[str] = None
    value: float = 0
    probability: int = 20
    stage: str = "NEW"
    expectedClose: Optional[str] = None
    assignedTo: Optional[str] = None
    vertical: Optional[str] = None


@api.get("/deals")
async def list_deals(vertical: Optional[str] = None, user=Depends(current_user)):
    filt = {}
    if vertical:
        filt["vertical"] = vertical
    items = await db.deals.find(filt, {"_id": 0}).sort("createdAt", -1).to_list(500)
    return {"items": items}


@api.post("/deals")
async def create_deal(data: DealIn, user=Depends(current_user)):
    doc = {**data.model_dump(), "id": uid(), "createdAt": now_iso(), "updatedAt": now_iso()}
    await db.deals.insert_one(doc)
    return clean(doc)


@api.put("/deals/{did}")
async def update_deal(did: str, body: Dict[str, Any], user=Depends(current_user)):
    body["updatedAt"] = now_iso()
    await db.deals.update_one({"id": did}, {"$set": body})
    d = await db.deals.find_one({"id": did}, {"_id": 0})
    return d


@api.delete("/deals/{did}")
async def delete_deal(did: str, user=Depends(current_user)):
    await db.deals.delete_one({"id": did})
    return {"ok": True}


# Quotations
class QuoteItem(BaseModel):
    productId: Optional[str] = None
    name: str
    hsn: Optional[str] = None
    qty: float = 1
    rate: float = 0
    discount: float = 0
    discountAmount: float = 0
    gstRate: float = 18
    taxInclusive: bool = False


class QuoteIn(BaseModel):
    customerId: Optional[str] = None
    customerName: str
    customerGst: Optional[str] = None
    customerState: Optional[str] = None
    items: List[QuoteItem] = []
    validity: Optional[str] = None
    notes: Optional[str] = None
    status: str = "DRAFT"
    vertical: Optional[str] = None


def calc_gst(items: List[dict], intra_state: bool = True, round_off: bool = False):
    """GST for a list of line items (see glc_finance.calc_gst). Returns subtotal/cgst/sgst/igst/total/roundOff/lines."""
    return gf.calc_gst(items, intra_state=intra_state, round_off=round_off)


@api.get("/quotations")
async def list_quotes(page: int = 1, limit: int = 50, q: Optional[str] = None, user=Depends(current_user)):
    return await paginate(db.quotations, {}, page, limit, search_fields=["quoteNo", "customerName"], q=q)


@api.post("/quotations")
async def create_quote(data: QuoteIn, user=Depends(current_user)):
    items = [i.model_dump() for i in data.items]
    intra = gf.is_intra_state(data.customerGst, data.customerState)
    totals = calc_gst(items, intra_state=intra)
    count = await db.quotations.count_documents({})
    doc = {
        **data.model_dump(),
        "id": uid(),
        "quoteNo": f"QT-{datetime.now().year}-{count+1001}",
        "items": items,
        **totals,
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    await db.quotations.insert_one(doc)
    await log_activity(user["id"], "quotations", "create", doc["id"])
    return clean(doc)


@api.get("/quotations/{qid}")
async def get_quote(qid: str, user=Depends(current_user)):
    d = await db.quotations.find_one({"id": qid}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Not found")
    return d


@api.put("/quotations/{qid}")
async def update_quote(qid: str, data: QuoteIn, user=Depends(current_user)):
    items = [i.model_dump() for i in data.items]
    intra = gf.is_intra_state(data.customerGst, data.customerState)
    totals = calc_gst(items, intra_state=intra)
    await db.quotations.update_one({"id": qid}, {"$set": {**data.model_dump(), "items": items, **totals, "updatedAt": now_iso()}})
    d = await db.quotations.find_one({"id": qid}, {"_id": 0})
    return d


@api.delete("/quotations/{qid}")
async def delete_quote(qid: str, user=Depends(current_user)):
    await db.quotations.delete_one({"id": qid})
    return {"ok": True}


@api.get("/quotations/{qid}/pdf")
async def quote_pdf(qid: str, cred: HTTPAuthorizationCredentials = Depends(bearer)):
    # Accept token from query param (for browser direct open) or header
    raw_token = cred.credentials if cred else None
    if not raw_token:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = pyjwt.decode(raw_token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    q = await db.quotations.find_one({"id": qid}, {"_id": 0})
    if not q:
        raise HTTPException(404, "Not found")
    from fastapi.responses import HTMLResponse
    items_html = ""
    for idx, it in enumerate(q.get("items", []), 1):
        disc = it.get("discount") or 0
        gst = it.get("gstRate") or 0
        amt = it["qty"] * it["rate"] * (1 - disc / 100)
        gst_class = "gst-zero" if gst == 0 else "gst-val"
        items_html += f"""<tr>
            <td style="color:#64748b;font-size:11px">{idx}</td>
            <td><span style="font-weight:600">{it.get("name","")}</span></td>
            <td><span class="hsn-badge">{it.get("hsn","") or "—"}</span></td>
            <td class="td-right">{it["qty"]}</td>
            <td class="td-right" style="color:#64748b;font-size:11px">{it.get("unit","PCS")}</td>
            <td class="td-right">₹{it["rate"]:,.2f}</td>
            <td class="td-right" style="color:#64748b">{disc}%</td>
            <td class="td-right"><span class="{gst_class}">{gst}%</span></td>
            <td class="td-right">₹{amt:,.2f}</td>
        </tr>"""
    valid_till = ""
    try:
        from datetime import datetime, timedelta
        created = q.get("createdAt","")[:10]
        vdays = int(q.get("validDays") or 30)
        dt = datetime.strptime(created, "%Y-%m-%d") + timedelta(days=vdays)
        valid_till = dt.strftime("%d %b %Y")
    except: pass

    status_colors = {"DRAFT":"#f59e0b","CONVERTED":"#16a34a","SENT":"#3b82f6","CANCELLED":"#ef4444"}
    status_color = status_colors.get(q.get("status","DRAFT"), "#64748b")

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{q.get("quoteNo","Quotation")} — GLC Zone</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',Arial,sans-serif;font-size:13px;color:#1e293b;background:#f8fafc;padding:0}}
  .page{{background:#fff;max-width:794px;margin:0 auto;padding:0;box-shadow:0 0 40px rgba(0,0,0,.08)}}
  .topbar{{background:linear-gradient(135deg,#0f4c35 0%,#166534 100%);padding:28px 40px;color:#fff;display:flex;justify-content:space-between;align-items:flex-start}}
  .company-name{{font-size:26px;font-weight:800;letter-spacing:-.5px;color:#fff}}
  .company-sub{{font-size:11px;color:rgba(255,255,255,.75);margin-top:4px}}
  .quote-badge{{text-align:right}}
  .quote-no{{font-size:22px;font-weight:700;color:#fff;font-family:monospace}}
  .quote-label{{font-size:10px;color:rgba(255,255,255,.6);text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px}}
  .status-pill{{display:inline-block;padding:3px 10px;border-radius:20px;font-size:10px;font-weight:700;margin-top:6px;background:rgba(255,255,255,.2);color:#fff;border:1px solid rgba(255,255,255,.3)}}
  .meta-bar{{background:#f0fdf4;border-bottom:1px solid #dcfce7;padding:14px 40px;display:flex;gap:32px}}
  .meta-item{{font-size:11px;color:#64748b}}.meta-item strong{{display:block;color:#1e293b;font-size:12px;margin-top:2px}}
  .body{{padding:32px 40px}}
  .bill-section{{display:flex;justify-content:space-between;margin-bottom:28px;gap:20px}}
  .bill-box{{flex:1;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px}}
  .bill-box h4{{font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.1em;margin-bottom:10px;font-weight:600}}
  .bill-box .name{{font-size:15px;font-weight:700;color:#0f4c35;margin-bottom:4px}}
  .bill-box .detail{{font-size:11.5px;color:#64748b;line-height:1.6}}
  table{{width:100%;border-collapse:collapse;margin-bottom:20px}}
  thead tr{{background:#0f4c35}}
  thead th{{color:#fff;text-align:left;padding:10px 14px;font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;font-weight:600}}
  thead th:last-child{{text-align:right}}
  tbody tr{{border-bottom:1px solid #f1f5f9}}
  tbody tr:nth-child(even){{background:#fafafa}}
  td{{padding:10px 14px;font-size:12.5px;vertical-align:middle}}
  td:last-child{{text-align:right;font-weight:600}}
  .td-right{{text-align:right}}
  .totals-wrap{{display:flex;justify-content:flex-end;margin-bottom:24px}}
  .totals-box{{width:280px;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden}}
  .totals-row{{display:flex;justify-content:space-between;padding:9px 16px;font-size:12.5px;border-bottom:1px solid #f1f5f9}}
  .totals-row:last-child{{background:#0f4c35;color:#fff;font-weight:700;font-size:14px;border:none}}
  .totals-row.tax{{color:#64748b}}
  .notes-section{{background:#fffbeb;border:1px solid #fef3c7;border-radius:10px;padding:14px 18px;margin-bottom:16px}}
  .notes-section h4{{font-size:10px;color:#92400e;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px}}
  .notes-section p{{font-size:12px;color:#78350f;line-height:1.5}}
  .terms-section{{background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;padding:14px 18px;margin-bottom:24px}}
  .terms-section h4{{font-size:10px;color:#0369a1;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px}}
  .terms-section p{{font-size:12px;color:#0c4a6e;line-height:1.5}}
  .footer{{background:#f8fafc;border-top:1px solid #e2e8f0;padding:16px 40px;text-align:center;font-size:11px;color:#94a3b8}}
  .footer strong{{color:#64748b}}
  .hsn-badge{{background:#f1f5f9;color:#64748b;font-size:10px;padding:2px 6px;border-radius:4px;font-family:monospace}}
  .gst-zero{{color:#16a34a;font-size:11px;font-weight:600}}
  .gst-val{{color:#64748b;font-size:11px}}
  @media print{{
    body{{background:#fff}}
    .page{{box-shadow:none;max-width:100%}}
    @page{{margin:0;size:A4}}
  }}
</style></head><body>
<div class="page">
  <div class="topbar">
    <div>
      <div class="company-name">GLC Zone</div>
      <div class="company-sub">GLC Zone Private Limited | CIN: U68100BR2025PTC077112</div>
      <div class="company-sub" style="margin-top:2px">GSTIN: 10FZTPA0354J1ZJ | Kishanganj, Bihar — 855107</div>
    </div>
    <div class="quote-badge">
      <div class="quote-label">Quotation</div>
      <div class="quote-no">{q.get("quoteNo","")}</div>
      <div class="status-pill">{q.get("status","DRAFT")}</div>
    </div>
  </div>

  <div class="meta-bar">
    <div class="meta-item">Date Issued<strong>{q.get("createdAt","")[:10]}</strong></div>
    {"<div class='meta-item'>Valid Until<strong>" + valid_till + "</strong></div>" if valid_till else ""}
    {"<div class='meta-item'>Delivery Address<strong>" + q.get("customerAddress","") + "</strong></div>" if q.get("customerAddress") else ""}
  </div>

  <div class="body">
    <div class="bill-section">
      <div class="bill-box">
        <h4>Bill To</h4>
        <div class="name">{q.get("customerName","")}</div>
        {"<div class='detail'>" + q.get("companyName","") + "</div>" if q.get("companyName") else ""}
        {"<div class='detail'>📞 " + q.get("customerPhone","") + "</div>" if q.get("customerPhone") else ""}
        {"<div class='detail'>✉ " + q.get("customerEmail","") + "</div>" if q.get("customerEmail") else ""}
        {"<div class='detail'>GSTIN: " + q.get("customerGst","") + "</div>" if q.get("customerGst") else ""}
        {"<div class='detail'>" + q.get("customerState","") + "</div>" if q.get("customerState") else ""}
      </div>
      <div class="bill-box">
        <h4>From</h4>
        <div class="name">GLC Zone</div>
        <div class="detail">GLC Zone Private Limited</div>
        <div class="detail">Kishanganj, Bihar — 855107</div>
        <div class="detail">GSTIN: 10FZTPA0354J1ZJ</div>
        <div class="detail">📞 +91 89691 25123</div>
      </div>
    </div>

    <table>
      <thead><tr>
        <th>#</th><th>Item Description</th><th>HSN</th>
        <th style="text-align:right">Qty</th><th style="text-align:right">Unit</th>
        <th style="text-align:right">Rate</th><th style="text-align:right">Disc%</th>
        <th style="text-align:right">GST%</th><th style="text-align:right">Amount</th>
      </tr></thead>
      <tbody>{items_html}</tbody>
    </table>

    <div class="totals-wrap">
      <div class="totals-box">
        <div class="totals-row"><span>Subtotal</span><span>₹{q.get("subtotal",0):,.2f}</span></div>
        {"<div class='totals-row tax'><span>CGST</span><span>₹" + f"{q.get('cgst',0):,.2f}" + "</span></div><div class='totals-row tax'><span>SGST</span><span>₹" + f"{q.get('sgst',0):,.2f}" + "</span></div>" if q.get("cgst") else "<div class='totals-row tax'><span>IGST</span><span>₹" + f"{q.get('igst',0):,.2f}" + "</span></div>"}
        <div class="totals-row"><span>Grand Total</span><span>₹{q.get("total",0):,.2f}</span></div>
      </div>
    </div>

    {"<div class='notes-section'><h4>📝 Notes</h4><p>" + q.get("notes","") + "</p></div>" if q.get("notes") else ""}
    {"<div class='terms-section'><h4>📋 Terms & Conditions</h4><p>" + q.get("terms","") + "</p></div>" if q.get("terms") else ""}
  </div>

  <div class="footer">
    <strong>GLC Zone Private Limited</strong> · CIN: U68100BR2025PTC077112 · GSTIN: 10FZTPA0354J1ZJ<br>
    This is a computer-generated quotation and does not require a physical signature.
  </div>
</div>
<script>window.onload=()=>window.print()</script>
</body></html>"""
    return HTMLResponse(content=html)


@api.post("/quotations/{qid}/email")
async def email_quote(qid: str, user=Depends(current_user)):
    """Email quotation PDF to customer"""
    q = await db.quotations.find_one({"id": qid}, {"_id": 0})
    if not q:
        raise HTTPException(404, "Not found")
    customer_email = q.get("customerEmail", "")
    if not customer_email:
        raise HTTPException(400, "Customer email not set on this quotation")

    # Build PDF HTML (reuse same logic)
    items_html = ""
    for idx, it in enumerate(q.get("items", []), 1):
        disc = it.get("discount") or 0
        gst = it.get("gstRate") or 0
        amt = it["qty"] * it["rate"] * (1 - disc / 100)
        items_html += f"""<tr>
            <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;color:#64748b">{idx}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;font-weight:600">{it.get("name","")}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;color:#64748b">{it.get("hsn","")}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;text-align:right">{it["qty"]} {it.get("unit","")}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;text-align:right">₹{it["rate"]:,.2f}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;text-align:right;color:{'#16a34a' if gst==0 else '#64748b'}">{gst}%</td>
            <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;text-align:right;font-weight:600">₹{amt:,.2f}</td>
        </tr>"""

    valid_till = ""
    try:
        from datetime import datetime, timedelta
        created = q.get("createdAt","")[:10]
        vdays = int(q.get("validDays") or 30)
        dt = datetime.strptime(created, "%Y-%m-%d") + timedelta(days=vdays)
        valid_till = dt.strftime("%d %b %Y")
    except: pass

    html_body = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head><body style="margin:0;padding:0;background:#f8fafc;font-family:'Segoe UI',Arial,sans-serif">
<div style="max-width:680px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)">
  <div style="background:linear-gradient(135deg,#0f4c35,#166534);padding:28px 36px;color:#fff">
    <div style="font-size:24px;font-weight:800">GLC Zone</div>
    <div style="font-size:11px;color:rgba(255,255,255,.7);margin-top:4px">GLC Zone Private Limited | GSTIN: 10FZTPA0354J1ZJ | Kishanganj, Bihar</div>
    <div style="margin-top:16px;font-size:20px;font-weight:700;font-family:monospace">{q.get("quoteNo","")}</div>
    <div style="font-size:11px;color:rgba(255,255,255,.6);margin-top:2px">Date: {q.get("createdAt","")[:10]}{" · Valid till: " + valid_till if valid_till else ""}</div>
  </div>
  <div style="padding:28px 36px">
    <p style="font-size:14px;color:#1e293b;margin-bottom:20px">Dear <strong>{q.get("customerName","")}</strong>,</p>
    <p style="font-size:13px;color:#64748b;margin-bottom:24px">Thank you for your interest in GLC Zone. Please find your quotation details below.</p>
    <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
      <thead><tr style="background:#0f4c35">
        <th style="padding:10px 12px;color:#fff;text-align:left;font-size:11px;text-transform:uppercase">#</th>
        <th style="padding:10px 12px;color:#fff;text-align:left;font-size:11px;text-transform:uppercase">Item</th>
        <th style="padding:10px 12px;color:#fff;text-align:left;font-size:11px;text-transform:uppercase">HSN</th>
        <th style="padding:10px 12px;color:#fff;text-align:right;font-size:11px;text-transform:uppercase">Qty</th>
        <th style="padding:10px 12px;color:#fff;text-align:right;font-size:11px;text-transform:uppercase">Rate</th>
        <th style="padding:10px 12px;color:#fff;text-align:right;font-size:11px;text-transform:uppercase">GST</th>
        <th style="padding:10px 12px;color:#fff;text-align:right;font-size:11px;text-transform:uppercase">Amount</th>
      </tr></thead>
      <tbody>{items_html}</tbody>
    </table>
    <div style="display:flex;justify-content:flex-end;margin-bottom:24px">
      <div style="width:260px;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden">
        <div style="display:flex;justify-content:space-between;padding:8px 16px;font-size:12.5px;border-bottom:1px solid #f1f5f9"><span>Subtotal</span><span>₹{q.get("subtotal",0):,.2f}</span></div>
        <div style="display:flex;justify-content:space-between;padding:8px 16px;font-size:12.5px;color:#64748b;border-bottom:1px solid #f1f5f9"><span>{"CGST + SGST" if q.get("cgst") else "IGST"}</span><span>₹{(q.get("cgst",0)*2 if q.get("cgst") else q.get("igst",0)):,.2f}</span></div>
        <div style="display:flex;justify-content:space-between;padding:10px 16px;font-size:14px;font-weight:700;background:#0f4c35;color:#fff"><span>Grand Total</span><span>₹{q.get("total",0):,.2f}</span></div>
      </div>
    </div>
    {"<div style='background:#fffbeb;border:1px solid #fef3c7;border-radius:8px;padding:12px 16px;margin-bottom:16px'><div style='font-size:10px;color:#92400e;font-weight:600;text-transform:uppercase;margin-bottom:4px'>Notes</div><div style='font-size:12px;color:#78350f'>" + q.get("notes","") + "</div></div>" if q.get("notes") else ""}
    {"<div style='background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;padding:12px 16px;margin-bottom:16px'><div style='font-size:10px;color:#0369a1;font-weight:600;text-transform:uppercase;margin-bottom:4px'>Terms & Conditions</div><div style='font-size:12px;color:#0c4a6e'>" + q.get("terms","") + "</div></div>" if q.get("terms") else ""}
    <p style="font-size:13px;color:#64748b;margin-top:24px">For any queries, please contact us at <strong>bdey@glczone.in</strong> or call <strong>+91 89691 25123</strong>.</p>
    <p style="font-size:13px;color:#1e293b;margin-top:8px">Thank you for your business! 🙏</p>
  </div>
  <div style="background:#f8fafc;border-top:1px solid #e2e8f0;padding:16px 36px;text-align:center;font-size:11px;color:#94a3b8">
    <strong style="color:#64748b">GLC Zone Private Limited</strong> · CIN: U68100BR2025PTC077112 · GSTIN: 10FZTPA0354J1ZJ<br>
    This is a computer-generated quotation and does not require a physical signature.
  </div>
</div></body></html>"""

    import aiosmtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Quotation {q.get('quoteNo','')} from GLC Zone — ₹{q.get('total',0):,.0f}"
    msg["From"] = "GLC Zone <bdey@glczone.in>"
    msg["To"] = customer_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname="smtp.gmail.com",
            port=587,
            start_tls=True,
            username="bdey@glczone.in",
            password=__import__("os").getenv("GLCZONE_DB_PASSWORD", ""),
        )
        await db.quotations.update_one({"id": qid}, {"$set": {"status": "SENT", "updatedAt": now_iso()}})
        return {"ok": True, "sent_to": customer_email}
    except Exception as e:
        raise HTTPException(500, f"Email failed: {str(e)}")


@api.post("/quotations/{qid}/convert")
async def convert_quote_to_order(qid: str, user=Depends(current_user)):
    q = await db.quotations.find_one({"id": qid}, {"_id": 0})
    if not q:
        raise HTTPException(404, "Not found")
    count = await db.sales_orders.count_documents({})
    order = {
        "id": uid(),
        "orderNo": f"SO-{datetime.now().year}-{count+1001}",
        "customerId": q.get("customerId"),
        "customerName": q["customerName"],
        "customerGst": q.get("customerGst"),
        "customerState": q.get("customerState"),
        "items": q["items"],
        "subtotal": q["subtotal"],
        "cgst": q["cgst"],
        "sgst": q["sgst"],
        "igst": q["igst"],
        "total": q["total"],
        "status": "CONFIRMED",
        "store": q.get("vertical") or "GLC Zone",
        "vertical": q.get("vertical"),
        "quotationId": qid,
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    await db.sales_orders.insert_one(order)
    await db.quotations.update_one({"id": qid}, {"$set": {"status": "CONVERTED", "orderId": order["id"]}})
    # deduct stock
    for it in q["items"]:
        if it.get("productId"):
            await db.stock_items.update_one({"productId": it["productId"]}, {"$inc": {"qty": -it["qty"]}})
    await log_activity(user["id"], "quotations", "convert-to-order", qid, {"orderId": order["id"]})
    return clean(order)


# =========================================================
# SALES: Orders, Invoices, Payments
# =========================================================
class OrderIn(BaseModel):
    customerId: Optional[str] = None
    customerName: str
    customerGst: Optional[str] = None
    customerState: Optional[str] = None
    items: List[QuoteItem] = []
    store: str = "GLC Zone"
    vertical: Optional[str] = None
    status: str = "PENDING"
    notes: Optional[str] = None


@api.get("/orders")
async def list_orders(page: int = 1, limit: int = 50, q: Optional[str] = None, status_: Optional[str] = Query(None, alias="status"), vertical: Optional[str] = None, user=Depends(current_user)):
    filt = {}
    if status_:
        filt["status"] = status_
    if vertical:
        filt["vertical"] = vertical
    return await paginate(db.sales_orders, filt, page, limit, search_fields=["orderNo", "customerName"], q=q)


@api.post("/orders")
async def create_order(data: OrderIn, user=Depends(current_user)):
    items = [i.model_dump() for i in data.items]
    intra = gf.is_intra_state(data.customerGst, data.customerState)
    totals = calc_gst(items, intra_state=intra)
    count = await db.sales_orders.count_documents({})
    doc = {**data.model_dump(), "id": uid(), "orderNo": f"SO-{datetime.now().year}-{count+1001}", "items": items, **totals, "createdAt": now_iso(), "updatedAt": now_iso()}
    await db.sales_orders.insert_one(doc)
    if doc["status"] == "CONFIRMED":
        for it in items:
            if it.get("productId"):
                await db.stock_items.update_one({"productId": it["productId"]}, {"$inc": {"qty": -it["qty"]}})
    await log_activity(user["id"], "orders", "create", doc["id"])
    return clean(doc)


@api.get("/orders/{oid}")
async def get_order(oid: str, user=Depends(current_user)):
    d = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Not found")
    return d


@api.put("/orders/{oid}")
async def update_order(oid: str, body: Dict[str, Any], user=Depends(current_user)):
    body["updatedAt"] = now_iso()
    await db.sales_orders.update_one({"id": oid}, {"$set": body})
    d = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
    return d


@api.delete("/orders/{oid}")
async def delete_order(oid: str, user=Depends(current_user)):
    await db.sales_orders.delete_one({"id": oid})
    return {"ok": True}


async def current_user_optional(request: Request):
    """JWT optional — None return karta hai agar token nahi."""
    try:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        token = auth.split(" ", 1)[1]
        return await current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    except Exception:
        return None

async def current_user_or_secret(request: Request):
    """GLC_BRIDGE_AUTH: JWT login ya X-CRM-Secret header dono accept karta hai."""
    secret = os.environ.get("CRM_BRIDGE_SECRET", "")
    if secret and request.headers.get("X-CRM-Secret") == secret:
        return {"id": "system", "role": "system"}
    user = await current_user_optional(request)
    if user:
        return user
    raise HTTPException(401, "Unauthorized")


@api.post("/orders/{oid}/invoice")
async def generate_invoice(oid: str, request: Request, user=Depends(current_user_or_secret)):
    # GLC_BRIDGE_AUTH: JWT ya X-CRM-Secret dono se kaam kare
    # id, externalId, ya orderNo (GLZ-25) teeno se dhundho
    o = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
    if not o:
        o = await db.sales_orders.find_one({"externalId": str(oid)}, {"_id": 0})
    if not o:
        o = await db.sales_orders.find_one({"orderNo": str(oid)}, {"_id": 0})
    if not o:
        # the website asks for "GLZ-<id>" but real-time webhook orders used to be stored as "#<id>": match on the website id
        site_id = re.sub(r"^(GLZ-|#)", "", str(oid))
        o = await db.sales_orders.find_one({"glczone_order_id": site_id}, {"_id": 0})
    if not o:
        raise HTTPException(404, "Not found")
    oid = o["id"]  # ab CRM ka internal UUID use karo
    exists = await db.invoices.find_one({"orderId": oid}, {"_id": 0})
    if exists:
        return exists
    if o.get("glczoneItems"):
        items = gf.items_from_glczone(o)          # website order: tax, discount and delivery charge as billed
    else:
        items = o.get("items") or []
        if not items and isinstance(o.get("products"), str) and o["products"].strip():
            paid = float(o.get("finalTotal") or o.get("total") or 0)      # legacy synced order: one line, what was paid
            items = [{"name": o["products"].strip(), "qty": 1, "rate": paid, "gstRate": 0}]
    if not items:
        raise HTTPException(400, "Order has no items to invoice")
    pos = gf.place_of_supply(o.get("customerGst"), o.get("customerState"))
    intra = pos == gf.COMPANY_STATE_CODE
    t = calc_gst(items, intra_state=intra, round_off=True)
    method = str(o.get("paymentMethod") or "").upper()
    delivered = str(o.get("glczone_status") or o.get("status") or "").lower() == "delivered"
    prepaid = str(o.get("paymentStatus") or "").upper() in ("PAID", "SUCCESS", "COMPLETED", "CAPTURED")
    paid_now = prepaid or (method in ("COD", "CASH") and delivered)      # COD cash is collected at the door
    inv_no = gf.doc_number("INV", await next_seq("INV"))
    inv = {
        "id": uid(),
        "invoiceNo": inv_no,
        "orderId": oid,
        "orderNo": o.get("orderNo"),
        "customerId": o.get("customerId"),
        "customerName": o["customerName"],
        "customerGst": o.get("customerGst"),
        "customerState": o.get("customerState") or gf.STATE_CODES.get(pos),
        "placeOfSupply": f"{pos}-{gf.STATE_CODES.get(pos, '')}",
        "supplyType": "INTRA" if intra else "INTER",
        "items": items,
        "lines": t["lines"],
        "subtotal": t["subtotal"],
        "cgst": t["cgst"],
        "sgst": t["sgst"],
        "igst": t["igst"],
        "roundOff": t["roundOff"],
        "total": t["total"],
        "paidAmount": t["total"] if paid_now else 0,
        "creditedAmount": 0,
        "dueAmount": 0 if paid_now else t["total"],
        "status": "PAID" if paid_now else "UNPAID",
        "vertical": o.get("vertical"),
        "invoiceDate": now_iso(),
        "dueDate": (datetime.now(timezone.utc) + timedelta(days=15)).isoformat(),
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    await db.invoices.insert_one(inv)
    await post_journal(f"Invoice {inv_no}", gf.journal_for_invoice(inv), "INV", inv["id"], user)
    if paid_now:
        pay = {"id": uid(), "invoiceId": inv["id"], "customerId": inv.get("customerId"), "amount": t["total"],
               "method": "CASH" if method in ("COD", "CASH") else (method or "ONLINE"), "reference": f"Auto: {method or 'prepaid'} order {o.get('orderNo') or oid}",
               "date": now_iso(), "createdAt": now_iso()}
        await db.payments.insert_one(pay)
        await post_journal(f"Payment for {inv_no}", gf.journal_for_payment(pay["amount"], pay["method"]), "PAY", pay["id"], user)
    await log_activity(user["id"], "invoices", "generate", inv["id"], {"orderId": oid})
    return clean(inv)

# Invoices
@api.get("/invoices")
async def list_invoices(page: int = 1, limit: int = 50, q: Optional[str] = None, status_: Optional[str] = Query(None, alias="status"), user=Depends(current_user)):
    filt = {}
    if status_:
        filt["status"] = status_
    return await paginate(db.invoices, filt, page, limit, search_fields=["invoiceNo", "customerName"], q=q)


@api.get("/invoices/{iid}")
async def get_invoice(iid: str, user=Depends(current_user)):
    d = await db.invoices.find_one({"id": iid}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Not found")
    pays = await db.payments.find({"invoiceId": iid}, {"_id": 0}).to_list(50)
    return {"invoice": d, "payments": pays}


class PaymentIn(BaseModel):
    invoiceId: str
    amount: float
    method: str = "CASH"
    reference: Optional[str] = None
    date: Optional[str] = None


@api.post("/payments")
async def add_payment(data: PaymentIn, user=Depends(finance_user)):
    inv = await db.invoices.find_one({"id": data.invoiceId}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if data.amount <= 0:
        raise HTTPException(400, "Payment amount must be positive")
    if inv.get("status") == "CANCELLED":
        raise HTTPException(400, "Invoice is cancelled")
    due_now = round(inv["total"] - (inv.get("paidAmount") or 0) - (inv.get("creditedAmount") or 0), 2)
    if data.amount > due_now + 0.01:
        raise HTTPException(400, f"Payment exceeds the amount due (₹{due_now:,.2f})")
    pay = {
        "id": uid(),
        "invoiceId": data.invoiceId,
        "customerId": inv.get("customerId"),
        "amount": data.amount,
        "method": data.method,
        "reference": data.reference,
        "date": data.date or now_iso(),
        "createdAt": now_iso(),
    }
    await db.payments.insert_one(pay)
    new_paid = (inv.get("paidAmount", 0) or 0) + data.amount
    new_due = max(round(inv["total"] - new_paid - (inv.get("creditedAmount") or 0), 2), 0)
    status_ = "PAID" if new_due <= 0.01 else ("PARTIAL" if new_paid > 0 else "UNPAID")
    await db.invoices.update_one({"id": data.invoiceId}, {"$set": {"paidAmount": new_paid, "dueAmount": new_due, "status": status_, "updatedAt": now_iso()}})
    await post_journal(f"Payment for {inv.get('invoiceNo')}", gf.journal_for_payment(data.amount, data.method), "PAY", pay["id"], user)
    await log_activity(user["id"], "payments", "create", pay["id"], {"invoiceId": data.invoiceId})
    return clean(pay)


@api.get("/payments")
async def list_payments(page: int = 1, limit: int = 50, user=Depends(finance_user)):
    return await paginate(db.payments, {}, page, limit)


# =========================================================
# INVENTORY: Products, Categories, Warehouses, Stock
# =========================================================
class ProductIn(BaseModel):
    name: str
    sku: str
    barcode: Optional[str] = None
    category: Optional[str] = None
    hsn: Optional[str] = None
    gstRate: float = 18
    unit: str = "PCS"
    buyingPrice: float = 0
    sellingPrice: float = 0
    mrp: float = 0
    minStock: int = 5
    image: Optional[str] = None
    description: Optional[str] = None
    vertical: Optional[str] = None


@api.get("/products")
async def list_products(page: int = 1, limit: int = 50, q: Optional[str] = None, vertical: Optional[str] = None, user=Depends(current_user)):
    filt = {}
    if vertical:
        filt["vertical"] = vertical
    return await paginate(db.products, filt, page, limit, search_fields=["name", "sku", "barcode", "category"], q=q)


@api.post("/products")
async def create_product(data: ProductIn, user=Depends(current_user)):
    doc = {**data.model_dump(), "id": uid(), "createdAt": now_iso(), "updatedAt": now_iso()}
    await db.products.insert_one(doc)
    # create default stock item
    wh = await db.warehouses.find_one({"isDefault": True}, {"_id": 0})
    if wh:
        await db.stock_items.insert_one({"id": uid(), "productId": doc["id"], "warehouseId": wh["id"], "qty": 0, "updatedAt": now_iso()})
    return clean(doc)


@api.put("/products/{pid}")
async def update_product(pid: str, data: ProductIn, user=Depends(current_user)):
    await db.products.update_one({"id": pid}, {"$set": {**data.model_dump(), "updatedAt": now_iso()}})
    d = await db.products.find_one({"id": pid}, {"_id": 0})
    return d


@api.delete("/products/{pid}")
async def delete_product(pid: str, user=Depends(current_user)):
    await db.products.delete_one({"id": pid})
    return {"ok": True}


@api.get("/warehouses")
async def list_warehouses(user=Depends(current_user)):
    items = await db.warehouses.find({}, {"_id": 0}).to_list(100)
    return {"items": items}


class WarehouseIn(BaseModel):
    name: str
    city: Optional[str] = None
    address: Optional[str] = None
    isDefault: bool = False


@api.post("/warehouses")
async def create_warehouse(data: WarehouseIn, user=Depends(current_user)):
    doc = {**data.model_dump(), "id": uid(), "createdAt": now_iso()}
    await db.warehouses.insert_one(doc)
    return clean(doc)


@api.get("/inventory/stock")
async def list_stock(user=Depends(current_user)):
    items = await db.stock_items.find({}, {"_id": 0}).to_list(1000)
    # enrich with product
    prod_ids = list({s["productId"] for s in items})
    prods = await db.products.find({"id": {"$in": prod_ids}}, {"_id": 0}).to_list(1000)
    pmap = {p["id"]: p for p in prods}
    whs = await db.warehouses.find({}, {"_id": 0}).to_list(100)
    wmap = {w["id"]: w for w in whs}
    for s in items:
        s["product"] = pmap.get(s["productId"])
        s["warehouse"] = wmap.get(s.get("warehouseId"))
    return {"items": items}


@api.get("/inventory/low-stock")
async def low_stock(user=Depends(current_user)):
    prods = await db.products.find({}, {"_id": 0}).to_list(1000)
    stocks = await db.stock_items.find({}, {"_id": 0}).to_list(1000)
    smap: Dict[str, float] = {}
    for s in stocks:
        smap[s["productId"]] = smap.get(s["productId"], 0) + s.get("qty", 0)
    low = [{**p, "currentStock": smap.get(p["id"], 0)} for p in prods if smap.get(p["id"], 0) <= p.get("minStock", 5)]
    return {"items": low}


class StockAdjIn(BaseModel):
    productId: str
    warehouseId: Optional[str] = None
    qty: float
    reason: str = "adjustment"


@api.post("/inventory/adjust")
async def adjust_stock(data: StockAdjIn, user=Depends(current_user)):
    wh_id = data.warehouseId
    if not wh_id:
        wh = await db.warehouses.find_one({"isDefault": True}, {"_id": 0})
        wh_id = wh["id"] if wh else None
    exist = await db.stock_items.find_one({"productId": data.productId, "warehouseId": wh_id})
    if exist:
        await db.stock_items.update_one({"id": exist["id"]}, {"$inc": {"qty": data.qty}, "$set": {"updatedAt": now_iso()}})
    else:
        await db.stock_items.insert_one({"id": uid(), "productId": data.productId, "warehouseId": wh_id, "qty": data.qty, "updatedAt": now_iso()})
    await db.stock_movements.insert_one({"id": uid(), "productId": data.productId, "warehouseId": wh_id, "qty": data.qty, "reason": data.reason, "by": user["id"], "at": now_iso()})
    return {"ok": True}


# =========================================================
# PURCHASE
# =========================================================
class SupplierIn(BaseModel):
    name: str
    gst: Optional[str] = None
    pan: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    bankName: Optional[str] = None
    accountNo: Optional[str] = None
    paymentTerms: Optional[str] = "Net 30"
    rating: float = 4.0
    vertical: Optional[str] = None


@api.get("/suppliers")
async def list_suppliers(page: int = 1, limit: int = 50, q: Optional[str] = None, user=Depends(current_user)):
    return await paginate(db.suppliers, {}, page, limit, search_fields=["name", "gst", "email", "phone"], q=q)


@api.post("/suppliers")
async def create_supplier(data: SupplierIn, user=Depends(current_user)):
    doc = {**data.model_dump(), "id": uid(), "createdAt": now_iso(), "updatedAt": now_iso()}
    await db.suppliers.insert_one(doc)
    return clean(doc)


@api.put("/suppliers/{sid}")
async def update_supplier(sid: str, data: SupplierIn, user=Depends(current_user)):
    await db.suppliers.update_one({"id": sid}, {"$set": {**data.model_dump(), "updatedAt": now_iso()}})
    d = await db.suppliers.find_one({"id": sid}, {"_id": 0})
    return d


@api.delete("/suppliers/{sid}")
async def delete_supplier(sid: str, user=Depends(current_user)):
    await db.suppliers.delete_one({"id": sid})
    return {"ok": True}


class POIn(BaseModel):
    supplierId: str
    supplierName: str
    items: List[QuoteItem] = []
    status: str = "DRAFT"
    expectedDate: Optional[str] = None
    notes: Optional[str] = None
    vertical: Optional[str] = None


@api.get("/purchase-orders")
async def list_pos(page: int = 1, limit: int = 50, q: Optional[str] = None, user=Depends(current_user)):
    return await paginate(db.purchase_orders, {}, page, limit, search_fields=["poNo", "supplierName"], q=q)


@api.post("/purchase-orders")
async def create_po(data: POIn, user=Depends(current_user)):
    items = [i.model_dump() for i in data.items]
    sup = await db.suppliers.find_one({"id": data.supplierId}, {"_id": 0}) or {}
    intra = gf.is_intra_state(sup.get("gst"), sup.get("state"))
    totals = calc_gst(items, intra_state=intra)
    count = await db.purchase_orders.count_documents({})
    doc = {**data.model_dump(), "id": uid(), "poNo": f"PO-{datetime.now().year}-{count+1001}", "items": items, **totals,
           "supplierGst": sup.get("gst") or "", "itcEligible": gf.valid_gstin(sup.get("gst")), "createdAt": now_iso(), "updatedAt": now_iso()}
    await db.purchase_orders.insert_one(doc)
    return clean(doc)


@api.put("/purchase-orders/{pid}")
async def update_po(pid: str, body: Dict[str, Any], user=Depends(current_user)):
    body["updatedAt"] = now_iso()
    # If marking RECEIVED, increment stock
    prev_po = await db.purchase_orders.find_one({"id": pid}, {"_id": 0}) or {}
    just_received = body.get("status") == "RECEIVED" and prev_po.get("status") != "RECEIVED"
    if just_received:
        body["receivedAt"] = now_iso()
        po = prev_po
        if po:
            for it in po.get("items", []):
                if it.get("productId"):
                    wh = await db.warehouses.find_one({"isDefault": True}, {"_id": 0})
                    wh_id = wh["id"] if wh else None
                    exist = await db.stock_items.find_one({"productId": it["productId"], "warehouseId": wh_id})
                    if exist:
                        await db.stock_items.update_one({"id": exist["id"]}, {"$inc": {"qty": it["qty"]}})
                    else:
                        await db.stock_items.insert_one({"id": uid(), "productId": it["productId"], "warehouseId": wh_id, "qty": it["qty"], "updatedAt": now_iso()})
    await db.purchase_orders.update_one({"id": pid}, {"$set": body})
    d = await db.purchase_orders.find_one({"id": pid}, {"_id": 0})
    if just_received and d:
        await post_journal(f"Goods received {d.get('poNo')}", gf.journal_for_purchase(d), "PO", pid, user)
    return d


@api.delete("/purchase-orders/{pid}")
async def delete_po(pid: str, user=Depends(current_user)):
    await db.purchase_orders.delete_one({"id": pid})
    return {"ok": True}


# =========================================================
# DELIVERY
# =========================================================
class DeliveryIn(BaseModel):
    orderId: str
    orderNo: Optional[str] = None
    customerName: Optional[str] = None
    address: Optional[str] = None
    assignedTo: Optional[str] = None
    status: str = "PENDING"
    otp: Optional[str] = None
    scheduledDate: Optional[str] = None


@api.get("/deliveries")
async def list_deliveries(status_: Optional[str] = Query(None, alias="status"), user=Depends(current_user)):
    filt = {}
    if status_:
        filt["status"] = status_
    items = await db.deliveries.find(filt, {"_id": 0}).sort("createdAt", -1).to_list(500)
    return {"items": items}


@api.post("/deliveries")
async def create_delivery(data: DeliveryIn, user=Depends(current_user)):
    import random
    otp = data.otp or f"{random.randint(1000,9999)}"
    doc = {**data.model_dump(), "id": uid(), "otp": otp, "createdAt": now_iso(), "updatedAt": now_iso()}
    await db.deliveries.insert_one(doc)
    return clean(doc)


@api.put("/deliveries/{did}")
async def update_delivery(did: str, body: Dict[str, Any], user=Depends(current_user)):
    body["updatedAt"] = now_iso()
    await db.deliveries.update_one({"id": did}, {"$set": body})
    d = await db.deliveries.find_one({"id": did}, {"_id": 0})
    return d


# =========================================================
# HR: employees / attendance / leaves / payroll
# =========================================================
class EmployeeIn(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    employeeId: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    joiningDate: Optional[str] = None
    salary: float = 0
    address: Optional[str] = None
    pan: Optional[str] = None
    bankName: Optional[str] = None
    accountNo: Optional[str] = None
    avatar: Optional[str] = None
    status: str = "ACTIVE"


@api.get("/employees")
async def list_employees(page: int = 1, limit: int = 100, q: Optional[str] = None, user=Depends(current_user)):
    return await paginate(db.employees, {}, page, limit, search_fields=["name", "email", "department", "designation", "employeeId"], q=q)


@api.post("/employees")
async def create_employee(data: EmployeeIn, user=Depends(current_user)):
    count = await db.employees.count_documents({})
    doc = {**data.model_dump(), "id": uid(), "employeeId": data.employeeId or f"GLC{1000+count+1}", "createdAt": now_iso(), "updatedAt": now_iso()}
    await db.employees.insert_one(doc)
    return clean(doc)


@api.put("/employees/{eid}")
async def update_employee(eid: str, data: EmployeeIn, user=Depends(current_user)):
    await db.employees.update_one({"id": eid}, {"$set": {**data.model_dump(), "updatedAt": now_iso()}})
    d = await db.employees.find_one({"id": eid}, {"_id": 0})
    return d


@api.delete("/employees/{eid}")
async def delete_employee(eid: str, user=Depends(current_user)):
    await db.employees.delete_one({"id": eid})
    return {"ok": True}


class AttendanceIn(BaseModel):
    employeeId: str
    date: str
    status: str = "PRESENT"
    checkIn: Optional[str] = None
    checkOut: Optional[str] = None


@api.get("/attendance")
async def list_attendance(month: Optional[str] = None, employeeId: Optional[str] = None, user=Depends(current_user)):
    filt = {}
    if month:
        filt["date"] = {"$regex": f"^{month}"}
    if employeeId:
        filt["employeeId"] = employeeId
    items = await db.attendance.find(filt, {"_id": 0}).to_list(2000)
    return {"items": items}


@api.post("/attendance")
async def mark_attendance(data: AttendanceIn, user=Depends(current_user)):
    exist = await db.attendance.find_one({"employeeId": data.employeeId, "date": data.date})
    if exist:
        await db.attendance.update_one({"id": exist["id"]}, {"$set": data.model_dump()})
        return {"ok": True, "updated": True}
    doc = {**data.model_dump(), "id": uid(), "createdAt": now_iso()}
    await db.attendance.insert_one(doc)
    return clean(doc)


class LeaveIn(BaseModel):
    employeeId: str
    employeeName: Optional[str] = None
    leaveType: str = "CL"
    fromDate: str
    toDate: str
    days: float = 1
    reason: Optional[str] = None
    status: str = "PENDING"


@api.get("/leaves")
async def list_leaves(status_: Optional[str] = Query(None, alias="status"), user=Depends(current_user)):
    filt = {}
    if status_:
        filt["status"] = status_
    items = await db.leaves.find(filt, {"_id": 0}).sort("createdAt", -1).to_list(500)
    return {"items": items}


@api.post("/leaves")
async def apply_leave(data: LeaveIn, user=Depends(current_user)):
    doc = {**data.model_dump(), "id": uid(), "createdAt": now_iso()}
    await db.leaves.insert_one(doc)
    return clean(doc)


@api.put("/leaves/{lid}")
async def update_leave(lid: str, body: Dict[str, Any], user=Depends(current_user)):
    await db.leaves.update_one({"id": lid}, {"$set": body})
    d = await db.leaves.find_one({"id": lid}, {"_id": 0})
    return d


@api.post("/payroll/generate")
async def generate_payroll(body: Dict[str, Any], user=Depends(current_user)):
    month = body.get("month") or datetime.now().strftime("%Y-%m")
    emps = await db.employees.find({"status": "ACTIVE"}, {"_id": 0}).to_list(500)
    generated = 0
    for e in emps:
        exist = await db.payroll.find_one({"employeeId": e["id"], "month": month})
        if exist:
            continue
        basic = e.get("salary", 0)
        pf = basic * 0.12
        esi = basic * 0.0175
        tds = basic * 0.05 if basic > 50000 else 0
        net = basic - pf - esi - tds
        await db.payroll.insert_one({
            "id": uid(),
            "employeeId": e["id"],
            "employeeName": e["name"],
            "month": month,
            "basic": basic,
            "pf": round(pf, 2),
            "esi": round(esi, 2),
            "tds": round(tds, 2),
            "netSalary": round(net, 2),
            "status": "GENERATED",
            "createdAt": now_iso(),
        })
        generated += 1
    return {"generated": generated, "month": month}


@api.get("/payroll")
async def list_payroll(month: Optional[str] = None, user=Depends(current_user)):
    filt = {}
    if month:
        filt["month"] = month
    items = await db.payroll.find(filt, {"_id": 0}).sort("createdAt", -1).to_list(500)
    return {"items": items}


# =========================================================
# ACCOUNTING / FINANCE
# =========================================================
class AccountIn(BaseModel):
    code: str
    name: str
    type: str  # ASSET / LIABILITY / EQUITY / INCOME / EXPENSE
    balance: float = 0


@api.get("/accounts")
async def list_accounts(user=Depends(finance_user)):
    items = await db.accounts.find({}, {"_id": 0}).sort("code", 1).to_list(500)
    journals = await db.journal.find({}, {"_id": 0, "entries": 1}).to_list(100000)
    bal = {r["id"]: r["balance"] for r in gf.trial_balance(items, journals)["rows"]}
    for a in items:
        a["balance"] = bal.get(a["id"], 0)
    return {"items": items}


@api.post("/accounts")
async def create_account(data: AccountIn, user=Depends(finance_user)):
    doc = {**data.model_dump(), "id": uid(), "createdAt": now_iso()}
    await db.accounts.insert_one(doc)
    return clean(doc)


class JournalIn(BaseModel):
    date: str
    narration: str
    entries: List[Dict[str, Any]] = []  # [{accountId, debit, credit}]


@api.get("/journal")
async def list_journal(user=Depends(current_user)):
    items = await db.journal.find({}, {"_id": 0}).sort("date", -1).to_list(500)
    return {"items": items}


@api.post("/journal")
async def create_journal(data: JournalIn, user=Depends(finance_user)):
    total_dr = sum(e.get("debit", 0) for e in data.entries)
    total_cr = sum(e.get("credit", 0) for e in data.entries)
    if round(total_dr, 2) != round(total_cr, 2):
        raise HTTPException(400, "Debit and Credit totals must match")
    ids = {a["id"]: a["code"] async for a in db.accounts.find({}, {"_id": 0, "id": 1, "code": 1})}
    for e in data.entries:
        if e.get("accountId") not in ids:
            raise HTTPException(400, "Unknown account in journal entry")
        if float(e.get("debit") or 0) < 0 or float(e.get("credit") or 0) < 0:
            raise HTTPException(400, "Debit/credit cannot be negative")
        e["accountCode"] = ids[e["accountId"]]
    doc = {**data.model_dump(), "id": uid(), "refType": "MANUAL", "refId": None, "totalDebit": total_dr, "totalCredit": total_cr,
           "createdBy": user.get("id"), "createdAt": now_iso()}
    await db.journal.insert_one(doc)
    return clean(doc)


def _month_filter(field: str, month: Optional[str]) -> dict:
    if month and not re.match(r"^\d{4}-\d{2}$", month):
        raise HTTPException(400, "month must look like 2026-09")
    return {field: {"$regex": f"^{month}"}} if month else {}


@api.get("/reports/gst")
async def gst_report(month: Optional[str] = None, user=Depends(finance_user)):
    invoices = await db.invoices.find({**_month_filter("invoiceDate", month), "status": {"$ne": "CANCELLED"}}, {"_id": 0}).to_list(20000)
    notes = await db.credit_notes.find(_month_filter("noteDate", month), {"_id": 0}).to_list(20000)

    def net(key):
        return round(sum(i.get(key, 0) or 0 for i in invoices) - sum(c.get(key, 0) or 0 for c in notes), 2)
    return {
        "month": month,
        "invoices": invoices,
        "creditNotes": notes,
        "summary": {
            "taxableValue": net("subtotal"), "cgst": net("cgst"), "sgst": net("sgst"), "igst": net("igst"),
            "total": net("total"), "count": len(invoices), "creditNoteCount": len(notes),
        },
    }


@api.get("/reports/pl")
async def pl_report(user=Depends(finance_user)):
    sales = credits = 0.0
    async for i in db.invoices.find({"status": {"$ne": "CANCELLED"}}, {"_id": 0, "subtotal": 1}):
        sales += i.get("subtotal", 0)
    async for c in db.credit_notes.find({}, {"_id": 0, "subtotal": 1}):
        credits += c.get("subtotal", 0)
    expenses = 0.0
    async for e in db.expenses.find({"status": "APPROVED"}, {"_id": 0}):
        expenses += e.get("amount", 0)
    revenue = sales - credits            # GST collected is not income, so only the taxable value counts
    return {"revenue": round(revenue, 2), "grossSales": round(sales, 2), "salesReturns": round(credits, 2),
            "expenses": round(expenses, 2), "netProfit": round(revenue - expenses, 2)}


class ExpenseIn(BaseModel):
    title: str
    amount: float
    category: str = "General"
    date: Optional[str] = None
    submittedBy: Optional[str] = None
    receipt: Optional[str] = None
    status: str = "PENDING"


@api.get("/expenses")
async def list_expenses(user=Depends(current_user)):
    items = await db.expenses.find({}, {"_id": 0}).sort("createdAt", -1).to_list(500)
    return {"items": items}


@api.post("/expenses")
async def create_expense(data: ExpenseIn, user=Depends(current_user)):
    doc = {**data.model_dump(), "id": uid(), "createdAt": now_iso()}
    await db.expenses.insert_one(doc)
    return clean(doc)


@api.put("/expenses/{eid}")
async def update_expense(eid: str, body: Dict[str, Any], user=Depends(current_user)):
    await db.expenses.update_one({"id": eid}, {"$set": body})
    d = await db.expenses.find_one({"id": eid}, {"_id": 0})
    return d


# =========================================================
# PROJECTS / TASKS
# =========================================================
class ProjectIn(BaseModel):
    name: str
    description: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    budget: float = 0
    status: str = "ACTIVE"
    team: List[str] = []
    vertical: Optional[str] = None


@api.get("/projects")
async def list_projects(user=Depends(current_user)):
    items = await db.projects.find({}, {"_id": 0}).sort("createdAt", -1).to_list(200)
    return {"items": items}


@api.post("/projects")
async def create_project(data: ProjectIn, user=Depends(current_user)):
    doc = {**data.model_dump(), "id": uid(), "createdAt": now_iso()}
    await db.projects.insert_one(doc)
    return clean(doc)


@api.put("/projects/{pid}")
async def update_project(pid: str, body: Dict[str, Any], user=Depends(current_user)):
    await db.projects.update_one({"id": pid}, {"$set": body})
    d = await db.projects.find_one({"id": pid}, {"_id": 0})
    return d


class TaskIn(BaseModel):
    title: str
    projectId: Optional[str] = None
    projectName: Optional[str] = None
    assignedTo: Optional[str] = None
    assignedToName: Optional[str] = None
    status: str = "TODO"
    priority: str = "MEDIUM"
    dueDate: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []


@api.get("/tasks")
async def list_tasks(projectId: Optional[str] = None, user=Depends(current_user)):
    filt = {}
    if projectId:
        filt["projectId"] = projectId
    items = await db.tasks.find(filt, {"_id": 0}).sort("createdAt", -1).to_list(500)
    return {"items": items}


@api.post("/tasks")
async def create_task(data: TaskIn, user=Depends(current_user)):
    doc = {**data.model_dump(), "id": uid(), "createdAt": now_iso()}
    await db.tasks.insert_one(doc)
    return clean(doc)


@api.put("/tasks/{tid}")
async def update_task(tid: str, body: Dict[str, Any], user=Depends(current_user)):
    await db.tasks.update_one({"id": tid}, {"$set": body})
    d = await db.tasks.find_one({"id": tid}, {"_id": 0})
    return d


@api.delete("/tasks/{tid}")
async def delete_task(tid: str, user=Depends(current_user)):
    await db.tasks.delete_one({"id": tid})
    return {"ok": True}


# =========================================================
# SUPPORT / TICKETS
# =========================================================
class TicketIn(BaseModel):
    subject: str
    description: Optional[str] = None
    customerId: Optional[str] = None
    customerName: Optional[str] = None
    priority: str = "MEDIUM"
    status: str = "OPEN"
    assignedTo: Optional[str] = None


@api.get("/tickets")
async def list_tickets(page: int = 1, limit: int = 50, q: Optional[str] = None, status_: Optional[str] = Query(None, alias="status"), user=Depends(current_user)):
    filt = {}
    if status_:
        filt["status"] = status_
    return await paginate(db.tickets, filt, page, limit, search_fields=["ticketNo", "subject", "customerName"], q=q)


@api.post("/tickets")
async def create_ticket(data: TicketIn, user=Depends(current_user)):
    count = await db.tickets.count_documents({})
    doc = {**data.model_dump(), "id": uid(), "ticketNo": f"TKT-{count+1001:04d}", "replies": [], "createdAt": now_iso(), "updatedAt": now_iso()}
    await db.tickets.insert_one(doc)
    return clean(doc)


# glczone.in ticket status (numeric) <-> CRM status (string) mapping
GLCZONE_TICKET_STATUS_TO_CRM = {1: "PENDING", 2: "OPEN", 3: "RESOLVED", 4: "CLOSED", 5: "REOPENED"}
CRM_TICKET_STATUS_TO_GLCZONE = {"PENDING": 1, "OPEN": 2, "RESOLVED": 3, "CLOSED": 4, "REOPENED": 5}

async def push_ticket_status_to_glczone(glczone_ticket_id: str, crm_status: str):
    """Two-way sync: CRM se ticket status badalne par glczone.in par bhi reflect karo."""
    import httpx, os
    glczone_status = CRM_TICKET_STATUS_TO_GLCZONE.get(crm_status)
    if glczone_status is None:
        return
    secret = os.getenv("CRM_BRIDGE_SECRET", "")
    if not secret:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                "https://glczone.in/api/crm-bridge/tickets/resolve",
                headers={"X-Crm-Bridge-Secret": secret},
                data={"ticket_id": glczone_ticket_id, "status": str(glczone_status)},
            )
    except Exception as e:
        log.warning(f"Failed to push ticket status to glczone: {e}")


@api.put("/tickets/{tid}")
async def update_ticket(tid: str, body: Dict[str, Any], user=Depends(current_user)):
    body["updatedAt"] = now_iso()
    await db.tickets.update_one({"id": tid}, {"$set": body})
    d = await db.tickets.find_one({"id": tid}, {"_id": 0})

    # Agar yeh ticket glczone.in se synced hai aur status badla hai, to wahan bhi push karo
    if d and d.get("glczone_ticket_id") and "status" in body:
        await push_ticket_status_to_glczone(d["glczone_ticket_id"], body["status"])

    return d


# ===================== REAL-TIME ORDER WEBHOOK (glczone.in -> CRM, instant push) =====================

@api.post("/webhooks/order-event")
async def order_event_webhook(request: Request):
    """glczone.in calls this the instant an order is created or its status changes.
    Protected by the same shared secret as the CRM bridge. Upserts sales_orders
    and deals so the CRM reflects it immediately, without waiting for the 15-min cron."""
    import os
    secret = request.headers.get("X-Crm-Bridge-Secret", "")
    expected = os.getenv("CRM_BRIDGE_SECRET", "")
    if not expected or secret != expected:
        raise HTTPException(401, "Unauthorized")

    body = await request.json()
    order_id = str(body.get("order_id", ""))
    status = body.get("status", "")
    customer_name = body.get("customer_name", "")
    customer_phone = body.get("customer_phone", "")
    customer_email = body.get("customer_email", "")
    total = float(body.get("total", 0) or 0)
    vertical = body.get("vertical", "GLC Zone")

    if not order_id:
        raise HTTPException(400, "order_id required")

    data = {
        "glczone_order_id": order_id,
        "orderNo": f"GLZ-{order_id}",
        "customerName": customer_name,
        "customerPhone": customer_phone,
        "customerEmail": customer_email,
        "status": status,
        "total": total,
        "vertical": vertical,
        "source": "glczone.in",
        "realtimeSync": True,
        "updatedAt": now_iso(),
    }

    rider = body.get("rider") or {}
    zone = body.get("zone") or {}
    addr = body.get("address") or {}
    addr_text = ", ".join(str(x) for x in [addr.get("line"), addr.get("landmark"), addr.get("city"), addr.get("pincode")] if x)
    for k_src, k_dst in (("final_total", "finalTotal"), ("payment_method", "paymentMethod"), ("payment_status", "paymentStatus")):
        if body.get(k_src) is not None:
            data[k_dst] = body.get(k_src)
    if body.get("items") is not None:
        data["glczoneItems"] = body.get("items")
    if addr_text:
        data["deliveryAddress"] = addr_text
    if body.get("delivery_charge") is not None:
        data["deliveryCharge"] = float(body.get("delivery_charge") or 0)
    if body.get("discount") is not None:
        data["discount"] = float(body.get("discount") or 0)
    if body.get("ward"):
        data["ward"] = body.get("ward")
    if zone.get("name"):
        data["zone"] = zone.get("name")
    if rider.get("name"):
        data["deliveryBoy"] = rider.get("name")

    existing = await db.sales_orders.find_one({"glczone_order_id": order_id})
    if existing:
        await db.sales_orders.update_one({"glczone_order_id": order_id}, {"$set": data})
    else:
        data["id"] = uid()
        data["createdAt"] = now_iso()
        await db.sales_orders.insert_one(data)

    deal_existing = await db.deals.find_one({"glczone_order_id": order_id})
    deal_data = {
        "glczone_order_id": order_id,
        "title": f"Order #{order_id} — {customer_name}",
        "customerName": customer_name,
        "customerPhone": customer_phone,
        "value": total,
        "stage": "WON" if status == "delivered" else ("LOST" if status in ("cancelled", "returned") else "NEW"),
        "glczone_status": status,
        "vertical": vertical,
        "source": "glczone.in",
        "updatedAt": now_iso(),
    }
    if deal_existing:
        await db.deals.update_one({"glczone_order_id": order_id}, {"$set": deal_data})
    else:
        deal_data["id"] = uid()
        deal_data["probability"] = 50
        deal_data["createdAt"] = now_iso()
        await db.deals.insert_one(deal_data)

    ds = str(body.get("delivery_status") or "").lower()
    if ds == "delivered" or status == "delivered":
        d_status = "DELIVERED"
    elif status in ("cancelled", "returned") or ds == "cancelled":
        d_status = "CANCELLED"
    elif ds == "out_for_delivery":
        d_status = "IN_TRANSIT"
    elif rider.get("name"):
        d_status = "ASSIGNED"
    else:
        d_status = "PENDING"
    d_doc = {
        "glczone_order_id": order_id,
        "orderNo": f"GLZ-{order_id}",
        "customerName": customer_name,
        "customerPhone": customer_phone,
        "deliveryAddress": addr_text,
        "deliveryBoy": rider.get("name") or "Unassigned",
        "riderId": rider.get("id"),
        "zone": zone.get("name"),
        "ward": body.get("ward"),
        "items": body.get("items") or [],
        "status": d_status,
        "source": "glczone.in",
        "updatedAt": now_iso(),
    }
    d_doc = {k: v for k, v in d_doc.items() if v not in (None, "", [])}
    if await db.deliveries.find_one({"glczone_order_id": order_id}, {"_id": 0}):
        await db.deliveries.update_one({"glczone_order_id": order_id}, {"$set": d_doc})
    else:
        d_doc["id"] = uid()
        d_doc["createdAt"] = now_iso()
        await db.deliveries.insert_one(d_doc)

    log.info(f"Real-time order webhook processed: order_id={order_id}, status={status}")
    return {"ok": True, "message": "Order event processed in real-time"}


# ===================== WITHDRAWALS (Two-way sync with glczone.in) =====================

async def call_glczone_bridge(path: str, data: dict):
    import httpx, os
    secret = os.getenv("CRM_BRIDGE_SECRET", "")
    if not secret:
        return {"error": True, "message": "CRM_BRIDGE_SECRET not configured"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://glczone.in/api/crm-bridge/{path}",
                headers={"X-Crm-Bridge-Secret": secret},
                data=data,
            )
            return resp.json()
    except Exception as e:
        log.warning(f"CRM bridge call failed ({path}): {e}")
        return {"error": True, "message": str(e)}


@api.get("/withdrawals")
async def list_withdrawals(page: int = 1, limit: int = 50, status_: Optional[str] = Query(None, alias="status"), user=Depends(current_user)):
    q = {}
    if status_:
        q["status"] = status_
    skip = (page - 1) * limit
    items = await db.withdrawals.find(q, {"_id": 0}).sort("createdAt", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.withdrawals.count_documents(q)
    return {"items": items, "total": total, "page": page, "limit": limit}


@api.post("/withdrawals/{wid}/approve")
async def approve_withdrawal(wid: str, user=Depends(current_user)):
    w = await db.withdrawals.find_one({"id": wid}, {"_id": 0})
    if not w:
        raise HTTPException(404, "Withdrawal not found")

    result = await call_glczone_bridge(f"withdrawals/{w['glczone_withdrawal_id']}/approve", {})
    if result.get("error"):
        raise HTTPException(400, result.get("message", "glczone.in rejected the request"))

    await db.withdrawals.update_one({"id": wid}, {"$set": {"status": "approved", "updatedAt": now_iso()}})
    return {"ok": True, "message": "Withdrawal approved on glczone.in and CRM"}


@api.post("/withdrawals/{wid}/reject")
async def reject_withdrawal(wid: str, body: Dict[str, Any], user=Depends(current_user)):
    w = await db.withdrawals.find_one({"id": wid}, {"_id": 0})
    if not w:
        raise HTTPException(404, "Withdrawal not found")

    reason = body.get("reason", "")
    result = await call_glczone_bridge(f"withdrawals/{w['glczone_withdrawal_id']}/reject", {"reason": reason})
    if result.get("error"):
        raise HTTPException(400, result.get("message", "glczone.in rejected the request"))

    await db.withdrawals.update_one({"id": wid}, {"$set": {"status": "rejected", "updatedAt": now_iso()}})
    return {"ok": True, "message": "Withdrawal rejected and refunded on glczone.in"}


@api.post("/withdrawals/{wid}/mark-paid")
async def mark_withdrawal_paid(wid: str, body: Dict[str, Any], user=Depends(current_user)):
    w = await db.withdrawals.find_one({"id": wid}, {"_id": 0})
    if not w:
        raise HTTPException(404, "Withdrawal not found")

    payment_reference = body.get("payment_reference", "")
    result = await call_glczone_bridge(f"withdrawals/{w['glczone_withdrawal_id']}/mark-paid", {"payment_reference": payment_reference})
    if result.get("error"):
        raise HTTPException(400, result.get("message", "glczone.in rejected the request"))

    await db.withdrawals.update_one({"id": wid}, {"$set": {"status": "paid", "updatedAt": now_iso()}})
    return {"ok": True, "message": "Withdrawal marked as paid"}


# ===================== RETURN REQUESTS (Two-way sync with glczone.in) =====================

@api.get("/returns")
async def list_returns(page: int = 1, limit: int = 50, status_: Optional[str] = Query(None, alias="status"), user=Depends(current_user)):
    q = {}
    if status_:
        q["status"] = status_
    skip = (page - 1) * limit
    items = await db.returns.find(q, {"_id": 0}).sort("createdAt", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.returns.count_documents(q)
    return {"items": items, "total": total, "page": page, "limit": limit}


@api.post("/returns/{rid}/approve")
async def approve_return(rid: str, user=Depends(current_user)):
    r = await db.returns.find_one({"id": rid}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Return request not found")

    result = await call_glczone_bridge("returns/update", {
        "return_request_id": r["glczone_return_id"],
        "status": "1",
        "order_item_id": r.get("productId", "0"),
        "update_remarks": "Approved via CRM",
    })
    if result.get("error"):
        raise HTTPException(400, result.get("message", "glczone.in rejected the request"))

    await db.returns.update_one({"id": rid}, {"$set": {"status": "APPROVED", "updatedAt": now_iso()}})
    return {"ok": True, "message": "Return approved on glczone.in and CRM"}


@api.post("/returns/{rid}/reject")
async def reject_return(rid: str, body: Dict[str, Any], user=Depends(current_user)):
    r = await db.returns.find_one({"id": rid}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Return request not found")

    reason = body.get("reason", "")
    result = await call_glczone_bridge("returns/update", {
        "return_request_id": r["glczone_return_id"],
        "status": "2",
        "order_item_id": r.get("productId", "0"),
        "update_remarks": reason,
    })
    if result.get("error"):
        raise HTTPException(400, result.get("message", "glczone.in rejected the request"))

    await db.returns.update_one({"id": rid}, {"$set": {"status": "REJECTED", "updatedAt": now_iso()}})
    return {"ok": True, "message": "Return rejected on glczone.in and CRM"}


@api.post("/tickets/{tid}/reply")
async def reply_ticket(tid: str, body: Dict[str, Any], user=Depends(current_user)):
    entry = {"id": uid(), "message": body.get("message"), "by": user.get("name"), "internal": body.get("internal", False), "at": now_iso()}
    await db.tickets.update_one({"id": tid}, {"$push": {"replies": entry}, "$set": {"updatedAt": now_iso()}})
    return entry


# =========================================================
# DOCUMENTS
# =========================================================
class DocumentIn(BaseModel):
    name: str
    url: str
    category: str = "GENERAL"
    linkedType: Optional[str] = None
    linkedId: Optional[str] = None
    size: Optional[int] = None
    mime: Optional[str] = None


@api.get("/documents")
async def list_documents(category: Optional[str] = None, user=Depends(current_user)):
    filt = {}
    if category:
        filt["category"] = category
    items = await db.documents.find(filt, {"_id": 0}).sort("createdAt", -1).to_list(500)
    return {"items": items}


@api.post("/documents")
async def create_document(data: DocumentIn, user=Depends(current_user)):
    doc = {**data.model_dump(), "id": uid(), "uploadedBy": user["name"], "createdAt": now_iso()}
    await db.documents.insert_one(doc)
    return clean(doc)


@api.delete("/documents/{did}")
async def delete_document(did: str, user=Depends(current_user)):
    await db.documents.delete_one({"id": did})
    return {"ok": True}


# =========================================================
# NOTIFICATIONS / AUDIT
# =========================================================
@api.get("/notifications")
async def list_notifications(user=Depends(current_user)):
    # Real-time alerts from live data
    alerts = []

    # 1. Pending leaves
    pending_leaves = await db.leaves.count_documents({"status": "PENDING"})
    if pending_leaves > 0:
        alerts.append({"id": "leave-pending", "title": "Leave Requests Pending", "message": f"{pending_leaves} employee leave request(s) awaiting approval", "type": "leave", "isRead": False, "createdAt": now_iso(), "url": "/hr/leaves"})

    # 2. Low stock
    low_stock = await db.stock_items.count_documents({"qty": {"$lt": 10, "$gt": 0}})
    if low_stock > 0:
        alerts.append({"id": "low-stock", "title": "Low Stock Alert", "message": f"{low_stock} product(s) running low on stock", "type": "stock", "isRead": False, "createdAt": now_iso(), "url": "/inventory/stock"})

    # 3. Pending withdrawals
    pending_w = await db.withdrawals.count_documents({"status": "PENDING"})
    if pending_w > 0:
        alerts.append({"id": "withdrawal-pending", "title": "Withdrawal Requests", "message": f"{pending_w} seller withdrawal(s) pending approval", "type": "withdrawal", "isRead": False, "createdAt": now_iso(), "url": "/sellers"})

    # 4. Pending returns
    pending_r = await db.returns.count_documents({"status": "PENDING"})
    if pending_r > 0:
        alerts.append({"id": "return-pending", "title": "Return Requests", "message": f"{pending_r} customer return(s) awaiting action", "type": "return", "isRead": False, "createdAt": now_iso(), "url": "/sellers"})

    # 5. Unpaid invoices
    unpaid = await db.invoices.count_documents({"status": {"$in": ["UNPAID", "OVERDUE"]}})
    if unpaid > 0:
        alerts.append({"id": "unpaid-invoices", "title": "Unpaid Invoices", "message": f"{unpaid} invoice(s) are unpaid or overdue", "type": "invoice", "isRead": False, "createdAt": now_iso(), "url": "/sales/invoices"})

    # 6. New leads today
    today = now_iso()[:10]
    new_leads = await db.leads.count_documents({"createdAt": {"$regex": f"^{today}"}})
    if new_leads > 0:
        alerts.append({"id": "new-leads", "title": "New Leads Today", "message": f"{new_leads} new lead(s) added today", "type": "lead", "isRead": False, "createdAt": now_iso(), "url": "/crm/leads"})

    # 7. Pending deliveries
    pending_d = await db.deliveries.count_documents({"status": "PENDING"})
    if pending_d > 0:
        alerts.append({"id": "pending-deliveries", "title": "Pending Deliveries", "message": f"{pending_d} delivery(ies) not yet assigned", "type": "delivery", "isRead": False, "createdAt": now_iso(), "url": "/delivery"})

    # 8. Scheduled social posts due today
    due_posts = await db.social_posts.count_documents({"status": "SCHEDULED", "scheduledAt": {"$lte": now_iso()}})
    if due_posts > 0:
        alerts.append({"id": "due-posts", "title": "Social Posts Due", "message": f"{due_posts} scheduled post(s) ready to publish", "type": "social", "isRead": False, "createdAt": now_iso(), "url": "/ocm/social"})

    # Also fetch stored notifications
    stored = await db.notifications.find({"userId": {"$in": [user["id"], "*"]}}, {"_id": 0}).sort("createdAt", -1).limit(20).to_list(20)

    # Merge — stored ones first, then live alerts
    read_ids = {n["id"] for n in stored if n.get("isRead")}
    for a in alerts:
        if a["id"] in read_ids:
            a["isRead"] = True

    all_items = alerts + [s for s in stored if s.get("id") not in {a["id"] for a in alerts}]
    unread = sum(1 for n in all_items if not n.get("isRead"))
    return {"items": all_items[:30], "unread": unread}


@api.put("/notifications/read-all")
async def mark_all_read(user=Depends(current_user)):
    await db.notifications.update_many({"userId": {"$in": [user["id"], "*"]}}, {"$set": {"isRead": True}})
    # Store read state for live alerts
    live_ids = ["leave-pending","low-stock","withdrawal-pending","return-pending","unpaid-invoices","new-leads","pending-deliveries","due-posts"]
    for lid in live_ids:
        existing = await db.notifications.find_one({"id": lid})
        if existing:
            await db.notifications.update_one({"id": lid}, {"$set": {"isRead": True}})
        else:
            await db.notifications.insert_one({"id": lid, "userId": user["id"], "isRead": True, "createdAt": now_iso()})
    return {"ok": True}


@api.get("/audit")
async def audit(page: int = 1, limit: int = 100, user=Depends(current_user)):
    return await paginate(db.audit_logs, {}, page, limit, sort_field="createdAt", sort_dir=-1)


# =========================================================
# SETTINGS / USERS
# =========================================================
@api.get("/users")
async def list_users(user=Depends(current_user)):
    items = await db.users.find({}, {"_id": 0, "password": 0}).to_list(500)
    return {"items": items}


@api.get("/settings/company")
async def get_company(user=Depends(current_user)):
    c = await db.settings.find_one({"key": "company"}, {"_id": 0})
    return c["value"] if c else {}


@api.put("/settings/company")
async def update_company(body: Dict[str, Any], user=Depends(current_user)):
    await db.settings.update_one({"key": "company"}, {"$set": {"value": body}}, upsert=True)
    return body


# =========================================================
# DASHBOARD (KPIs)
# =========================================================
@api.get("/dashboard")
async def dashboard(vertical: Optional[str] = None, user=Depends(current_user)):
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")

    order_filter = {}
    inv_filter = {}
    if vertical:
        order_filter["vertical"] = vertical
        inv_filter["vertical"] = vertical

    # today revenue
    today_rev = 0.0
    today_orders = 0
    async for o in db.sales_orders.find({**order_filter, "createdAt": {"$regex": f"^{today}"}}, {"_id": 0}):
        today_rev += o.get("total", 0)
        today_orders += 1

    new_customers = await db.customers.count_documents({"createdAt": {"$regex": f"^{today}"}})
    pending_orders = await db.sales_orders.count_documents({**order_filter, "status": {"$in": ["PENDING", "CONFIRMED", "PROCESSING"]}})

    unpaid_amt = 0.0
    async for i in db.invoices.find({**inv_filter, "status": {"$in": ["UNPAID", "PARTIAL"]}}, {"_id": 0}):
        unpaid_amt += i.get("dueAmount", 0)

    open_tickets = await db.tickets.count_documents({"status": {"$in": ["OPEN", "IN_PROGRESS"]}})
    total_leads = await db.leads.count_documents({})
    pending_deliveries = await db.deliveries.count_documents({"status": {"$in": ["PENDING", "ASSIGNED", "IN_TRANSIT", "RECEIVED", "PROCESSED", "PROCESSING", "SHIPPED"]}})
    employee_count = await db.employees.count_documents({})

    today_attn = await db.attendance.count_documents({"date": today, "status": "PRESENT"})

    # 6-month revenue
    rev_series = []
    for i in range(5, -1, -1):
        m = (now.replace(day=1) - timedelta(days=30 * i)).strftime("%Y-%m")
        total = 0.0
        async for o in db.sales_orders.find({**order_filter, "createdAt": {"$regex": f"^{m}"}}, {"_id": 0}):
            total += o.get("total", 0)
        rev_series.append({"month": m, "revenue": round(total, 2)})

    # sales by store/vertical
    sbv: Dict[str, float] = {}
    async for o in db.sales_orders.find({}, {"_id": 0}):
        k = o.get("vertical") or o.get("store") or "Other"
        sbv[k] = sbv.get(k, 0) + o.get("total", 0)
    sales_by_vertical = [{"name": k, "value": round(v, 2)} for k, v in sbv.items()]

    # lead funnel
    stages = ["NEW", "CONTACTED", "QUALIFIED", "PROPOSAL", "NEGOTIATION", "WON"]
    funnel = []
    for s in stages:
        c = await db.leads.count_documents({"status": s})
        funnel.append({"stage": s, "count": c})

    # inventory value by category
    invb: Dict[str, float] = {}
    prods = await db.products.find({}, {"_id": 0}).to_list(1000)
    stocks = await db.stock_items.find({}, {"_id": 0}).to_list(1000)
    smap: Dict[str, float] = {}
    for s in stocks:
        smap[s["productId"]] = smap.get(s["productId"], 0) + s.get("qty", 0)
    for p in prods:
        cat = p.get("category") or "Uncategorized"
        invb[cat] = invb.get(cat, 0) + smap.get(p["id"], 0) * p.get("buyingPrice", 0)
    inventory_by_cat = [{"name": k, "value": round(v, 2)} for k, v in invb.items()]

    # weekly attendance
    week_attn = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        present = await db.attendance.count_documents({"date": day, "status": "PRESENT"})
        week_attn.append({"day": day[-2:], "present": present})

    # recent activity
    recent_orders = await db.sales_orders.find({}, {"_id": 0}).sort("createdAt", -1).limit(5).to_list(5)
    low_stock_list = []
    for p in prods:
        if smap.get(p["id"], 0) <= p.get("minStock", 5):
            low_stock_list.append({"name": p["name"], "sku": p["sku"], "current": smap.get(p["id"], 0), "min": p.get("minStock", 5)})
        if len(low_stock_list) >= 5:
            break

    pending_leaves = await db.leaves.count_documents({"status": "PENDING"})
    pending_expenses = await db.expenses.count_documents({"status": "PENDING"})
    pending_pos = await db.purchase_orders.count_documents({"status": "DRAFT"})

    return {
        "kpi": {
            "todayRevenue": round(today_rev, 2),
            "todayOrders": today_orders,
            "newCustomers": new_customers,
            "pendingOrders": pending_orders,
            "unpaidAmount": round(unpaid_amt, 2),
            "openTickets": open_tickets,
            "totalLeads": total_leads,
            "pendingDeliveries": pending_deliveries,
            "employeeCount": employee_count,
            "todayAttendance": today_attn,
        },
        "charts": {
            "revenueSeries": rev_series,
            "salesByVertical": sales_by_vertical,
            "leadFunnel": funnel,
            "inventoryByCategory": inventory_by_cat,
            "weeklyAttendance": week_attn,
        },
        "recent": {
            "orders": recent_orders,
            "lowStock": low_stock_list,
        },
        "pending": {
            "leaves": pending_leaves,
            "expenses": pending_expenses,
            "purchaseOrders": pending_pos,
        },
    }


# =========================================================
# RBAC — role → allowed modules
# =========================================================
ROLE_PERMS = {
    "Super Admin": ["*"],
    "Admin": ["*"],
    "Manager": ["dashboard", "crm", "sales", "inventory", "purchase", "delivery", "projects", "tasks", "tickets", "documents", "settings", "ocm"],
    "Support Executive": ["dashboard", "crm.customers", "tickets", "documents", "ocm.inbox", "ocm.contacts"],
    "Sales": ["dashboard", "crm", "sales", "inventory.products", "delivery", "documents", "ocm"],
    "Accounts": ["dashboard", "sales.invoices", "finance", "purchase", "documents", "hr.payroll"],
    "HR": ["dashboard", "hr", "documents"],
    "Catalog Manager": ["dashboard", "inventory.products", "documents"],
    "Logistics Manager": ["dashboard", "delivery", "sales.orders", "documents"],
    "Warehouse Manager": ["dashboard", "inventory.stock", "purchase", "documents"],
    "Seller Relations Manager": ["dashboard", "purchase.suppliers", "documents"],
    "Telecaller": ["dashboard", "crm.leads", "crm.customers", "tasks", "documents"],
    "Finance Staff": ["dashboard", "finance", "sales.invoices", "documents"],
    "Marketing Manager": ["dashboard", "ocm", "documents"],
    "System Admin": ["dashboard", "settings", "audit", "documents"],
}


@api.get("/rbac/me")
async def rbac_me(user=Depends(current_user)):
    role = user.get("role", "Admin")
    stored = await db.settings.find_one({"key": "role_perms"})
    perms_map = stored["value"] if stored else ROLE_PERMS
    perms = perms_map.get(role, ROLE_PERMS.get(role, ["dashboard"]))
    return {"role": role, "modules": perms}


class RbacSyncIn(BaseModel):
    permissions_json: str
    sig: str


@api.post("/rbac/sync")
async def rbac_sync(data: RbacSyncIn):
    if not CRM_SSO_SECRET:
        raise HTTPException(500, "Sync not configured")
    expected_sig = hmac.new(CRM_SSO_SECRET.encode(), data.permissions_json.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, data.sig):
        raise HTTPException(401, "Invalid sync signature")
    import json as _json
    try:
        permissions = _json.loads(data.permissions_json)
    except Exception:
        raise HTTPException(400, "Invalid JSON payload")
    await db.settings.update_one(
        {"key": "role_perms"},
        {"$set": {"value": permissions}},
        upsert=True,
    )
    return {"ok": True}


# =========================================================
# Documents Vault — real file upload / download via object storage
# =========================================================
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50MB


@api.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), category: str = "GENERAL", user=Depends(current_user)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File exceeds 50MB")
    ext = (file.filename or "file").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "bin"
    doc_id = uid()
    path = f"{STORAGE_APP_NAME}/documents/{user['id']}/{doc_id}.{ext}"
    result = put_object(path, data, file.content_type or "application/octet-stream")
    rec = {
        "id": doc_id,
        "name": file.filename,
        "storage_path": result["path"],
        "size": result.get("size", len(data)),
        "mime": file.content_type or "application/octet-stream",
        "category": category,
        "uploadedBy": user["name"],
        "uploadedById": user["id"],
        "isDeleted": False,
        "createdAt": now_iso(),
    }
    await db.documents.insert_one(rec)
    await log_activity(user["id"], "documents", "upload", doc_id, {"name": file.filename, "size": rec["size"]})
    return clean(rec)


@api.get("/documents/{doc_id}/download")
async def download_document(doc_id: str, auth: Optional[str] = None, cred: HTTPAuthorizationCredentials = Depends(bearer)):
    # Support token via query param for <a href> and <img src>
    token = None
    if cred:
        token = cred.credentials
    elif auth:
        token = auth
    if not token:
        raise HTTPException(401, "Missing token")
    try:
        pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception:
        raise HTTPException(401, "Invalid token")
    rec = await db.documents.find_one({"id": doc_id, "isDeleted": {"$ne": True}}, {"_id": 0})
    if not rec or not rec.get("storage_path"):
        raise HTTPException(404, "Not found")
    data, ctype = get_object(rec["storage_path"])
    return Response(
        content=data,
        media_type=rec.get("mime") or ctype or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{rec.get("name", "file")}"'},
    )


@api.delete("/documents/{doc_id}")
async def delete_document_v2(doc_id: str, user=Depends(current_user)):
    await db.documents.update_one({"id": doc_id}, {"$set": {"isDeleted": True, "deletedAt": now_iso()}})
    await log_activity(user["id"], "documents", "delete", doc_id)
    return {"ok": True}


# =========================================================
# OCM — Omnichannel Communication Module (Phase 1 MVP)
# =========================================================
OCM_CHANNELS = ["TELEGRAM", "WHATSAPP", "INSTAGRAM", "FACEBOOK", "WEBCHAT"]


class OcmContactIn(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    channels: List[str] = []
    telegramId: Optional[str] = None
    whatsappId: Optional[str] = None
    instagramId: Optional[str] = None
    tags: List[str] = []
    subscribed: bool = True
    vertical: Optional[str] = None


@api.get("/ocm/contacts")
async def ocm_list_contacts(page: int = 1, limit: int = 100, q: Optional[str] = None, user=Depends(current_user)):
    return await paginate(db.ocm_contacts, {}, page, limit, search_fields=["name", "phone", "email"], q=q)


@api.post("/ocm/contacts")
async def ocm_create_contact(data: OcmContactIn, user=Depends(current_user)):
    doc = {**data.model_dump(), "id": uid(), "createdAt": now_iso(), "updatedAt": now_iso()}
    await db.ocm_contacts.insert_one(doc)
    return clean(doc)


class OcmMessageIn(BaseModel):
    conversationId: Optional[str] = None
    contactId: Optional[str] = None
    channel: str = "WEBCHAT"
    text: str
    direction: str = "OUT"


@api.get("/ocm/conversations")
async def ocm_list_convs(channel: Optional[str] = None, status_: Optional[str] = Query(None, alias="status"), user=Depends(current_user)):
    filt = {}
    if channel:
        filt["channel"] = channel
    if status_:
        filt["status"] = status_
    items = await db.ocm_conversations.find(filt, {"_id": 0}).sort("lastMessageAt", -1).limit(200).to_list(200)
    return {"items": items}


@api.get("/ocm/conversations/{cid}")
async def ocm_get_conv(cid: str, user=Depends(current_user)):
    conv = await db.ocm_conversations.find_one({"id": cid}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Not found")
    msgs = await db.ocm_messages.find({"conversationId": cid}, {"_id": 0}).sort("createdAt", 1).to_list(500)
    contact = None
    if conv.get("contactId"):
        contact = await db.ocm_contacts.find_one({"id": conv["contactId"]}, {"_id": 0})
    return {"conversation": conv, "messages": msgs, "contact": contact}


@api.post("/ocm/conversations/{cid}/messages")
async def ocm_send_message(cid: str, body: OcmMessageIn, user=Depends(current_user)):
    conv = await db.ocm_conversations.find_one({"id": cid}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Not found")

    send_status = "SENT"
    channel = conv.get("channel", "WEBCHAT")
    if channel in ("WHATSAPP", "INSTAGRAM", "FACEBOOK") and (body.direction or "OUT") == "OUT":
        contact = await db.ocm_contacts.find_one({"id": conv.get("contactId")}, {"_id": 0}) or {}
        result = send_platform_message(channel, contact, body.text)
        if not result.get("success"):
            send_status = "FAILED"

    msg = {
        "id": uid(),
        "conversationId": cid,
        "channel": conv.get("channel", "WEBCHAT"),
        "direction": body.direction or "OUT",
        "text": body.text,
        "sentBy": user["name"],
        "sentById": user["id"],
        "status": send_status,
        "createdAt": now_iso(),
    }
    await db.ocm_messages.insert_one(msg)
    # Agent ne reply kiya — agentMode on karo (AI band)
    await db.ocm_conversations.update_one({"id": cid}, {"$set": {"lastMessage": body.text, "lastMessageAt": now_iso(), "agentMode": True, "agentId": user["id"], "agentName": user["name"]}})
    return clean(msg)


@api.put("/ocm/conversations/{cid}")
async def ocm_update_conv(cid: str, body: Dict[str, Any], user=Depends(current_user)):
    body["updatedAt"] = now_iso()
    await db.ocm_conversations.update_one({"id": cid}, {"$set": body})
    d = await db.ocm_conversations.find_one({"id": cid}, {"_id": 0})
    return d


class BroadcastIn(BaseModel):
    name: str
    channels: List[str] = ["TELEGRAM"]
    audience: str = "ALL"
    message: str
    scheduledAt: Optional[str] = None
    status: str = "DRAFT"


@api.get("/ocm/broadcasts")
async def ocm_list_broadcasts(user=Depends(current_user)):
    items = await db.ocm_broadcasts.find({}, {"_id": 0}).sort("createdAt", -1).to_list(200)
    return {"items": items}


@api.post("/ocm/broadcasts")
async def ocm_create_broadcast(data: BroadcastIn, user=Depends(current_user)):
    doc = {**data.model_dump(), "id": uid(), "createdAt": now_iso(), "createdBy": user["name"], "sentCount": 0, "deliveredCount": 0, "readCount": 0}
    await db.ocm_broadcasts.insert_one(doc)
    return clean(doc)


@api.post("/ocm/broadcasts/{bid}/send")
async def ocm_send_broadcast(bid: str, user=Depends(current_user)):
    """Sends the broadcast message on each selected channel to all subscribed contacts that have that channel's contact id."""
    # claim the broadcast atomically so a double click / retry can't send it twice
    b = await db.ocm_broadcasts.find_one_and_update(
        {"id": bid, "status": {"$nin": ["SENT", "SENDING"]}},
        {"$set": {"status": "SENDING"}},
        projection={"_id": 0},
    )
    if not b:
        if await db.ocm_broadcasts.find_one({"id": bid}, {"_id": 1}):
            raise HTTPException(409, "This broadcast is already sent or being sent")
        raise HTTPException(404, "Not found")

    channels = b.get("channels") or ["TELEGRAM"]
    message = b.get("message") or ""
    audience = b.get("audience") or "ALL"

    sent_count = 0
    failed_count = 0
    seen_recipients = set()
    failure_reasons = {}

    def send_error(result: dict) -> str:
        """Real reason a send failed: our own error, else the provider's error message/code."""
        if result.get("error"):
            return str(result["error"])[:200]
        resp = result.get("response")
        err = resp.get("error") if isinstance(resp, dict) else None
        if isinstance(err, dict):
            return f"({err.get('code')}) {err.get('message')}"[:200]
        return (str(resp)[:200] if resp else "unknown error")

    def note_failure(result: dict) -> str:
        reason = send_error(result)
        failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
        return reason

    for channel in channels:
        field = CHANNEL_CONTACT_FIELD.get(channel)
        if not field:
            continue
        query = {"subscribed": True, field: {"$exists": True, "$ne": None, "$ne": ""}}
        if audience != "ALL":
            query["tags"] = audience.lower()
        contacts = await db.ocm_contacts.find(query, {"_id": 0}).to_list(5000)

        for contact in contacts:
            recipient = contact.get(field)
            if not recipient:
                continue
            dedupe_key = (channel, recipient)
            if dedupe_key in seen_recipients:
                continue
            seen_recipients.add(dedupe_key)
            try:
                if channel == "WHATSAPP":
                    result = send_whatsapp_text(recipient, message)
                elif channel == "TELEGRAM":
                    result = send_telegram_text(recipient, message)
                elif channel in ("INSTAGRAM", "FACEBOOK"):
                    result = send_messenger_style_text(recipient, message)
                else:
                    result = {"success": False, "error": f"Unsupported channel {channel}"}
            except Exception as e:
                result = {"success": False, "error": str(e)}

            if result.get("success"):
                sent_count += 1
            else:
                failed_count += 1
                log.warning(f"Broadcast {bid}: failed to send to {recipient} via {channel}: {note_failure(result)}")

        # Also reach GlcZone e-commerce customers directly by phone (WhatsApp only for now)
        if channel == "WHATSAPP":
            cust_query = {"phone": {"$exists": True, "$ne": None, "$ne": ""}}
            if audience != "ALL":
                cust_query["type"] = audience
            glczone_customers = await db.customers.find(cust_query, {"_id": 0, "phone": 1}).to_list(20000)
            for cust in glczone_customers:
                raw_phone = (cust.get("phone") or "").strip()
                digits = "".join(ch for ch in raw_phone if ch.isdigit())
                if len(digits) == 10:
                    recipient = "91" + digits
                elif len(digits) == 12 and digits.startswith("91"):
                    recipient = digits
                else:
                    continue
                if recipient == "910000000000" or digits == "0000000000":
                    continue
                dedupe_key = (channel, recipient)
                if dedupe_key in seen_recipients:
                    continue
                seen_recipients.add(dedupe_key)
                try:
                    result = send_whatsapp_text(recipient, message)
                except Exception as e:
                    result = {"success": False, "error": str(e)}

                if result.get("success"):
                    sent_count += 1
                else:
                    failed_count += 1
                    log.warning(f"Broadcast {bid}: failed to send to GlcZone customer {recipient}: {note_failure(result)}")

    await db.ocm_broadcasts.update_one(
        {"id": bid},
        {"$set": {
            "status": "SENT",
            "sentAt": now_iso(),
            "sentCount": sent_count,
            "failedCount": failed_count,
            "deliveredCount": sent_count,
            "readCount": 0,
            "failureReasons": [{"reason": k, "count": v} for k, v in sorted(failure_reasons.items(), key=lambda kv: -kv[1])[:5]],
        }}
    )
    await log_activity(user["id"], "ocm.broadcasts", "send", bid, {"channels": channels, "sent": sent_count, "failed": failed_count})
    return {"ok": True, "sent": sent_count, "failed": failed_count}


WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_API_VERSION = "v20.0"


def send_whatsapp_text(to_phone: str, text: str) -> dict:
    """Send a free-form WhatsApp text message (only valid within the 24h customer service window)."""
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        log.warning("WhatsApp send skipped: credentials not configured")
        return {"success": False, "error": "WhatsApp credentials not configured"}
    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text},
    }
    try:
        r = requests.post(url, json=payload, headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"}, timeout=15)
        return {"success": r.status_code == 200, "response": r.json()}
    except Exception as e:
        log.exception(f"WhatsApp send failed: {e}")
        return {"success": False, "error": str(e)}


def send_messenger_style_text(recipient_id: str, text: str) -> dict:
    """Send a DM via the Messenger Platform Send API — used for both Instagram DMs and Facebook Messenger."""
    if not FB_PAGE_ACCESS_TOKEN:
        log.warning("Messenger send skipped: FB_PAGE_ACCESS_TOKEN not configured")
        return {"success": False, "error": "Facebook Page not configured"}
    url = f"https://graph.facebook.com/{FB_API_VERSION}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE",
    }
    try:
        r = requests.post(url, json=payload, params={"access_token": FB_PAGE_ACCESS_TOKEN}, timeout=15)
        return {"success": r.status_code == 200, "response": r.json()}
    except Exception as e:
        log.exception(f"Messenger-style send failed: {e}")
        return {"success": False, "error": str(e)}


CHANNEL_CONTACT_FIELD = {
    "WHATSAPP": "whatsappId",
    "INSTAGRAM": "instagramId",
    "FACEBOOK": "facebookId",
    "TELEGRAM": "telegramId",
}


def send_telegram_text(chat_id: str, text: str) -> dict:
    """Send a message via Telegram Bot API."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        log.warning("Telegram send skipped: TELEGRAM_BOT_TOKEN not configured")
        return {"success": False, "error": "Telegram not configured"}
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=15
        )
        body = r.json()
        if r.status_code == 200 and body.get("ok"):
            return {"success": True, "messageId": body["result"]["message_id"]}
        return {"success": False, "error": body.get("description", "Telegram error")}
    except Exception as e:
        log.exception(f"Telegram send failed: {e}")
        return {"success": False, "error": str(e)}


def send_platform_message(channel: str, contact: dict, text: str) -> dict:
    """Dispatch an outgoing message to the right platform based on channel."""
    field = CHANNEL_CONTACT_FIELD.get(channel, "phone")
    recipient = contact.get(field) or contact.get("phone")
    if not recipient:
        return {"success": False, "error": f"No {field} on contact"}
    if channel == "WHATSAPP":
        return send_whatsapp_text(recipient, text)
    elif channel in ("INSTAGRAM", "FACEBOOK"):
        return send_messenger_style_text(recipient, text)
    elif channel == "TELEGRAM":
        return send_telegram_text(recipient, text)
    else:
        return {"success": False, "error": f"Sending on {channel} not supported yet"}



async def lookup_order_status(order_id_str: str, phone: str) -> str:
    """MySQL se order status fetch karo."""
    import aiomysql, os, json, re
    # order number extract karo (#2 ya sirf 2)
    match = re.search(r'\d+', order_id_str)
    if not match:
        return ""
    order_id = int(match.group())
    try:
        conn = await aiomysql.connect(
            host="127.0.0.1", port=3306,
            user="glczone", password=__import__("os").getenv("GLCZONE_DB_PASSWORD", ""),
            db="glczone_db", autocommit=True
        )
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT o.id, o.total, o.payment_method, o.created_at, oi.status "
                "FROM orders o LEFT JOIN order_items oi ON oi.order_id = o.id "
                "WHERE o.id = %s LIMIT 1",
                (order_id,)
            )
            row = await cur.fetchone()
        conn.close()
        if not row:
            return f"Order #{order_id} nahi mila is number par."
        oid, total, payment, created, status_json = row
        # status JSON parse karo
        try:
            status_list = json.loads(status_json or "[]")
            current_status = status_list[-1][0] if status_list else "received"
        except Exception:
            current_status = "received"
        status_map = {
            "received": "प्राप्त हो गया ✅",
            "processing": "तैयार हो रहा है 🔄",
            "shipped": "रास्ते में है 🚚",
            "delivered": "डिलीवर हो गया 🎉",
            "cancelled": "रद्द हो गया ❌",
        }
        status_hindi = status_map.get(current_status, current_status)
        return (f"Order #{oid} की जानकारी:\n"
                f"💰 कुल: ₹{total}\n"
                f"💳 Payment: {payment}\n"
                f"📦 Status: {status_hindi}\n"
                f"📅 Date: {str(created)[:10]}")
    except Exception as e:
        log.exception(f"Order lookup failed: {e}")
        return ""


async def fetch_glczone_context() -> str:
    """Fetch live data from glczone MySQL for AI context."""
    import aiomysql, json as _json
    try:
        conn = await aiomysql.connect(
            host="127.0.0.1", port=3306,
            user="glczone", password=__import__("os").getenv("GLCZONE_DB_PASSWORD", ""),
            db="glczone_db", autocommit=True
        )
        async with conn.cursor() as cur:
            # Live products with prices
            await cur.execute("""
                SELECT p.name, (SELECT GROUP_CONCAT(CONCAT(IFNULL(pv.base_qty,0), ':', IFNULL(pv.unit_type,'weight'), ':', CASE WHEN pv.special_price > 0 AND pv.special_price < pv.price THEN pv.special_price ELSE pv.price END) ORDER BY pv.price SEPARATOR '|') FROM product_variants pv WHERE pv.product_id = p.id AND pv.status = 1) AS packs /* GLC_PACKS */, p.stock, c.name as category
                FROM products p
                LEFT JOIN categories c ON c.id = p.category_id
                WHERE p.status = 1
                ORDER BY c.name, p.name
                LIMIT 50
            """)
            products = await cur.fetchall()

            # Store settings
            await cur.execute("SELECT value FROM settings WHERE variable = 'business_name' LIMIT 1")
            biz = await cur.fetchone()

            # Delivery areas - hardcoded since table has no city column
            areas = [("Kishanganj",), ("Bahadurganj",), ("Thakurganj",)]

        conn.close()

        # Build products section
        product_lines = []
        current_cat = None
        for name, price, stock, cat in products:
            try:
                name_parsed = _json.loads(name) if name and name.startswith("{") else {"en": str(name)}
                name_en = name_parsed.get("en") or name_parsed.get("hi") or str(name)
            except Exception:
                name_en = str(name)

            cat_parsed = cat or "General"
            try:
                cat_dict = _json.loads(cat_parsed) if cat_parsed.startswith("{") else {"en": cat_parsed}
                cat_en = cat_dict.get("en") or cat_parsed
            except Exception:
                cat_en = cat_parsed

            if cat_en != current_cat:
                current_cat = cat_en
                product_lines.append(f"\n  [{cat_en}]")

            stock_status = "In Stock" if (stock or 0) > 0 else "Out of Stock"
            # GLC_PACKS: har pack ka exact size + price
            packs_txt = []
            for part in str(price or "").split("|"):
                try:
                    q, ut, pr = part.split(":")
                    q = int(float(q)); pr = float(pr)
                    if q <= 0:
                        size = "1 pack"
                    elif ut == "volume":
                        size = f"{q/1000:g}L" if q >= 1000 else f"{q}ml"
                    elif ut == "count":
                        size = f"{q} pcs"
                    else:
                        size = f"{q/1000:g}kg" if q >= 1000 else f"{q}g"
                    packs_txt.append(f"{size} ₹{pr:g}")
                except Exception:
                    continue
            price_txt = " | ".join(packs_txt) if packs_txt else "price website pe dekhein"
            product_lines.append(f"  - {name_en}: {price_txt} ({stock_status})")

        products_text = "\n".join(product_lines) if product_lines else "  - Contact us for current prices"

        # Delivery areas
        area_names = [a[0] for a in areas if a[0]] if areas else ["Kishanganj"]
        areas_text = ", ".join(area_names) if area_names else "Kishanganj and nearby areas"

        return f"""
🏪 LIVE PRODUCT PRICES (updated daily):
{products_text}

🚚 DELIVERY AREAS: {areas_text}
"""
    except Exception as e:
        log.exception(f"fetch_glczone_context failed: {e}")
        return "\n🏪 Contact us for current prices and availability.\n"


async def run_ai_reply(contact: dict, conversation: dict, incoming_text: str, lang: str = "Hindi", channel: str = "WHATSAPP"):
    """Fallback: call Groq AI when no chatbot flow matched."""
    import os, httpx, re
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return

    # Order number detect karo — agar customer ne diya to direct lookup
    phone = contact.get("whatsappId") or contact.get("phone", "")
    # Order number detect — #4, order 4, order #4, 4th order etc
    order_match = re.search(r'#(\d+)', incoming_text)
    if not order_match:
        # Try natural language: "order 4", "4 number ka order", "#4 ka status"
        order_keywords = ['order', 'status', 'deliver', 'track', 'kahan', 'kab']
        if any(kw in incoming_text.lower() for kw in order_keywords):
            order_match = re.search(r'\b(\d+)\b', incoming_text)
    if order_match:
        matched_num = order_match.group(1) if order_match.lastindex and order_match.group(1) else order_match.group()
        order_info = await lookup_order_status(matched_num, phone)
        if order_info and "नही मिला" not in order_info:
            # Direct order info send karo, AI call ki zarurat nahi
            send_platform_message(channel, contact, order_info)
            out_msg = {
                "id": uid(), "conversationId": conversation["id"],
                "channel": channel, "direction": "OUT",
                "text": order_info, "sentBy": "AI Assistant",
                "sentById": "ai", "status": "SENT", "createdAt": now_iso(),
            }
            await db.ocm_messages.insert_one(out_msg)
            await db.ocm_conversations.update_one(
                {"id": conversation["id"]},
                {"$set": {"lastMessage": order_info, "lastMessageAt": now_iso()}}
            )
            return

    # Fetch live GLC Zone data
    glczone_context = await fetch_glczone_context()
    log.info(f"CONTEXT_DEBUG: {glczone_context[:200]}")

    # Last 6 messages fetch karo context ke liye
    recent_msgs = await db.ocm_messages.find(
        {"conversationId": conversation["id"]},
        {"_id": 0}
    ).sort("createdAt", -1).limit(6).to_list(6)
    recent_msgs.reverse()

    messages = [
        {
            "role": "system",
            "content": (
                f"You are Zara, a friendly and knowledgeable customer support agent for GLC Zone (glczone.in), an Indian e-commerce platform based in Kishanganj, Bihar. "
                f"Always reply in {lang} language only. Keep replies concise but helpful — 2-4 lines maximum. Be warm, professional and solution-focused. "
                "\n\n🏪 ABOUT GLC ZONE:"
                "\n- GLC Zone is Kishanganj, Bihar's #1 online shopping platform"
                "\n- Founded by Bishwajeet Dey, GLC Zone Private Limited (GSTIN: 10FZTPA0354J1ZJ)"
                "\n- Website: glczone.in | Instagram: @glczonecoin | Facebook: GLCZone Market"
                f"\n{glczone_context}"
                "\n\n🚚 DELIVERY:"
                "\n- Delivery time: Within 30-60 minutes for local orders"
                "\n- Delivery charge: ₹20 flat for orders up to 15kg"
                "\n- Orders above 15kg: ₹2 per kg charge"
                "\n- NO free delivery — delivery charge always applies"
                "\n\n💳 PAYMENT:"
                "\n- COD (Cash on Delivery) available"
                "\n- Online payment: UPI, Net Banking, Cards"
                "\n- GLC Wallet: Add money and pay from wallet"
                "\n\n🔄 RETURN POLICY:"
                "\n- Returns accepted within 24 hours for damaged or wrong items"
                "\n- Send photo proof to our team"
                "\n- Full refund or replacement guaranteed"
                "\n\n👥 SPV & COMMISSION SYSTEM:"
                "\n- SPV = Self Point Value — Selling Price minus Vendor Price ke barabar points milte hain"
                "\n- SPV cash nahi hai — yeh points hain jo commission calculate karne ke liye use hote hain"
                "\n- 49% SPV affiliate pool mein jaata hai — 7 levels tak 7% commission"
                "\n- 4 wallet types: Cash (withdraw), Repurchase (sirf shopping), Reward (max 30% use), Travel"
                "\n- CSB share: 10,000 SPV = 1 share; monthly dividend milta hai"
                "\n- Commission delivery ke baad credit hota hai"
                "\n- Details: glczone.in/wallet par dekhen"
                "\n\n📞 CUSTOMER CARE:"
                "\n- Available: 9 AM to 8 PM, Monday to Saturday"
                "\n- For urgent issues, our team will call back within 2 hours"
                "\n\n❓ COMMON Q&A:"
                "\n- Order not delivered? → Ask for Order ID, check status, escalate if needed"
                "\n- Wrong item received? → Ask for photo, arrange return/replacement"
                "\n- Payment failed? → Check UPI/bank, retry or use COD"
                "\n- How to order? → Visit glczone.in, add to cart, choose payment"
                "\n- Wallet not working? → Check balance, minimum ₹10 required"
                "\n\n⚠️ RULES FOR ZARA:"
                "\n- NEVER make up order status — always ask for Order ID (#1, #2 etc)"
                "\n- NEVER ask for phone number — you already have it"
                "\n- NEVER repeat the same question twice"
                "\n- NEVER ask for information you already have"
                "\n- Give DIRECT answers — no beating around the bush"
                "\n- If order ID given, look it up IMMEDIATELY without asking again"
                "\n- Maximum 2-3 lines per reply — be concise"
                "\n\n🚫 ZARA KYA NAHI KAR SAKTI (website par bhejo):"
                "\n- Order place nahi kar sakti — glczone.in par jaiye ya app download karein"
                "\n- Payment process nahi kar sakti — glczone.in par payment karein"
                "\n- Account create/login nahi kar sakti — glczone.in/login par jaiye"
                "\n- Order cancel/modify nahi kar sakti — glczone.in/account par jaiye"
                "\n- Refund process nahi kar sakti — support@glczone.in par mail karein"
                "\n- NEVER invent product varieties not in LIVE PRICES — only one Mango at ₹130, not Alphonso/Kesar/Desi"
                "\n- If unsure, say: 'Let me check with our team and get back to you shortly!'"
                "\n- Always end with a helpful follow-up offer"
                "\n- Be empathetic — customers may be frustrated"
                "\n- Use emojis occasionally to keep tone friendly"
                "\n- NEVER take or process a new order yourself in this chat, and never ask for product/quantity details to build an order — "
                "if the customer wants to buy something or place a new order, tell them to visit glczone.in, log in, and order there"
            )
        }
    ]
    for m in recent_msgs:
        role = "user" if m.get("direction") == "IN" else "assistant"
        messages.append({"role": role, "content": m.get("text", "")})

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={"model": "openai/gpt-oss-120b", "messages": [{"role": "system", "content": "GLC_PRICE_RULE: Product ka price hamesha EXACTLY wahi batao jo product list mein likha hai. Har price ke saath uska pack size zaroor batao (jaise Tomato 250g ₹10). Khud se calculate, per-kg convert ya andaza kabhi mat lagao. Agar price list mein nahi hai toh bolo: website ya app pe latest rate check karein."}] + messages, "max_tokens": 300, "temperature": 0.2}
            )
            data = resp.json()
            ai_text = data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.exception(f"Groq AI reply failed: {e}")
        return

    if not ai_text:
        return

    send_platform_message(channel, contact, ai_text)

    # DB mein save karo
    out_msg = {
        "id": uid(),
        "conversationId": conversation["id"],
        "channel": channel,
        "direction": "OUT",
        "text": ai_text,
        "sentBy": "AI Assistant",
        "sentById": "ai",
        "status": "SENT",
        "createdAt": now_iso(),
    }
    await db.ocm_messages.insert_one(out_msg)
    await db.ocm_conversations.update_one(
        {"id": conversation["id"]},
        {"$set": {"lastMessage": ai_text, "lastMessageAt": now_iso()}}
    )

async def run_matching_flows(contact: dict, conversation: dict, incoming_text: str, channel: str):
    """Check active flows for a keyword match and auto-send their steps."""
    flows = await db.ocm_flows.find({"channel": channel, "status": {"$in": ["ACTIVE", "PUBLISHED"]}}).to_list(100)
    text_lower = (incoming_text or "").lower().strip()

    for flow in flows:
        trigger = flow.get("trigger", "KEYWORD")
        trigger_value = (flow.get("triggerValue") or "").lower().strip()
        matched = False
        if trigger == "KEYWORD" and trigger_value:
            import re as _re
            clean_text = _re.sub(r"[^\w\s]", " ", text_lower)
            words_in_text = set(clean_text.split())
            keywords = [k.strip() for k in trigger_value.split(",") if k.strip()]
            for kw in keywords:
                kw_clean = _re.sub(r"[^\w\s]", " ", kw).strip()
                if " " in kw_clean:
                    if kw_clean in clean_text:
                        matched = True
                        break
                elif kw_clean in words_in_text:
                    matched = True
                    break
        elif trigger == "WELCOME":
            existing_count = await db.ocm_messages.count_documents({"conversationId": conversation["id"]})
            if existing_count <= 1:
                matched = True

        if not matched:
            continue

        for step in flow.get("steps", []):
            step_text = step.get("text") or step.get("message")
            if not step_text:
                continue
            send_platform_message(channel, contact, step_text)
            out_msg = {
                "id": uid(),
                "conversationId": conversation["id"],
                "channel": channel,
                "direction": "OUT",
                "text": step_text,
                "sentBy": f"Bot: {flow.get('name', 'Flow')}",
                "sentById": "system",
                "status": "SENT",
                "createdAt": now_iso(),
            }
            await db.ocm_messages.insert_one(out_msg)
            await db.ocm_conversations.update_one({"id": conversation["id"]}, {"$set": {"lastMessage": step_text, "lastMessageAt": now_iso()}})
        return True  # flow matched and ran
    return False  # no flow matched


@api.post("/ocm/message/incoming")
async def ocm_message_incoming(request: Request):
    body = await request.json()
    sig = body.pop("sig", "")

    if not CRM_SSO_SECRET:
        raise HTTPException(500, "Not configured")
    channel = body.get("channel") or "WHATSAPP"
    payload_json = json.dumps({"from": body.get("from"), "name": body.get("name"), "text": body.get("text"), "channel": channel}, separators=(",", ":"))
    expected_sig = hmac.new(CRM_SSO_SECRET.encode(), payload_json.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, sig):
        raise HTTPException(401, "Invalid signature")

    from_id = body.get("from")
    name = body.get("name") or f"{channel.title()} User"
    text = body.get("text") or ""
    id_field = CHANNEL_CONTACT_FIELD.get(channel, "phone")

    if not from_id:
        raise HTTPException(400, "Missing sender id")

    contact = await db.ocm_contacts.find_one({id_field: from_id})
    if not contact:
        contact = {
            "id": uid(),
            "name": name,
            "phone": from_id if channel == "WHATSAPP" else None,
            id_field: from_id,
            "channels": [channel],
            "tags": [],
            "subscribed": True,
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
        }
        await db.ocm_contacts.insert_one(dict(contact))
    else:
        # Update name if it was Unknown before
        update_fields = {"updatedAt": now_iso()}
        if name and name != "Unknown" and (not contact.get("name") or contact.get("name") in ["Unknown", "Telegram User", "Instagram User", "Facebook User", "WhatsApp User"]):
            update_fields["name"] = name
        if channel not in contact.get("channels", []):
            await db.ocm_contacts.update_one({"id": contact["id"]}, {"$addToSet": {"channels": channel}, "$set": update_fields})
        elif update_fields:
            await db.ocm_contacts.update_one({"id": contact["id"]}, {"$set": update_fields})

    conversation = await db.ocm_conversations.find_one({"contactId": contact["id"], "channel": channel})
    if not conversation:
        conversation = {
            "id": uid(),
            "contactId": contact["id"],
            "channel": channel,
            "status": "OPEN",
            "lastMessage": text,
            "lastMessageAt": now_iso(),
            "createdAt": now_iso(),
        }
        await db.ocm_conversations.insert_one(dict(conversation))

    in_msg = {
        "id": uid(),
        "conversationId": conversation["id"],
        "channel": channel,
        "direction": "IN",
        "text": text,
        "sentBy": name,
        "sentById": contact["id"],
        "status": "RECEIVED",
        "createdAt": now_iso(),
    }
    await db.ocm_messages.insert_one(in_msg)
    await db.ocm_conversations.update_one({"id": conversation["id"]}, {"$set": {"lastMessage": text, "lastMessageAt": now_iso(), "status": "OPEN"}})

    flow_matched = await run_matching_flows(contact, conversation, text, channel)
    if flow_matched:
        return {"ok": True}

    # Language preference check (only meaningful for AI-assisted channels)
    contact_fresh = await db.ocm_contacts.find_one({"id": contact["id"]}, {"_id": 0})
    preferred_lang = (contact_fresh or {}).get("preferredLang")

    lang_map = {"1": "Hindi", "2": "English", "3": "Hinglish", "4": "Bengali"}
    if not preferred_lang and text.strip() in lang_map:
        chosen_lang = lang_map[text.strip()]
        await db.ocm_contacts.update_one({"id": contact["id"]}, {"$set": {"preferredLang": chosen_lang}})
        confirm = {"Hindi": "धन्यवाद! अब मैं हिंदी में बात करूँगा। क्या मदद चाहिए? 😊", "English": "Thank you! I will now reply in English. How can I help? 😊", "Hinglish": "Thanks! Ab Hinglish mein baat karenge. Kya help chahiye? 😊", "Bengali": "ধন্যবাদ! এখন বাংলায় কথা বলব। কী সাহায্য দরকার? 😊"}
        msg = confirm[chosen_lang]
        send_platform_message(channel, contact, msg)
        out = {"id": uid(), "conversationId": conversation["id"], "channel": channel, "direction": "OUT", "text": msg, "sentBy": "AI Assistant", "sentById": "ai", "status": "SENT", "createdAt": now_iso()}
        await db.ocm_messages.insert_one(out)
        await db.ocm_conversations.update_one({"id": conversation["id"]}, {"$set": {"lastMessage": msg, "lastMessageAt": now_iso()}})
        return {"ok": True}

    if not preferred_lang:
        lang_asked = (contact_fresh or {}).get("langAsked", False)
        if not lang_asked:
            await db.ocm_contacts.update_one({"id": contact["id"]}, {"$set": {"langAsked": True}})
            lp = "\U0001f64f Welcome to GLC Zone!\n\nMain hoon Zara, aapki GLC Zone assistant! \U0001f31f\n\nPlease select your preferred language:\n1 Hindi\n2 English\n3 Hinglish\n4 Bengali\n\nReply with 1, 2, 3, or 4"
            send_platform_message(channel, contact, lp)
            out = {"id": uid(), "conversationId": conversation["id"], "channel": channel, "direction": "OUT", "text": lp, "sentBy": "AI Assistant", "sentById": "ai", "status": "SENT", "createdAt": now_iso()}
            await db.ocm_messages.insert_one(out)
            await db.ocm_conversations.update_one({"id": conversation["id"]}, {"$set": {"lastMessage": lp, "lastMessageAt": now_iso()}})
            return {"ok": True}

    conv_fresh = await db.ocm_conversations.find_one({"id": conversation["id"]}, {"_id": 0})
    if (conv_fresh or {}).get("agentMode"):
        log.info(f"AgentMode ON for conv {conversation['id']} — AI skipped")
    else:
        await run_ai_reply(contact, conversation, text, preferred_lang or "Hindi", channel)

    return {"ok": True}


from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
import io

@api.get("/invoices/{iid}/pdf")
async def download_invoice_pdf(iid: str, user=Depends(current_user)):
    from fastapi.responses import StreamingResponse
    d = await db.invoices.find_one({"id": iid}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Invoice not found")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    bold = ParagraphStyle("bold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10)
    normal = styles["Normal"]
    normal.fontSize = 9
    right = ParagraphStyle("right", parent=styles["Normal"], alignment=TA_RIGHT, fontSize=9)
    center = ParagraphStyle("center", parent=styles["Normal"], alignment=TA_CENTER, fontSize=9)

    elems = []

    # Header
    elems.append(Paragraph("GLC Zone Private Limited", ParagraphStyle("h1", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=16)))
    elems.append(Paragraph("Kishanganj, Bihar | GSTIN: 10FZTPA0354J1ZJ | glczone.in", ParagraphStyle("sub", parent=styles["Normal"], fontSize=8, textColor=colors.grey)))
    elems.append(Spacer(1, 6*mm))

    # Invoice info table
    inv_date = str(d.get("invoiceDate", ""))[:10]
    due_date = str(d.get("dueDate", ""))[:10]
    info_data = [
        [Paragraph(f"<b>TAX INVOICE</b>", bold), "", Paragraph(f"Invoice No: <b>{d.get('invoiceNo','')}</b>", bold)],
        ["", "", f"Date: {inv_date}"],
        ["", "", f"Due Date: {due_date}"],
    ]
    info_table = Table(info_data, colWidths=[80*mm, 40*mm, 65*mm])
    info_table.setStyle(TableStyle([
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("ALIGN", (2,0), (2,-1), "RIGHT"),
    ]))
    elems.append(info_table)
    elems.append(Spacer(1, 4*mm))

    # Bill to
    elems.append(Paragraph(f"<b>Bill To:</b> {d.get('customerName','')} | GST: {d.get('customerGst') or '-'} | State: {d.get('customerState') or '-'} | Place of supply: {d.get('placeOfSupply') or '-'}", bold))
    elems.append(Spacer(1, 4*mm))

    # Items table
    headers = ["#", "Item", "HSN", "Qty", "Rate (₹)", "GST%", "Amount (₹)"]
    rows = [headers]
    for i, item in enumerate(gf.ensure_lines(d), 1):
        rows.append([
            str(i),
            item.get("name", ""),
            item.get("hsn", ""),
            f"{item.get('qty', 0):g}",
            f"{item.get('rate', 0):,.2f}",
            f"{item.get('gstRate', 0):g}%",
            f"{item.get('total', 0):,.2f}",
        ])

    item_table = Table(rows, colWidths=[8*mm, 65*mm, 18*mm, 12*mm, 22*mm, 14*mm, 26*mm])
    item_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#064E3B")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F0FDF4")]),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#D1FAE5")),
        ("ALIGN", (3,0), (-1,-1), "RIGHT"),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    elems.append(item_table)
    elems.append(Spacer(1, 4*mm))

    # Totals
    status = d.get("status", "")
    status_color = colors.green if status == "PAID" else colors.orange if status == "PARTIAL" else colors.red
    totals = [
        ["", "Subtotal:", f"₹{d.get('subtotal',0):,.2f}"],
        ["", "CGST:", f"₹{d.get('cgst',0):,.2f}"],
        ["", "SGST:", f"₹{d.get('sgst',0):,.2f}"],
        ["", "IGST:", f"₹{d.get('igst',0):,.2f}"],
        ["", "Round off:", f"₹{d.get('roundOff',0):,.2f}"],
        ["", Paragraph("<b>Total:</b>", bold), Paragraph(f"<b>₹{d.get('total',0):,.2f}</b>", bold)],
        ["", "Paid:", f"₹{d.get('paidAmount',0):,.2f}"],
        ["", Paragraph("<b>Due:</b>", bold), Paragraph(f"<b>₹{d.get('dueAmount',0):,.2f}</b>", bold)],
    ]
    tot_table = Table(totals, colWidths=[100*mm, 40*mm, 45*mm])
    tot_table.setStyle(TableStyle([
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("ALIGN", (1,0), (-1,-1), "RIGHT"),
        ("LINEABOVE", (1,5), (-1,5), 0.5, colors.grey),
        ("LINEBELOW", (1,7), (-1,7), 0.5, colors.grey),
    ]))
    elems.append(tot_table)
    elems.append(Spacer(1, 6*mm))

    # Footer
    elems.append(Paragraph(f"Status: <b>{status}</b> | Vertical: {d.get('vertical','')} | Thank you for your business!", normal))
    elems.append(Spacer(1, 4*mm))
    elems.append(Paragraph("This is a computer generated invoice.", ParagraphStyle("foot", parent=styles["Normal"], fontSize=7, textColor=colors.grey, alignment=TA_CENTER)))

    doc.build(elems)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={d.get('invoiceNo','invoice')}.pdf"})


@api.get("/search")
async def global_search(q: str = "", user=Depends(current_user)):
    if not q or len(q) < 2:
        return {"results": []}
    
    pattern = {"$regex": q, "$options": "i"}
    results = []

    # Leads
    leads = await db.leads.find(
        {"$or": [{"name": pattern}, {"email": pattern}, {"phone": pattern}, {"company": pattern}]},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "status": 1}
    ).limit(4).to_list(4)
    for l in leads:
        results.append({"type": "Lead", "id": l["id"], "title": l.get("name",""), "subtitle": l.get("email",""), "url": "/crm/leads", "status": l.get("status","")})

    # Customers
    custs = await db.customers.find(
        {"$or": [{"name": pattern}, {"email": pattern}, {"phone": pattern}]},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1}
    ).limit(4).to_list(4)
    for c in custs:
        results.append({"type": "Customer", "id": c["id"], "title": c.get("name",""), "subtitle": c.get("phone",""), "url": "/crm/customers"})

    # Invoices
    invs = await db.invoices.find(
        {"$or": [{"invoiceNo": pattern}, {"customerName": pattern}]},
        {"_id": 0, "id": 1, "invoiceNo": 1, "customerName": 1, "total": 1, "status": 1}
    ).limit(4).to_list(4)
    for i in invs:
        results.append({"type": "Invoice", "id": i["id"], "title": i.get("invoiceNo",""), "subtitle": i.get("customerName",""), "url": "/sales/invoices", "status": i.get("status","")})

    # Products
    prods = await db.products.find(
        {"$or": [{"name": pattern}, {"sku": pattern}]},
        {"_id": 0, "id": 1, "name": 1, "sku": 1, "price": 1}
    ).limit(3).to_list(3)
    for p in prods:
        results.append({"type": "Product", "id": p["id"], "title": p.get("name",""), "subtitle": f"SKU: {p.get('sku','')}", "url": "/inventory/products"})

    # Employees
    emps = await db.employees.find(
        {"$or": [{"name": pattern}, {"email": pattern}, {"employeeCode": pattern}]},
        {"_id": 0, "id": 1, "name": 1, "role": 1, "employeeCode": 1}
    ).limit(3).to_list(3)
    for e in emps:
        results.append({"type": "Employee", "id": e["id"], "title": e.get("name",""), "subtitle": e.get("role",""), "url": "/hr/employees"})

    return {"results": results[:12]}


import pyotp
import qrcode
import qrcode.image.svg

@api.get("/auth/2fa/setup")
async def setup_2fa(user=Depends(current_user)):
    """Generate TOTP secret and QR code for user."""
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user["email"], issuer_name="GLC Zone CRM")
    
    # QR code as base64 image
    import io, base64
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    
    # Save secret temporarily (not enabled yet)
    await db.users.update_one({"id": user["id"]}, {"$set": {"totp_secret_pending": secret}})
    
    return {"secret": secret, "qr": f"data:image/png;base64,{qr_b64}", "uri": uri}

@api.post("/auth/2fa/enable")
async def enable_2fa(body: Dict[str, Any], user=Depends(current_user)):
    """Verify OTP and enable 2FA."""
    code = str(body.get("code", ""))
    u = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    secret = u.get("totp_secret_pending")
    if not secret:
        raise HTTPException(400, "Setup 2FA first")
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(400, "Invalid OTP code")
    await db.users.update_one({"id": user["id"]}, {
        "$set": {"totp_secret": secret, "twofa_enabled": True},
        "$unset": {"totp_secret_pending": ""}
    })
    return {"ok": True, "message": "2FA enabled successfully"}

@api.post("/auth/2fa/disable")
async def disable_2fa(body: Dict[str, Any], user=Depends(current_user)):
    """Disable 2FA after verifying OTP."""
    code = str(body.get("code", ""))
    u = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    secret = u.get("totp_secret")
    if not secret:
        raise HTTPException(400, "2FA not enabled")
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(400, "Invalid OTP code")
    await db.users.update_one({"id": user["id"]}, {
        "$unset": {"totp_secret": "", "twofa_enabled": ""}
    })
    return {"ok": True, "message": "2FA disabled"}

@api.post("/auth/2fa/verify")
async def verify_2fa(body: Dict[str, Any]):
    """Verify OTP during login (no auth required)."""
    token = body.get("temp_token", "")
    code = str(body.get("code", ""))
    if not token or not code:
        raise HTTPException(400, "Missing fields")
    
    # Decode temp token to get user
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        uid_ = payload.get("sub")
    except Exception:
        raise HTTPException(401, "Invalid token")
    
    u = await db.users.find_one({"id": uid_}, {"_id": 0})
    if not u:
        raise HTTPException(404, "User not found")
    
    secret = u.get("totp_secret")
    if not secret:
        raise HTTPException(400, "2FA not configured")
    
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(400, "Invalid OTP")
    
    # Issue full token
    full_token = make_token(u["id"], u.get("email",""), u.get("role",""))
    return {"token": full_token, "user": {k: u[k] for k in ["id","name","email","role","employeeCode"] if k in u}}


import shutil
from fastapi import UploadFile, File
from fastapi.responses import FileResponse
import uuid as uuid_lib

UPLOAD_DIR = "/var/www/crm-glc-source/backend/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@api.post("/upload")
async def upload_file(file: UploadFile = File(...), user=Depends(current_user)):
    ext = os.path.splitext(file.filename)[1].lower()
    allowed = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".doc", ".docx", ".xls", ".xlsx", ".txt", ".zip"}
    if ext not in allowed:
        raise HTTPException(400, f"File type {ext} not allowed")
    if file.size and file.size > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(400, "File too large (max 10MB)")
    
    file_id = str(uuid_lib.uuid4())
    filename = f"{file_id}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    return {
        "id": file_id,
        "filename": file.filename,
        "stored_name": filename,
        "url": f"/api/files/{filename}",
        "size": os.path.getsize(filepath),
        "type": file.content_type,
    }

@api.get("/files/{filename}")
async def get_file(filename: str, user=Depends(current_user)):
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(404, "File not found")
    return FileResponse(filepath)


# ── GLC Zone Sync Endpoints ──────────────────────────────────────
@api.post("/sync/deals")
async def sync_glczone_deals_endpoint(user=Depends(current_user)):
    """Sync GlcZone orders → CRM Pipeline deals"""
    import aiomysql
    conn = await aiomysql.connect(host="127.0.0.1", port=3306, user="glczone", password=__import__("os").getenv("GLCZONE_DB_PASSWORD", ""), db="glczone_db", autocommit=True)
    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT o.id, o.mobile, o.total, o.payment_method, o.payment_status, o.created_at,
                   u.username, u.email,
                   GROUP_CONCAT(oi.product_name SEPARATOR ', ') as product_names
            FROM orders o
            LEFT JOIN users u ON u.mobile = o.mobile
            LEFT JOIN order_items oi ON oi.order_id = o.id
            GROUP BY o.id
            ORDER BY o.created_at DESC
            LIMIT 500
        """)
        rows = await cur.fetchall()
    conn.close()

    created = updated = 0
    for row in rows:
        oid, mobile, total, payment, pay_status, created_at, username, email, product_names = row
        existing = await db.deals.find_one({"glczone_order_id": str(oid)}, {"_id": 0})
        stage = "WON" if str(pay_status or "").lower() == "paid" else "NEW"
        prob = 100 if stage == "WON" else 50
        data = {
            "glczone_order_id": str(oid),
            "title": f"Order #{oid} — {username or mobile}",
            "customerName": username or mobile,
            "customerPhone": mobile or "",
            "customerEmail": email or "",
            "value": float(total or 0),
            "stage": existing.get("stage", stage) if existing else stage,
            "probability": existing.get("probability", prob) if existing else prob,
            "paymentMethod": payment or "COD",
            "paymentStatus": str(pay_status or "pending").lower(),
            "notes": str(product_names or ""),
            "source": "glczone.in",
            "vertical": "GLC Zone",
            "updatedAt": now_iso(),
        }
        if existing:
            data["stage"] = existing.get("stage", stage)
            await db.deals.update_one({"glczone_order_id": str(oid)}, {"$set": data})
            updated += 1
        else:
            data.update({"id": uid(), "createdAt": str(created_at)})
            await db.deals.insert_one(data)
            created += 1
    return {"ok": True, "created": created, "updated": updated, "total": len(rows)}


@api.post("/sync/orders")
async def sync_glczone_orders(user=Depends(current_user)):
    """Sync glczone.in orders → CRM deals"""
    # Permission check
    role = user.get("role", "")
    stored = await db.settings.find_one({"key": "role_perms"})
    perms_map = stored["value"] if stored else ROLE_PERMS
    perms = perms_map.get(role, ROLE_PERMS.get(role, []))
    has_access = "*" in perms or any(p in perms for p in ["sales", "crm", "sales.orders"])
    if not has_access:
        raise HTTPException(403, "Access denied: insufficient permissions")
    import aiomysql, json as _json
    conn = await aiomysql.connect(
        host="127.0.0.1", port=3306,
        user="glczone", password=__import__("os").getenv("GLCZONE_DB_PASSWORD", ""),
        db="glczone_db", autocommit=True
    )
    created = updated = 0
    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT o.id, o.mobile, o.total, o.payment_method, o.payment_status,
                   o.created_at, u.username, u.email, oi.status as item_status
            FROM orders o
            LEFT JOIN users u ON u.mobile = o.mobile
            LEFT JOIN order_items oi ON oi.order_id = o.id
            GROUP BY o.id
            ORDER BY o.created_at DESC
            LIMIT 500
        """)
        rows = await cur.fetchall()
    conn.close()

    for row in rows:
        oid, mobile, total, payment, pay_status, created_at, username, email, status_json = row
        # Status parse karo
        try:
            status_list = _json.loads(status_json or "[]")
            current_status = status_list[-1][0] if status_list else "received"
        except Exception:
            current_status = "received"

        # CRM stage mapping
        stage_map = {
            "received": "NEW",
            "processing": "PROPOSAL",
            "shipped": "NEGOTIATION",
            "delivered": "WON",
            "cancelled": "LOST",
        }
        stage = stage_map.get(current_status, "NEW")

        # Check if deal already exists
        existing = await db.deals.find_one({"glczone_order_id": str(oid)}, {"_id": 0})
        deal_data = {
            "glczone_order_id": str(oid),
            "title": f"Order #{oid} — {username or mobile}",
            "customerName": username or mobile,
            "customerPhone": mobile,
            "customerEmail": email or "",
            "value": float(total or 0),
            "stage": stage,
            "paymentMethod": payment or "COD",
            "paymentStatus": pay_status or "PENDING",
            "glczone_status": current_status,
            "vertical": "GLC Zone",
            "source": "glczone.in",
            "updatedAt": now_iso(),
        }
        if existing:
            await db.deals.update_one({"glczone_order_id": str(oid)}, {"$set": deal_data})
            updated += 1
        else:
            deal_data.update({
                "id": uid(),
                "probability": 100 if stage == "WON" else 50,
                "createdAt": str(created_at),
            })
            await db.deals.insert_one(deal_data)
            created += 1

    return {"ok": True, "created": created, "updated": updated, "total": len(rows)}


@api.post("/sync/customers")
async def sync_glczone_customers(user=Depends(current_user)):
    """Sync glczone.in users → CRM customers"""
    # Permission check
    role = user.get("role", "")
    stored = await db.settings.find_one({"key": "role_perms"})
    perms_map = stored["value"] if stored else ROLE_PERMS
    perms = perms_map.get(role, ROLE_PERMS.get(role, []))
    has_access = "*" in perms or any(p in perms for p in ["crm", "crm.customers"])
    if not has_access:
        raise HTTPException(403, "Access denied: insufficient permissions")
    import aiomysql
    conn = await aiomysql.connect(
        host="127.0.0.1", port=3306,
        user="glczone", password=__import__("os").getenv("GLCZONE_DB_PASSWORD", ""),
        db="glczone_db", autocommit=True
    )
    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT u.id, u.username, u.email, u.mobile, u.created_at,
                   COUNT(o.id) as order_count,
                   COALESCE(SUM(o.total), 0) as total_spent
            FROM users u
            LEFT JOIN orders o ON o.mobile = u.mobile
            WHERE u.type = 'phone' AND u.username IS NOT NULL
            GROUP BY u.id
            ORDER BY total_spent DESC
            LIMIT 500
        """)
        rows = await cur.fetchall()
    conn.close()

    created = updated = 0
    for row in rows:
        uid_, username, email, mobile, created_at, order_count, total_spent = row
        existing = await db.customers.find_one({"glczone_user_id": str(uid_)}, {"_id": 0})
        cdata = {
            "glczone_user_id": str(uid_),
            "name": username or f"User {mobile}",
            "email": email or "",
            "phone": mobile or "",
            "type": "RETAIL",
            "source": "glczone.in",
            "glczone_orders": int(order_count),
            "glczone_spent": float(total_spent),
            "updatedAt": now_iso(),
        }
        if existing:
            await db.customers.update_one({"glczone_user_id": str(uid_)}, {"$set": cdata})
            updated += 1
        else:
            cdata.update({
                "id": uid(),
                "creditLimit": 0,
                "vertical": "GLC Zone",
                "createdAt": str(created_at),
            })
            await db.customers.insert_one(cdata)
            created += 1

    return {"ok": True, "created": created, "updated": updated, "total": len(rows)}


@api.get("/sync/status")
async def sync_status(user=Depends(current_user)):
    """Sync status — kitne records synced hain"""
    import aiomysql
    conn = await aiomysql.connect(
        host="127.0.0.1", port=3306,
        user="glczone", password=__import__("os").getenv("GLCZONE_DB_PASSWORD", ""),
        db="glczone_db", autocommit=True
    )
    async with conn.cursor() as cur:
        await cur.execute("SELECT COUNT(*) FROM orders")
        total_orders = (await cur.fetchone())[0]
        await cur.execute("SELECT COUNT(*) FROM users WHERE type='phone'")
        total_users = (await cur.fetchone())[0]
    conn.close()

    synced_deals = await db.deals.count_documents({"source": "glczone.in"})
    synced_customers = await db.customers.count_documents({"source": "glczone.in"})

    return {
        "glczone": {"orders": total_orders, "customers": total_users},
        "crm": {"deals": synced_deals, "customers": synced_customers},
        "last_sync": now_iso(),
    }


@api.post("/sync/products")
async def sync_glczone_products(user=Depends(current_user)):
    """Sync glczone.in products → CRM inventory"""
    role = user.get("role", "")
    stored = await db.settings.find_one({"key": "role_perms"})
    perms_map = stored["value"] if stored else ROLE_PERMS
    perms = perms_map.get(role, ROLE_PERMS.get(role, []))
    if "*" not in perms and not any(p in perms for p in ["inventory", "inventory.products"]):
        raise HTTPException(403, "Access denied")

    import aiomysql
    conn = await aiomysql.connect(host="127.0.0.1", port=3306, user="glczone", password=__import__("os").getenv("GLCZONE_DB_PASSWORD", ""), db="glczone_db", autocommit=True)
    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT p.id, p.name, p.sku, (SELECT CASE WHEN pv.special_price > 0 AND pv.special_price < pv.price THEN pv.special_price ELSE pv.price END FROM product_variants pv WHERE pv.product_id = p.id ORDER BY pv.price LIMIT 1) AS sale_price /* GLC_VARIANT_PRICE */, p.vendor_price, p.stock, p.status,
                   c.name as category_name
            FROM products p
            LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.status = 1
            LIMIT 500
        """)
        rows = await cur.fetchall()
    conn.close()

    created = updated = 0
    for row in rows:
        pid, name, sku, sale_price, vendor_price, stock, status, category = row
        # Parse JSON name: {"en":"Potato"} → "Potato"
        try:
            name_parsed = json.loads(name or "{}")
            clean_name = name_parsed.get("en") or name_parsed.get("hi") or str(name or "")
        except:
            clean_name = str(name or "")
        # Parse category name same way
        try:
            cat_parsed = json.loads(category or "{}")
            clean_cat = cat_parsed.get("en") or cat_parsed.get("hi") or str(category or "General")
        except:
            clean_cat = str(category or "General")
        existing = await db.products.find_one({"glczone_id": str(pid)}, {"_id": 0})
        data = {
            "glczone_id": str(pid),
            "name": clean_name,
            "sku": sku or f"GLC-{pid}",
            "sellingPrice": float(sale_price or 0),
            "buyingPrice": float(vendor_price or 0),
            "mrp": float(sale_price or 0),
            "stock": int(stock or 0),
            "category": clean_cat,
            "source": "glczone.in",
            "vertical": "GLC Zone",
            "updatedAt": now_iso(),
        }
        if existing:
            await db.products.update_one({"glczone_id": str(pid)}, {"$set": data})
            updated += 1
        else:
            data.update({"id": uid(), "createdAt": now_iso()})
            await db.products.insert_one(data)
            created += 1

    return {"ok": True, "created": created, "updated": updated, "total": len(rows)}


@api.post("/sync/orders-crm")
async def sync_glczone_orders_crm(user=Depends(current_user)):
    """Sync glczone.in orders → CRM Sales Orders"""
    role = user.get("role", "")
    stored = await db.settings.find_one({"key": "role_perms"})
    perms_map = stored["value"] if stored else ROLE_PERMS
    perms = perms_map.get(role, ROLE_PERMS.get(role, []))
    if "*" not in perms and not any(p in perms for p in ["sales", "sales.orders"]):
        raise HTTPException(403, "Access denied")

    import aiomysql, json as _json
    conn = await aiomysql.connect(host="127.0.0.1", port=3306, user="glczone", password=__import__("os").getenv("GLCZONE_DB_PASSWORD", ""), db="glczone_db", autocommit=True)
    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT o.id, o.mobile, o.total, o.final_total, o.payment_method,
                   o.payment_status, o.address, o.created_at,
                   u.username, oi.status as item_status,
                   GROUP_CONCAT(oi.product_name SEPARATOR ', ') as product_names
            FROM orders o
            LEFT JOIN users u ON u.mobile = o.mobile
            LEFT JOIN order_items oi ON oi.order_id = o.id
            GROUP BY o.id
            ORDER BY o.created_at DESC
            LIMIT 500
        """)
        rows = await cur.fetchall()
    conn.close()

    created = updated = 0
    for row in rows:
        oid, mobile, total, final_total, payment, pay_status, address, created_at, username, status_json, product_names = row
        try:
            status_list = _json.loads(status_json or "[]")
            current_status = status_list[-1][0] if status_list else "received"
        except:
            current_status = "received"

        status_map = {"received": "PENDING", "processing": "PROCESSING", "shipped": "SHIPPED", "delivered": "DELIVERED", "cancelled": "CANCELLED"}
        crm_status = status_map.get(current_status, "PENDING")

        existing = await db.sales_orders.find_one({"glczone_order_id": str(oid)}, {"_id": 0})
        data = {
            "glczone_order_id": str(oid),
            "orderNo": f"GLZ-{oid}",
            "customerName": username or mobile,
            "customerPhone": mobile,
            "total": float(total or 0),
            "finalTotal": float(final_total or 0),
            "paymentMethod": payment or "COD",
            "paymentStatus": pay_status or "PENDING",
            "status": crm_status,
            "glczone_status": current_status,
            "products": str(product_names or ""),
            "deliveryAddress": str(address or ""),
            "source": "glczone.in",
            "vertical": "GLC Zone",
            "updatedAt": now_iso(),
        }
        if existing:
            await db.sales_orders.update_one({"glczone_order_id": str(oid)}, {"$set": data})
            updated += 1
        else:
            data.update({"id": uid(), "createdAt": str(created_at)})
            await db.sales_orders.insert_one(data)
            created += 1

    return {"ok": True, "created": created, "updated": updated, "total": len(rows)}


@api.post("/sync/deliveries")
async def sync_glczone_deliveries(user=Depends(current_user)):
    """Sync glczone.in delivery orders → CRM deliveries"""
    role = user.get("role", "")
    stored = await db.settings.find_one({"key": "role_perms"})
    perms_map = stored["value"] if stored else ROLE_PERMS
    perms = perms_map.get(role, ROLE_PERMS.get(role, []))
    if "*" not in perms and "delivery" not in perms:
        raise HTTPException(403, "Access denied")

    import aiomysql, json as _json
    conn = await aiomysql.connect(host="127.0.0.1", port=3306, user="glczone", password=__import__("os").getenv("GLCZONE_DB_PASSWORD", ""), db="glczone_db", autocommit=True)
    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT o.id, o.mobile, o.address, o.created_at,
                   u.username, oi.status, oi.delivery_boy_id,
                   db_user.username as delivery_boy_name
            FROM orders o
            LEFT JOIN users u ON u.mobile = o.mobile
            LEFT JOIN order_items oi ON oi.order_id = o.id
            LEFT JOIN users db_user ON db_user.id = oi.delivery_boy_id
            GROUP BY o.id
            ORDER BY o.created_at DESC
            LIMIT 500
        """)
        rows = await cur.fetchall()
    conn.close()

    created = updated = 0
    for row in rows:
        oid, mobile, address, created_at, username, status_json, db_id, db_name = row
        try:
            status_list = _json.loads(status_json or "[]")
            current_status = status_list[-1][0] if status_list else "received"
        except:
            current_status = "received"

        existing = await db.deliveries.find_one({"glczone_order_id": str(oid)}, {"_id": 0})
        data = {
            "glczone_order_id": str(oid),
            "orderNo": f"GLZ-{oid}",
            "customerName": username or mobile,
            "customerPhone": mobile,
            "deliveryAddress": str(address or ""),
            "deliveryBoy": db_name or "Unassigned",
            "status": {"RECEIVED": "PENDING", "PROCESSED": "PENDING", "PROCESSING": "PENDING", "SHIPPED": "IN_TRANSIT", "OUT_FOR_DELIVERY": "IN_TRANSIT"}.get(str(current_status).upper(), str(current_status).upper()),
            "source": "glczone.in",
            "updatedAt": now_iso(),
        }
        if existing:
            await db.deliveries.update_one({"glczone_order_id": str(oid)}, {"$set": data})
            updated += 1
        else:
            data.update({"id": uid(), "createdAt": str(created_at)})
            await db.deliveries.insert_one(data)
            created += 1

    return {"ok": True, "created": created, "updated": updated, "total": len(rows)}


@api.get("/sync/all")
async def sync_all(user=Depends(current_user)):
    """Sync status of all modules"""
    orders_count = await db.sales_orders.count_documents({"source": "glczone.in"})
    products_count = await db.products.count_documents({"source": "glczone.in"})
    customers_count = await db.customers.count_documents({"source": "glczone.in"})
    deals_count = await db.deals.count_documents({"source": "glczone.in"})
    deliveries_count = await db.deliveries.count_documents({"source": "glczone.in"})
    return {
        "synced": {
            "orders": orders_count,
            "products": products_count,
            "customers": customers_count,
            "deals": deals_count,
            "deliveries": deliveries_count,
        }
    }


@api.post("/ocm/webchat")
async def webchat_incoming(request: Request):
    """Website chat widget endpoint — no auth required."""
    body = await request.json()
    session_id = body.get("sessionId", "unknown")
    text = body.get("text", "")
    name = body.get("name", "Web Visitor")

    if not text:
        return {"ok": False, "error": "No text"}

    # Find or create contact
    contact = await db.ocm_contacts.find_one({"webchatId": session_id})
    if not contact:
        contact = {
            "id": uid(),
            "name": name,
            "webchatId": session_id,
            "channels": ["WEBCHAT"],
            "tags": ["website"],
            "subscribed": True,
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
        }
        await db.ocm_contacts.insert_one(dict(contact))

    # Find or create conversation
    conversation = await db.ocm_conversations.find_one({"contactId": contact["id"], "channel": "WEBCHAT"})
    if not conversation:
        conversation = {
            "id": uid(),
            "contactId": contact["id"],
            "channel": "WEBCHAT",
            "status": "OPEN",
            "lastMessage": text,
            "lastMessageAt": now_iso(),
            "createdAt": now_iso(),
        }
        await db.ocm_conversations.insert_one(dict(conversation))

    # Save incoming message
    in_msg = {
        "id": uid(),
        "conversationId": conversation["id"],
        "channel": "WEBCHAT",
        "direction": "IN",
        "text": text,
        "sentBy": name,
        "sentById": contact["id"],
        "status": "RECEIVED",
        "createdAt": now_iso(),
    }
    await db.ocm_messages.insert_one(in_msg)
    await db.ocm_conversations.update_one(
        {"id": conversation["id"]},
        {"$set": {"lastMessage": text, "lastMessageAt": now_iso(), "status": "OPEN"}}
    )

    # Get AI reply
    glczone_context = await fetch_glczone_context()
    contact_fresh = await db.ocm_contacts.find_one({"id": contact["id"]}, {"_id": 0})
    preferred_lang = (contact_fresh or {}).get("preferredLang", "Hinglish")

    import httpx, os
    groq_key = os.getenv("GROQ_API_KEY", "")
    ai_reply = "Namaste! Kya madad kar sakti hoon? 😊"

    if groq_key:
        recent_msgs = await db.ocm_messages.find(
            {"conversationId": conversation["id"]}, {"_id": 0}
        ).sort("createdAt", -1).limit(6).to_list(6)
        recent_msgs.reverse()

        messages = [{
            "role": "system",
            "content": (
                f"You are Zara, a friendly AI assistant for GLC Zone (glczone.in). "
                f"Reply in {preferred_lang}. Keep replies under 3 lines. Be helpful and warm."
                f"\n{glczone_context}"
                "\n- Delivery: ₹20 flat upto 15kg, ₹2/kg above"
                "\n- Time: 30-60 min delivery"
                "\n- Payment: COD/UPI/Card/Wallet"
            )
        }]
        for m in recent_msgs:
            role = "user" if m.get("direction") == "IN" else "assistant"
            messages.append({"role": role, "content": m.get("text", "")})

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    json={"model": "openai/gpt-oss-120b", "messages": messages, "max_tokens": 200}
                )
                ai_reply = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            log.exception(f"Webchat AI failed: {e}")

    # Save AI reply
    out_msg = {
        "id": uid(),
        "conversationId": conversation["id"],
        "channel": "WEBCHAT",
        "direction": "OUT",
        "text": ai_reply,
        "sentBy": "Zara AI",
        "sentById": "ai",
        "status": "SENT",
        "createdAt": now_iso(),
    }
    await db.ocm_messages.insert_one(out_msg)
    await db.ocm_conversations.update_one(
        {"id": conversation["id"]},
        {"$set": {"lastMessage": ai_reply, "lastMessageAt": now_iso()}}
    )

    return {"ok": True, "reply": ai_reply, "conversationId": conversation["id"]}


class FlowIn(BaseModel):
    name: str
    channel: str = "TELEGRAM"
    trigger: str = "KEYWORD"
    triggerValue: str = ""
    steps: List[Dict[str, Any]] = []
    status: str = "DRAFT"


@api.get("/ocm/flows")
async def ocm_list_flows(user=Depends(current_user)):
    items = await db.ocm_flows.find({}, {"_id": 0}).sort("createdAt", -1).to_list(200)
    return {"items": items}


@api.post("/ocm/flows")
async def ocm_create_flow(data: FlowIn, user=Depends(current_user)):
    doc = {**data.model_dump(), "id": uid(), "createdAt": now_iso()}
    await db.ocm_flows.insert_one(doc)
    return clean(doc)


@api.put("/ocm/flows/{fid}")
async def ocm_update_flow(fid: str, body: Dict[str, Any], user=Depends(current_user)):
    await db.ocm_flows.update_one({"id": fid}, {"$set": body})
    d = await db.ocm_flows.find_one({"id": fid}, {"_id": 0})
    return d


class SocialPostIn(BaseModel):
    caption: str
    hashtags: List[str] = []
    channels: List[str] = ["INSTAGRAM"]
    mediaUrl: Optional[str] = None
    scheduledAt: Optional[str] = None
    status: str = "SCHEDULED"


FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "")
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
IG_BUSINESS_ACCOUNT_ID = os.environ.get("IG_BUSINESS_ACCOUNT_ID", "")
FB_API_VERSION = "v20.0"


def build_full_caption(caption: str, hashtags: List[str]) -> str:
    tag_str = " ".join(h if h.startswith("#") else f"#{h}" for h in hashtags)
    return f"{caption}\n\n{tag_str}".strip()


def publish_to_facebook(full_caption: str, media_url: Optional[str]) -> dict:
    if not FB_PAGE_ID or not FB_PAGE_ACCESS_TOKEN:
        return {"success": False, "error": "Facebook Page not configured"}
    try:
        if media_url:
            url = f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/photos"
            payload = {"url": media_url, "caption": full_caption, "access_token": FB_PAGE_ACCESS_TOKEN}
        else:
            url = f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/feed"
            payload = {"message": full_caption, "access_token": FB_PAGE_ACCESS_TOKEN}
        r = requests.post(url, data=payload, timeout=30)
        body = r.json()
        if r.status_code == 200:
            return {"success": True, "postId": body.get("id") or body.get("post_id")}
        return {"success": False, "error": body.get("error", {}).get("message", "Unknown Facebook error")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def publish_to_instagram(full_caption: str, media_url: Optional[str]) -> dict:
    if not IG_BUSINESS_ACCOUNT_ID or not FB_PAGE_ACCESS_TOKEN:
        return {"success": False, "error": "Instagram Business Account not configured"}
    if not media_url:
        return {"success": False, "error": "Instagram requires an image/video URL — text-only posts are not supported"}
    try:
        create_url = f"https://graph.facebook.com/{FB_API_VERSION}/{IG_BUSINESS_ACCOUNT_ID}/media"
        r1 = requests.post(create_url, data={
            "image_url": media_url,
            "caption": full_caption,
            "access_token": FB_PAGE_ACCESS_TOKEN,
        }, timeout=30)
        body1 = r1.json()
        if r1.status_code != 200 or "id" not in body1:
            return {"success": False, "error": body1.get("error", {}).get("message", "Failed to create Instagram media container")}
        creation_id = body1["id"]

        publish_url = f"https://graph.facebook.com/{FB_API_VERSION}/{IG_BUSINESS_ACCOUNT_ID}/media_publish"
        r2 = requests.post(publish_url, data={
            "creation_id": creation_id,
            "access_token": FB_PAGE_ACCESS_TOKEN,
        }, timeout=30)
        body2 = r2.json()
        if r2.status_code == 200:
            return {"success": True, "postId": body2.get("id")}
        return {"success": False, "error": body2.get("error", {}).get("message", "Failed to publish Instagram media")}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def broadcast_whatsapp(text: str) -> dict:
    """Send WhatsApp message to all active conversations in 24hr window."""
    try:
        conversations = await db.ocm_conversations.find(
            {"channel": "WHATSAPP", "status": "OPEN"},
            {"_id": 0, "contactId": 1}
        ).to_list(500)
        
        sent = 0
        failed = 0
        for conv in conversations:
            contact = await db.ocm_contacts.find_one({"id": conv["contactId"]}, {"_id": 0})
            if contact:
                to_phone = contact.get("whatsappId") or contact.get("phone")
                if to_phone:
                    result = send_whatsapp_text(to_phone, text)
                    if result.get("success"):
                        sent += 1
                    else:
                        failed += 1
        
        return {"success": sent > 0, "sent": sent, "failed": failed, 
                "error": None if sent > 0 else "No active WhatsApp conversations"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def publish_to_telegram(full_caption: str, media_url: Optional[str]) -> dict:
    """Publish a post to Telegram channel."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID", "")
    if not token or not channel_id:
        return {"success": False, "error": "Telegram not configured"}
    try:
        if media_url:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            payload = {"chat_id": channel_id, "photo": media_url, "caption": full_caption, "parse_mode": "Markdown"}
        else:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": channel_id, "text": full_caption, "parse_mode": "Markdown"}
        r = requests.post(url, json=payload, timeout=15)
        body = r.json()
        if body.get("ok"):
            return {"success": True, "postId": str(body["result"]["message_id"])}
        return {"success": False, "error": body.get("description", "Telegram error")}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def publish_social_post(post: dict) -> dict:
    full_caption = build_full_caption(post.get("caption", ""), post.get("hashtags", []))
    media_url = post.get("mediaUrl")
    results = {}
    any_success = False
    errors = []

    for channel in post.get("channels", []):
        if channel == "FACEBOOK":
            res = publish_to_facebook(full_caption, media_url)
        elif channel == "INSTAGRAM":
            res = publish_to_instagram(full_caption, media_url)
        elif channel == "TELEGRAM":
            res = publish_to_telegram(full_caption, media_url)
        elif channel == "WHATSAPP":
            # WhatsApp broadcast to all active conversations (24hr window)
            res = await broadcast_whatsapp(full_caption)
        else:
            res = {"success": False, "error": f"Publishing to {channel} not supported yet"}
        results[channel] = res
        if res.get("success"):
            any_success = True
        else:
            errors.append(f"{channel}: {res.get('error')}")

    new_status = "PUBLISHED" if any_success and not errors else ("PARTIALLY_PUBLISHED" if any_success else "FAILED")
    update = {
        "status": new_status,
        "publishResults": results,
        "publishedAt": now_iso() if any_success else None,
        "publishError": "; ".join(errors) if errors else None,
    }
    await db.social_posts.update_one({"id": post["id"]}, {"$set": update})
    return {**post, **update}


@api.get("/ocm/social-posts")
async def ocm_list_posts(user=Depends(current_user)):
    items = await db.social_posts.find({}, {"_id": 0}).sort("scheduledAt", -1).to_list(500)
    return {"items": items}


@api.post("/ocm/social-posts")
async def ocm_create_post(data: SocialPostIn, user=Depends(current_user)):
    doc = {**data.model_dump(), "id": uid(), "createdBy": user["name"], "createdAt": now_iso()}
    await db.social_posts.insert_one(doc)
    return clean(doc)


@api.post("/ocm/social-posts/{pid}/publish")
async def ocm_publish_post_now(pid: str, user=Depends(current_user)):
    post = await db.social_posts.find_one({"id": pid}, {"_id": 0})
    if not post:
        raise HTTPException(404, "Post not found")
    result = await publish_social_post(post)
    await log_activity(user["id"], "ocm.social-posts", "publish", pid, {"channels": post.get("channels")})
    return clean(result)


@api.put("/ocm/social-posts/{pid}")
async def ocm_update_post(pid: str, body: Dict[str, Any], user=Depends(current_user)):
    await db.social_posts.update_one({"id": pid}, {"$set": body})
    d = await db.social_posts.find_one({"id": pid}, {"_id": 0})
    return d


@api.delete("/ocm/social-posts/{pid}")
async def ocm_delete_post(pid: str, user=Depends(current_user)):
    await db.social_posts.delete_one({"id": pid})
    return {"ok": True}


class AiCaptionIn(BaseModel):
    prompt: str
    tone: str = "friendly"
    vertical: Optional[str] = None
    channel: str = "INSTAGRAM"


@api.post("/ai/caption")
async def ai_caption(data: AiCaptionIn, user=Depends(current_user)):
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI key not configured")
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        system = (
            "You are a social media copywriter for GLC Zone, an India-first business running 8 verticals "
            "(GLC Fresh, GLC Store, GLC Garden, GLC Hardwares, Dhani Jewellers, India Mandi, GLC Property, GLC Legal). "
            f"Write a {data.tone} caption in <60 words for {data.channel}. "
            "Return JSON only in this exact shape: "
            '{"caption": "...", "hashtags": ["#tag1", "#tag2", ...]} '
            "with 5-8 relevant hashtags. Do not wrap in code fences."
        )
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"ai-caption-{user['id']}", system_message=system).with_model("gemini", "gemini-3-flash-preview")
        prompt = f"Topic: {data.prompt}\nVertical: {data.vertical or 'GLC Zone'}\nChannel: {data.channel}\nTone: {data.tone}"
        resp = await chat.send_message(UserMessage(text=prompt))
        text = (resp or "").strip()
        # Attempt to parse JSON
        import json as _json
        import re
        m = re.search(r"\{.*\}", text, re.S)
        payload = _json.loads(m.group(0)) if m else {"caption": text, "hashtags": []}
        return payload
    except Exception as e:
        logging.getLogger("glc").exception(f"AI caption failed: {e}")
        return {"caption": data.prompt, "hashtags": ["#glczone"], "error": str(e)}


@api.get("/ocm/stats")
async def ocm_stats(user=Depends(current_user)):
    contacts = await db.ocm_contacts.count_documents({})
    convs = await db.ocm_conversations.count_documents({})
    open_convs = await db.ocm_conversations.count_documents({"status": "OPEN"})
    broadcasts = await db.ocm_broadcasts.count_documents({})
    scheduled_posts = await db.social_posts.count_documents({"status": "SCHEDULED"})
    return {
        "contacts": contacts,
        "conversations": convs,
        "openConversations": open_convs,
        "broadcasts": broadcasts,
        "scheduledPosts": scheduled_posts,
    }


# =========================================================
# Seed on startup
# =========================================================
async def scheduled_posts_worker():
    while True:
        try:
            now = now_iso()
            due_posts = await db.social_posts.find({
                "status": "SCHEDULED",
                "scheduledAt": {"$ne": None, "$lte": now},
            }, {"_id": 0}).to_list(50)
            for post in due_posts:
                try:
                    await publish_social_post(post)
                    log.info(f"Scheduled post auto-published: {post['id']}")
                except Exception as e:
                    log.exception(f"Scheduled post publish failed: {post.get('id')}: {e}")
        except Exception as e:
            log.exception(f"scheduled_posts_worker loop error: {e}")
        await asyncio.sleep(60)


@app.on_event("startup")
async def startup_seed():
    from seed import seed_all
    try:
        pass  # seed_all disabled permanently - live production CRM, no auto demo-seed
        log.info("Seed complete")
    except Exception as e:
        log.exception(f"Seed failed: {e}")
    try:
        init_storage()
        log.info("Storage initialized")
    except Exception as e:
        log.warning(f"Storage init deferred: {e}")
    try:
        await ensure_finance_accounts()
    except Exception as e:
        log.warning(f"Finance accounts check failed: {e}")
    asyncio.create_task(scheduled_posts_worker())
    log.info("Scheduled posts worker started")


@app.on_event("shutdown")
async def shutdown_db():
    client.close()


# =========================================================
# FINANCE: double-entry books, credit notes, GST returns
# =========================================================
async def next_seq(prefix: str) -> int:
    """Atomic per-financial-year counter (no duplicate document numbers under concurrent requests)."""
    doc = await db.counters.find_one_and_update({"_id": gf.counter_key(prefix)}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER)
    return int(doc["seq"])


async def ensure_finance_accounts():
    have = {a["code"] async for a in db.accounts.find({}, {"code": 1, "_id": 0})}
    for code, (name, typ) in gf.REQUIRED_ACCOUNTS.items():
        if code not in have:
            await db.accounts.insert_one({"id": uid(), "code": code, "name": name, "type": typ, "balance": 0, "createdAt": now_iso()})


async def post_journal(narration: str, entries: List[dict], ref_type: str, ref_id: str, user: Optional[dict] = None):
    """Posts one balanced journal entry, once per (ref_type, ref_id). Never raises: a bookkeeping problem must not
    block an invoice or payment; gaps are listed by /finance/books-check and repaired by /finance/backfill-books."""
    try:
        if not entries:
            return None
        if not gf.check_balanced(entries):
            log.error(f"journal not balanced, skipped: {narration}")
            return None
        if await db.journal.find_one({"refType": ref_type, "refId": ref_id}, {"_id": 0, "id": 1}):
            return None
        await ensure_finance_accounts()
        ids = {a["code"]: a["id"] async for a in db.accounts.find({}, {"code": 1, "id": 1, "_id": 0})}
        rows = [{"accountId": ids[e["accountCode"]], "accountCode": e["accountCode"], "debit": e["debit"], "credit": e["credit"]} for e in entries]
        doc = {"id": uid(), "date": datetime.now(timezone.utc).date().isoformat(), "narration": narration, "entries": rows,
               "totalDebit": round(sum(r["debit"] for r in rows), 2), "totalCredit": round(sum(r["credit"] for r in rows), 2),
               "refType": ref_type, "refId": ref_id, "createdBy": (user or {}).get("id"), "createdAt": now_iso()}
        await db.journal.insert_one(doc)
        return doc
    except Exception as e:
        log.exception(f"post_journal failed ({narration}): {e}")
        return None


@api.get("/finance/company")
async def finance_company(user=Depends(finance_user)):
    return {"gstin": gf.COMPANY_GSTIN, "gstinValid": gf.valid_gstin(gf.COMPANY_GSTIN), "stateCode": gf.COMPANY_STATE_CODE,
            "state": gf.STATE_CODES.get(gf.COMPANY_STATE_CODE), "financialYear": gf.fy_label(),
            "delivery": {"sac": gf.DELIVERY_SAC, "gstRate": gf.DELIVERY_GST_RATE, "taxInclusive": gf.DELIVERY_TAX_INCLUSIVE}}


class CreditNoteIn(BaseModel):
    reason: str = "Sales return"
    items: Optional[List[Dict[str, Any]]] = None      # [{"index": 0, "qty": 1}]; omit for the whole invoice
    includeDelivery: bool = False


@api.post("/invoices/{iid}/credit-note")
async def create_credit_note(iid: str, data: CreditNoteIn, user=Depends(finance_user)):
    inv = await db.invoices.find_one({"id": iid}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if inv.get("status") == "CANCELLED":
        raise HTTPException(400, "Invoice is cancelled")
    prior_qty = inv.get("creditedQty") or {}
    if data.items is None and (inv.get("creditedAmount") or 0) > 0:
        raise HTTPException(400, "This invoice already has a credit note; choose the items to credit")
    try:
        items = gf.credit_note_items(inv, data.items, data.includeDelivery)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not items:
        raise HTTPException(400, "Nothing to credit")
    lines = gf.ensure_lines(inv)
    for p in data.items or []:
        idx = str(int(p.get("index", -1)))
        if float(prior_qty.get(idx, 0)) + float(p.get("qty") or 0) > lines[int(idx)]["qty"] + 1e-9:
            raise HTTPException(400, "Credit quantity exceeds what was invoiced")
    intra = (inv.get("supplyType") == "INTRA") if inv.get("supplyType") else gf.is_intra_state(inv.get("customerGst"), inv.get("customerState"))
    t = calc_gst(items, intra_state=intra, round_off=True)
    remaining = round(inv["total"] - (inv.get("creditedAmount") or 0), 2)
    if t["total"] > remaining + 0.01:
        raise HTTPException(400, f"Credit note (₹{t['total']:,.2f}) exceeds the invoice balance (₹{remaining:,.2f})")
    note_no = gf.doc_number("CN", await next_seq("CN"))
    cn = {"id": uid(), "noteNo": note_no, "invoiceId": iid, "invoiceNo": inv.get("invoiceNo"), "customerName": inv.get("customerName"),
          "customerGst": inv.get("customerGst"), "customerState": inv.get("customerState"), "placeOfSupply": inv.get("placeOfSupply"),
          "reason": data.reason, "items": items, "lines": t["lines"], "subtotal": t["subtotal"], "cgst": t["cgst"], "sgst": t["sgst"],
          "igst": t["igst"], "roundOff": t["roundOff"], "total": t["total"], "noteDate": now_iso(), "createdBy": user.get("id"), "createdAt": now_iso()}
    await db.credit_notes.insert_one(cn)
    credited = round((inv.get("creditedAmount") or 0) + t["total"], 2)
    for p in data.items or []:
        idx = str(int(p["index"]))
        prior_qty[idx] = float(prior_qty.get(idx, 0)) + float(p["qty"])
    if data.items is None:
        for i, l in enumerate(lines):
            if not l.get("isDelivery") or data.includeDelivery:
                prior_qty[str(i)] = l["qty"]
    net_due = round(inv["total"] - credited, 2)
    paid = inv.get("paidAmount") or 0
    due = max(round(net_due - paid, 2), 0)
    status_ = "CREDITED" if net_due <= 0.01 else ("PAID" if due <= 0.01 else ("PARTIAL" if paid > 0 else "UNPAID"))
    await db.invoices.update_one({"id": iid}, {"$set": {"creditedAmount": credited, "creditedQty": prior_qty, "dueAmount": due,
                                                        "refundDue": max(round(paid - net_due, 2), 0), "status": status_, "updatedAt": now_iso()}})
    await post_journal(f"Credit note {note_no} against {inv.get('invoiceNo')}", gf.journal_for_credit_note(cn), "CN", cn["id"], user)
    await log_activity(user["id"], "credit_notes", "create", cn["id"], {"invoiceId": iid})
    return clean(cn)


@api.get("/credit-notes")
async def list_credit_notes(page: int = 1, limit: int = 50, q: Optional[str] = None, user=Depends(finance_user)):
    return await paginate(db.credit_notes, {}, page, limit, search_fields=["noteNo", "invoiceNo", "customerName"], q=q)


@api.post("/invoices/{iid}/cancel")
async def cancel_invoice(iid: str, user=Depends(finance_user)):
    inv = await db.invoices.find_one({"id": iid}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if inv.get("status") != "UNPAID" or (inv.get("paidAmount") or 0) > 0 or (inv.get("creditedAmount") or 0) > 0:
        raise HTTPException(400, "Only an unpaid invoice with no credit note can be cancelled; otherwise issue a credit note")
    await db.invoices.update_one({"id": iid}, {"$set": {"status": "CANCELLED", "dueAmount": 0, "cancelledAt": now_iso(), "updatedAt": now_iso()}})
    rev = [{"accountCode": e["accountCode"], "debit": e["credit"], "credit": e["debit"]} for e in gf.journal_for_invoice({**inv, "lines": gf.ensure_lines(inv)})]
    await post_journal(f"Cancelled invoice {inv.get('invoiceNo')}", rev, "INV_CANCEL", iid, user)
    await log_activity(user["id"], "invoices", "cancel", iid)
    return {"ok": True}


@api.get("/finance/trial-balance")
async def finance_trial_balance(user=Depends(finance_user)):
    accts = await db.accounts.find({}, {"_id": 0}).to_list(500)
    journals = await db.journal.find({}, {"_id": 0, "entries": 1}).to_list(100000)
    return gf.trial_balance(accts, journals)


@api.get("/finance/ledger/{code}")
async def finance_ledger(code: str, user=Depends(finance_user)):
    acct = await db.accounts.find_one({"code": code}, {"_id": 0})
    if not acct:
        raise HTTPException(404, "Account not found")
    journals = await db.journal.find({"entries.accountId": acct["id"]}, {"_id": 0}).to_list(100000)
    return gf.ledger(acct, journals)


@api.get("/finance/receivables-ageing")
async def finance_ageing(user=Depends(finance_user)):
    invs = await db.invoices.find({"status": {"$in": ["UNPAID", "PARTIAL"]}}, {"_id": 0}).to_list(20000)
    return gf.receivables_ageing(invs)


@api.get("/reports/gstr1")
async def report_gstr1(month: Optional[str] = None, user=Depends(finance_user)):
    invs = await db.invoices.find(_month_filter("invoiceDate", month), {"_id": 0}).to_list(50000)
    notes = await db.credit_notes.find(_month_filter("noteDate", month), {"_id": 0}).to_list(50000)
    return {"month": month, "gstin": gf.COMPANY_GSTIN, **gf.gstr1(invs, notes)}


@api.get("/reports/gstr3b")
async def report_gstr3b(month: Optional[str] = None, user=Depends(finance_user)):
    invs = await db.invoices.find(_month_filter("invoiceDate", month), {"_id": 0}).to_list(50000)
    notes = await db.credit_notes.find(_month_filter("noteDate", month), {"_id": 0}).to_list(50000)
    pos = await db.purchase_orders.find({"status": "RECEIVED", **_month_filter("receivedAt", month)}, {"_id": 0}).to_list(50000)
    return {"month": month, "gstin": gf.COMPANY_GSTIN, **gf.gstr3b(invs, notes, pos),
            "note": "Draft for the accountant: check ITC eligibility (blocked credits, supplier filing) and reverse-charge items before filing."}


@api.get("/finance/books-check")
async def finance_books_check(user=Depends(finance_user)):
    """Which invoices / payments / credit notes / received POs have no journal entry yet."""
    have = {(j["refType"], j["refId"]) async for j in db.journal.find({"refType": {"$in": ["INV", "PAY", "CN", "PO"]}}, {"_id": 0, "refType": 1, "refId": 1})}
    missing = {
        "invoices": [i.get("invoiceNo") async for i in db.invoices.find({"status": {"$ne": "CANCELLED"}}, {"_id": 0, "id": 1, "invoiceNo": 1}) if ("INV", i["id"]) not in have],
        "payments": [p["id"] async for p in db.payments.find({}, {"_id": 0, "id": 1}) if ("PAY", p["id"]) not in have],
        "creditNotes": [c.get("noteNo") async for c in db.credit_notes.find({}, {"_id": 0, "id": 1, "noteNo": 1}) if ("CN", c["id"]) not in have],
        "purchaseOrders": [p.get("poNo") async for p in db.purchase_orders.find({"status": "RECEIVED"}, {"_id": 0, "id": 1, "poNo": 1}) if ("PO", p["id"]) not in have],
    }
    return {"missing": missing, "allPosted": not any(missing.values())}


@api.post("/finance/backfill-books")
async def finance_backfill_books(user=Depends(finance_user)):
    """Posts the missing journal entries for documents created before auto-posting existed (safe to repeat)."""
    await ensure_finance_accounts()
    posted = {"invoices": 0, "payments": 0, "creditNotes": 0, "purchaseOrders": 0}
    async for inv in db.invoices.find({}, {"_id": 0}):
        if inv.get("status") == "CANCELLED":
            continue
        lines = gf.ensure_lines(inv)
        inv2 = {**inv, "lines": lines}
        entries = gf.journal_for_invoice(inv2)
        if not gf.check_balanced(entries):      # old invoice whose lines do not add up to its stored total
            taxes = round((inv.get("cgst") or 0) + (inv.get("sgst") or 0) + (inv.get("igst") or 0), 2)
            entries = gf._entries([("1300", inv["total"], 0), ("4100", 0, round(inv["total"] - taxes, 2)),
                                   ("2210", 0, inv.get("cgst", 0)), ("2220", 0, inv.get("sgst", 0)), ("2230", 0, inv.get("igst", 0))])
        if await post_journal(f"Invoice {inv.get('invoiceNo')} (backfill)", entries, "INV", inv["id"], user):
            posted["invoices"] += 1
    async for pay in db.payments.find({}, {"_id": 0}):
        if await post_journal(f"Payment (backfill) {pay.get('reference') or ''}".strip(), gf.journal_for_payment(pay["amount"], pay.get("method")), "PAY", pay["id"], user):
            posted["payments"] += 1
    async for cn in db.credit_notes.find({}, {"_id": 0}):
        if await post_journal(f"Credit note {cn.get('noteNo')} (backfill)", gf.journal_for_credit_note(cn), "CN", cn["id"], user):
            posted["creditNotes"] += 1
    async for po in db.purchase_orders.find({"status": "RECEIVED"}, {"_id": 0}):
        if await post_journal(f"Goods received {po.get('poNo')} (backfill)", gf.journal_for_purchase(po), "PO", po["id"], user):
            posted["purchaseOrders"] += 1
    return {"posted": posted}


@api.get("/")
async def root():
    return {"message": "GLC Zone CRM+ERP API", "version": "1.0.0"}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
