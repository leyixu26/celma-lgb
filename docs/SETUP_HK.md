# Operator setup — refresh machine (Windows, direct access to celma)

The refresh machine needs: **Python 3.11+**, internet access to celma.org.cn
and github.com. No git, no VPN, no admin rights required.

## 1. One-time setup (~10 min)

1. **Get the project** (either way):
   - `python get_repo.py` (after downloading just that one file from the repo), or
   - github.com/leyixu26/celma-lgb → **Code → Download ZIP** → extract.
2. **Install dependencies** — in the project folder (type `cmd` in the Explorer
   address bar to open a terminal there):
   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   *(Corporate SSL error? Append:
   `--trusted-host pypi.org --trusted-host files.pythonhosted.org`)*
3. **Create the publish token** (lets this machine push refreshed data):
   - github.com → Settings → Developer settings → **Fine-grained tokens** →
     Generate new token
   - Repository access: **Only select repositories → celma-lgb**
   - Permissions: **Contents → Read and write** (nothing else)
   - Expiry: 90 days. Copy the token string.
   - On the refresh machine, save it as **`token.txt`** in the project folder
     (the file is git-ignored and never leaves the machine).

## 2. Refresh — one click

Double-click **`refresh.bat`**. It runs: scrape → parse → **verify** (hard gate:
any completeness failure stops the run before publishing) → analyze →
dashboard → publish. ~15–40 min depending on how many new schedule PDFs exist.
When it finishes, the team dashboard is live at
**https://leyixu26.github.io/celma-lgb/** (~1 min for Pages to redeploy).

Interrupted? Run it again — scraping is resumable and the publish is atomic
(one commit at the end).

## 3. Fully automatic (daily)

Windows **Task Scheduler** → Create Basic Task:
- Trigger: Daily, e.g. **08:30**
- Action: *Start a program* → Program: `refresh.bat` in the project folder
  (set *Start in* to the project folder)
- Finish. The machine must be on at that time; a missed day is harmless — the
  next run catches everything (schedules post ~the 20th; results within
  3 working days).

## 4. Renewals & upkeep

- **Token expires** (90 days): generate a new one, overwrite `token.txt`.
- **Yearly**: `pip install -U chinesecalendar` (holiday calendar for the new year).
- If a run ends with `INCOMPLETE`, just re-run — the site's live count moved
  mid-scrape; off-peak (early morning) converges in one pass.
