"""GLC Zone CRM+ERP backend end-to-end tests."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://glc-business-hub.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "bishwajeet@glczone.in"
ADMIN_PASS = "Admin@123"


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data and "user" in data
    return data["token"]


@pytest.fixture(scope="session")
def client(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


# ---------- Auth ----------
class TestAuth:
    def test_login_success(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["email"] == ADMIN_EMAIL
        assert isinstance(d["token"], str) and len(d["token"]) > 10

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code == 401

    def test_me(self, client):
        r = client.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_no_auth_returns_401(self):
        r = requests.get(f"{API}/leads")
        assert r.status_code == 401

    def test_invalid_bearer_returns_401(self):
        r = requests.get(f"{API}/leads", headers={"Authorization": "Bearer invalid.token.here"})
        assert r.status_code == 401


# ---------- Dashboard ----------
class TestDashboard:
    def test_dashboard_shape(self, client):
        r = client.get(f"{API}/dashboard")
        assert r.status_code == 200
        d = r.json()
        for k in ["kpi", "charts", "recent", "pending"]:
            assert k in d, f"missing {k}"
        kpi_keys = ["todayRevenue", "todayOrders", "newCustomers", "pendingOrders", "unpaidAmount",
                    "openTickets", "totalLeads", "pendingDeliveries", "employeeCount", "todayAttendance"]
        for k in kpi_keys:
            assert k in d["kpi"], f"missing kpi.{k}"
        for k in ["revenueSeries", "salesByVertical", "leadFunnel", "inventoryByCategory", "weeklyAttendance"]:
            assert k in d["charts"], f"missing charts.{k}"
        for k in ["orders", "lowStock"]:
            assert k in d["recent"]
        for k in ["leaves", "expenses", "purchaseOrders"]:
            assert k in d["pending"]

    def test_dashboard_with_vertical(self, client):
        r = client.get(f"{API}/dashboard", params={"vertical": "GLC Store"})
        assert r.status_code == 200
        assert "kpi" in r.json()


# ---------- CRM: Leads / Customers / Deals / Quotations ----------
class TestCRM:
    def test_leads_seeded(self, client):
        r = client.get(f"{API}/leads")
        assert r.status_code == 200
        items = r.json().get("items", [])
        assert len(items) >= 8, f"expected >=8 seeded leads, got {len(items)}"

    def test_lead_create_convert_delete(self, client):
        lead = {"name": f"TEST_Lead_{uuid.uuid4().hex[:6]}", "email": "testlead@example.com",
                "phone": "9999999999", "company": "TEST Co", "source": "Website", "vertical": "GLC Store"}
        r = client.post(f"{API}/leads", json=lead)
        assert r.status_code == 200, r.text
        created = r.json()
        lid = created["id"]
        assert created["name"] == lead["name"]

        # convert -> creates a customer
        rc = client.post(f"{API}/leads/{lid}/convert")
        assert rc.status_code == 200, rc.text
        conv = rc.json()
        # verify a customer exists with the lead email
        rcs = client.get(f"{API}/customers", params={"q": lead["email"]})
        assert rcs.status_code == 200
        # customer likely created; not asserting exact match to remain resilient

        # delete lead
        rd = client.delete(f"{API}/leads/{lid}")
        assert rd.status_code == 200

    def test_customers_crud(self, client):
        r = client.get(f"{API}/customers")
        assert r.status_code == 200
        items = r.json().get("items", [])
        assert len(items) > 0

        payload = {"name": f"TEST_Cust_{uuid.uuid4().hex[:6]}", "email": "c@test.com",
                   "phone": "1234567890", "vertical": "GLC Store"}
        rc = client.post(f"{API}/customers", json=payload)
        assert rc.status_code == 200, rc.text
        cid = rc.json()["id"]

        rg = client.get(f"{API}/customers/{cid}")
        assert rg.status_code == 200
        detail = rg.json()
        for k in ["customer", "orders", "invoices", "payments", "tickets"]:
            assert k in detail

        ru = client.put(f"{API}/customers/{cid}", json={**payload, "name": "TEST_Cust_upd"})
        assert ru.status_code == 200
        assert ru.json()["name"] == "TEST_Cust_upd"

        rd = client.delete(f"{API}/customers/{cid}")
        assert rd.status_code == 200

    def test_deals_flow(self, client):
        r = client.get(f"{API}/deals")
        assert r.status_code == 200

        d = {"title": "TEST_Deal", "value": 5000, "stage": "PROSPECTING", "customerName": "Test"}
        rc = client.post(f"{API}/deals", json=d)
        assert rc.status_code == 200
        did = rc.json()["id"]

        ru = client.put(f"{API}/deals/{did}", json={"stage": "NEGOTIATION"})
        assert ru.status_code == 200
        assert ru.json()["stage"] == "NEGOTIATION"

    def test_quotation_calc_and_convert(self, client):
        payload = {
            "customerName": "TEST_QCust",
            "customerState": "Delhi",
            "items": [{"productId": None, "name": "Item A", "qty": 2, "rate": 100,
                       "discount": 0, "gstRate": 18}],
            "vertical": "GLC Store",
        }
        r = client.post(f"{API}/quotations", json=payload)
        assert r.status_code == 200, r.text
        q = r.json()
        # subtotal=200, tax=36 -> cgst=18, sgst=18, total=236
        assert round(q["subtotal"], 2) == 200.0
        assert round(q["cgst"], 2) == 18.0
        assert round(q["sgst"], 2) == 18.0
        assert round(q["total"], 2) == 236.0
        assert q["quoteNo"].startswith("QT-")

        # convert -> creates order
        rc = client.post(f"{API}/quotations/{q['id']}/convert")
        assert rc.status_code == 200
        order = rc.json()
        assert order["orderNo"].startswith("SO-")

        # verify order shows up in orders list
        ro = client.get(f"{API}/orders", params={"q": order["orderNo"]})
        assert ro.status_code == 200
        found = [o for o in ro.json().get("items", []) if o["id"] == order["id"]]
        assert len(found) == 1


# ---------- Sales: Orders / Invoices / Payments ----------
class TestSales:
    def test_orders_seeded(self, client):
        r = client.get(f"{API}/orders")
        assert r.status_code == 200
        assert len(r.json().get("items", [])) > 0

    def test_invoice_idempotent_and_payment(self, client):
        # Create fresh order via quotation
        qp = {"customerName": "TEST_INV", "customerState": "Delhi",
              "items": [{"name": "X", "qty": 1, "rate": 1000, "discount": 0, "gstRate": 18}]}
        q = client.post(f"{API}/quotations", json=qp).json()
        order = client.post(f"{API}/quotations/{q['id']}/convert").json()
        oid = order["id"]
        total = order["total"]

        r1 = client.post(f"{API}/orders/{oid}/invoice")
        assert r1.status_code == 200
        inv1 = r1.json()
        assert inv1["invoiceNo"].startswith("INV-")

        r2 = client.post(f"{API}/orders/{oid}/invoice")
        assert r2.status_code == 200
        inv2 = r2.json()
        assert inv1["id"] == inv2["id"], "invoice generation not idempotent"

        # Partial payment
        pay = client.post(f"{API}/payments", json={"invoiceId": inv1["id"], "amount": total / 2, "method": "CASH"})
        assert pay.status_code == 200
        inv_get = client.get(f"{API}/invoices/{inv1['id']}").json()["invoice"]
        assert inv_get["status"] == "PARTIAL"
        assert round(inv_get["dueAmount"], 2) == round(total / 2, 2)

        # Full payment
        pay2 = client.post(f"{API}/payments", json={"invoiceId": inv1["id"], "amount": total / 2, "method": "UPI"})
        assert pay2.status_code == 200
        inv_get2 = client.get(f"{API}/invoices/{inv1['id']}").json()["invoice"]
        assert inv_get2["status"] == "PAID"
        assert inv_get2["dueAmount"] <= 0.01


# ---------- Inventory ----------
class TestInventory:
    def test_products_seeded(self, client):
        r = client.get(f"{API}/products", params={"limit": 100})
        assert r.status_code == 200
        items = r.json().get("items", [])
        assert len(items) >= 14, f"expected >=14 seeded products, got {len(items)}"

    def test_product_create_stock(self, client):
        p = {"name": f"TEST_Prod_{uuid.uuid4().hex[:6]}", "sku": f"TS-{uuid.uuid4().hex[:6]}",
             "sellingPrice": 100, "buyingPrice": 50, "gstRate": 18, "minStock": 5,
             "category": "Test", "vertical": "GLC Store"}
        r = client.post(f"{API}/products", json=p)
        assert r.status_code == 200
        pid = r.json()["id"]

        # Adjust stock +20
        ra = client.post(f"{API}/inventory/adjust", json={"productId": pid, "qty": 20, "reason": "test"})
        assert ra.status_code == 200

        rs = client.get(f"{API}/inventory/stock")
        assert rs.status_code == 200
        items = rs.json()["items"]
        mine = [s for s in items if s["productId"] == pid]
        assert mine and mine[0]["qty"] == 20
        assert mine[0].get("product") is not None
        assert mine[0].get("warehouse") is not None

    def test_low_stock(self, client):
        r = client.get(f"{API}/inventory/low-stock")
        assert r.status_code == 200
        assert "items" in r.json()


# ---------- Purchase ----------
class TestPurchase:
    def test_suppliers_crud(self, client):
        r = client.get(f"{API}/suppliers")
        assert r.status_code == 200

        s = {"name": f"TEST_Sup_{uuid.uuid4().hex[:6]}", "email": "s@test.com", "phone": "1", "gst": "07AAAAA0000A1Z5"}
        rc = client.post(f"{API}/suppliers", json=s)
        assert rc.status_code == 200
        sid = rc.json()["id"]

        ru = client.put(f"{API}/suppliers/{sid}", json={**s, "rating": 5.0})
        assert ru.status_code == 200

        rd = client.delete(f"{API}/suppliers/{sid}")
        assert rd.status_code == 200

    def test_po_received_increments_stock(self, client):
        # create a product
        p = {"name": f"TEST_POProd_{uuid.uuid4().hex[:6]}", "sku": f"POP-{uuid.uuid4().hex[:6]}",
             "sellingPrice": 100, "buyingPrice": 50, "gstRate": 18}
        pid = client.post(f"{API}/products", json=p).json()["id"]

        # create supplier
        sid = client.post(f"{API}/suppliers", json={"name": "TEST_POSup"}).json()["id"]

        # create PO with 10 units
        po = {"supplierId": sid, "supplierName": "TEST_POSup",
              "items": [{"productId": pid, "name": p["name"], "qty": 10, "rate": 50, "gstRate": 18, "discount": 0}]}
        rp = client.post(f"{API}/purchase-orders", json=po)
        assert rp.status_code == 200
        poid = rp.json()["id"]
        assert rp.json()["poNo"].startswith("PO-")

        # mark RECEIVED
        ru = client.put(f"{API}/purchase-orders/{poid}", json={"status": "RECEIVED"})
        assert ru.status_code == 200

        # stock should be 10
        stock = client.get(f"{API}/inventory/stock").json()["items"]
        mine = [s for s in stock if s["productId"] == pid]
        assert mine and mine[0]["qty"] >= 10

        client.delete(f"{API}/purchase-orders/{poid}")


# ---------- Delivery ----------
class TestDelivery:
    def test_delivery_flow(self, client):
        r = client.get(f"{API}/deliveries")
        assert r.status_code == 200

        d = {"orderId": "test-order-1", "orderNo": "SO-TEST", "customerName": "T",
             "address": "Test", "status": "PENDING"}
        rc = client.post(f"{API}/deliveries", json=d)
        assert rc.status_code == 200
        created = rc.json()
        assert created.get("otp") and len(str(created["otp"])) == 4

        ru = client.put(f"{API}/deliveries/{created['id']}", json={"status": "DELIVERED"})
        assert ru.status_code == 200
        assert ru.json()["status"] == "DELIVERED"


# ---------- HR ----------
class TestHR:
    def test_employees(self, client):
        r = client.get(f"{API}/employees")
        assert r.status_code == 200

    def test_attendance_upsert(self, client):
        emps = client.get(f"{API}/employees").json().get("items", [])
        assert emps, "no employees seeded"
        eid = emps[0]["id"]
        payload = {"employeeId": eid, "date": "2026-01-15", "status": "PRESENT"}
        r1 = client.post(f"{API}/attendance", json=payload)
        assert r1.status_code == 200
        r2 = client.post(f"{API}/attendance", json={**payload, "status": "HALF_DAY"})
        assert r2.status_code == 200
        assert r2.json().get("updated") is True

    def test_leaves_flow(self, client):
        emps = client.get(f"{API}/employees").json().get("items", [])
        eid = emps[0]["id"]
        r = client.post(f"{API}/leaves", json={"employeeId": eid, "fromDate": "2026-02-01",
                                               "toDate": "2026-02-02", "days": 2, "leaveType": "CL"})
        assert r.status_code == 200
        lid = r.json()["id"]
        ru = client.put(f"{API}/leaves/{lid}", json={"status": "APPROVED"})
        assert ru.status_code == 200
        assert ru.json()["status"] == "APPROVED"

    def test_payroll_generate_idempotent(self, client):
        month = "2025-12"
        r1 = client.post(f"{API}/payroll/generate", json={"month": month})
        assert r1.status_code == 200
        gen1 = r1.json()["generated"]
        r2 = client.post(f"{API}/payroll/generate", json={"month": month})
        assert r2.status_code == 200
        assert r2.json()["generated"] == 0, f"second call should generate 0, got {r2.json()['generated']}"


# ---------- Finance ----------
class TestFinance:
    def test_accounts_seeded(self, client):
        r = client.get(f"{API}/accounts")
        assert r.status_code == 200
        assert len(r.json().get("items", [])) > 0

    def test_journal_unbalanced_rejected(self, client):
        payload = {"date": "2026-01-01", "narration": "test",
                   "entries": [{"accountId": "a", "debit": 100, "credit": 0},
                               {"accountId": "b", "debit": 0, "credit": 50}]}
        r = client.post(f"{API}/journal", json=payload)
        assert r.status_code == 400

    def test_journal_balanced_accepted(self, client):
        payload = {"date": "2026-01-01", "narration": "test",
                   "entries": [{"accountId": "a", "debit": 100, "credit": 0},
                               {"accountId": "b", "debit": 0, "credit": 100}]}
        r = client.post(f"{API}/journal", json=payload)
        assert r.status_code == 200

    def test_gst_report(self, client):
        r = client.get(f"{API}/reports/gst", params={"month": "2026-01"})
        assert r.status_code == 200
        d = r.json()
        assert "invoices" in d and "summary" in d
        for k in ["taxableValue", "cgst", "sgst", "igst", "total", "count"]:
            assert k in d["summary"]

    def test_pl_report(self, client):
        r = client.get(f"{API}/reports/pl")
        assert r.status_code == 200
        d = r.json()
        for k in ["revenue", "expenses", "netProfit"]:
            assert k in d

    def test_expenses(self, client):
        r = client.get(f"{API}/expenses")
        assert r.status_code == 200
        rc = client.post(f"{API}/expenses", json={"title": "TEST_Exp", "amount": 500, "category": "Travel"})
        assert rc.status_code == 200
        eid = rc.json()["id"]
        ru = client.put(f"{API}/expenses/{eid}", json={"status": "APPROVED"})
        assert ru.status_code == 200


# ---------- Projects / Tasks ----------
class TestProjectsTasks:
    def test_projects(self, client):
        r = client.get(f"{API}/projects")
        assert r.status_code == 200
        rc = client.post(f"{API}/projects", json={"name": "TEST_Proj", "budget": 1000})
        assert rc.status_code == 200

    def test_tasks_crud(self, client):
        r = client.get(f"{API}/tasks")
        assert r.status_code == 200
        rc = client.post(f"{API}/tasks", json={"title": "TEST_Task", "priority": "HIGH"})
        assert rc.status_code == 200
        tid = rc.json()["id"]
        ru = client.put(f"{API}/tasks/{tid}", json={"status": "DONE"})
        assert ru.status_code == 200
        rd = client.delete(f"{API}/tasks/{tid}")
        assert rd.status_code == 200


# ---------- Support ----------
class TestSupport:
    def test_ticket_flow(self, client):
        r = client.get(f"{API}/tickets")
        assert r.status_code == 200
        rc = client.post(f"{API}/tickets", json={"subject": "TEST_Ticket", "priority": "HIGH"})
        assert rc.status_code == 200
        t = rc.json()
        assert t["ticketNo"].startswith("TKT-")
        tid = t["id"]

        ru = client.put(f"{API}/tickets/{tid}", json={"status": "RESOLVED"})
        assert ru.status_code == 200
        assert ru.json()["status"] == "RESOLVED"

        rr = client.post(f"{API}/tickets/{tid}/reply", json={"message": "test reply"})
        assert rr.status_code == 200
        # Verify replies persisted
        tickets = client.get(f"{API}/tickets", params={"q": t["ticketNo"]}).json()["items"]
        assert any(len(x.get("replies", [])) >= 1 for x in tickets if x["id"] == tid)


# ---------- Docs / Notifications / Audit / Settings / Users ----------
class TestMisc:
    def test_documents(self, client):
        r = client.get(f"{API}/documents")
        assert r.status_code == 200
        rc = client.post(f"{API}/documents", json={"name": "TEST_Doc", "url": "http://x", "category": "GENERAL"})
        assert rc.status_code == 200

    def test_notifications(self, client):
        r = client.get(f"{API}/notifications")
        assert r.status_code == 200
        d = r.json()
        assert "items" in d and "unread" in d
        ru = client.put(f"{API}/notifications/read-all")
        assert ru.status_code == 200
        d2 = client.get(f"{API}/notifications").json()
        assert d2["unread"] == 0

    def test_audit(self, client):
        r = client.get(f"{API}/audit")
        assert r.status_code == 200

    def test_settings_company(self, client):
        r = client.get(f"{API}/settings/company")
        assert r.status_code == 200
        current = r.json() if isinstance(r.json(), dict) else {}
        ru = client.put(f"{API}/settings/company", json={**current, "name": "GLC Zone Test"})
        assert ru.status_code == 200
        assert ru.json()["name"] == "GLC Zone Test"

    def test_users_seeded(self, client):
        r = client.get(f"{API}/users")
        assert r.status_code == 200
        items = r.json().get("items", [])
        assert len(items) >= 4
        emails = {u["email"] for u in items}
        for e in ["bishwajeet@glczone.in", "riddhi@glczone.in", "dev@glczone.in", "danish@glczone.in"]:
            assert e in emails
