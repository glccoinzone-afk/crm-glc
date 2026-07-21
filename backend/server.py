"""GLC Zone CRM + ERP - Backend (FastAPI + MongoDB)."""
from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta, date
import os
import uuid
import logging
import bcrypt
import jwt as pyjwt
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ.get("JWT_SECRET", "glc-zone-supersecret-dev-only-change-in-prod")
JWT_ALGO = "HS256"
JWT_EXPIRES_MIN = 60 * 24 * 7

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
    token = make_token(u["id"], u["email"], u.get("role", "Admin"))
    await log_activity(u["id"], "auth", "login")
    return {"token": token, "user": clean(u)}


@api.get("/auth/me")
async def auth_me(user=Depends(current_user)):
    return user


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
    gstRate: float = 18


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


def calc_gst(items: List[dict], intra_state: bool = True):
    subtotal = 0.0
    cgst = sgst = igst = 0.0
    for it in items:
        line = it["qty"] * it["rate"]
        line -= line * (it.get("discount", 0) / 100)
        subtotal += line
        tax = line * (it.get("gstRate", 0) / 100)
        if intra_state:
            cgst += tax / 2
            sgst += tax / 2
        else:
            igst += tax
    total = subtotal + cgst + sgst + igst
    return {"subtotal": round(subtotal, 2), "cgst": round(cgst, 2), "sgst": round(sgst, 2), "igst": round(igst, 2), "total": round(total, 2)}


@api.get("/quotations")
async def list_quotes(page: int = 1, limit: int = 50, q: Optional[str] = None, user=Depends(current_user)):
    return await paginate(db.quotations, {}, page, limit, search_fields=["quoteNo", "customerName"], q=q)


@api.post("/quotations")
async def create_quote(data: QuoteIn, user=Depends(current_user)):
    items = [i.model_dump() for i in data.items]
    intra = (data.customerState or "").strip().lower() in ("", "delhi", "dl")
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
    intra = (data.customerState or "").strip().lower() in ("", "delhi", "dl")
    totals = calc_gst(items, intra_state=intra)
    await db.quotations.update_one({"id": qid}, {"$set": {**data.model_dump(), "items": items, **totals, "updatedAt": now_iso()}})
    d = await db.quotations.find_one({"id": qid}, {"_id": 0})
    return d


@api.delete("/quotations/{qid}")
async def delete_quote(qid: str, user=Depends(current_user)):
    await db.quotations.delete_one({"id": qid})
    return {"ok": True}


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
        "store": q.get("vertical") or "GLC Store",
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
    store: str = "GLC Store"
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
    intra = (data.customerState or "").strip().lower() in ("", "delhi", "dl")
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


