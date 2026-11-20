"""GLC Business (bulk buyers) in the CRM: webhook from glczone.in and the list. Run: python -m pytest -p no:cacheprovider -o addopts="" tests/test_business_accounts_api.py"""
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mongomock_motor")
from fastapi.testclient import TestClient  # noqa: E402
import motor.motor_asyncio  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "glc_biz_test")
os.environ["CRM_BRIDGE_SECRET"] = "s3cret"
os.environ.pop("EMERGENT_LLM_KEY", None)
motor.motor_asyncio.AsyncIOMotorClient = AsyncMongoMockClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402


@pytest.fixture(scope="module")
def api():
    saved = server.db
    server.db = AsyncMongoMockClient()["glc_biz_isolated"]
    try:
        with TestClient(server.app) as c:
            c.portal.call(server.db.users.insert_one, {"id": "b-admin", "name": "Admin", "email": "b@x.in", "role": "Admin"})
            c.h = {"Authorization": "Bearer " + server.make_token("b-admin", "b@x.in", "Admin")}
            yield c
    finally:
        server.db = saved


SECRET = {"X-Crm-Bridge-Secret": "s3cret"}


def test_webhook_needs_the_secret(api):
    assert api.post("/api/webhooks/business-event", json={"business_id": "1", "business_name": "X"}).status_code == 401
    assert api.post("/api/webhooks/business-event", json={"business_id": "1", "business_name": "X"}, headers={"X-Crm-Bridge-Secret": "wrong"}).status_code == 401


def test_create_update_and_list(api):
    body = {"business_id": "7", "user_id": 42, "code": "GB007", "business_name": "Hotel Sai", "business_type": "hotel", "phone": "9953002239", "city": "Patna",
            "status": "pending", "orders": 0, "spend": 0}
    r = api.post("/api/webhooks/business-event", json=body, headers=SECRET)
    assert r.status_code == 200 and r.json()["created"] is True

    body.update({"status": "approved", "orders": 3, "spend": 12500.5, "saved": 900, "quotes_open": 1, "quotes_total": 2})
    r = api.post("/api/webhooks/business-event", json=body, headers=SECRET)
    assert r.json()["created"] is False       # same business again: refreshed, not duplicated

    api.post("/api/webhooks/business-event", json={"business_id": "8", "business_name": "Mess One", "status": "pending"}, headers=SECRET)

    d = api.get("/api/business-accounts", headers=api.h).json()
    assert d["summary"]["total"] == 2 and d["summary"]["approved"] == 1 and d["summary"]["pending"] == 1
    assert d["summary"]["orders"] == 3 and d["summary"]["spend"] == 12500.5 and d["summary"]["quotesOpen"] == 1
    sai = [x for x in d["items"] if x["name"] == "Hotel Sai"][0]
    assert sai["status"] == "approved" and len(sai["activities"]) == 2   # registered, then pending -> approved

    assert [x["name"] for x in api.get("/api/business-accounts?status=pending", headers=api.h).json()["items"]] == ["Mess One"]
    assert [x["name"] for x in api.get("/api/business-accounts?q=patna", headers=api.h).json()["items"]] == ["Hotel Sai"]


def test_list_needs_a_login(api):
    assert api.get("/api/business-accounts").status_code in (401, 403)
