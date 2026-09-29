# Website Change Monitor → Telegram

A tiny Python bot that checks a website every 5 minutes and sends you a Telegram message when its content changes. Built to watch [justhoot.fun](https://justhoot.fun/) for the moment it goes live, but it works for any URL.

## Features

- Detects changes in visible page text and in referenced assets (scripts, stylesheets, images)
- Ignores noise such as inline scripts, comments and cache-busting query strings
- Sends a readable summary of what was added and removed
- Sends a baseline message on first run so you know it's working
- Alerts you if the site fails 3 checks in a row, and again when it recovers
- Runs free on GitHub Actions, or anywhere Python runs

## How it works

1. Fetches the page HTML.
2. Strips scripts, styles and comments, and extracts the visible text plus a list of asset URLs.
3. Hashes the result and compares it with the hash saved from the previous run (`state.json`).
4. If the hash differs, sends a diff summary to your Telegram chat.

## Setup

### 1. Create a Telegram bot

1. In Telegram, message [@BotFather](https://t.me/BotFather) and send `/newbot`.
2. Follow the prompts and copy the **bot token**.
3. Open a chat with your new bot, press **Start**, and send any message (for example, "hi").

### 2. Get your chat ID

Open this URL in a browser, replacing the token:

```
https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```

Find `"chat":{"id": 123456789 ...}` in the response. That number is your **chat ID**.

If `result` is empty, you haven't messaged the bot yet. Send it a message and reload. Alternatively, message [@userinfobot](https://t.me/userinfobot) and use the ID it replies with.

## Option A: Run on GitHub Actions (free)

1. Create a **public** GitHub repository (private repos will exceed the free minutes at a 5-minute schedule).
2. Add `monitor.py` and this README to the repo root.
3. Create `.github/workflows/monitor.yml`:

   ```yaml
   name: Site monitor

   on:
     schedule:
       - cron: "*/5 * * * *"
     workflow_dispatch:

   concurrency:
     group: site-monitor
     cancel-in-progress: false

   jobs:
     check:
       runs-on: ubuntu-latest
       timeout-minutes: 3
       steps:
         - uses: actions/checkout@v4

         - uses: actions/setup-python@v5
           with:
             python-version: "3.12"

         - run: pip install requests

         - name: Restore previous state
           uses: actions/cache@v4
           with:
             path: state.json
             key: state-${{ github.run_id }}
             restore-keys: state-

         - name: Check site
           env:
             TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
             TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
             WATCH_URL: https://justhoot.fun/
           run: python monitor.py --once
   ```

4. In the repo, go to **Settings → Secrets and variables → Actions** and add two secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
5. Go to the **Actions** tab, select **Site monitor**, and click **Run workflow** to test. You should receive a "👀 Now monitoring…" message.

### GitHub Actions caveats

- Scheduled runs are approximate and can be delayed by several minutes.
- GitHub disables scheduled workflows after 60 days without repo activity. Re-enable in the Actions tab, or push a small commit.
- `state.json` is persisted via the Actions cache. If the cache is evicted (unused for 7 days), you'll simply get a fresh "Now monitoring" message.

## Option B: Run locally or on a server

```bash
pip install requests

export TELEGRAM_BOT_TOKEN="123456:ABC..."
export TELEGRAM_CHAT_ID="123456789"

python monitor.py            # loops forever, checking every 5 minutes
python monitor.py --once     # single check, useful for cron
```

Keep it alive with `systemd`, `tmux`, `pm2`, or `nohup python monitor.py &`.

Cron example (every 5 minutes):

```
*/5 * * * * cd /path/to/repo && TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python monitor.py --once
```

## Configuration

| Variable             | Required | Default                | Description                          |
| -------------------- | -------- | ---------------------- | ------------------------------------ |
| `TELEGRAM_BOT_TOKEN` | Yes      | –                      | Token from @BotFather                |
| `TELEGRAM_CHAT_ID`   | Yes      | –                      | Chat that receives alerts            |
| `WATCH_URL`          | No       | `https://justhoot.fun/` | Page to monitor                      |
| `CHECK_INTERVAL`     | No       | `300`                  | Seconds between checks (loop mode)   |
| `STATE_FILE`         | No       | `state.json`           | Where the last snapshot is stored    |

## Limitations

- The bot reads raw HTML, not a rendered browser view. Content injected purely by client-side JavaScript may not be detected, though a site launch usually changes the script files too.
- Only the single URL is checked, not other pages on the site.

## Troubleshooting

- **No messages arriving:** confirm you pressed Start in the bot's chat and that the chat ID is correct.
- **`getUpdates` returns an empty result:** send your bot a message, then reload the URL. If it's still empty, check `getWebhookInfo` and run `deleteWebhook` if a webhook is set.
- **Workflow missing in the Actions tab:** the file must be at exactly `.github/workflows/monitor.yml` on the default branch, with valid YAML indentation.
- **Too many alerts:** the site may be changing on every load (for example, rotating content). Check the diff in the alert to see what's changing.
