"""API-level tests for the finance module against an in-memory MongoDB (mongomock-motor). No network, no real database.
Run: python -m pytest -p no:cacheprovider -o addopts="" tests/test_finance_api.py"""
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mongomock_motor")
from fastapi.testclient import TestClient  # noqa: E402
import motor.motor_asyncio  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "glc_test")
os.environ.pop("EMERGENT_LLM_KEY", None)
motor.motor_asyncio.AsyncIOMotorClient = AsyncMongoMockClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402


@pytest.fixture(scope="module")
def api():
    with TestClient(server.app) as c:
        loop_run = c.portal.call
        for uid_, role in (("u-admin", "Admin"), ("u-tele", "Telecaller")):
            loop_run(server.db.users.insert_one, {"id": uid_, "name": role, "email": f"{uid_}@x.in", "role": role})
        c.admin = {"Authorization": "Bearer " + server.make_token("u-admin", "a@x.in", "Admin")}
        c.tele = {"Authorization": "Bearer " + server.make_token("u-tele", "t@x.in", "Telecaller")}
        c.run = loop_run
        yield c


def _order(api, oid, **kw):
    doc = {"id": f"so-{oid}", "glczone_order_id": str(oid), "orderNo": f"GLZ-{oid}", "customerName": "Reshmi", "status": "delivered",
           "glczone_status": "delivered", "total": 4, "finalTotal": 24, "deliveryCharge": 20, "paymentMethod": "COD", "vertical": "GLC Fresh",
           "glczoneItems": [{"name": "Raw Banana", "quantity": 1, "price": 4, "tax_percent": 0, "tax_amount": 0, "sub_total": 4, "status": "delivered"}]}
    doc.update(kw)
    api.run(server.db.sales_orders.insert_one, doc)
    return doc["id"]


def test_cod_delivered_order_is_invoiced_with_delivery_gst_and_paid(api):
    oid = _order(api, 37)
    r = api.post(f"/api/orders/{oid}/invoice", headers=api.admin)
    assert r.status_code == 200, r.text
    inv = r.json()
    assert inv["invoiceNo"] == server.gf.doc_number("INV", 1)
    assert inv["total"] == 24 and inv["status"] == "PAID" and inv["dueAmount"] == 0
    assert inv["supplyType"] == "INTRA" and inv["placeOfSupply"].startswith("10-")
    assert round(inv["cgst"] + inv["sgst"], 2) == 3.05 and inv["igst"] == 0       # 18% GST inside the Rs 20 delivery charge
    assert abs(inv["cgst"] - inv["sgst"]) < 0.011
    again = api.post(f"/api/orders/{oid}/invoice", headers=api.admin).json()
    assert again["id"] == inv["id"]                                             # idempotent


def test_books_balance_after_invoice_and_payment(api):
    tb = api.get("/api/finance/trial-balance", headers=api.admin).json()
    assert tb["balanced"]
    by = {r["code"]: r for r in tb["rows"]}
    assert by["4100"]["balance"] == 4 and by["4300"]["balance"] == 16.95
    assert by["1300"]["balance"] == 0 and by["1100"]["balance"] == 24          # COD cash received, receivable cleared
    led = api.get("/api/finance/ledger/1100", headers=api.admin).json()
    assert led["closing"] == 24


def test_unpaid_invoice_payment_rules(api):
    oid = _order(api, 40, paymentMethod="RAZORPAY", paymentStatus="PENDING", glczone_status="received", status="received")
    inv = api.post(f"/api/orders/{oid}/invoice", headers=api.admin).json()
    assert inv["status"] == "UNPAID" and inv["dueAmount"] == 24
    assert api.post("/api/payments", headers=api.admin, json={"invoiceId": inv["id"], "amount": 30, "method": "UPI"}).status_code == 400
    assert api.post("/api/payments", headers=api.admin, json={"invoiceId": inv["id"], "amount": -5, "method": "UPI"}).status_code == 400
    assert api.post("/api/payments", headers=api.admin, json={"invoiceId": inv["id"], "amount": 10, "method": "UPI"}).status_code == 200
    got = api.get(f"/api/invoices/{inv['id']}", headers=api.admin).json()["invoice"]
    assert got["status"] == "PARTIAL" and got["dueAmount"] == 14
    assert api.post("/api/payments", headers=api.admin, json={"invoiceId": inv["id"], "amount": 14, "method": "UPI"}).status_code == 200
    assert api.get(f"/api/invoices/{inv['id']}", headers=api.admin).json()["invoice"]["status"] == "PAID"
    assert api.get("/api/finance/trial-balance", headers=api.admin).json()["balanced"]


def test_invoice_numbers_are_unique_and_sequential(api):
    nums = []
    for n in range(50, 55):
        oid = _order(api, n, paymentMethod="RAZORPAY", paymentStatus="PENDING", glczone_status="received")
        nums.append(api.post(f"/api/orders/{oid}/invoice", headers=api.admin).json()["invoiceNo"])
    assert len(set(nums)) == 5 and nums == sorted(nums)


