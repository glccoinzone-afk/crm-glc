"""Data-integrity tests (in-memory MongoDB): document numbers, stock, double conversion, double invoice, payments, payouts, month ranges.
Run: python -m pytest -p no:cacheprovider -o addopts="" tests/test_integrity_api.py"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mongomock_motor")
from fastapi.testclient import TestClient  # noqa: E402
import motor.motor_asyncio  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "glc_int_test")
os.environ.pop("EMERGENT_LLM_KEY", None)
motor.motor_asyncio.AsyncIOMotorClient = AsyncMongoMockClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402


@pytest.fixture(scope="module")
def api():
    saved_db = server.db
    server.db = AsyncMongoMockClient()["glc_int_isolated"]          # own empty database: other test files keep their own state
    try:
        yield from _client()
    finally:
        server.db = saved_db


def _client():
    with TestClient(server.app) as c:
        run = c.portal.call
        run(server.db.users.insert_one, {"id": "int-admin", "name": "Admin", "email": "a@x.in", "role": "Admin"})
        c.h = {"Authorization": "Bearer " + server.make_token("int-admin", "a@x.in", "Admin")}
        c.run = run
        yield c


def _item(pid="p1", qty=2, rate=100):
    return {"productId": pid, "name": "Atta", "qty": qty, "rate": rate, "gstRate": 5}


def test_document_numbers_never_repeat_even_after_a_delete(api):
    nums = []
    for _ in range(3):
        r = api.post("/api/quotations", json={"customerName": "A", "items": [_item()]}, headers=api.h)
        assert r.status_code == 200, r.text
        nums.append(r.json()["quoteNo"])
    assert len(set(nums)) == 3
    first = api.run(server.db.quotations.find_one, {"quoteNo": nums[0]})
    api.run(server.db.quotations.delete_one, {"id": first["id"]})
    again = api.post("/api/quotations", json={"customerName": "A", "items": [_item()]}, headers=api.h).json()["quoteNo"]
    assert again not in nums


def test_numbers_are_unique_under_parallel_requests(api):
    async def many():
        return await asyncio.gather(*[server.next_doc_number("PAR", server.db.tickets, "TKT") for _ in range(25)])
    got = api.run(many)
    assert len(set(got)) == 25


def test_bad_quantities_and_prices_are_refused(api):
    for bad in ({"qty": 0}, {"qty": -3}, {"rate": -1}, {"gstRate": 150}, {"discount": 120}):
        it = {**_item(), **bad}
        assert api.post("/api/quotations", json={"customerName": "A", "items": [it]}, headers=api.h).status_code == 422


def test_stock_never_goes_below_zero_and_comes_back_on_cancel(api):
    api.run(server.db.stock_items.insert_one, {"id": "s1", "productId": "p1", "warehouseId": "w", "qty": 5})
    ok = api.post("/api/orders", json={"customerName": "A", "status": "CONFIRMED", "items": [_item(qty=3)]}, headers=api.h)
    assert ok.status_code == 200
    assert api.run(server.db.stock_items.find_one, {"id": "s1"})["qty"] == 2
    too_much = api.post("/api/orders", json={"customerName": "B", "status": "CONFIRMED", "items": [_item(qty=3)]}, headers=api.h)
    assert too_much.status_code == 409 and "Not enough stock" in too_much.json()["detail"]
    assert api.run(server.db.stock_items.find_one, {"id": "s1"})["qty"] == 2          # nothing was taken
    oid = ok.json()["id"]
    assert api.put(f"/api/orders/{oid}", json={"status": "CANCELLED"}, headers=api.h).status_code == 200
    assert api.run(server.db.stock_items.find_one, {"id": "s1"})["qty"] == 5          # given back
    assert api.put(f"/api/orders/{oid}", json={"status": "CANCELLED"}, headers=api.h).status_code == 200
    assert api.run(server.db.stock_items.find_one, {"id": "s1"})["qty"] == 5          # and only once


def test_a_quotation_converts_once(api):
    api.run(server.db.stock_items.update_one, {"id": "s1"}, {"$set": {"qty": 10}})
    q = api.post("/api/quotations", json={"customerName": "C", "items": [_item(qty=4)]}, headers=api.h).json()
    r1 = api.post(f"/api/quotations/{q['id']}/convert", headers=api.h)
    r2 = api.post(f"/api/quotations/{q['id']}/convert", headers=api.h)
    assert r1.status_code == 200 and r2.status_code == 409
    assert api.run(server.db.stock_items.find_one, {"id": "s1"})["qty"] == 6
    assert api.run(server.db.sales_orders.count_documents, {"quotationId": q["id"]}) == 1


def test_a_lead_converts_once_and_links_an_existing_customer(api):
    api.run(server.db.customers.insert_one, {"id": "c-old", "name": "Old", "phone": "9876543210"})
    api.run(server.db.leads.insert_one, {"id": "l1", "name": "Ram", "phone": "+91 98765 43210", "status": "NEW"})
    r1 = api.post("/api/leads/l1/convert", headers=api.h)
    r2 = api.post("/api/leads/l1/convert", headers=api.h)
    assert r1.status_code == 200 and r1.json()["id"] == "c-old"
    assert r2.status_code == 200 and r2.json()["id"] == "c-old"
    assert api.run(server.db.customers.count_documents, {}) == 1


def test_one_invoice_per_order_even_with_two_clicks(api):
    api.run(server.db.sales_orders.insert_one, {"id": "so-i", "orderNo": "SO-X", "customerName": "D", "items": [_item(pid=None, qty=1, rate=100)], "status": "CONFIRMED"})
    a = api.post("/api/orders/so-i/invoice", headers=api.h)
    b = api.post("/api/orders/so-i/invoice", headers=api.h)
    assert a.status_code == 200 and b.status_code == 200 and a.json()["invoiceNo"] == b.json()["invoiceNo"]
    assert api.run(server.db.invoices.count_documents, {"orderId": "so-i"}) == 1


def test_two_payments_at_the_same_moment_cannot_both_win(api):
    api.run(server.db.sales_orders.insert_one, {"id": "so-p", "orderNo": "SO-P", "customerName": "E", "items": [_item(pid=None, qty=1, rate=100)], "status": "CONFIRMED"})
    inv = api.post("/api/orders/so-p/invoice", headers=api.h).json()
    full = inv["total"]

    async def pay_twice():
        user = {"id": "int-admin", "name": "Admin", "role": "Admin"}
        data = server.PaymentIn(invoiceId=inv["id"], amount=full, method="CASH")
        return await asyncio.gather(server.add_payment(data, user), server.add_payment(data, user), return_exceptions=True)
    results = api.run(pay_twice)
    won = [r for r in results if isinstance(r, dict)]
    assert len(won) == 1, results                                   # the invoice is paid once, never twice
    assert api.run(server.db.payments.count_documents, {"invoiceId": inv["id"]}) == 1
    final = api.run(server.db.invoices.find_one, {"id": inv["id"]})
    assert final["status"] == "PAID" and final["dueAmount"] == 0


def test_a_payout_can_only_be_approved_once(api, monkeypatch):
    calls = []

    async def fake_bridge(path, data):
        calls.append(path)
        return {"error": False}
    monkeypatch.setattr(server, "call_glczone_bridge", fake_bridge)
    api.run(server.db.withdrawals.insert_one, {"id": "w1", "glczone_withdrawal_id": 7, "status": "pending"})
    assert api.post("/api/withdrawals/w1/approve", headers=api.h).status_code == 200
    assert api.post("/api/withdrawals/w1/approve", headers=api.h).status_code == 409
    assert api.post("/api/withdrawals/w1/reject", json={}, headers=api.h).status_code == 409      # an approved payout cannot be rejected
    assert calls == ["withdrawals/7/approve"]                                                       # the website was called once
    assert api.post("/api/withdrawals/w1/mark-paid", json={}, headers=api.h).status_code == 200
    assert api.post("/api/withdrawals/w1/mark-paid", json={}, headers=api.h).status_code == 409


def test_a_failed_payout_call_puts_the_request_back(api, monkeypatch):
    async def failing(path, data):
        return {"error": True, "message": "website down"}
    monkeypatch.setattr(server, "call_glczone_bridge", failing)
    api.run(server.db.withdrawals.insert_one, {"id": "w2", "glczone_withdrawal_id": 8, "status": "pending"})
    assert api.post("/api/withdrawals/w2/approve", headers=api.h).status_code == 400
    row = api.run(server.db.withdrawals.find_one, {"id": "w2"})
    assert row["status"] == "pending" and row["lastBridgeError"] == "website down"


def test_month_ranges_follow_indian_time():
    r = server.ist_month_range("2026-09")
    assert r["$gte"] == "2026-08-31T18:30:00+00:00" and r["$lt"] == "2026-09-30T18:30:00+00:00"
    assert server.ist_day_range("2026-10-15")["$gte"] == "2026-10-14T18:30:00+00:00"
    dec = server.ist_month_range("2026-12")
    assert dec["$lt"] == "2026-12-31T18:30:00+00:00"


def test_a_sale_at_1am_on_the_first_belongs_to_the_new_indian_month(api):
    api.run(server.db.invoices.insert_one, {"id": "inv-m", "invoiceNo": "INV-M", "invoiceDate": "2026-08-31T20:00:00+00:00", "status": "PAID", "total": 100,
                                            "cgst": 0, "sgst": 0, "igst": 0, "subtotal": 100, "lines": [], "placeOfSupply": "10-Bihar"})
    found = api.run(server.db.invoices.count_documents, {"invoiceDate": server.ist_month_range("2026-09")})
    missed = api.run(server.db.invoices.count_documents, {"invoiceDate": server.ist_month_range("2026-08")})
    assert found == 1 and missed == 0        # 20:00 UTC on 31 Aug is 01:30 IST on 1 Sep


def test_notification_read_state_is_per_person(api):
    api.run(server.db.users.insert_one, {"id": "int-u2", "name": "Two", "email": "b@x.in", "role": "Admin"})
    api.run(server.db.leads.insert_one, {"id": "nl1", "name": "New", "status": "NEW", "createdAt": server.now_iso()})
    h2 = {"Authorization": "Bearer " + server.make_token("int-u2", "b@x.in", "Admin")}
    first = api.get("/api/notifications", headers=api.h).json()
    assert any(i["id"] == "new-leads" and not i["isRead"] for i in first["items"])
    assert api.put("/api/notifications/read-all", headers=api.h).status_code == 200
    mine = api.get("/api/notifications", headers=api.h).json()
    other = api.get("/api/notifications", headers=h2).json()
    assert all(i["isRead"] for i in mine["items"] if i["id"] == "new-leads")
    assert any(i["id"] == "new-leads" and not i["isRead"] for i in other["items"])        # the other person still sees it
    api.run(server.db.leads.insert_one, {"id": "nl2", "name": "New2", "status": "NEW", "createdAt": server.now_iso()})
    again = api.get("/api/notifications", headers=api.h).json()
    assert any(i["id"] == "new-leads" and not i["isRead"] for i in again["items"])        # a new lead makes it unread again