@api.post("/orders/{oid}/invoice")
async def generate_invoice(oid: str, user=Depends(current_user)):
    o = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
    if not o:
        raise HTTPException(404, "Not found")
    exists = await db.invoices.find_one({"orderId": oid}, {"_id": 0})
    if exists:
        return exists
    count = await db.invoices.count_documents({})
    inv = {
        "id": uid(),
        "invoiceNo": f"INV-{datetime.now().year}-{count+1001}",
        "orderId": oid,
        "customerId": o.get("customerId"),
        "customerName": o["customerName"],
        "customerGst": o.get("customerGst"),
        "customerState": o.get("customerState"),
        "items": o["items"],
        "subtotal": o["subtotal"],
        "cgst": o["cgst"],
        "sgst": o["sgst"],
        "igst": o["igst"],
        "total": o["total"],
        "paidAmount": 0,
        "dueAmount": o["total"],
        "status": "UNPAID",
        "vertical": o.get("vertical"),
        "invoiceDate": now_iso(),
        "dueDate": (datetime.now(timezone.utc) + timedelta(days=15)).isoformat(),
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    await db.invoices.insert_one(inv)
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
async def add_payment(data: PaymentIn, user=Depends(current_user)):
    inv = await db.invoices.find_one({"id": data.invoiceId}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invoice not found")
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
    new_due = max(inv["total"] - new_paid, 0)
    status_ = "PAID" if new_due <= 0.01 else ("PARTIAL" if new_paid > 0 else "UNPAID")
    await db.invoices.update_one({"id": data.invoiceId}, {"$set": {"paidAmount": new_paid, "dueAmount": new_due, "status": status_, "updatedAt": now_iso()}})
    await log_activity(user["id"], "payments", "create", pay["id"], {"invoiceId": data.invoiceId})
    return clean(pay)


@api.get("/payments")
async def list_payments(page: int = 1, limit: int = 50, user=Depends(current_user)):
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
    totals = calc_gst(items, intra_state=True)
    count = await db.purchase_orders.count_documents({})
    doc = {**data.model_dump(), "id": uid(), "poNo": f"PO-{datetime.now().year}-{count+1001}", "items": items, **totals, "createdAt": now_iso(), "updatedAt": now_iso()}
    await db.purchase_orders.insert_one(doc)
    return clean(doc)


@api.put("/purchase-orders/{pid}")
async def update_po(pid: str, body: Dict[str, Any], user=Depends(current_user)):
    body["updatedAt"] = now_iso()
    # If marking RECEIVED, increment stock
    if body.get("status") == "RECEIVED":
        po = await db.purchase_orders.find_one({"id": pid}, {"_id": 0})
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
async def list_accounts(user=Depends(current_user)):
    items = await db.accounts.find({}, {"_id": 0}).sort("code", 1).to_list(500)
    return {"items": items}


@api.post("/accounts")
async def create_account(data: AccountIn, user=Depends(current_user)):
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
async def create_journal(data: JournalIn, user=Depends(current_user)):
    total_dr = sum(e.get("debit", 0) for e in data.entries)
    total_cr = sum(e.get("credit", 0) for e in data.entries)
    if round(total_dr, 2) != round(total_cr, 2):
        raise HTTPException(400, "Debit and Credit totals must match")
    doc = {**data.model_dump(), "id": uid(), "totalDebit": total_dr, "totalCredit": total_cr, "createdAt": now_iso()}
    await db.journal.insert_one(doc)
    return clean(doc)


@api.get("/reports/gst")
async def gst_report(month: Optional[str] = None, user=Depends(current_user)):
    filt = {}
    if month:
        filt["invoiceDate"] = {"$regex": f"^{month}"}
    invoices = await db.invoices.find(filt, {"_id": 0}).to_list(1000)
    total_taxable = sum(i.get("subtotal", 0) for i in invoices)
    total_cgst = sum(i.get("cgst", 0) for i in invoices)
    total_sgst = sum(i.get("sgst", 0) for i in invoices)
    total_igst = sum(i.get("igst", 0) for i in invoices)
    total = sum(i.get("total", 0) for i in invoices)
    return {
        "month": month,
        "invoices": invoices,
        "summary": {
            "taxableValue": round(total_taxable, 2),
            "cgst": round(total_cgst, 2),
            "sgst": round(total_sgst, 2),
            "igst": round(total_igst, 2),
            "total": round(total, 2),
            "count": len(invoices),
        }
    }


@api.get("/reports/pl")
async def pl_report(user=Depends(current_user)):
    revenue = 0.0
    async for i in db.invoices.find({}, {"_id": 0}):
        revenue += i.get("subtotal", 0)
    expenses = 0.0
    async for e in db.expenses.find({"status": "APPROVED"}, {"_id": 0}):
        expenses += e.get("amount", 0)
    return {"revenue": round(revenue, 2), "expenses": round(expenses, 2), "netProfit": round(revenue - expenses, 2)}


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


@api.put("/tickets/{tid}")
async def update_ticket(tid: str, body: Dict[str, Any], user=Depends(current_user)):
    body["updatedAt"] = now_iso()
    await db.tickets.update_one({"id": tid}, {"$set": body})
    d = await db.tickets.find_one({"id": tid}, {"_id": 0})
    return d


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
    items = await db.notifications.find({"userId": {"$in": [user["id"], "*"]}}, {"_id": 0}).sort("createdAt", -1).limit(50).to_list(50)
    unread = sum(1 for n in items if not n.get("isRead"))
    return {"items": items, "unread": unread}


@api.put("/notifications/read-all")
async def mark_all_read(user=Depends(current_user)):
    await db.notifications.update_many({"userId": {"$in": [user["id"], "*"]}}, {"$set": {"isRead": True}})
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
    pending_deliveries = await db.deliveries.count_documents({"status": {"$in": ["PENDING", "ASSIGNED", "IN_TRANSIT"]}})
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
# Seed on startup
# =========================================================
@app.on_event("startup")
async def startup_seed():
    from seed import seed_all
    try:
        await seed_all(db)
        log.info("Seed complete")
    except Exception as e:
        log.exception(f"Seed failed: {e}")


@app.on_event("shutdown")
async def shutdown_db():
    client.close()


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
