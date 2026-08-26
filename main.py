"""
Kashafdeals Channel Scraper
Monitors Telegram channels, resolves short Amazon links, swaps affiliate tags,
cleans captions, and reposts to destination channel.
Deploy on Render.com - runs 24/7, no laptop needed.
"""
import asyncio
import os
import re
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import aiohttp
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import MessageEntityTextUrl

# -- Logging -------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# -- Config from environment variables -----------------------------------------
API_ID        = int(os.environ["TELEGRAM_API_ID"])
API_HASH      = os.environ["TELEGRAM_API_HASH"]
SESSION_STR   = os.environ["TELEGRAM_SESSION"]
DEST_CHANNEL  = os.environ.get("DEST_CHANNEL", "@kashafdeals")
AFFILIATE_TAG = os.environ.get("AFFILIATE_TAG", "kashafdeals-21")

# Comma-separated channel usernames (without @)
CHANNELS = [
    ch.strip().lstrip("@").replace("https://t.me/", "")
    for ch in os.environ.get("CHANNELS", "EgyptOffersHunter").split(",")
    if ch.strip()
]

# -- Short link patterns -------------------------------------------------------
_SHORT_LINK_RE = re.compile(
    r'https?://(?:link\.amazon|amzn\.to|amzn\.eu|a\.co)[^\s)\]>"\n]*',
    re.IGNORECASE
)

_AMAZON_RE = re.compile(
    r'(https?://(?:www\.)?amazon\.[a-z.]+/[^\s)\]>"\n]*)',
    re.IGNORECASE
)

_TAG_RE = re.compile(r'\btag=[^&\s)\]>\n]+')

# Spam patterns to remove from captions
_SPAM_PATTERNS = [
    re.compile(r'تابعنا على جميع منصات التواصل[:\s]*', re.IGNORECASE),
    re.compile(r'قناتنا على واتساب[^\n]*', re.IGNORECASE),
    re.compile(r'قناتنا لعروض نون[^\n]*', re.IGNORECASE),
    re.compile(r'اضغط هنا للانضمام[^\n]*', re.IGNORECASE),
    re.compile(r'تابعونا[^\n]*', re.IGNORECASE),
    re.compile(r'https?://(?:wa\.me|chat\.whatsapp\.com|t\.me/(?!arkhashom|kashaf))[^\s)\n]*', re.IGNORECASE),
    re.compile(r'https?://(?:www\.)?noon\.com[^\s)\n]*', re.IGNORECASE),
    re.compile(r'\U0001F4F1[^\n]*واتساب[^\n]*', re.IGNORECASE),
    re.compile(r'\U0001F4F1[^\n]*\n', re.IGNORECASE),
]


# -- Resolve short links -------------------------------------------------------
async def resolve_short_link(url: str) -> str:
    """Follow redirects on a short Amazon link to get the full URL."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                final_url = str(resp.url)
                if "amazon" in final_url:
                    return final_url
                return url
    except Exception as e:
        log.warning(f"Failed to resolve {url}: {e}")
        return url


async def resolve_all_short_links(text: str) -> str:
    """Find all short Amazon links in text and replace with resolved full URLs."""
    short_links = _SHORT_LINK_RE.findall(text)
    if not short_links:
        return text

    for short_url in short_links:
        full_url = await resolve_short_link(short_url)
        text = text.replace(short_url, full_url)
        log.info(f"Resolved: {short_url} -> {full_url[:80]}...")

    return text


# -- Affiliate tag swap --------------------------------------------------------
def swap_tag(url: str) -> str:
    """Replace or add affiliate tag in an Amazon URL."""
    if not url:
        return url

    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params["tag"] = [AFFILIATE_TAG]
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def swap_tag_in_text(text: str) -> str:
    """Replace tags in all Amazon URLs found in text."""
    if not text:
        return text
    # Replace existing tag= values
    result = _TAG_RE.sub(f"tag={AFFILIATE_TAG}", text)

    # Add tag to Amazon URLs that have none
    def _add_tag(m):
        url = m.group(1)
        if "tag=" not in url:
            sep = "&" if "?" in url else "?"
            return url + f"{sep}tag={AFFILIATE_TAG}"
        return url
    return _AMAZON_RE.sub(_add_tag, result)


# -- Caption cleaning ----------------------------------------------------------
def clean_caption(text: str) -> str:
    """Remove spam text (WhatsApp links, Noon links, follow-us text).
    Keep only: product title, discount info, description, and Amazon link."""
    if not text:
        return text

    # Remove spam patterns
    for pattern in _SPAM_PATTERNS:
        text = pattern.sub("", text)

    # Remove non-Amazon links (keep only amazon links)
    text = re.sub(
        r'https?://(?!(?:www\.)?amazon\.|link\.amazon|amzn)[^\s)\]>"\n]*',
        "", text
    )

    # Clean up extra whitespace and empty lines
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]

    # Remove consecutive duplicate empty-ish lines
    cleaned = []
    for line in lines:
        if line or (cleaned and cleaned[-1]):
            cleaned.append(line)

    result = "\n".join(cleaned).strip()
    return result


# -- Entity patching -----------------------------------------------------------
def patch_entities(entities, text: str):
    """Swap affiliate tag inside TextUrl entities and remove non-Amazon link entities."""
    if not entities:
        return None
    patched = []
    for ent in entities:
        if isinstance(ent, MessageEntityTextUrl) and ent.url:
            # Skip non-Amazon URL entities (WhatsApp, Noon, etc.)
            if "amazon" not in ent.url and "amzn" not in ent.url and "link.amazon" not in ent.url:
                continue
            new_url = swap_tag(ent.url) if "amazon" in ent.url else ent.url
            if new_url != ent.url:
                ent = MessageEntityTextUrl(
                    offset=ent.offset, length=ent.length, url=new_url
                )
        patched.append(ent)
    return patched if patched else None


# -- HTTP keepalive server (Render free-tier) ----------------------------------
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
        pass


def _start_http():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), _HealthHandler).serve_forever()


# -- Telethon client -----------------------------------------------------------
client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)


async def handle_post(event):
    msg = event.message
    src = getattr(event.chat, "username", None) or str(event.chat_id)
    raw = msg.message or ""

    # Step 1: Resolve short links to full Amazon URLs
    resolved_text = await resolve_all_short_links(raw)

    # Step 2: Swap affiliate tags
    tagged_text = swap_tag_in_text(resolved_text)

    # Step 3: Clean caption (remove spam)
    clean_text = clean_caption(tagged_text)

    # Step 4: Patch entities
    new_entities = patch_entities(msg.entities, clean_text)

    # Skip if no Amazon link found after processing
    if not _AMAZON_RE.search(clean_text) and "amazon" not in clean_text:
        log.info(f"Skipped from @{src} - no Amazon link found")
        return

    # Skip if caption is too short (likely just spam with no real content)
    if len(clean_text.strip()) < 10:
        log.info(f"Skipped from @{src} - caption too short after cleaning")
        return

    try:
        if msg.media:
            await client.send_file(
                DEST_CHANNEL,
                msg.media,
                caption=clean_text,
                formatting_entities=new_entities,
            )
        else:
            await client.send_message(
                DEST_CHANNEL,
                clean_text,
                formatting_entities=new_entities,
            )
        log.info(f"Posted from @{src} | resolved links + cleaned caption")

    except Exception as e:
        log.error(f"Failed to post from @{src}: {e}")
        if msg.media:
            try:
                data = await client.download_media(msg.media, bytes)
                await client.send_file(
                    DEST_CHANNEL,
                    data,
                    caption=clean_text,
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