def test_credit_note_partial_cap_and_journal(api):
    it = [{"name": "Soap", "quantity": 2, "price": 100, "tax_percent": 18, "tax_amount": 36, "sub_total": 236, "status": "delivered", "hsn": "3401"}]
    oid = _order(api, 60, paymentMethod="RAZORPAY", paymentStatus="PAID", deliveryCharge=0, total=200, finalTotal=236, glczoneItems=it)
    inv = api.post(f"/api/orders/{oid}/invoice", headers=api.admin).json()
    assert inv["total"] == 236 and inv["subtotal"] == 200 and inv["status"] == "PAID"
    r = api.post(f"/api/invoices/{inv['id']}/credit-note", headers=api.admin, json={"reason": "Damaged", "items": [{"index": 0, "qty": 1}]})
    assert r.status_code == 200, r.text
    cn = r.json()
    assert cn["total"] == 118 and cn["cgst"] == 9 and cn["sgst"] == 9 and cn["noteNo"].startswith("CN/")
    assert api.post(f"/api/invoices/{inv['id']}/credit-note", headers=api.admin, json={"items": [{"index": 0, "qty": 2}]}).status_code == 400
    after = api.get(f"/api/invoices/{inv['id']}", headers=api.admin).json()["invoice"]
    assert after["creditedAmount"] == 118 and after["refundDue"] == 118
    assert api.get("/api/finance/trial-balance", headers=api.admin).json()["balanced"]


def test_gst_reports(api):
    m = api.get("/api/reports/gstr1", headers=api.admin)
    assert m.status_code == 200
    g1 = m.json()
    assert g1["documents"]["invoices"] >= 8 and g1["documents"]["creditNotes"] == 1
    assert any(h["hsn"] == "3401" and h["qty"] == 1 for h in g1["hsn"])          # 2 sold - 1 returned
    g3 = api.get("/api/reports/gstr3b", headers=api.admin).json()
    assert g3["outward"]["cgst"] > 0 and g3["netPayableCash"]["total"] > 0
    assert api.get("/api/reports/gst", headers=api.admin).json()["summary"]["creditNoteCount"] == 1
    assert api.get("/api/reports/gstr1?month=2026-13x", headers=api.admin).status_code == 400
    pl = api.get("/api/reports/pl", headers=api.admin).json()
    assert pl["salesReturns"] == 100 and abs(pl["revenue"] - (pl["grossSales"] - 100)) < 0.01


def test_cancel_only_unpaid(api):
    oid = _order(api, 70, paymentMethod="RAZORPAY", paymentStatus="PENDING", glczone_status="received")
    inv = api.post(f"/api/orders/{oid}/invoice", headers=api.admin).json()
    assert api.post(f"/api/invoices/{inv['id']}/cancel", headers=api.admin).status_code == 200
    assert api.post("/api/payments", headers=api.admin, json={"invoiceId": inv["id"], "amount": 1, "method": "CASH"}).status_code == 400
    assert api.post(f"/api/invoices/{inv['id']}/cancel", headers=api.admin).status_code == 400
    assert api.get("/api/finance/trial-balance", headers=api.admin).json()["balanced"]


def test_bihar_customer_is_intra_and_delhi_is_inter(api):
    it = [{"name": "Soap", "quantity": 1, "price": 100, "tax_percent": 18, "tax_amount": 18, "sub_total": 118}]
    for oid, state, expect in ((80, "Bihar", "INTRA"), (81, "Delhi", "INTER")):
        _order(api, oid, paymentMethod="RAZORPAY", paymentStatus="PENDING", deliveryCharge=0, customerState=state, glczoneItems=it)
        inv = api.post(f"/api/orders/so-{oid}/invoice", headers=api.admin).json()
        assert inv["supplyType"] == expect and (inv["igst"] > 0) == (expect == "INTER")


def test_legacy_invoice_backfill(api):
    legacy = {"id": "legacy-1", "invoiceNo": "INV-2026-1001", "customerName": "Old", "items": [{"name": "x", "qty": 1, "rate": 8, "gst": 0}],
              "subtotal": 8, "cgst": 0, "sgst": 0, "igst": 0, "total": 8, "paidAmount": 0, "dueAmount": 8, "status": "UNPAID",
              "invoiceDate": "2026-08-01T00:00:00", "dueDate": "2026-08-16T00:00:00"}
    api.run(server.db.invoices.insert_one, legacy)
    assert "INV-2026-1001" in api.get("/api/finance/books-check", headers=api.admin).json()["missing"]["invoices"]
    assert api.post("/api/finance/backfill-books", headers=api.admin).json()["posted"]["invoices"] == 1
    assert api.get("/api/finance/books-check", headers=api.admin).json()["missing"]["invoices"] == []
    assert api.get("/api/finance/trial-balance", headers=api.admin).json()["balanced"]
    age = api.get("/api/finance/receivables-ageing", headers=api.admin).json()
    assert age["totals"]["total"] > 0


def test_only_finance_roles_can_use_the_books(api):
    for path in ("/api/reports/pl", "/api/reports/gstr1", "/api/finance/trial-balance", "/api/accounts", "/api/payments"):
        assert api.get(path, headers=api.tele).status_code == 403, path
        assert api.get(path).status_code in (401, 403), path


def test_invoice_pdf_renders(api):
    inv = api.get("/api/invoices?limit=1", headers=api.admin).json()["items"][0]
    r = api.get(f"/api/invoices/{inv['id']}/pdf", headers=api.admin)
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
