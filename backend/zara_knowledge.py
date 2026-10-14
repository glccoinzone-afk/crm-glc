"""Zara's editable knowledge: backend/zara_knowledge.md is read on every reply (cached by modification time) and added to her instructions."""
import os

KNOWLEDGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zara_knowledge.md")
MAX_CHARS = 8000

# Always added, so Zara never invents an address or an account when she does not know one.
RULES = (
    "\n\n⚠️ CONTACT RULE: NEVER invent an email address, LinkedIn page, social account or phone number. "
    "Only use glczone.in, glczone.in/careers, support@glczone.in and this WhatsApp number. "
    "If a person is needed, say the GLC Zone team will call back."
)

_cache = {"mtime": None, "text": ""}


def load(path: str = KNOWLEDGE_PATH) -> str:
    """The knowledge text (without the leading comment line), or '' when the file is missing or empty."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return ""
    if _cache["mtime"] == (path, mtime):
        return _cache["text"]
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return ""
    if lines and lines[0].startswith("# Zara knowledge"):
        lines = lines[1:]
    text = "\n".join(lines).strip()[:MAX_CHARS]
    _cache["mtime"] = (path, mtime)
    _cache["text"] = text
    return text


def prompt_block(path: str = KNOWLEDGE_PATH) -> str:
    """What is appended to the system prompt."""
    text = load(path)
    return ("\n\n📚 GLC ZONE KNOWLEDGE (use this, it is current):\n" + text if text else "") + RULES
