"""Channels hub and cross-channel reports for the OCM module.

`CHANNELS` describes every channel the CRM can talk on and which environment variables it needs; `channel_config`
turns the process environment into a ready / missing report (pure, unit tested). `register()` adds the live
connection checks, a test-send, and the reports endpoint to the FastAPI app server.py builds.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
from fastapi import Depends, HTTPException
from pydantic import BaseModel

log = logging.getLogger("glc.channels")
FB_API = os.environ.get("FB_API_VERSION", "v20.0")

CHANNELS: Dict[str, Dict[str, Any]] = {
    "WHATSAPP": {
        "label": "WhatsApp", "needs": ["WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"],
        "receive": "Customer messages arrive through the store's Meta webhook (/webhook/whatsapp).",
        "send": "Replies inside 24 hours, approved templates for campaigns.",
        "setup": ["Create a System User token with whatsapp_business_messaging and whatsapp_business_management.",
                  "Add the token and Phone Number ID to the server .env.", "Set the Business Account ID on the WhatsApp page."],
        "contactField": "whatsappId", "idHelp": "WhatsApp number with country code, e.g. 919608261539",
    },
    "TELEGRAM": {
        "label": "Telegram", "needs": ["TELEGRAM_BOT_TOKEN"], "optional": ["TELEGRAM_CHANNEL_ID"],
        "receive": "Messages to the bot arrive through the store's Telegram webhook.",
        "send": "Bot replies and Quick Broadcast; posts to your channel from the Social Scheduler (needs TELEGRAM_CHANNEL_ID).",
        "setup": ["In Telegram open @BotFather, send /newbot and copy the token.", "Add TELEGRAM_BOT_TOKEN to the server .env.",
                  "To post to a channel, make the bot an admin there and set TELEGRAM_CHANNEL_ID."],
        "contactField": "telegramId", "idHelp": "Telegram chat id (a number). A person must press Start on the bot first.",
    },
    "FACEBOOK": {
        "label": "Facebook Page", "needs": ["FB_PAGE_ID", "FB_PAGE_ACCESS_TOKEN"],
        "receive": "Page messages arrive through the store's Meta webhook.",
        "send": "Messenger replies and page posts from the Social Scheduler.",
        "setup": ["Create a Page access token with pages_messaging and pages_manage_posts.", "Add FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN to the server .env.",
                  "Subscribe the page to the app's webhook (messages)."],
        "contactField": "facebookId", "idHelp": "Facebook page-scoped user id (PSID).",
    },
    "INSTAGRAM": {
        "label": "Instagram", "needs": ["IG_BUSINESS_ACCOUNT_ID", "FB_PAGE_ACCESS_TOKEN"],
        "receive": "Direct messages arrive through the store's Meta webhook.",
        "send": "DM replies and posts from the Social Scheduler.",
        "setup": ["Connect the Instagram business account to your Facebook Page.", "Add IG_BUSINESS_ACCOUNT_ID (and the Page token) to the server .env.",
                  "Enable instagram_manage_messages for the app."],
        "contactField": "instagramId", "idHelp": "Instagram-scoped user id (IGSID).",
    },
    "WEBCHAT": {
        "label": "Website chat (Zara)", "needs": [],
        "receive": "Visitors chat from the website widget; the AI assistant answers.",
        "send": "Always on. Staff can take over from the Inbox.",
        "setup": ["Nothing to set up; it is part of the store website."],
        "contactField": "phone", "idHelp": "",
    },
}


def channel_config(env: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """Per channel: label, which required variables are set or missing, and whether it is ready. Never returns secret values."""
    env = os.environ if env is None else env
    out = []
    for key, c in CHANNELS.items():
        missing = [v for v in c["needs"] if not env.get(v)]
        out.append({
            "key": key, "label": c["label"], "ready": not missing, "missing": missing,
            "optionalMissing": [v for v in c.get("optional", []) if not env.get(v)],
            "receive": c["receive"], "send": c["send"], "setup": c["setup"], "idHelp": c["idHelp"],
        })
    return out


def daily_buckets(rows: List[Dict[str, Any]], days: int, today: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Message counts per UTC day for the last `days` days, oldest first, with zero-filled gaps. rows: {_id: 'YYYY-MM-DD', in, out}."""
    today = today or datetime.now(timezone.utc)
    by_day = {r["_id"]: r for r in rows}
    out = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        r = by_day.get(d, {})
        out.append({"date": d, "in": r.get("in", 0), "out": r.get("out", 0)})
    return out


