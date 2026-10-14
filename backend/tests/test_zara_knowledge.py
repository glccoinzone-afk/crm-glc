"""Zara's editable knowledge file: loading, the comment line, the length cap and the always-on contact rule."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import zara_knowledge as zk  # noqa: E402


def test_the_shipped_file_covers_careers_and_the_grocery_delivery_rules():
    text = zk.load()
    assert "glczone.in/careers" in text
    assert "Become a Franchise" in text and "DPCP" in text
    assert "Rs 199" in text and "Rs 30" in text and "Rs 20" in text       # grocery minimum order and delivery tiers
    assert not text.startswith("# Zara knowledge")                           # the comment line is not sent to the model


def test_prompt_block_always_carries_the_contact_rule():
    block = zk.prompt_block()
    assert "NEVER invent an email address" in block
    assert "GLC ZONE KNOWLEDGE" in block


def test_missing_file_gives_only_the_rule(tmp_path):
    block = zk.prompt_block(str(tmp_path / "nope.md"))
    assert "GLC ZONE KNOWLEDGE" not in block
    assert "NEVER invent an email address" in block


def test_edits_are_picked_up_and_length_is_capped(tmp_path):
    f = tmp_path / "k.md"
    f.write_text("# Zara knowledge (x)\nfirst fact", encoding="utf-8")
    assert zk.load(str(f)) == "first fact"
    time.sleep(0.02)
    f.write_text("# Zara knowledge (x)\n" + "a" * 20000, encoding="utf-8")
    os.utime(f, (time.time() + 5, time.time() + 5))
    assert len(zk.load(str(f))) == zk.MAX_CHARS
