"""Lead follow-up tests (in-memory MongoDB). Run: python -m pytest -p no:cacheprovider -o addopts="" tests/test_leads_api.py"""
import os
import sys
from datetime import timedelta
from pathlib import Path

import pytest

pytest.importorskip("mongomock_motor")
from fastapi.testclient import TestClient  # noqa: E402
import motor.motor_asyncio  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "glc_leads_test")
os.environ.pop("EMERGENT_LLM_KEY", None)
motor.motor_asyncio.AsyncIOMotorClient = AsyncMongoMockClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402


@pytest.fixture(scope="module")
def api():
    saved = server.db
    server.db = AsyncMongoMockClient()["glc_leads_isolated"]
    try:
        with TestClient(server.app) as c:
            run = c.portal.call
            for uid_, role in (("ld-admin", "Admin"), ("ld-tele", "Telecaller"), ("ld-tele2", "Telecaller")):
                run(server.db.users.insert_one, {"id": uid_, "name": uid_.title(), "email": f"{uid_}@x.in", "role": role})
            c.h = lambda uid_, role: {"Authorization": "Bearer " + server.make_token(uid_, f"{uid_}@x.in", role)}
            c.run = run
            c.today = server.ist_now().strftime("%Y-%m-%d")
            c.yesterday = (server.ist_now() - timedelta(days=1)).strftime("%Y-%m-%d")
            c.tomorrow = (server.ist_now() + timedelta(days=1)).strftime("%Y-%m-%d")
            yield c
    finally:
        server.db = saved


def mk(api, name, **kw):
    doc = {"id": f"L-{name}", "name": name, "status": "NEW", "createdAt": server.now_iso(), "activities": [], **kw}
    api.run(server.db.leads.insert_one, doc)
    return doc["id"]


def test_follow_up_views_and_summary(api):
    t = api.h("ld-tele", "Telecaller")
    mk(api, "late", followUpDate=api.yesterday, assignedTo="ld-tele")
    mk(api, "now", followUpDate=api.today, assignedTo="ld-tele")
    mk(api, "now2", followUpDate=api.today + "T10:00:00", assignedTo="ld-tele2")
    mk(api, "later", followUpDate=api.tomorrow, assignedTo="ld-tele")
    mk(api, "none1")
    mk(api, "closed", followUpDate=api.yesterday, status="WON", assignedTo="ld-tele")

    def names(**p):
        return sorted(i["name"] for i in api.get("/api/leads", params=p, headers=t).json()["items"])
    assert names(follow="overdue") == ["late"]
    assert names(follow="today") == ["now", "now2"]
    assert names(follow="due") == ["late", "now", "now2"]
    assert names(follow="due", assigned="me") == ["late", "now"]
    assert names(assigned="none") == ["none1"]
    assert names(follow="none") == ["none1"]
    s = api.get("/api/leads/summary", headers=t).json()
    assert (s["today"], s["overdue"], s["mine"], s["unassigned"]) == (2, 1, 3, 1)
    # the late ones come first
    first = api.get("/api/leads", params={"follow": "due"}, headers=t).json()["items"][0]["name"]
    assert first == "late"


def test_my_follow_ups_show_in_the_notification_bell(api):
    items = api.get("/api/notifications", headers=api.h("ld-tele", "Telecaller")).json()["items"]
    due = [i for i in items if i["id"] == "followups-due"]
    assert due and due[0]["message"].startswith("2 ")          # late + now (not the closed one, not tomorrow)
    other = api.get("/api/notifications", headers=api.h("ld-admin", "Admin")).json()["items"]
    assert not [i for i in other if i["id"] == "followups-due"]


def test_a_duplicate_phone_is_stopped_but_can_be_forced(api):
    t = api.h("ld-tele", "Telecaller")
    api.run(server.db.customers.insert_one, {"id": "cu1", "name": "Old Customer", "phone": "+91 98765-43210"})
    r = api.post("/api/leads", json={"name": "New", "phone": "09876543210"}, headers=t)
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["code"] == "duplicate" and d["existing"]["type"] == "customer" and d["existing"]["id"] == "cu1"
    assert api.post("/api/leads", json={"name": "New", "phone": "9876543210"}, params={"force": "true"}, headers=t).status_code == 200
    again = api.post("/api/leads", json={"name": "Again", "phone": "98765 43210"}, headers=t)
    assert again.status_code == 409 and again.json()["detail"]["existing"]["type"] == "lead"
    api.run(server.db.customers.insert_one, {"id": "cu2", "name": "With code", "phone": "919000000077"})
    assert api.post("/api/leads", json={"name": "WithCode", "phone": "9000000077"}, headers=t).status_code == 409     # country code in front is the same person
    assert api.post("/api/leads", json={"name": "Different", "phone": "9000000001", "email": "x@y.in"}, headers=t).status_code == 200


def test_changes_are_written_in_the_history(api):
    t = api.h("ld-tele", "Telecaller")
    lid = mk(api, "hist", phone="9111111111")
    r = api.patch(f"/api/leads/{lid}", json={"status": "QUALIFIED", "followUpDate": api.tomorrow, "assignedTo": "ld-tele2", "id": "hack"}, headers=t)
    assert r.status_code == 200
    d = r.json()
    assert d["id"] == lid and d["assignedName"] == "Ld-Tele2" and d["followUpDate"] == api.tomorrow
    texts = [a["text"] for a in d["activities"]]
    assert any("NEW → QUALIFIED" in x for x in texts) and any("Assigned to" in x for x in texts) and any("Next follow-up" in x for x in texts)


def test_a_lost_lead_needs_a_reason_and_dates_are_checked(api):
    t = api.h("ld-tele", "Telecaller")
    lid = mk(api, "lostone")
    assert api.patch(f"/api/leads/{lid}", json={"status": "LOST"}, headers=t).status_code == 400
    ok = api.patch(f"/api/leads/{lid}", json={"status": "LOST", "lostReason": "Too expensive"}, headers=t)
    assert ok.status_code == 200 and ok.json()["lostReason"] == "Too expensive"
    assert api.patch(f"/api/leads/{lid}", json={"followUpDate": "tomorrow"}, headers=t).status_code == 400
    assert api.patch(f"/api/leads/{lid}", json={"assignedTo": "nobody-here"}, headers=t).status_code == 400
    assert api.patch(f"/api/leads/{lid}", json={"status": "MAYBE"}, headers=t).status_code == 400


def test_a_call_note_sets_the_next_date_and_moves_new_to_contacted(api):
    t = api.h("ld-tele", "Telecaller")
    lid = mk(api, "caller")
    r = api.post(f"/api/leads/{lid}/activity", json={"type": "call", "outcome": "No answer", "nextFollowUp": api.tomorrow}, headers=t)
    assert r.status_code == 200
    lead = r.json()["lead"]
    assert lead["status"] == "CONTACTED" and lead["followUpDate"] == api.tomorrow
    assert lead["activities"][-1]["outcome"] == "No answer" and lead["activities"][-1]["type"] == "call"
    assert api.post(f"/api/leads/{lid}/activity", json={"type": "note"}, headers=t).status_code == 400
    note = api.post(f"/api/leads/{lid}/activity", json={"type": "note", "text": "Asked to call after Diwali"}, headers=t).json()["lead"]
    assert note["status"] == "CONTACTED"                         # a plain note does not change the status


def test_a_search_filter_and_page_size_are_safe(api):
    t = api.h("ld-tele", "Telecaller")
    assert api.get("/api/leads", params={"q": "(", "limit": 500}, headers=t).status_code == 200
    assert api.get("/api/leads", params={"limit": 500}, headers=t).json()["limit"] == 200
