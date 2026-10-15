"""WhatsApp assistant flow tests (in-memory MongoDB; nothing is sent anywhere). Run:
python -m pytest -p no:cacheprovider -o addopts="" tests/test_whatsapp_flow_api.py"""
import hashlib
import hmac
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("mongomock_motor")
from fastapi.testclient import TestClient  # noqa: E402
import motor.motor_asyncio  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "glc_wa_test")
os.environ.pop("EMERGENT_LLM_KEY", None)
motor.motor_asyncio.AsyncIOMotorClient = AsyncMongoMockClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402

SECRET = "test-sso-secret"


@pytest.fixture(scope="module")
def api():
    saved = (server.db, server.CRM_SSO_SECRET)
    server.db = AsyncMongoMockClient()["glc_wa_isolated"]
    server.CRM_SSO_SECRET = SECRET
    try:
        with TestClient(server.app) as c:
            c.run = c.portal.call
            c.run(server.db.users.insert_one, {"id": "wa-admin", "name": "Admin", "email": "wa@x.in", "role": "Admin"})
            c.h = {"Authorization": "Bearer " + server.make_token("wa-admin", "wa@x.in", "Admin")}
            yield c
    finally:
        server.db, server.CRM_SSO_SECRET = saved


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    sent, ai = [], []

    async def fake_asend(channel, contact, text):
        sent.append(text)
        return {"success": True}

    async def fake_groq(key, payload):
        ai.append(payload)
        return "Sure, here is the answer."
    async def no_context():
        return ""
    monkeypatch.setattr(server, "fetch_glczone_context", no_context)
    monkeypatch.setattr(server, "asend", fake_asend)
    monkeypatch.setattr(server, "groq_chat", fake_groq)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    return sent, ai


def post(api, phone, text="hello", **extra):
    body = {"from": phone, "name": "Asha", "text": text, "channel": "WHATSAPP"}
    signed = dict(body)
    for k in ("waMessageId", "msgType", "mediaId", "ts"):
        if extra.get(k) is not None:
            signed[k] = extra[k]
    sig = hmac.new(SECRET.encode(), json.dumps(signed, separators=(",", ":")).encode(), hashlib.sha256).hexdigest()
    return api.post("/api/ocm/message/incoming", json={**body, **{k: v for k, v in extra.items() if v is not None}, "sig": sig})


def contact(api, phone, **kw):
    api.run(server.db.ocm_contacts.update_one, {"whatsappId": phone}, {"$set": {"id": f"c-{phone}", "phone": phone, "whatsappId": phone, "name": "Asha", "channels": ["WHATSAPP"], "subscribed": True,
                                                                            "preferredLang": "English", **kw}}, True)


def conv(api, phone):
    c = api.run(server.db.ocm_contacts.find_one, {"whatsappId": phone})
    return api.run(server.db.ocm_conversations.find_one, {"contactId": c["id"]})


def test_the_same_whatsapp_message_is_answered_once(api, fakes):
    sent, ai = fakes
    contact(api, "9100000001")
    assert post(api, "9100000001", "Do you have atta?", waMessageId="wamid.A1").json() == {"ok": True}
    again = post(api, "9100000001", "Do you have atta?", waMessageId="wamid.A1").json()
    assert again.get("duplicate") is True
    assert len(ai) == 1 and len(sent) == 1
    assert api.run(server.db.ocm_messages.count_documents, {"waMessageId": "wamid.A1"}) == 1


def test_an_old_signed_request_is_refused(api):
    r = post(api, "9100000002", "hi", ts=int(time.time()) - 3600)
    assert r.status_code == 401
    assert post(api, "9100000002", "hi", ts=int(time.time())).status_code == 200


def test_a_bad_signature_is_refused(api):
    r = api.post("/api/ocm/message/incoming", json={"from": "9100000003", "name": "x", "text": "hi", "channel": "WHATSAPP", "sig": "bad"})
    assert r.status_code == 401


def test_a_photo_is_acknowledged_flagged_and_not_sent_to_the_ai(api, fakes):
    sent, ai = fakes
    contact(api, "9100000004")
    assert post(api, "9100000004", "", msgType="image", mediaId="m1").status_code == 200
    assert not ai and sent and "received it" in sent[0]
    c = conv(api, "9100000004")
    assert c["needsHuman"] is True and "Photo" in c["needsHumanReason"]
    msg = api.run(server.db.ocm_messages.find_one, {"conversationId": c["id"], "direction": "IN"})
    assert msg["text"] == "[📷 Photo received]" and msg["mediaId"] == "m1"


def test_stop_and_start_are_confirmed_and_logged(api, fakes):
    sent, ai = fakes
    contact(api, "9100000005")
    post(api, "9100000005", "STOP")
    c = api.run(server.db.ocm_contacts.find_one, {"whatsappId": "9100000005"})
    assert c["optedOut"] is True and c["subscribed"] is False
    assert any("unsubscribed" in t for t in sent) and not ai
    post(api, "9100000005", "start")
    c = api.run(server.db.ocm_contacts.find_one, {"whatsappId": "9100000005"})
    assert c["optedOut"] is False and c["subscribed"] is True
    assert [x["action"] for x in c["consentLog"]] == ["opt_out", "opt_in"]


def test_the_word_cancel_is_not_an_opt_out(api, fakes):
    sent, ai = fakes
    contact(api, "9100000006")
    post(api, "9100000006", "Cancel")
    c = api.run(server.db.ocm_contacts.find_one, {"whatsappId": "9100000006"})
    assert not c.get("optedOut")
    assert len(ai) == 1                       # it goes to the assistant like any question


