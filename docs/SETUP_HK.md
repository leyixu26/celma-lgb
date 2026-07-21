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

   Then add the **optional China holiday calendar** (recommended — used for
   working-day lead metrics):
   ```bat
   pip install chinesecalendar
   ```
   If that fails with *"No matching distribution found"* (common on corporate
   PyPI mirrors that don't carry this niche package), install it straight from
   this repo's GitHub release instead — GitHub is reachable where PyPI mirrors
   are curated:
   ```bat
   pip install https://github.com/leyixu26/celma-lgb/releases/download/v1.1/chinesecalendar-1.11.0-py2.py3-none-any.whl
   ```
   If both fail, **just proceed without it** — the pipeline runs fully and
   falls back to a Mon–Fri calendar. Only `lead_wd` (working-day lead times) is
   affected, slightly overcounting across CN holidays/调休 weeks; the on-time
   test, coverage, and all amounts are date-based and unaffected. Runs in
   fallback mode print an explicit `NOTE:` so the basis is always visible.
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

## Troubleshooting install

- **`No matching distribution found for <package>`** — your network's PyPI
  mirror doesn't carry it. For `chinesecalendar` use the GitHub-release wheel
  (see step 2 above); for a core package, retry against PyPI directly:
  `pip install -r requirements.txt -i https://pypi.org/simple --trusted-host pypi.org --trusted-host files.pythonhosted.org`
- **SSL / certificate errors from pip** — append
  `--trusted-host pypi.org --trusted-host files.pythonhosted.org`.
- **Older download of this repo?** Early copies listed `chinesecalendar` as a
  hard requirement, so `pip install -r requirements.txt` aborted entirely when
  the mirror lacked it. Either re-download the repo, or install the core set
  directly: `pip install httpx pandas lxml beautifulsoup4 pdfplumber matplotlib openpyxl`
  and then follow step 2's optional-calendar instructions.

## 4. Renewals & upkeep

- **Token expires** (90 days): generate a new one, overwrite `token.txt`.
- **Yearly**: `pip install -U chinesecalendar` (holiday calendar for the new year).
- If a run ends with `INCOMPLETE`, just re-run — the site's live count moved
  mid-scrape; off-peak (early morning) converges in one pass.
