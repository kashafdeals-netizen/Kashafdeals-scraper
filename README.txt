================================================================
  KASHAFDEALS CHANNEL SCRAPER
  Monitors Telegram channels, swaps affiliate tags, reposts
================================================================

WHAT IT DOES
------------
- Watches @EgyptOffersHunter (and any channels you add) for new posts
- Any Amazon link found → replaces tag=XXX with tag=kashafdeals-21
- Reposts to @kashafdeals with the same image and caption
- Runs 24/7 on Render.com — no laptop needed

================================================================
  ONE-TIME SETUP (do this once, takes ~10 minutes)
================================================================

STEP 1 — Get Telegram API credentials
--------------------------------------
1. Open https://my.telegram.org/apps in your browser
2. Log in with your phone number (the same account you want to
   monitor channels with — any personal account is fine)
3. Click "Create new application"
   - App title: anything (e.g. "KashafdealsBot")
   - Short name: anything (e.g. "kashafdeals")
   - Platform: Other
4. Click Save. You'll see:
   - App api_id:   (a number, e.g. 12345678)
   - App api_hash: (a long hex string)
   Keep these — you'll need them in Steps 2 and 3.

STEP 2 — Generate your session string (run ONCE on your PC)
------------------------------------------------------------
This step logs in to Telegram and produces a "session string"
that the cloud server uses to stay logged in without your phone.

1. Install Python if not already installed (python.org)
2. Open a terminal / command prompt in this folder
3. Run:
       pip install telethon
       python generate_session.py
4. Enter your API ID and API Hash when prompted
5. Telegram sends a code to your phone — enter it
6. Copy the long string that appears between the ===== lines
   (It looks like: 1BVtsOLkBu3Q5...)
   KEEP THIS STRING PRIVATE — treat it like a password.

STEP 3 — Deploy to Render.com
------------------------------
1. Create a free account at https://render.com

2. Push this folder to a GitHub repo:
   - Go to github.com → New repository → name it "kashafdeals-scraper"
   - Upload all files in this folder to the repo

3. On Render dashboard:
   - Click "New +" → "Web Service"
   - Connect your GitHub account and select the repo
   - Settings:
       Name:          kashafdeals-scraper
       Runtime:       Python 3
       Build Command: pip install -r requirements.txt
       Start Command: python main.py
   - Click "Create Web Service"

4. Go to the service → "Environment" tab → Add these variables:
   ┌─────────────────────┬──────────────────────────────────────┐
   │ TELEGRAM_API_ID     │ (your number from Step 1)            │
   │ TELEGRAM_API_HASH   │ (your hex string from Step 1)        │
   │ TELEGRAM_SESSION    │ (the string you copied in Step 2)    │
   │ DEST_CHANNEL        │ @kashafdeals                         │
   │ AFFILIATE_TAG       │ kashafdeals-21                       │
   │ CHANNELS            │ EgyptOffersHunter                    │
   └─────────────────────┴──────────────────────────────────────┘
   Click "Save Changes" — Render will redeploy automatically.

5. Check the Logs tab. You should see:
       Logged in as: [Your Name] (@yourusername)
       Monitoring:   ['@EgyptOffersHunter']
       Posting to:   @kashafdeals
   That means it's working.

STEP 4 — Keep it awake (free tier only)
----------------------------------------
Render's free tier sleeps after 15 minutes of no web traffic.
To keep it awake 24/7 for free:

1. Go to https://uptimerobot.com → Create free account
2. "Add New Monitor":
   - Monitor Type: HTTP(s)
   - URL: https://kashafdeals-scraper.onrender.com
     (Render shows you the exact URL in the service dashboard)
   - Monitoring Interval: Every 5 minutes
3. Save. UptimeRobot pings every 5 min → service stays awake.

================================================================
  ADDING MORE CHANNELS
================================================================
To monitor additional channels:

1. Go to Render dashboard → your service → Environment tab
2. Find the CHANNELS variable
3. Change the value from:
       EgyptOffersHunter
   To (comma-separated, no spaces, no @):
       EgyptOffersHunter,AnotherChannel,ThirdChannel
4. Click "Save Changes" — service redeploys in ~30 seconds.

That's it. No code changes needed.

================================================================
  CHECKING IT'S WORKING
================================================================
- Render dashboard → Logs tab: shows every post it forwards
- Or open the service URL in your browser — shows a status page
- When a new post appears in @EgyptOffersHunter, it should
  appear in @kashafdeals within a few seconds

================================================================
  TROUBLESHOOTING
================================================================
"SESSION_STRING_INVALID" error
  → Your session expired. Run generate_session.py again and
    update TELEGRAM_SESSION on Render.

"Could not find the input entity" error
  → The channel username in CHANNELS is wrong. Double-check
    the exact @handle (no t.me/ prefix).

Bot posts nothing
  → Check the Logs tab on Render for errors.
  → Make sure UptimeRobot is set up (Step 4) so the service
    doesn't sleep.

Post comes through but tag not replaced
  → The original post may use a TextUrl entity (link behind
    display text). The bot handles this too — check the logs.