def response_minutes(pairs: List[Dict[str, Any]]) -> Optional[float]:
    """Median minutes between a customer message and the next staff/bot reply. pairs: {inAt, outAt} ISO strings."""
    gaps = []
    for p in pairs:
        try:
            a = datetime.fromisoformat(p["inAt"].replace("Z", "+00:00"))
            b = datetime.fromisoformat(p["outAt"].replace("Z", "+00:00"))
        except (KeyError, ValueError, AttributeError):
            continue
        if b >= a:
            gaps.append((b - a).total_seconds() / 60)
    if not gaps:
        return None
    gaps.sort()
    mid = len(gaps) // 2
    return round(gaps[mid] if len(gaps) % 2 else (gaps[mid - 1] + gaps[mid]) / 2, 1)


class TestSendIn(BaseModel):
    to: str
    text: str = "Test message from GLC Zone CRM"


def register(api, db, current_user, send_platform_message, log_activity):
    async def get(url: str, **kw) -> requests.Response:
        return await asyncio.to_thread(requests.get, url, timeout=12, **kw)

    async def live_check(key: str) -> Dict[str, Any]:
        """One real call per channel so 'ready' means the credentials actually work."""
        try:
            if key == "TELEGRAM":
                tok = os.environ.get("TELEGRAM_BOT_TOKEN", "")
                r = await get(f"https://api.telegram.org/bot{tok}/getMe")
                j = r.json()
                return {"ok": bool(j.get("ok")), "name": "@" + j["result"]["username"] if j.get("ok") else None, "error": None if j.get("ok") else j.get("description", "Telegram rejected the token")}
            if key == "FACEBOOK":
                r = await get(f"https://graph.facebook.com/{FB_API}/{os.environ.get('FB_PAGE_ID')}", params={"fields": "name", "access_token": os.environ.get("FB_PAGE_ACCESS_TOKEN", "")})
                return {"ok": r.ok, "name": r.json().get("name") if r.ok else None, "error": None if r.ok else r.json().get("error", {}).get("message", "Facebook rejected the token")}
            if key == "INSTAGRAM":
                r = await get(f"https://graph.facebook.com/{FB_API}/{os.environ.get('IG_BUSINESS_ACCOUNT_ID')}", params={"fields": "username", "access_token": os.environ.get("FB_PAGE_ACCESS_TOKEN", "")})
                return {"ok": r.ok, "name": "@" + r.json().get("username", "") if r.ok else None, "error": None if r.ok else r.json().get("error", {}).get("message", "Instagram rejected the token")}
            if key == "WHATSAPP":
                r = await get(f"https://graph.facebook.com/{FB_API}/{os.environ.get('WHATSAPP_PHONE_NUMBER_ID')}", params={"fields": "display_phone_number,verified_name", "access_token": os.environ.get("WHATSAPP_ACCESS_TOKEN", "")})
                j = r.json()
                return {"ok": r.ok, "name": f"{j.get('verified_name', '')} {j.get('display_phone_number', '')}".strip() if r.ok else None, "error": None if r.ok else j.get("error", {}).get("message", "WhatsApp rejected the token")}
        except Exception as e:  # network trouble must not break the page
            return {"ok": False, "name": None, "error": str(e)[:160]}
        return {"ok": True, "name": None, "error": None}

    @api.get("/ocm/channels")
    async def ocm_channels(user=Depends(current_user)):
        cfg = channel_config()
        checks = await asyncio.gather(*[live_check(c["key"]) if c["ready"] and c["key"] != "WEBCHAT" else asyncio.sleep(0, result=None) for c in cfg])
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        for c, chk in zip(cfg, checks):
            c["live"] = chk
            c["contacts"] = await db.ocm_contacts.count_documents({"channels": c["key"]})
            c["conversations"] = await db.ocm_conversations.count_documents({"channel": c["key"]})
            c["messages30"] = await db.ocm_messages.count_documents({"channel": c["key"], "createdAt": {"$gte": since}})
            lastmsg = await db.ocm_messages.find({"channel": c["key"]}, {"_id": 0, "createdAt": 1}).sort("createdAt", -1).limit(1).to_list(1)
            c["lastMessageAt"] = lastmsg[0]["createdAt"] if lastmsg else None
        return {"items": cfg}

    @api.post("/ocm/channels/{key}/test")
    async def ocm_channel_test(key: str, body: TestSendIn, user=Depends(current_user)):
        key = key.upper()
        if key not in CHANNELS or key == "WEBCHAT":
            raise HTTPException(400, "This channel cannot send a test message")
        if not body.to.strip():
            raise HTTPException(400, "Enter the recipient id")
        field = CHANNELS[key]["contactField"]
        res = await asyncio.to_thread(send_platform_message, key, {field: body.to.strip()}, body.text)
        await log_activity(user["id"], "ocm.channels", "test", key, {"ok": bool(res.get("success"))})
        if not res.get("success"):
            err = res.get("error") or (res.get("response") or {}).get("error", {}).get("message") or (res.get("response") or {}).get("description") or "Send failed"
            raise HTTPException(400, str(err))
        return {"ok": True}

    @api.get("/ocm/reports")
    async def ocm_reports(days: int = 30, user=Depends(current_user)):
        days = max(1, min(days, 90))
        since_dt = datetime.now(timezone.utc) - timedelta(days=days)
        since = since_dt.isoformat()

        per_channel: Dict[str, Dict[str, int]] = {}
        async for g in db.ocm_messages.aggregate([
            {"$match": {"createdAt": {"$gte": since}}},
            {"$group": {"_id": {"c": "$channel", "d": "$direction"}, "n": {"$sum": 1}}}]):
            ch = g["_id"].get("c") or "OTHER"
            per_channel.setdefault(ch, {"in": 0, "out": 0})["in" if g["_id"].get("d") == "IN" else "out"] += g["n"]

        daily_rows = []
        async for g in db.ocm_messages.aggregate([
            {"$match": {"createdAt": {"$gte": since}}},
            {"$group": {"_id": {"$substr": ["$createdAt", 0, 10]},
                        "in": {"$sum": {"$cond": [{"$eq": ["$direction", "IN"]}, 1, 0]}},
                        "out": {"$sum": {"$cond": [{"$eq": ["$direction", "OUT"]}, 1, 0]}}}}]):
            daily_rows.append(g)

        status: Dict[str, int] = {}
        async for g in db.ocm_conversations.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
            status[g["_id"] or "OPEN"] = g["n"]

        # median first-reply time on the most recent conversations
        pairs = []
        for conv in await db.ocm_conversations.find({}, {"_id": 0, "id": 1}).sort("lastMessageAt", -1).limit(100).to_list(100):
            msgs = await db.ocm_messages.find({"conversationId": conv["id"]}, {"_id": 0, "direction": 1, "createdAt": 1}).sort("createdAt", 1).to_list(200)
            first_in = next((m for m in msgs if m["direction"] == "IN"), None)
            if first_in:
                reply = next((m for m in msgs if m["direction"] == "OUT" and m["createdAt"] >= first_in["createdAt"]), None)
                if reply:
                    pairs.append({"inAt": first_in["createdAt"], "outAt": reply["createdAt"]})

        posts: Dict[str, int] = {}
        async for g in db.social_posts.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
            posts[g["_id"] or "DRAFT"] = g["n"]

        return {
            "days": days,
            "channels": [{"key": k, "label": CHANNELS.get(k, {}).get("label", k), **v} for k, v in sorted(per_channel.items(), key=lambda kv: -(kv[1]["in"] + kv[1]["out"]))],
            "daily": daily_buckets(daily_rows, days),
            "conversations": status,
            "medianFirstReplyMinutes": response_minutes(pairs),
            "contacts": await db.ocm_contacts.count_documents({}),
            "newContacts": await db.ocm_contacts.count_documents({"createdAt": {"$gte": since}}),
            "posts": posts,
        }
