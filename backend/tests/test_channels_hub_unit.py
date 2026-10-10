"""Unit tests for the pure helpers in channels_hub (no database, no network)."""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import channels_hub as c  # noqa: E402


def test_channel_config_reports_missing_variables_without_secrets():
    cfg = {x["key"]: x for x in c.channel_config({"TELEGRAM_BOT_TOKEN": "secret-token", "WHATSAPP_ACCESS_TOKEN": "x"})}
    assert cfg["TELEGRAM"]["ready"] and cfg["TELEGRAM"]["optionalMissing"] == ["TELEGRAM_CHANNEL_ID"]
    assert not cfg["WHATSAPP"]["ready"] and cfg["WHATSAPP"]["missing"] == ["WHATSAPP_PHONE_NUMBER_ID"]
    assert not cfg["FACEBOOK"]["ready"] and set(cfg["FACEBOOK"]["missing"]) == {"FB_PAGE_ID", "FB_PAGE_ACCESS_TOKEN"}
    assert cfg["WEBCHAT"]["ready"]
    assert "secret-token" not in str(cfg)


def test_daily_buckets_fill_gaps():
    today = datetime(2026, 10, 10, 15, tzinfo=timezone.utc)
    out = c.daily_buckets([{"_id": "2026-10-10", "in": 3, "out": 2}, {"_id": "2026-10-08", "in": 1, "out": 0}], 4, today)
    assert [d["date"] for d in out] == ["2026-10-07", "2026-10-08", "2026-10-09", "2026-10-10"]
    assert [(d["in"], d["out"]) for d in out] == [(0, 0), (1, 0), (0, 0), (3, 2)]


def test_response_minutes_median_and_bad_rows():
    pairs = [
        {"inAt": "2026-10-10T10:00:00+00:00", "outAt": "2026-10-10T10:02:00+00:00"},
        {"inAt": "2026-10-10T10:00:00+00:00", "outAt": "2026-10-10T10:10:00+00:00"},
        {"inAt": "2026-10-10T10:00:00+00:00", "outAt": "2026-10-10T09:00:00+00:00"},  # reply before message: ignored
        {"inAt": "bad", "outAt": "x"},
    ]
    assert c.response_minutes(pairs) == 6.0
    assert c.response_minutes([]) is None
