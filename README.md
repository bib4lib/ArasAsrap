# Fizz Utrecht Availability Bot — Setup Guide (no coding needed)

This bot checks https://www.the-fizz.com/en/student-accommodation/utrecht/
every 2 minutes, Monday to Friday between 06:00 and 21:00 (Amsterdam time),
and sends you a Telegram message the moment the "fully booked" notice
disappears from the page. It runs entirely on GitHub's free servers — your
laptop can be off.

You will do everything below through GitHub's website. No terminal, no
installing anything.

## Step 1 — Create a free GitHub account
Go to https://github.com and sign up if you don't already have an account.

## Step 2 — Create a new repository
1. Click the **+** icon (top right) → **New repository**.
2. Name it something like `fizz-utrecht-bot`.
3. Set it to **Private** (recommended) or Public — either works.
4. Click **Create repository**.

## Step 3 — Upload the files
1. On your new repo's page, click **Add file** → **Upload files**.
2. Drag in these 4 files (keep the same names):
   - `check_availability.py`
   - `requirements.txt`
   - `state.json`
   - `.github/workflows/check-availability.yml` — GitHub's uploader should
     preserve the folder structure automatically if you drag the whole
     `.github` folder in. If it doesn't, create the folders manually:
     click **Add file → Create new file**, and type
     `.github/workflows/check-availability.yml` as the file name (GitHub
     creates the folders for you), then paste in the file's contents.
3. Click **Commit changes**.

## Step 4 — Add your Telegram credentials as secrets
These are stored securely by GitHub and never appear in your code.

1. In your repo, go to **Settings** → **Secrets and variables** → **Actions**.
2. Click **New repository secret**.
   - Name: `TELEGRAM_BOT_TOKEN` → Value: (the token you got from BotFather)
   - Click **Add secret**.
3. Click **New repository secret** again.
   - Name: `TELEGRAM_CHAT_ID` → Value: (the chat ID number you found earlier)
   - Click **Add secret**.

## Step 5 — Turn it on
1. Go to the **Actions** tab of your repo.
2. If prompted, click **I understand my workflows, go ahead and enable them**.
3. You should see "Check Fizz Utrecht Availability" listed as a workflow.
4. To test it immediately rather than waiting: click on it, then click
   **Run workflow** → **Run workflow**. Check the run's log to confirm it
   says "No change since last check" (or that you get a Telegram message,
   if availability happens to have just opened up).

That's it — it now runs automatically every 5 minutes in the allowed window,
with no further action needed from you.

## Adjusting things later
- **Change the checking days/hours:** edit the numbers at the top of
  `check_availability.py` (`ALLOWED_DAYS`, `ALLOWED_START_HOUR`,
  `ALLOWED_END_HOUR`), and/or the `cron` line in the workflow file.
- **Change the frequency:** edit the `cron: "*/5 4-17 * * 2-5"` line —
  the `*/5` is "every 5 minutes."
- **Test locally isn't required** — everything runs on GitHub, so editing
  a file and committing it is enough to update the bot's behavior.

## Troubleshooting
- No message ever arrives: check the Actions tab → click a recent run → read
  the log for errors (most common: a typo in one of the two secrets).
- Getting an error about permissions when it tries to save `state.json`:
  make sure the workflow file's `permissions: contents: write` line is
  present (it's already included in the file above).
