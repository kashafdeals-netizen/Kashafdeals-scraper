"""
Kashafdeals Channel Scraper
Monitors Telegram channels, swaps Amazon affiliate tags, reposts to @kashafdeals.
Deploy on Render.com — runs 24/7, no laptop needed.
"""
import asyncio
import os
import re
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import MessageEntityTextUrl

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Config from environment variables ────────────────────────────────────────
API_ID        = int(os.environ["TELEGRAM_API_ID"])
API_HASH      = os.environ["TELEGRAM_API_HASH"]
SESSION_STR   = os.environ["TELEGRAM_SESSION"]
DEST_CHANNEL  = os.environ.get("DEST_CHANNEL", "@kashafdeals")
AFFILIATE_TAG = os.environ.get("AFFILIATE_TAG", "kashafdeals-21")

# Comma-separated channel usernames (without @), e.g. "EgyptOffersHunter,AnotherChannel"
# To add a channel: update this env var on Render dashboard → service redeploys automatically
CHANNELS = [
    ch.strip().lstrip("@").lstrip("https://t.me/")
    for ch in os.environ.get("CHANNELS", "EgyptOffersHunter").split(",")
    if ch.strip()
]

# ── Affiliate tag replacement ─────────────────────────────────────────────────
_TAG_RE    = re.compile(r'\btag=[^&\s\)\]\>\n]+')
_AMAZON_RE = re.compile(
    r'(https?://(?:www\.)?amazon\.[a-z.]+/(?:dp|gp|s)[^\s\)\]\>\n]*)'
)

def swap_tag(text: str) -> str:
    """Replace any existing tag= value; add tag if Amazon URL has none."""
    if not text:
        return text
    # Replace existing tags
    result = _TAG_RE.sub(f"tag={AFFILIATE_TAG}", text)
    # Add tag to bare Amazon URLs that have no query string tag yet
    def _add_tag(m):
        url = m.group(1)
        if "tag=" not in url:
            sep = "&" if "?" in url else "?"
            return url + f"{sep}tag={AFFILIATE_TAG}"
        return url
    return _AMAZON_RE.sub(_add_tag, result)

def patch_entities(entities):
    """Swap affiliate tag inside TextUrl entities (hidden-URL links)."""
    if not entities:
        return None
    patched = []
    changed = False
    for ent in entities:
        if isinstance(ent, MessageEntityTextUrl) and ent.url:
            new_url = swap_tag(ent.url)
            if new_url != ent.url:
                ent = MessageEntityTextUrl(
                    offset=ent.offset, length=ent.length, url=new_url
                )
                changed = True
        patched.append(ent)
    return patched if changed else entities

# ── HTTP keepalive server (keeps Render free-tier web service awake) ──────────
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        body = (
            f"Kashafdeals scraper running\n"
            f"Monitoring: {', '.join('@' + c for c in CHANNELS)}\n"
            f"Posting to: {DEST_CHANNEL}\n"
        ).encode()
        self.wfile.write(body)
    def log_message(self, *args):
        pass  # suppress noisy access logs

def _start_http():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), _HealthHandler).serve_forever()

# ── Telethon client ───────────────────────────────────────────────────────────
client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)

async def handle_post(event):
    msg  = event.message
    src  = getattr(event.chat, "username", None) or str(event.chat_id)
    raw  = msg.message or ""

    new_text     = swap_tag(raw)
    new_entities = patch_entities(msg.entities)
    tag_swapped  = raw != new_text

    try:
        if msg.media:
            await client.send_file(
                DEST_CHANNEL,
                msg.media,
                caption=new_text,
                formatting_entities=new_entities,
            )
        else:
            await client.send_message(
                DEST_CHANNEL,
                new_text,
                formatting_entities=new_entities,
            )
        log.info(f"Posted from @{src} | tag swapped: {tag_swapped}")

    except Exception as e:
        log.error(f"Failed to post from @{src}: {e}")
        # Fallback: download media to memory then reupload
        if msg.media:
            try:
                data = await client.download_media(msg.media, bytes)
                await client.send_file(
                    DEST_CHANNEL,
                    data,
                    caption=new_text,
                    formatting_entities=new_entities,
                )
                log.info(f"Posted via fallback download from @{src}")
            except Exception as e2:
                log.error(f"Fallback also failed: {e2}")

async def main():
    await client.start()
    me = await client.get_me()
    log.info(f"Logged in as: {me.first_name} (@{me.username})")
    log.info(f"Monitoring:   {[('@' + c) for c in CHANNELS]}")
    log.info(f"Posting to:   {DEST_CHANNEL}")
    log.info(f"Affiliate:    {AFFILIATE_TAG}")

    client.add_event_handler(handle_post, events.NewMessage(chats=CHANNELS))
    await client.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=_start_http, daemon=True).start()
    asyncio.run(main())
