"""Unit tests for the pure helpers in wa_crm (no database, no network)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wa_crm as w  # noqa: E402


def test_normalize_phone():
    assert w.normalize_phone("96082 61539") == "919608261539"
    assert w.normalize_phone("+91 96082-61539") == "919608261539"
    assert w.normalize_phone("09608261539") == "919608261539"
    assert w.normalize_phone("447911123456") == "447911123456"
    assert w.normalize_phone("12345") is None
    assert w.normalize_phone(None) is None


def test_split_tags_dedupes():
    assert w.split_tags("vip, Vip; retail|new") == ["vip", "retail", "new"]
    assert w.split_tags(["a", " a ", "b"]) == ["a", "b"]


def test_parse_contacts_csv():
    text = "Name,Phone,Email,Tags\nRohit,9608261539,r@x.in,vip;retail\nBad,123,,\nRohit again,+91 96082 61539,,\n"
    rows, errors = w.parse_contacts_csv(text)
    assert [r["phone"] for r in rows] == ["919608261539"]
    assert rows[0]["tags"] == ["vip", "retail"]
    assert {e["reason"] for e in errors} == {"Invalid phone number", "Duplicate in file"}


def test_segment_filter_always_excludes_opted_out():
    f = w.build_segment_filter({"tags": ["vip"], "excludeTags": ["blocked"], "vertical": "RETAIL"})
    assert f["optedOut"] == {"$ne": True} and f["subscribed"] == {"$ne": False}
    assert f["tags"] == {"$all": ["vip"], "$nin": ["blocked"]}
    assert f["vertical"] == "RETAIL"
    assert "vertical" not in w.build_segment_filter({"vertical": "ALL"})


def test_param_helpers():
    assert w.template_param_count("Hi {{1}}, order {{2}} is ready") == 2
    assert w.render_template_body("Hi {{1}}!", ["Rohit"]) == "Hi Rohit!"
    assert w.clean_param("a\n\nb    c") == "a b c"
    assert w.clean_param("") == "-"
    assert w.fill_params(["{{first_name}}", "10% off"], {"name": "Rohit Kumar"}) == ["Rohit", "10% off"]


def test_create_template_payload():
    p = w.build_template_create_payload({"name": "glc_offer", "category": "marketing", "body": "Hi {{1}}, 10% off", "examples": ["Rohit"],
                                         "footer": "GLC Zone", "buttons": [{"type": "URL", "text": "Shop", "url": "https://glczone.in"}]})
    assert p["category"] == "MARKETING"
    assert [c["type"] for c in p["components"]] == ["BODY", "FOOTER", "BUTTONS"]
    assert p["components"][0]["example"] == {"body_text": [["Rohit"]]}


@pytest.mark.parametrize("bad", [
    {"name": "Bad Name", "body": "x"},
    {"name": "ok_name", "body": ""},
    {"name": "ok_name", "body": "Hi {{1}}"},
    {"name": "ok_name", "body": "x", "category": "weird"},
    {"name": "ok_name", "body": "x", "buttons": [{"type": "URL", "text": "Go", "url": "nope"}]},
])
def test_create_template_payload_rejects(bad):
    with pytest.raises(ValueError):
        w.build_template_create_payload(bad)


def test_send_payload_cleans_params():
    p = w.build_template_send_payload("919608261539", "glc_offer", "en", ["Hi\nthere"])
    assert p["template"]["components"][0]["parameters"] == [{"type": "text", "text": "Hi there"}]
    assert "components" not in w.build_template_send_payload("1", "n", "en", [])["template"]


def test_webhook_parsing():
    body = {"entry": [{"changes": [{"value": {
        "statuses": [{"id": "wamid.1", "status": "failed", "recipient_id": "9196", "errors": [{"code": 131026, "title": "Undeliverable"}]}],
        "contacts": [{"wa_id": "9196", "profile": {"name": "Rohit"}}],
        "messages": [{"from": "9196", "id": "m1", "type": "text", "text": {"body": "STOP"}}]}}]}]}
    st = w.parse_status_webhook(body)[0]
    assert st["status"] == "FAILED" and st["error"] == "Undeliverable" and st["errorCode"] == 131026
    msg = w.parse_inbound_webhook(body)[0]
    assert msg["name"] == "Rohit" and w.is_stop_request(msg["text"])
    assert not w.is_stop_request("please stop calling about the stop sign")


def test_status_never_goes_backwards():
    assert w.advance_status("READ", "DELIVERED") == "READ"
    assert w.advance_status("SENT", "DELIVERED") == "DELIVERED"
    assert w.advance_status("DELIVERED", "FAILED") == "FAILED"


def test_signature_and_codes():
    import hashlib, hmac
    raw = b'{"a":1}'
    good = "sha256=" + hmac.new(b"s", raw, hashlib.sha256).hexdigest()
    assert w.verify_meta_signature(raw, good, "s") and not w.verify_meta_signature(raw, "sha256=bad", "s")
    assert w.verify_meta_signature(raw, "", "")
    assert len(w.new_short_code()) == 7


def test_relay_signature_matches_store_format():
    import hashlib, hmac
    sts = [{"waMessageId": "wamid.1", "status": "delivered"}, {"waMessageId": "wamid.2", "status": "read"}]
    expected = hmac.new(b"k", b"wamid.1|DELIVERED\nwamid.2|READ", hashlib.sha256).hexdigest()
    assert w.relay_signature("k", sts) == expected


def test_media_kind_accepts_only_whatsapp_formats():
    assert w.media_kind("Offer.JPG") == ("IMAGE", "image/jpeg")
    assert w.media_kind("clip.mp4") == ("VIDEO", "video/mp4")
    assert w.media_kind("rates.pdf") == ("DOCUMENT", "application/pdf")
    assert w.media_kind("anim.gif") is None and w.media_kind("") is None


def test_media_header_template_needs_a_sample_handle():
    base = {"name": "glc_offer_img", "category": "marketing", "body": "Big sale", "headerFormat": "IMAGE"}
    with pytest.raises(ValueError):
        w.build_template_create_payload(base)
    p = w.build_template_create_payload({**base, "headerHandle": "4::aW1hZ2U="})
    assert p["components"][0] == {"type": "HEADER", "format": "IMAGE", "example": {"header_handle": ["4::aW1hZ2U="]}}


def test_send_payload_with_media_header_and_body():
    p = w.build_template_send_payload("919608261539", "glc_offer_img", "en", ["Rohit"], {"format": "IMAGE", "id": "m1"})
    comps = p["template"]["components"]
    assert comps[0] == {"type": "header", "parameters": [{"type": "image", "image": {"id": "m1"}}]}
    assert comps[1]["type"] == "body"
    doc = w.build_template_send_payload("1", "n", "en", [], {"format": "DOCUMENT", "id": "d1", "filename": "rates.pdf"})
    assert doc["template"]["components"][0]["parameters"][0]["document"] == {"id": "d1", "filename": "rates.pdf"}
