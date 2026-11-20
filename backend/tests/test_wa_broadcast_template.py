"""WhatsApp broadcast through an approved template: the message goes into the template's one variable. Run: python -m pytest -p no:cacheprovider -o addopts="" -o required_plugins="" tests/test_wa_broadcast_template.py"""
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mongomock_motor")
import motor.motor_asyncio  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "glc_wabt_test")
os.environ.pop("EMERGENT_LLM_KEY", None)
motor.motor_asyncio.AsyncIOMotorClient = AsyncMongoMockClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402


class FakeResp:
    status_code = 200

    def json(self):
        return {"messages": [{"id": "wamid.1"}]}


def test_template_payload_has_one_clean_variable(monkeypatch):
    sent = {}
    monkeypatch.setattr(server, "WHATSAPP_ACCESS_TOKEN", "tok")
    monkeypatch.setattr(server, "WHATSAPP_PHONE_NUMBER_ID", "123")
    monkeypatch.setattr(server.requests, "post", lambda url, json=None, headers=None, timeout=None: (sent.update(url=url, body=json, headers=headers), FakeResp())[1])

    r = server.send_whatsapp_template_text("919999999999", "glc_notice", "en", "Hello\nSale\ttoday")

    assert r["success"] is True
    comp = sent["body"]["template"]["components"][0]["parameters"]
    assert len(comp) == 1 and "\n" not in comp[0]["text"] and "\t" not in comp[0]["text"]   # Meta rejects newlines / tabs
    assert sent["body"]["template"]["name"] == "glc_notice"


def test_without_credentials_nothing_is_sent(monkeypatch):
    monkeypatch.setattr(server, "WHATSAPP_ACCESS_TOKEN", "")
    r = server.send_whatsapp_template_text("919999999999", "glc_notice", "en", "x")
    assert r["success"] is False
