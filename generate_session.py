"""
Run this ONCE on your local machine to generate the Telegram session string.
You only need to do this one time. After that, the session works forever on Render.

Requirements: pip install telethon
"""
print("=" * 60)
print("  Kashafdeals — Telegram Session Generator")
print("=" * 60)
print()
print("Step 1: Go to https://my.telegram.org/apps")
print("        Log in with your phone number")
print("        Create an app (any name, any platform)")
print("        Copy the API ID and API Hash")
print()

from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id   = int(input("Paste your API ID:   ").strip())
api_hash = input("Paste your API Hash: ").strip()

print()
print("Telegram will send a login code to your phone now...")
print()

with TelegramClient(StringSession(), api_id, api_hash) as client:
    session_string = client.session.save()

print()
print("=" * 60)
print("  YOUR SESSION STRING (copy everything between the lines)")
print("=" * 60)
print(session_string)
print("=" * 60)
print()
print("Next steps:")
print("  1. Copy the session string above")
print("  2. On Render.com dashboard → your service → Environment")
print("  3. Add variable:  TELEGRAM_SESSION = <paste here>")
print()
print("IMPORTANT: Keep this string private — it has access to your account.")
