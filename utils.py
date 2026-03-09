import re
from telegram import Message, User


# ── Антимат ──────────────────────────────────────

def has_profanity(text: str, words: list[str]) -> bool:
    low = text.lower()
    cleaned = re.sub(r"[^а-яёa-z\s]", "", low)
    leet = (
        low.replace("0", "o")
        .replace("1", "i")
        .replace("3", "e")
        .replace("4", "a")
        .replace("5", "s")
        .replace("@", "a")
    )
    for w in words:
        if w in cleaned or w in low or w in leet:
            return True
    return False


# ── Антиссылки ───────────────────────────────────

_URL_RE = re.compile(
    r"(?:https?://|www\.|t\.me/|telegram\.me/)\S+"
    r"|(?:[a-z0-9-]+\.)"
    r"(?:com|net|org|ru|me|link|xyz|top|site|pro|info|click|online|club)\b",
    re.I,
)


def has_links_in_text(text: str) -> bool:
    return bool(_URL_RE.search(text))


def has_links(msg: Message) -> bool:
    """Проверяет и текст, и Telegram-entities"""
    text = msg.text or msg.caption or ""
    if has_links_in_text(text):
        return True
    for ent in msg.entities or msg.caption_entities or []:
        if ent.type in ("url", "text_link"):
            return True
    return False


# ── Форматирование ───────────────────────────────

def mention(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    return f'<a href="tg://user?id={user.id}">{user.first_name}</a>'


def display_name(user: User) -> str:
    parts = [user.first_name or ""]
    if user.last_name:
        parts.append(user.last_name)
    return " ".join(parts)
