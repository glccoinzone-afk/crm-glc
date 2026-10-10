"""WhatsApp CRM add-on for the OCM module: Meta template manager, template campaigns with scheduling and
delivery tracking, segments/tags/CSV import, opt-in/out, canned replies, conversation assignment and notes,
and short links with click tracking.

The top half is pure Python (no database, no web framework) so it can be unit tested on its own;
`register()` wires everything into the FastAPI app that server.py already builds.
"""
import asyncio
import csv
import hashlib
import hmac
import io
import json
import logging
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel

log = logging.getLogger("glc.wa")

GRAPH_VERSION = os.environ.get("WHATSAPP_API_VERSION", "v20.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
STOP_WORDS = {"stop", "unsubscribe", "optout", "opt out", "cancel"}
STATUS_RANK = {"QUEUED": 0, "SENT": 1, "DELIVERED": 2, "READ": 3}
TEMPLATE_CATEGORIES = ("MARKETING", "UTILITY", "AUTHENTICATION")
MAX_MEDIA_BYTES = 16 * 1024 * 1024
MEDIA_TYPES = {  # extension -> (header format, mime) as WhatsApp accepts them
    ".jpg": ("IMAGE", "image/jpeg"), ".jpeg": ("IMAGE", "image/jpeg"), ".png": ("IMAGE", "image/png"),
    ".mp4": ("VIDEO", "video/mp4"), ".3gp": ("VIDEO", "video/3gpp"),
    ".pdf": ("DOCUMENT", "application/pdf"),
}


def media_kind(filename: str) -> Optional[Tuple[str, str]]:
    """(HEADER format, mime type) for an uploaded file name, or None when WhatsApp cannot use it."""
    return MEDIA_TYPES.get(os.path.splitext(filename or "")[1].lower())


# ------------------------------------------------------------------ pure helpers
def normalize_phone(raw: Any, default_cc: str = "91") -> Optional[str]:
    """Digits-only WhatsApp number with country code, or None when it cannot be a real number."""
    digits = re.sub(r"\D", "", str(raw or ""))
    digits = digits.lstrip("0") if len(digits) == 11 and digits.startswith("0") else digits
    if len(digits) == 10:
        digits = default_cc + digits
    if 11 <= len(digits) <= 15:
        return digits
    return None


def split_tags(raw: Any) -> List[str]:
    if isinstance(raw, list):
        items = raw
    else:
        items = re.split(r"[;,|]", str(raw or ""))
    seen, out = set(), []
    for t in items:
        t = str(t).strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def parse_contacts_csv(text: str, default_cc: str = "91") -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Rows from a CSV with a header (name, phone, email, tags, vertical). Returns (contacts, errors); duplicates inside the file are dropped."""
    reader = csv.DictReader(io.StringIO((text or "").lstrip("﻿")))
    rows, errors, seen = [], [], set()
    for i, raw in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        phone = normalize_phone(row.get("phone") or row.get("mobile") or row.get("whatsapp"), default_cc)
        if not phone:
            errors.append({"line": i, "reason": "Invalid phone number", "value": row.get("phone") or row.get("mobile") or ""})
            continue
        if phone in seen:
            errors.append({"line": i, "reason": "Duplicate in file", "value": phone})
            continue
        seen.add(phone)
        rows.append({
            "name": row.get("name") or phone,
            "phone": phone,
            "email": row.get("email") or None,
            "tags": split_tags(row.get("tags")),
            "vertical": row.get("vertical") or None,
        })
    return rows, errors


def build_segment_filter(seg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Mongo filter for a campaign audience. Opted-out and unsubscribed contacts are always excluded."""
    seg = seg or {}
    filt: Dict[str, Any] = {"subscribed": {"$ne": False}, "optedOut": {"$ne": True}}
    all_tags = split_tags(seg.get("tags"))
    any_tags = split_tags(seg.get("anyTags"))
    not_tags = split_tags(seg.get("excludeTags"))
    tag_cond: Dict[str, Any] = {}
    if all_tags:
        tag_cond["$all"] = all_tags
    if any_tags:
        tag_cond["$in"] = any_tags
    if not_tags:
        tag_cond["$nin"] = not_tags
    if tag_cond:
        filt["tags"] = tag_cond
    if seg.get("vertical") and seg["vertical"] != "ALL":
        filt["vertical"] = seg["vertical"]
    if seg.get("channel"):
        filt["channels"] = seg["channel"]
    if seg.get("search"):
        rx = {"$regex": re.escape(str(seg["search"])), "$options": "i"}
        filt["$or"] = [{"name": rx}, {"phone": rx}, {"email": rx}]
    return filt


def template_param_count(text: str) -> int:
    nums = [int(n) for n in re.findall(r"\{\{\s*(\d+)\s*\}\}", text or "")]
    return max(nums) if nums else 0


def render_template_body(text: str, params: List[str]) -> str:
    def sub(m):
        i = int(m.group(1)) - 1
        return params[i] if 0 <= i < len(params) else m.group(0)
    return re.sub(r"\{\{\s*(\d+)\s*\}\}", sub, text or "")


def clean_param(value: Any) -> str:
    """Meta rejects template parameters with newlines, tabs or 4+ spaces (#132018) and empty ones (#131008)."""
    s = re.sub(r"[\r\n\t]+", " ", str(value if value is not None else ""))
    s = re.sub(r" {2,}", " ", s).strip()
    return s or "-"


def fill_params(spec: List[str], contact: Dict[str, Any]) -> List[str]:
    """Campaign parameter spec such as ["{{name}}", "10% off"] -> values for one contact."""
    first = (contact.get("name") or "").split(" ")[0] if contact.get("name") else ""
    values = {"name": contact.get("name") or "", "first_name": first, "phone": contact.get("phone") or "", "email": contact.get("email") or ""}

    def sub(m):
        return values.get(m.group(1).strip().lower(), "")
    return [clean_param(re.sub(r"\{\{\s*([a-zA-Z_]+)\s*\}\}", sub, str(p))) for p in (spec or [])]


def build_template_create_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Meta message_templates payload from the simple form the UI posts. Raises ValueError with a readable reason."""
    name = (data.get("name") or "").strip()
    if not re.fullmatch(r"[a-z0-9_]{1,512}", name):
        raise ValueError("Template name can only have lowercase letters, numbers and underscores")
    category = (data.get("category") or "UTILITY").upper()
    if category not in TEMPLATE_CATEGORIES:
        raise ValueError("Category must be Marketing, Utility or Authentication")
    body = (data.get("body") or "").strip()
    if not body:
        raise ValueError("Body text is required")
    if len(body) > 1024:
        raise ValueError("Body can be at most 1024 characters")
    n = template_param_count(body)
    examples = [str(e) for e in (data.get("examples") or [])]
    if n and len(examples) < n:
        raise ValueError(f"Add a sample value for each of the {n} variables")
    components: List[Dict[str, Any]] = []
    header = (data.get("header") or "").strip()
    header_format = (data.get("headerFormat") or "TEXT").upper()
    if header_format in ("IMAGE", "VIDEO", "DOCUMENT"):
        if not data.get("headerHandle"):
            raise ValueError(f"Upload a sample {header_format.lower()} for the header")
        components.append({"type": "HEADER", "format": header_format, "example": {"header_handle": [data["headerHandle"]]}})
    elif header:
        if len(header) > 60:
            raise ValueError("Header can be at most 60 characters")
        components.append({"type": "HEADER", "format": "TEXT", "text": header})
    body_comp: Dict[str, Any] = {"type": "BODY", "text": body}
    if n:
        body_comp["example"] = {"body_text": [examples[:n]]}
    components.append(body_comp)
    footer = (data.get("footer") or "").strip()
    if footer:
        if len(footer) > 60:
            raise ValueError("Footer can be at most 60 characters")
        components.append({"type": "FOOTER", "text": footer})
    buttons = []
    for b in (data.get("buttons") or [])[:3]:
        text = (b.get("text") or "").strip()
        if not text:
            continue
        if b.get("type") == "URL":
            if not (b.get("url") or "").startswith("http"):
                raise ValueError("A URL button needs a full link starting with http")
            buttons.append({"type": "URL", "text": text[:25], "url": b["url"]})
        elif b.get("type") == "PHONE_NUMBER":
            buttons.append({"type": "PHONE_NUMBER", "text": text[:25], "phone_number": "+" + re.sub(r"\D", "", b.get("phone") or "")})
        else:
            buttons.append({"type": "QUICK_REPLY", "text": text[:25]})
    if buttons:
        components.append({"type": "BUTTONS", "buttons": buttons})
    return {"name": name, "language": data.get("language") or "en", "category": category, "components": components}


def build_template_send_payload(to: str, name: str, language: str, params: List[str], header_media: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """header_media: {"format": "IMAGE"|"VIDEO"|"DOCUMENT", "id": "<WhatsApp media id>", "filename": optional for documents}."""
    payload: Dict[str, Any] = {
        "messaging_product": "whatsapp", "to": to, "type": "template",
        "template": {"name": name, "language": {"code": language or "en"}},
    }
    components: List[Dict[str, Any]] = []
    if header_media:
        kind = header_media["format"].lower()
        media: Dict[str, Any] = {"id": header_media["id"]}
        if kind == "document" and header_media.get("filename"):
            media["filename"] = header_media["filename"]
        components.append({"type": "header", "parameters": [{"type": kind, kind: media}]})
    if params:
        components.append({"type": "body", "parameters": [{"type": "text", "text": clean_param(p)} for p in params]})
    if components:
        payload["template"]["components"] = components
    return payload


def parse_status_webhook(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for entry in (body or {}).get("entry", []):
        for change in entry.get("changes", []):
            for st in (change.get("value") or {}).get("statuses", []) or []:
                err = (st.get("errors") or [{}])[0]
                out.append({
                    "waMessageId": st.get("id"), "status": str(st.get("status", "")).upper(), "to": st.get("recipient_id"),
                    "error": (err.get("title") or err.get("message") or "") if st.get("errors") else "",
                    "errorCode": err.get("code") if st.get("errors") else None,
                })
    return out


def parse_inbound_webhook(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for entry in (body or {}).get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts", []) or []}
            for m in value.get("messages", []) or []:
                text = ""
                if m.get("type") == "text":
                    text = (m.get("text") or {}).get("body", "")
                elif m.get("type") == "button":
                    text = (m.get("button") or {}).get("text", "")
                elif m.get("type") == "interactive":
                    inter = m.get("interactive") or {}
                    text = (inter.get("button_reply") or inter.get("list_reply") or {}).get("title", "")
                out.append({"from": m.get("from"), "name": names.get(m.get("from")), "text": text, "id": m.get("id"), "type": m.get("type")})
    return out


def is_stop_request(text: str) -> bool:
    return re.sub(r"[^a-z ]", "", (text or "").lower()).strip() in STOP_WORDS


def advance_status(current: str, new: str) -> str:
    """Delivery receipts can arrive out of order; never move READ back to DELIVERED. FAILED always wins."""
    if new == "FAILED":
        return "FAILED"
    if new not in STATUS_RANK:
        return current
    return new if STATUS_RANK.get(new, 0) > STATUS_RANK.get(current, 0) else current


def new_short_code() -> str:
    return secrets.token_urlsafe(5).replace("-", "a").replace("_", "b")[:7]


def relay_signature(secret: str, statuses: List[Dict[str, Any]]) -> str:
    """HMAC over 'id|status' lines; the Laravel store builds the same string so no JSON canonicalisation is needed."""
    text = "\n".join(f"{x.get('waMessageId')}|{str(x.get('status', '')).upper()}" for x in statuses)
    return hmac.new(secret.encode(), text.encode(), hashlib.sha256).hexdigest()


def verify_meta_signature(raw: bytes, header: str, secret: str) -> bool:
    if not secret:
        return True
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header or "")


# ------------------------------------------------------------------ Meta media (sync; callers use asyncio.to_thread)
MEDIA_DIR = os.environ.get("CRM_MEDIA_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads_wa")


def _meta_err(r: requests.Response) -> str:
    try:
        e = r.json().get("error", {})
        return e.get("error_user_msg") or e.get("message") or r.text[:200]
    except Exception:
        return r.text[:200]


def meta_upload_media(token: str, phone_id: str, path: str, mime: str) -> str:
    """Upload a local file to WhatsApp and return its media id (valid for about 30 days). Raises RuntimeError with Meta's reason."""
    with open(path, "rb") as fh:
        r = requests.post(f"{GRAPH}/{phone_id}/media", headers={"Authorization": f"Bearer {token}"},
                          data={"messaging_product": "whatsapp", "type": mime},
                          files={"file": (os.path.basename(path), fh, mime)}, timeout=120)
    if not r.ok:
        raise RuntimeError(_meta_err(r))
    return r.json()["id"]


def meta_resumable_handle(token: str, path: str, mime: str) -> str:
    """Header sample handle for template creation (Meta Resumable Upload API). Raises RuntimeError with Meta's reason."""
    dbg = requests.get(f"{GRAPH}/debug_token", params={"input_token": token, "access_token": token}, timeout=20)
    app_id = (dbg.json().get("data") or {}).get("app_id") if dbg.ok else None
    if not app_id:
        raise RuntimeError("Could not find the Meta app id for this token")
    size = os.path.getsize(path)
    start = requests.post(f"{GRAPH}/{app_id}/uploads", params={"file_length": size, "file_type": mime, "file_name": os.path.basename(path), "access_token": token}, timeout=30)
    if not start.ok:
        raise RuntimeError(_meta_err(start))
    with open(path, "rb") as fh:
        up = requests.post(f"{GRAPH}/{start.json()['id']}", headers={"Authorization": f"OAuth {token}", "file_offset": "0"}, data=fh.read(), timeout=180)
    if not up.ok or not up.json().get("h"):
        raise RuntimeError(_meta_err(up))
    return up.json()["h"]


def meta_send_media(token: str, phone_id: str, to: str, fmt: str, media_id: str, caption: str = "", filename: str = "") -> Dict[str, Any]:
    """Send an image/video/document inside the 24-hour window (used by chatbot flows and the inbox)."""
    kind = fmt.lower()
    body: Dict[str, Any] = {"id": media_id}
    if caption:
        body["caption"] = caption
    if kind == "document" and filename:
        body["filename"] = filename
    r = requests.post(f"{GRAPH}/{phone_id}/messages", headers={"Authorization": f"Bearer {token}"},
                      json={"messaging_product": "whatsapp", "to": to, "type": kind, kind: body}, timeout=30)
    if r.ok:
        return {"success": True, "id": ((r.json().get("messages") or [{}])[0]).get("id")}
    return {"success": False, "error": _meta_err(r)}


_media_id_cache: Dict[str, Tuple[str, float]] = {}


def cached_media_id(token: str, phone_id: str, path: str, mime: str, ttl: float = 25 * 24 * 3600) -> str:
    """WhatsApp media ids last ~30 days; reuse one for 25 days per file instead of uploading for every message."""
    import time
    hit = _media_id_cache.get(path)
    if hit and time.time() - hit[1] < ttl:
        return hit[0]
    mid = meta_upload_media(token, phone_id, path, mime)
    _media_id_cache[path] = (mid, time.time())
    return mid


def media_file_path(doc: Dict[str, Any]) -> str:
    return os.path.join(MEDIA_DIR, doc["stored"])


# ------------------------------------------------------------------ request models
class TemplateIn(BaseModel):
    name: str
    category: str = "UTILITY"
    language: str = "en"
    header: Optional[str] = None
    body: str
    footer: Optional[str] = None
    examples: List[str] = []
    buttons: List[Dict[str, Any]] = []
    headerFormat: str = "TEXT"
    headerMediaId: Optional[str] = None


class ImportIn(BaseModel):
    csv: str
    tags: List[str] = []
    defaultCountryCode: str = "91"


class BulkTagIn(BaseModel):
    ids: List[str] = []
    add: List[str] = []
    remove: List[str] = []


class SegmentIn(BaseModel):
    name: str
    filter: Dict[str, Any] = {}


class CampaignIn(BaseModel):
    name: str
    templateName: str
    language: str = "en"
    params: List[str] = []
    segment: Dict[str, Any] = {}
    segmentId: Optional[str] = None
    scheduledAt: Optional[str] = None
    mediaFileId: Optional[str] = None


class CannedIn(BaseModel):
    title: str
    text: str
    shortcut: Optional[str] = None


class NoteIn(BaseModel):
    text: str


class AssignIn(BaseModel):
    agentId: Optional[str] = None


class LinkIn(BaseModel):
    url: str
    name: Optional[str] = None


class WaSettingsIn(BaseModel):
    wabaId: Optional[str] = None


# ------------------------------------------------------------------ wiring
def register(app, api, db, current_user, uid, now_iso, clean, log_activity):
    """Add the routes and the campaign scheduler. Call before app.include_router(api)."""

    async def cfg() -> Dict[str, str]:
        saved = await db.ocm_settings.find_one({"key": "whatsapp"}, {"_id": 0}) or {}
        return {
            "token": os.environ.get("WHATSAPP_ACCESS_TOKEN", ""),
            "phoneId": os.environ.get("WHATSAPP_PHONE_NUMBER_ID", ""),
            "wabaId": saved.get("wabaId") or os.environ.get("WHATSAPP_WABA_ID", ""),
        }

    def meta_error(r: requests.Response) -> str:
        try:
            e = r.json().get("error", {})
            return e.get("error_user_msg") or e.get("message") or r.text[:200]
        except Exception:
            return r.text[:200]

    async def graph(method: str, path: str, token: str, **kw) -> requests.Response:
        return await asyncio.to_thread(
            requests.request, method, f"{GRAPH}/{path}", headers={"Authorization": f"Bearer {token}"}, timeout=20, **kw)

    async def need_waba() -> Dict[str, str]:
        c = await cfg()
        if not c["token"]:
            raise HTTPException(400, "WhatsApp access token is not set on the server")
        if not c["wabaId"]:
            raise HTTPException(400, "WhatsApp Business Account ID is not set. Add it under WhatsApp Setup.")
        return c

    # ---------------- connection / settings
    @api.get("/ocm/wa/settings")
    async def wa_get_settings(user=Depends(current_user)):
        c = await cfg()
        info: Dict[str, Any] = {"tokenSet": bool(c["token"]), "phoneId": c["phoneId"], "wabaId": c["wabaId"], "lastReceiptAt": (await db.ocm_settings.find_one({"key": "whatsapp"}, {"_id": 0}) or {}).get("lastReceiptAt")}
        if c["token"] and c["phoneId"]:
            r = await graph("GET", f"{c['phoneId']}?fields=display_phone_number,verified_name,quality_rating,name_status", c["token"])
            info["phone"] = r.json() if r.ok else {"error": meta_error(r)}
        if c["token"] and c["wabaId"]:
            r = await graph("GET", f"{c['wabaId']}?fields=name,currency,message_template_namespace", c["token"])
            info["waba"] = r.json() if r.ok else {"error": meta_error(r)}
        return info

    @api.put("/ocm/wa/settings")
    async def wa_put_settings(body: WaSettingsIn, user=Depends(current_user)):
        waba = re.sub(r"\D", "", body.wabaId or "")
        await db.ocm_settings.update_one({"key": "whatsapp"}, {"$set": {"key": "whatsapp", "wabaId": waba, "updatedAt": now_iso()}}, upsert=True)
        return await wa_get_settings(user)

    # ---------------- templates
    @api.get("/ocm/wa/templates")
    async def wa_list_templates(refresh: bool = False, user=Depends(current_user)):
        c = await cfg()
        cached = await db.ocm_wa_templates.find({}, {"_id": 0}).sort("name", 1).to_list(500)
        if not (c["token"] and c["wabaId"]):
            return {"items": cached, "live": False, "error": "WhatsApp Business Account ID is not set"}
        if cached and not refresh:
            return {"items": cached, "live": False}
        items, url = [], f"{c['wabaId']}/message_templates?limit=100&fields=name,status,category,language,components,rejected_reason,quality_score"
        for _ in range(10):
            r = await graph("GET", url, c["token"])
            if not r.ok:
                return {"items": cached, "live": False, "error": meta_error(r)}
            j = r.json()
            items += j.get("data", [])
            nxt = (j.get("paging") or {}).get("next")
            if not nxt:
                break
            url = re.sub(r"^https://graph\.facebook\.com/v[\d.]+/", "", nxt)
        for t in items:
            body = next((x.get("text", "") for x in t.get("components", []) if x.get("type") == "BODY"), "")
            head = next((x for x in t.get("components", []) if x.get("type") == "HEADER"), {})
            t.update({"id": t.get("id") or t["name"], "body": body, "paramCount": template_param_count(body), "headerFormat": head.get("format", "NONE"), "syncedAt": now_iso()})
            await db.ocm_wa_templates.update_one({"name": t["name"], "language": t.get("language")}, {"$set": t}, upsert=True)
        names = {(t["name"], t.get("language")) for t in items}
        for old in cached:
            if (old["name"], old.get("language")) not in names:
                await db.ocm_wa_templates.delete_one({"name": old["name"], "language": old.get("language")})
        return {"items": sorted(items, key=lambda t: t["name"]), "live": True}

    @api.post("/ocm/wa/media")
    async def wa_upload_media(file: UploadFile = File(...), user=Depends(current_user)):
        kind = media_kind(file.filename or "")
        if not kind:
            raise HTTPException(400, "Use a JPG or PNG image, an MP4 video, or a PDF")
        data = await file.read()
        if len(data) > MAX_MEDIA_BYTES:
            raise HTTPException(400, "File is too large (16 MB maximum)")
        if kind[0] == "IMAGE" and len(data) > 5 * 1024 * 1024:
            raise HTTPException(400, "WhatsApp images can be at most 5 MB")
        os.makedirs(MEDIA_DIR, exist_ok=True)
        fid = uid()
        stored = fid + os.path.splitext(file.filename)[1].lower()
        with open(os.path.join(MEDIA_DIR, stored), "wb") as fh:
            fh.write(data)
        doc = {"id": fid, "filename": file.filename, "stored": stored, "format": kind[0], "mime": kind[1], "size": len(data), "createdAt": now_iso(), "createdBy": user["name"]}
        await db.ocm_media.insert_one(dict(doc))
        return doc

    @api.post("/ocm/wa/templates")
    async def wa_create_template(body: TemplateIn, user=Depends(current_user)):
        c = await need_waba()
        data = body.model_dump()
        if body.headerFormat.upper() in ("IMAGE", "VIDEO", "DOCUMENT"):
            media = await db.ocm_media.find_one({"id": body.headerMediaId or ""}, {"_id": 0})
            if not media or media["format"] != body.headerFormat.upper():
                raise HTTPException(400, f"Upload a sample {body.headerFormat.lower()} for the header")
            try:
                data["headerHandle"] = await asyncio.to_thread(meta_resumable_handle, c["token"], media_file_path(media), media["mime"])
            except RuntimeError as e:
                raise HTTPException(400, f"Could not upload the sample: {e}")
        try:
            payload = build_template_create_payload(data)
        except ValueError as e:
            raise HTTPException(400, str(e))
        r = await graph("POST", f"{c['wabaId']}/message_templates", c["token"], json=payload)
        if not r.ok:
            raise HTTPException(400, meta_error(r))
        await log_activity(user["id"], "ocm.templates", "create", payload["name"], {"category": payload["category"]})
        return {"ok": True, "meta": r.json()}

    @api.delete("/ocm/wa/templates/{name}")
    async def wa_delete_template(name: str, user=Depends(current_user)):
        c = await need_waba()
        r = await graph("DELETE", f"{c['wabaId']}/message_templates?name={name}", c["token"])
        if not r.ok:
            raise HTTPException(400, meta_error(r))
        await db.ocm_wa_templates.delete_many({"name": name})
        return {"ok": True}

    # ---------------- contacts: edit, tags, import, opt-out, segments
    @api.put("/ocm/contacts/{cid}")
    async def ocm_update_contact(cid: str, body: Dict[str, Any], user=Depends(current_user)):
        allowed = {k: body[k] for k in ("name", "phone", "email", "tags", "vertical", "subscribed", "channels") if k in body}
        if "tags" in allowed:
            allowed["tags"] = split_tags(allowed["tags"])
        if "phone" in allowed:
            allowed["phone"] = normalize_phone(allowed["phone"]) or allowed["phone"]
        allowed["updatedAt"] = now_iso()
        await db.ocm_contacts.update_one({"id": cid}, {"$set": allowed})
        doc = await db.ocm_contacts.find_one({"id": cid}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Not found")
        return doc

    @api.delete("/ocm/contacts/{cid}")
    async def ocm_delete_contact(cid: str, user=Depends(current_user)):
        await db.ocm_contacts.delete_one({"id": cid})
        return {"ok": True}

    @api.get("/ocm/contacts-tags")
    async def ocm_contact_tags(user=Depends(current_user)):
        tags = await db.ocm_contacts.distinct("tags")
        return {"items": sorted({t for t in tags if t}, key=str.lower)}

    @api.post("/ocm/contacts-import")
    async def ocm_import_contacts(body: ImportIn, user=Depends(current_user)):
        rows, errors = parse_contacts_csv(body.csv, body.defaultCountryCode)
        created = updated = 0
        extra = split_tags(body.tags)
        for r in rows:
            existing = await db.ocm_contacts.find_one({"$or": [{"phone": r["phone"]}, {"whatsappId": r["phone"]}]})
            if existing:
                add = {"$addToSet": {"tags": {"$each": r["tags"] + extra}, "channels": "WHATSAPP"}, "$set": {"updatedAt": now_iso()}}
                if r["email"] and not existing.get("email"):
                    add["$set"]["email"] = r["email"]
                await db.ocm_contacts.update_one({"id": existing["id"]}, add)
                updated += 1
            else:
                await db.ocm_contacts.insert_one({
                    "id": uid(), "name": r["name"], "phone": r["phone"], "whatsappId": r["phone"], "email": r["email"],
                    "channels": ["WHATSAPP"], "tags": split_tags(r["tags"] + extra), "vertical": r["vertical"],
                    "subscribed": True, "optedOut": False, "source": "CSV", "createdAt": now_iso(), "updatedAt": now_iso()})
                created += 1
        await log_activity(user["id"], "ocm.contacts", "import", None, {"created": created, "updated": updated, "errors": len(errors)})
        return {"created": created, "updated": updated, "errors": errors[:200], "errorCount": len(errors)}

    @api.post("/ocm/contacts-bulk-tag")
    async def ocm_bulk_tag(body: BulkTagIn, user=Depends(current_user)):
        if not body.ids:
            raise HTTPException(400, "Select at least one contact")
        if body.add:
            await db.ocm_contacts.update_many({"id": {"$in": body.ids}}, {"$addToSet": {"tags": {"$each": split_tags(body.add)}}})
        if body.remove:
            await db.ocm_contacts.update_many({"id": {"$in": body.ids}}, {"$pull": {"tags": {"$in": split_tags(body.remove)}}})
        return {"ok": True}

    @api.post("/ocm/contacts/{cid}/opt")
    async def ocm_contact_opt(cid: str, body: Dict[str, Any], user=Depends(current_user)):
        out = bool(body.get("optedOut"))
        await db.ocm_contacts.update_one({"id": cid}, {"$set": {"optedOut": out, "subscribed": not out, "optedOutAt": now_iso() if out else None, "updatedAt": now_iso()}})
        return {"ok": True}

    @api.get("/ocm/segments")
    async def ocm_list_segments(user=Depends(current_user)):
        items = await db.ocm_segments.find({}, {"_id": 0}).sort("name", 1).to_list(200)
        for s in items:
            s["count"] = await db.ocm_contacts.count_documents(build_segment_filter(s.get("filter")))
        return {"items": items}

    @api.post("/ocm/segments")
    async def ocm_create_segment(body: SegmentIn, user=Depends(current_user)):
        doc = {"id": uid(), "name": body.name.strip(), "filter": body.filter, "createdAt": now_iso(), "createdBy": user["name"]}
        if not doc["name"]:
            raise HTTPException(400, "Segment name is required")
        await db.ocm_segments.insert_one(dict(doc))
        return doc

    @api.delete("/ocm/segments/{sid}")
    async def ocm_delete_segment(sid: str, user=Depends(current_user)):
        await db.ocm_segments.delete_one({"id": sid})
        return {"ok": True}

    @api.post("/ocm/segments-preview")
    async def ocm_preview_segment(body: Dict[str, Any], user=Depends(current_user)):
        filt = build_segment_filter(body.get("filter") if "filter" in body else body)
        filt["phone"] = {"$nin": [None, ""]}
        sample = await db.ocm_contacts.find(filt, {"_id": 0, "name": 1, "phone": 1}).limit(5).to_list(5)
        return {"count": await db.ocm_contacts.count_documents(filt), "sample": sample}

    # ---------------- campaigns
    async def audience(c: Dict[str, Any]) -> List[Dict[str, Any]]:
        seg = c.get("segment") or {}
        if c.get("segmentId"):
            s = await db.ocm_segments.find_one({"id": c["segmentId"]}, {"_id": 0})
            seg = (s or {}).get("filter", seg)
        filt = build_segment_filter(seg)
        filt["phone"] = {"$nin": [None, ""]}
        return await db.ocm_contacts.find(filt, {"_id": 0}).to_list(20000)

    async def send_template(conf: Dict[str, str], to: str, name: str, lang: str, params: List[str], header_media: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        if not conf["token"] or not conf["phoneId"]:
            return {"ok": False, "error": "WhatsApp credentials are not configured"}
        try:
            r = await graph("POST", f"{conf['phoneId']}/messages", conf["token"], json=build_template_send_payload(to, name, lang, params, header_media))
        except Exception as e:  # network error
            return {"ok": False, "error": str(e)[:200]}
        if r.ok:
            return {"ok": True, "id": ((r.json().get("messages") or [{}])[0]).get("id")}
        return {"ok": False, "error": meta_error(r)}

    async def run_campaign(cid: str) -> Dict[str, Any]:
        camp = await db.ocm_campaigns.find_one_and_update(
            {"id": cid, "status": {"$in": ["DRAFT", "SCHEDULED"]}}, {"$set": {"status": "SENDING", "startedAt": now_iso()}})
        if not camp:
            return {"ok": False, "error": "Already sent or in progress"}
        conf = await cfg()
        people = await audience(camp)
        tpl = await db.ocm_wa_templates.find_one({"name": camp["templateName"], "language": camp.get("language")}, {"_id": 0}) or {}
        sent = failed = 0
        reasons: Dict[str, int] = {}
        header_media = None
        if camp.get("mediaFileId"):
            media = await db.ocm_media.find_one({"id": camp["mediaFileId"]}, {"_id": 0})
            try:
                if not media:
                    raise RuntimeError("The campaign media file is missing")
                mid = await asyncio.to_thread(meta_upload_media, conf["token"], conf["phoneId"], media_file_path(media), media["mime"])
                header_media = {"format": media["format"], "id": mid, "filename": media["filename"]}
            except Exception as e:
                await db.ocm_campaigns.update_one({"id": cid}, {"$set": {"status": "FAILED", "finishedAt": now_iso(), "audienceSize": len(people), "failureReasons": [{"reason": f"Media upload failed: {e}", "count": len(people)}]}})
                return {"ok": True, "sent": 0, "failed": len(people)}
        for p in people:
            to = normalize_phone(p.get("phone"))
            if not to:
                continue
            params = fill_params(camp.get("params") or [], p)
            res = await send_template(conf, to, camp["templateName"], camp.get("language") or "en", params, header_media)
            await db.ocm_wa_messages.insert_one({
                "id": uid(), "campaignId": cid, "contactId": p.get("id"), "to": to, "waMessageId": res.get("id"),
                "status": "SENT" if res["ok"] else "FAILED", "error": res.get("error", ""), "createdAt": now_iso(),
                "text": render_template_body(tpl.get("body", ""), params)})
            if res["ok"]:
                sent += 1
            else:
                failed += 1
                reasons[res["error"]] = reasons.get(res["error"], 0) + 1
            await asyncio.sleep(0.04)
        await db.ocm_campaigns.update_one({"id": cid}, {"$set": {
            "status": "SENT" if sent or not failed else "FAILED", "finishedAt": now_iso(), "audienceSize": len(people),
            "failureReasons": [{"reason": k, "count": v} for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])[:5]]}})
        return {"ok": True, "sent": sent, "failed": failed}

    async def with_stats(c: Dict[str, Any]) -> Dict[str, Any]:
        counts = {"SENT": 0, "DELIVERED": 0, "READ": 0, "FAILED": 0}
        async for g in db.ocm_wa_messages.aggregate([{"$match": {"campaignId": c["id"]}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
            counts[g["_id"]] = g["n"]
        total = sum(counts.values())
        c["stats"] = {
            "total": total, "failed": counts["FAILED"],
            "sent": total - counts["FAILED"],
            "delivered": counts["DELIVERED"] + counts["READ"], "read": counts["READ"]}
        return c

    @api.get("/ocm/wa/campaigns")
    async def wa_list_campaigns(user=Depends(current_user)):
        items = await db.ocm_campaigns.find({}, {"_id": 0}).sort("createdAt", -1).to_list(200)
        return {"items": [await with_stats(c) for c in items]}

    @api.get("/ocm/wa/campaigns/{cid}")
    async def wa_get_campaign(cid: str, user=Depends(current_user)):
        c = await db.ocm_campaigns.find_one({"id": cid}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Not found")
        msgs = await db.ocm_wa_messages.find({"campaignId": cid}, {"_id": 0}).sort("createdAt", -1).to_list(500)
        return {"campaign": await with_stats(c), "messages": msgs}

    @api.post("/ocm/wa/campaigns")
    async def wa_create_campaign(body: CampaignIn, user=Depends(current_user)):
        tpl = await db.ocm_wa_templates.find_one({"name": body.templateName, "language": body.language}, {"_id": 0})
        if not tpl:
            raise HTTPException(400, "Choose one of your templates (refresh the template list if it is new)")
        if tpl.get("status") != "APPROVED":
            raise HTTPException(400, f"Template is {tpl.get('status', 'not approved')}; only approved templates can be sent")
        need = tpl.get("paramCount", 0)
        if len(body.params) < need:
            raise HTTPException(400, f"This template needs {need} variable(s)")
        head = tpl.get("headerFormat", "NONE")
        if head in ("IMAGE", "VIDEO", "DOCUMENT"):
            media = await db.ocm_media.find_one({"id": body.mediaFileId or ""}, {"_id": 0})
            if not media or media["format"] != head:
                raise HTTPException(400, f"This template needs a {head.lower()} in its header. Upload one.")
        elif body.mediaFileId:
            raise HTTPException(400, "This template has no media header; remove the file")
        scheduled = body.scheduledAt or None
        if scheduled:
            try:
                when = datetime.fromisoformat(scheduled.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(400, "Invalid schedule time")
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            scheduled = when.astimezone(timezone.utc).isoformat()
        doc = {**body.model_dump(), "scheduledAt": scheduled, "id": uid(), "status": "SCHEDULED" if scheduled else "DRAFT",
               "createdAt": now_iso(), "createdBy": user["name"]}
        await db.ocm_campaigns.insert_one(dict(doc))
        return clean(doc)

    @api.post("/ocm/wa/campaigns/{cid}/send")
    async def wa_send_campaign(cid: str, user=Depends(current_user)):
        res = await run_campaign(cid)
        if not res["ok"]:
            raise HTTPException(409, res["error"])
        await log_activity(user["id"], "ocm.campaigns", "send", cid, res)
        return res

    @api.post("/ocm/wa/campaigns/{cid}/cancel")
    async def wa_cancel_campaign(cid: str, user=Depends(current_user)):
        r = await db.ocm_campaigns.update_one({"id": cid, "status": {"$in": ["DRAFT", "SCHEDULED"]}}, {"$set": {"status": "CANCELLED"}})
        if not r.modified_count:
            raise HTTPException(409, "Only draft or scheduled campaigns can be cancelled")
        return {"ok": True}

    @api.post("/ocm/wa/audience-preview")
    async def wa_audience_preview(body: Dict[str, Any], user=Depends(current_user)):
        people = await audience(body)
        return {"count": len(people), "sample": [{"name": p.get("name"), "phone": p.get("phone")} for p in people[:5]]}

    async def scheduler_loop():
        while True:
            try:
                due = await db.ocm_campaigns.find({"status": "SCHEDULED", "scheduledAt": {"$lte": now_iso()}}, {"id": 1}).to_list(5)
                for d in due:
                    log.info("Running scheduled campaign %s", d["id"])
                    await run_campaign(d["id"])
            except Exception:
                log.exception("Campaign scheduler error")
            await asyncio.sleep(30)

    app.router.add_event_handler("startup", lambda: asyncio.create_task(scheduler_loop()))

    # ---------------- Meta webhook (delivery receipts, opt-out replies)
    @api.get("/webhooks/whatsapp")
    async def wa_verify(request: Request):
        q = request.query_params
        token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
        if token and q.get("hub.mode") == "subscribe" and hmac.compare_digest(q.get("hub.verify_token", ""), token):
            return PlainTextResponse(q.get("hub.challenge", ""))
        raise HTTPException(403, "Verification failed")

    async def apply_statuses(statuses: List[Dict[str, Any]]) -> int:
        """Record delivery receipts on campaign messages (or inbox replies). Returns how many were applied."""
        applied = 0
        for st in statuses:
            if not st.get("waMessageId"):
                continue
            doc = await db.ocm_wa_messages.find_one({"waMessageId": st["waMessageId"]})
            if doc:
                new = advance_status(doc.get("status", "SENT"), st["status"])
                upd: Dict[str, Any] = {"status": new, f"at{st['status'].title()}": now_iso()}
                if st["status"] == "FAILED":
                    upd["error"] = st.get("error") or "Failed"
                await db.ocm_wa_messages.update_one({"id": doc["id"]}, {"$set": upd})
                applied += 1
            else:  # reply sent from the inbox
                await db.ocm_messages.update_one({"waMessageId": st["waMessageId"]}, {"$set": {"status": st["status"]}})
        if statuses:
            await db.ocm_settings.update_one({"key": "whatsapp"}, {"$set": {"key": "whatsapp", "lastReceiptAt": now_iso()}}, upsert=True)
        return applied

    @api.post("/ocm/wa/status-relay")
    async def wa_status_relay(request: Request):
        """The store's Meta webhook forwards delivery receipts here, signed with the shared CRM secret."""
        secret = os.environ.get("CRM_SSO_SECRET", "")
        body = await request.json()
        statuses = [{"waMessageId": x.get("id"), "status": str(x.get("status", "")).upper(), "error": x.get("error", "")} for x in body.get("statuses", [])]
        if not secret or not hmac.compare_digest(relay_signature(secret, statuses), str(body.get("sig", ""))):
            raise HTTPException(401, "Invalid signature")
        return {"ok": True, "applied": await apply_statuses(statuses)}

    @api.post("/webhooks/whatsapp")
    async def wa_webhook(request: Request):
        raw = await request.body()
        if not verify_meta_signature(raw, request.headers.get("X-Hub-Signature-256", ""), os.environ.get("WHATSAPP_APP_SECRET", "")):
            raise HTTPException(401, "Invalid signature")
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            raise HTTPException(400, "Bad JSON")
        await apply_statuses(parse_status_webhook(body))
        for m in parse_inbound_webhook(body):
            if is_stop_request(m["text"]):
                await db.ocm_contacts.update_many(
                    {"$or": [{"phone": m["from"]}, {"whatsappId": m["from"]}]},
                    {"$set": {"optedOut": True, "subscribed": False, "optedOutAt": now_iso()}})
        return {"ok": True}

    # ---------------- inbox: assign, notes, canned replies, unread
    @api.get("/ocm/agents")
    async def ocm_agents(user=Depends(current_user)):
        users = await db.users.find({}, {"_id": 0, "id": 1, "name": 1, "role": 1}).sort("name", 1).to_list(500)
        return {"items": users}

    @api.post("/ocm/conversations/{cid}/assign")
    async def ocm_assign(cid: str, body: AssignIn, user=Depends(current_user)):
        agent = None
        if body.agentId:
            agent = await db.users.find_one({"id": body.agentId}, {"_id": 0, "id": 1, "name": 1})
            if not agent:
                raise HTTPException(404, "Agent not found")
        await db.ocm_conversations.update_one({"id": cid}, {"$set": {
            "assignedTo": agent["id"] if agent else None, "assignedName": agent["name"] if agent else None, "updatedAt": now_iso()}})
        return {"ok": True}

    @api.post("/ocm/conversations/{cid}/read")
    async def ocm_mark_read(cid: str, user=Depends(current_user)):
        await db.ocm_conversations.update_one({"id": cid}, {"$set": {"unread": 0}})
        return {"ok": True}

    @api.get("/ocm/conversations/{cid}/notes")
    async def ocm_notes(cid: str, user=Depends(current_user)):
        return {"items": await db.ocm_notes.find({"conversationId": cid}, {"_id": 0}).sort("createdAt", 1).to_list(200)}

    @api.post("/ocm/conversations/{cid}/notes")
    async def ocm_add_note(cid: str, body: NoteIn, user=Depends(current_user)):
        if not body.text.strip():
            raise HTTPException(400, "Note is empty")
        doc = {"id": uid(), "conversationId": cid, "text": body.text.strip(), "by": user["name"], "byId": user["id"], "createdAt": now_iso()}
        await db.ocm_notes.insert_one(dict(doc))
        return doc

    @api.get("/ocm/canned")
    async def ocm_canned(user=Depends(current_user)):
        return {"items": await db.ocm_canned.find({}, {"_id": 0}).sort("title", 1).to_list(200)}

    @api.post("/ocm/canned")
    async def ocm_add_canned(body: CannedIn, user=Depends(current_user)):
        doc = {"id": uid(), "title": body.title.strip(), "text": body.text.strip(), "shortcut": (body.shortcut or "").strip().lstrip("/"), "createdAt": now_iso()}
        if not doc["title"] or not doc["text"]:
            raise HTTPException(400, "Title and text are required")
        await db.ocm_canned.insert_one(dict(doc))
        return doc

    @api.delete("/ocm/canned/{rid}")
    async def ocm_delete_canned(rid: str, user=Depends(current_user)):
        await db.ocm_canned.delete_one({"id": rid})
        return {"ok": True}

    # ---------------- short links with click tracking
    @api.get("/ocm/links")
    async def ocm_links(user=Depends(current_user)):
        return {"items": await db.ocm_links.find({}, {"_id": 0}).sort("createdAt", -1).to_list(300)}

    @api.post("/ocm/links")
    async def ocm_create_link(body: LinkIn, request: Request, user=Depends(current_user)):
        if not body.url.startswith(("http://", "https://")):
            raise HTTPException(400, "Link must start with http:// or https://")
        code = new_short_code()
        base = os.environ.get("PUBLIC_API_URL", "").rstrip("/") or str(request.base_url).rstrip("/") + "/api"
        doc = {"id": uid(), "code": code, "url": body.url, "name": body.name or body.url[:60], "clicks": 0, "shortUrl": f"{base}/r/{code}",
               "createdAt": now_iso(), "createdBy": user["name"]}
        await db.ocm_links.insert_one(dict(doc))
        return doc

    @api.delete("/ocm/links/{lid}")
    async def ocm_delete_link(lid: str, user=Depends(current_user)):
        await db.ocm_links.delete_one({"id": lid})
        return {"ok": True}

    @api.get("/r/{code}")
    async def ocm_redirect(code: str):
        link = await db.ocm_links.find_one_and_update({"code": code}, {"$inc": {"clicks": 1}, "$set": {"lastClickAt": now_iso()}})
        if not link:
            raise HTTPException(404, "Link not found")
        return RedirectResponse(link["url"], status_code=302)

    # ---------------- overview numbers
    @api.get("/ocm/wa/stats")
    async def wa_stats(user=Depends(current_user)):
        subscribed = await db.ocm_contacts.count_documents({"subscribed": {"$ne": False}, "optedOut": {"$ne": True}})
        by_status: Dict[str, int] = {}
        async for g in db.ocm_wa_messages.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
            by_status[g["_id"]] = g["n"]
        tpl: Dict[str, int] = {}
        async for g in db.ocm_wa_templates.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
            tpl[g["_id"] or "UNKNOWN"] = g["n"]
        sent = sum(v for k, v in by_status.items() if k != "FAILED")
        return {
            "contacts": await db.ocm_contacts.count_documents({}), "subscribed": subscribed,
            "optedOut": await db.ocm_contacts.count_documents({"optedOut": True}),
            "campaigns": await db.ocm_campaigns.count_documents({}),
            "scheduled": await db.ocm_campaigns.count_documents({"status": "SCHEDULED"}),
            "messages": {"sent": sent, "delivered": by_status.get("DELIVERED", 0) + by_status.get("READ", 0), "read": by_status.get("READ", 0), "failed": by_status.get("FAILED", 0)},
            "templates": tpl,
            "linkClicks": sum([l.get("clicks", 0) async for l in db.ocm_links.find({}, {"clicks": 1, "_id": 0})]),
        }