def test_when_the_ai_fails_the_customer_still_gets_an_answer(api, fakes, monkeypatch):
    sent, ai = fakes

    async def broken(key, payload):
        return ""
    monkeypatch.setattr(server, "groq_chat", broken)
    contact(api, "9100000007")
    post(api, "9100000007", "Where is my order?")
    assert sent and "will reply" in sent[-1]
    c = conv(api, "9100000007")
    assert c["needsHuman"] is True


def test_no_ai_key_hands_over_to_a_person(api, fakes, monkeypatch):
    sent, ai = fakes
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    contact(api, "9100000008")
    post(api, "9100000008", "hello")
    assert sent and "will reply" in sent[-1] and not ai


def test_long_messages_are_cut_before_they_reach_the_ai(api, fakes):
    sent, ai = fakes
    contact(api, "9100000009")
    post(api, "9100000009", "x" * 3000)
    assert len(ai) == 1
    assert len(ai[0]["messages"][-1]["content"]) <= server.AI_MAX_INPUT


def test_the_ai_stops_after_the_daily_limit(api, fakes, monkeypatch):
    sent, ai = fakes
    monkeypatch.setattr(server, "AI_DAILY_LIMIT", 2)
    contact(api, "9100000010")
    for i in range(4):
        post(api, "9100000010", f"question {i}")
    assert len(ai) == 2
    assert sum(1 for t in sent if "will reply" in t) == 1      # the handover message is sent once, not every time
    assert conv(api, "9100000010")["needsHuman"] is True


def test_the_assistant_takes_the_chat_back_after_12_silent_hours_and_on_resolve(api, fakes):
    sent, ai = fakes
    contact(api, "9100000011")
    post(api, "9100000011", "first")
    c = conv(api, "9100000011")
    old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    api.run(server.db.ocm_conversations.update_one, {"id": c["id"]}, {"$set": {"agentMode": True, "agentAt": old}})
    n = len(ai)
    post(api, "9100000011", "second")
    assert len(ai) == n                                         # a person is on it: Zara stays quiet
    api.run(server.db.ocm_conversations.update_one, {"id": c["id"]}, {"$set": {"agentAt": (datetime.now(timezone.utc) - timedelta(hours=13)).isoformat()}})
    post(api, "9100000011", "third")
    assert len(ai) == n + 1                                     # 13 hours of silence: Zara is back
    api.run(server.db.ocm_conversations.update_one, {"id": c["id"]}, {"$set": {"agentMode": True, "agentAt": old}})
    r = api.put(f"/api/ocm/conversations/{c['id']}", json={"status": "RESOLVED", "id": "x"}, headers=api.h)
    assert r.status_code == 200
    d = api.run(server.db.ocm_conversations.find_one, {"id": c["id"]})
    assert d["agentMode"] is False and d["id"] == c["id"]


def test_a_broadcast_skips_people_who_said_stop(api, monkeypatch):
    got = []

    def fake_send(to, text):
        got.append(to)
        return {"success": True}
    monkeypatch.setattr(server, "send_whatsapp_text", fake_send)
    for ph, out in (("9199990001", False), ("9199990002", True)):
        api.run(server.db.ocm_contacts.insert_one, {"id": f"b-{ph}", "phone": ph, "whatsappId": ph, "channels": ["WHATSAPP"], "subscribed": not out, "optedOut": out})
    api.run(server.db.customers.insert_one, {"id": "bc1", "name": "C", "phone": "9199990002"})
    api.run(server.db.ocm_broadcasts.insert_one, {"id": "bro1", "name": "T", "channels": ["WHATSAPP"], "audience": "ALL", "message": "Offer", "status": "DRAFT"})
    r = api.post("/api/ocm/broadcasts/bro1/send", headers=api.h)
    assert r.status_code == 200, r.text
    assert "9199990001" in got and "9199990002" not in got and "919199990002" not in got
    assert api.run(server.db.ocm_broadcasts.find_one, {"id": "bro1"})["deliveredCount"] == 0


def test_a_customer_can_only_see_their_own_order(api, monkeypatch):
    asked = {}

    class Cur:
        async def execute(self, sql, args):
            asked["sql"], asked["args"] = sql, args

        async def fetchone(self):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class Conn:
        def cursor(self):
            return Cur()

        def close(self):
            pass

    async def fake_connect():
        return Conn()
    monkeypatch.setattr(server, "mysql_connect", fake_connect)
    out = api.run(server.lookup_order_status, "5", "919876543210")
    assert "o.mobile LIKE" in asked["sql"] and asked["args"][1] == "%9876543210"
    assert api.run(server.lookup_order_status, "5", "12") == "nahi mila is number par."       # no usable number: nothing is shown


def test_webchat_needs_a_session_and_is_rate_limited(api, fakes):
    assert api.post("/api/ocm/webchat", json={"text": "hi"}).status_code == 400              # no session id
    assert api.post("/api/ocm/webchat", json={"sessionId": "short", "text": "hi"}).status_code == 400
    ok = 0
    for i in range(22):
        r = api.post("/api/ocm/webchat", json={"sessionId": "visitor-abcdef12", "text": f"hello {i}"})
        ok += r.status_code == 200
        if r.status_code == 429:
            break
    assert ok == 20 and r.status_code == 429                                                # the 21st message is refused
    assert api.post("/api/ocm/webchat", json={"sessionId": "visitor-other-99", "text": "hello"}).status_code == 200   # another visitor is fine
