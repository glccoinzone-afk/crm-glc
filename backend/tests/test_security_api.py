"""Security tests (in-memory MongoDB, no network). Run: python -m pytest -p no:cacheprovider -o addopts="" tests/test_security_api.py"""
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mongomock_motor")
from fastapi.testclient import TestClient  # noqa: E402
import motor.motor_asyncio  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "glc_sec_test")
os.environ.pop("EMERGENT_LLM_KEY", None)
motor.motor_asyncio.AsyncIOMotorClient = AsyncMongoMockClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyotp  # noqa: E402
import server  # noqa: E402


@pytest.fixture(scope="module")
def api():
    with TestClient(server.app) as c:
        run = c.portal.call
        secret = pyotp.random_base32()
        users = [
            {"id": "u-admin", "name": "Admin", "email": "admin@x.in", "role": "Admin", "password": server.hash_pw("Pass#1234"), "totp_secret": secret, "twofa_enabled": False},
            {"id": "u-tele", "name": "Tele", "email": "tele@x.in", "role": "Telecaller", "password": server.hash_pw("Pass#1234")},
            {"id": "u-hr", "name": "HR", "email": "hr@x.in", "role": "HR", "password": server.hash_pw("Pass#1234")},
            {"id": "u-2fa", "name": "TwoFA", "email": "two@x.in", "role": "Admin", "password": server.hash_pw("Pass#1234"), "totp_secret": secret, "twofa_enabled": True},
            {"id": "u-off", "name": "Off", "email": "off@x.in", "role": "Admin", "password": server.hash_pw("Pass#1234"), "isActive": False},
        ]
        for u in users:
            run(server.db.users.insert_one, u)
        c.h = lambda uid_, role: {"Authorization": "Bearer " + server.make_token(uid_, f"{uid_}@x.in", role)}
        c.secret = secret
        c.run = run
        yield c


def test_2fa_step_one_token_is_not_a_login(api):
    r = api.post("/api/auth/login", json={"email": "two@x.in", "password": "Pass#1234"})
    assert r.status_code == 200 and r.json()["requires_2fa"] is True
    temp = r.json()["temp_token"]
    # the temp token must not open the CRM
    assert api.get("/api/auth/me", headers={"Authorization": "Bearer " + temp}).status_code == 401
    assert api.get("/api/leads", headers={"Authorization": "Bearer " + temp}).status_code == 401
    # a wrong code is refused, the right code gives a real token
    assert api.post("/api/auth/2fa/verify", json={"temp_token": temp, "code": "000000"}).status_code == 400
    ok = api.post("/api/auth/2fa/verify", json={"temp_token": temp, "code": pyotp.TOTP(api.secret).now()})
    assert ok.status_code == 200
    real = ok.json()["token"]
    assert api.get("/api/auth/me", headers={"Authorization": "Bearer " + real}).status_code == 200


def test_a_normal_token_cannot_be_used_as_the_2fa_step(api):
    normal = server.make_token("u-2fa", "two@x.in", "Admin")
    r = api.post("/api/auth/2fa/verify", json={"temp_token": normal, "code": pyotp.TOTP(api.secret).now()})
    assert r.status_code == 401


def test_login_locks_after_five_wrong_passwords(api):
    for _ in range(5):
        assert api.post("/api/auth/login", json={"email": "hr@x.in", "password": "wrong"}).status_code == 401
    r = api.post("/api/auth/login", json={"email": "hr@x.in", "password": "Pass#1234"})
    assert r.status_code == 429
    api.run(server.db.login_attempts.delete_many, {})


def test_disabled_user_token_stops_working(api):
    assert api.get("/api/auth/me", headers=api.h("u-off", "Admin")).status_code == 403


def test_2fa_secrets_are_never_returned(api):
    h = api.h("u-admin", "Admin")
    me = api.get("/api/auth/me", headers=h).json()
    assert "totp_secret" not in me and "totp_secret_pending" not in me and "password" not in me
    users = api.get("/api/users", headers=h).json()["items"]
    assert users and all("totp_secret" not in u and "password" not in u for u in users)
    login = api.post("/api/auth/login", json={"email": "admin@x.in", "password": "Pass#1234"}).json()
    assert "totp_secret" not in login["user"]


def test_telecaller_cannot_do_admin_things(api):
    t = api.h("u-tele", "Telecaller")
    assert api.get("/api/users", headers=t).status_code == 403
    assert api.get("/api/payroll", headers=t).status_code == 403
    assert api.get("/api/employees", headers=t).status_code == 403
    assert api.post("/api/withdrawals/x/approve", headers=t).status_code == 403
    assert api.post("/api/returns/x/approve", headers=t).status_code == 403
    assert api.delete("/api/customers/x", headers=t).status_code == 403
    assert api.put("/api/settings/company", json={"name": "x"}, headers=t).status_code == 403
    assert api.get("/api/audit", headers=t).status_code == 403
    # and still do the daily work
    assert api.get("/api/leads", headers=t).status_code == 200


def test_hr_can_run_hr_but_not_money(api):
    h = api.h("u-hr", "HR")
    assert api.get("/api/employees", headers=h).status_code == 200
    assert api.get("/api/payroll", headers=h).status_code == 200
    assert api.post("/api/withdrawals/x/approve", headers=h).status_code == 403
    assert api.put("/api/expenses/x", json={"status": "APPROVED"}, headers=h).status_code == 403


def test_admin_is_allowed(api):
    a = api.h("u-admin", "Admin")
    assert api.get("/api/users", headers=a).status_code == 200
    assert api.get("/api/audit", headers=a).status_code == 200


def test_update_cannot_change_id_or_use_operators(api):
    a = api.h("u-admin", "Admin")
    api.run(server.db.tasks.insert_one, {"id": "t1", "title": "A", "status": "TODO"})
    r = api.put("/api/tasks/t1", json={"id": "hacked", "title": "B", "$set": {"x": 1}, "a.b": 2}, headers=a)
    assert r.status_code == 200
    doc = api.run(server.db.tasks.find_one, {"id": "t1"})
    assert doc["title"] == "B" and doc["id"] == "t1" and "a" not in doc


def test_search_with_special_characters_does_not_crash(api):
    t = api.h("u-tele", "Telecaller")
    for q in ["+91", "(", "98*", "[a-", "\\"]:
        assert api.get("/api/leads", params={"q": q}, headers=t).status_code == 200


def test_uploaded_html_is_a_download_not_a_page():
    r = server.download_response(b"<script>alert(1)</script>", "text/html", 'x".html')
    assert r.headers["content-disposition"].startswith("attachment")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.media_type == "application/octet-stream"
    img = server.download_response(b"x", "image/png", "a.png")
    assert img.headers["content-disposition"].startswith("inline")
    assert '"' not in img.headers["content-disposition"].split("filename=")[1].strip('"')


def test_safe_fields():
    assert server.safe_fields({"id": "x", "a": 1, "$set": 2, "b.c": 3, "createdAt": "x"}) == {"a": 1}
    assert server.safe_fields({"a": 1, "b": 2}, allowed={"a"}) == {"a": 1}
