"""Withdrawals from glczone.in reach the CRM. Run: python -m pytest -p no:cacheprovider -o addopts="" -o required_plugins="" tests/test_withdrawal_event_api.py"""
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mongomock_motor")
from fastapi.testclient import TestClient  # noqa: E402
import motor.motor_asyncio  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "glc_wd_test")
os.environ["CRM_BRIDGE_SECRET"] = "s3cret"
os.environ.pop("EMERGENT_LLM_KEY", None)
motor.motor_asyncio.AsyncIOMotorClient = AsyncMongoMockClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402

SECRET = {"X-Crm-Bridge-Secret": "s3cret"}


@pytest.fixture(scope="module")
def api():
    saved = server.db
    server.db = AsyncMongoMockClient()["glc_wd_isolated"]
    try:
        with TestClient(server.app) as c:
            c.portal.call(server.db.users.insert_one, {"id": "w-admin", "name": "Admin", "email": "w@x.in", "role": "Admin"})
            c.h = {"Authorization": "Bearer " + server.make_token("w-admin", "w@x.in", "Admin")}
            c.run = c.portal.call
            yield c
    finally:
        server.db = saved


def test_needs_the_secret(api):
    assert api.post("/api/webhooks/withdrawal-event", json={"withdrawal_id": "1"}).status_code == 401


def test_request_then_status_changes_are_one_row(api):
    body = {"withdrawal_id": "11", "user_id": 5, "name": "Ravi", "mobile": "9999999999", "wallet": "cash", "amount": 500, "tds": 10, "net_amount": 490,
            "payment_address": "ravi@upi", "status": "pending", "requested_at": "2026-11-20 10:00:00"}
    r = api.post("/api/webhooks/withdrawal-event", json=body, headers=SECRET)
    assert r.json()["created"] is True

    rows = api.get("/api/withdrawals", headers=api.h).json()["items"]
    assert len(rows) == 1 and rows[0]["sellerName"] == "Ravi" and rows[0]["netAmount"] == 490 and rows[0]["status"] == "pending" and rows[0]["upiId"] == "ravi@upi"

    body["status"] = "approved"                     # approved on the website
    assert api.post("/api/webhooks/withdrawal-event", json=body, headers=SECRET).json()["created"] is False
    rows = api.get("/api/withdrawals", headers=api.h).json()["items"]
    assert len(rows) == 1 and rows[0]["status"] == "approved"


def test_an_older_message_does_not_undo_a_click_in_progress(api):
    body = {"withdrawal_id": "12", "name": "Sita", "amount": 200, "net_amount": 196, "status": "pending"}
    api.post("/api/webhooks/withdrawal-event", json=body, headers=SECRET)
    api.run(server.db.withdrawals.update_one, {"glczone_withdrawal_id": "12"}, {"$set": {"status": "processing"}})   # the CRM is approving it right now

    api.post("/api/webhooks/withdrawal-event", json=body, headers=SECRET)                                         # a late "pending" message

    row = api.run(server.db.withdrawals.find_one, {"glczone_withdrawal_id": "12"})
    assert row["status"] == "processing"
