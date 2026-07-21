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
   If that fails for ANY reason ("No matching distribution found" on a corporate
   mirror, timeouts, SSL) — the wheel **ships inside this repo**, so install it
   with no network at all:
   ```bat
   pip install vendor\chinesecalendar-1.11.0-py2.py3-none-any.whl
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
  mirror doesn't carry it. For `chinesecalendar` use the vendored wheel
  (see step 2 above); for a core package, retry against PyPI directly:
  `pip install -r requirements.txt -i https://pypi.org/simple --trusted-host pypi.org --trusted-host files.pythonhosted.org`
- **Timeouts from pip (to PyPI or GitHub)** — your browser uses the corporate
  proxy but pip usually doesn't, so pip gets firewalled. In order:
  1. quick retry with a longer timeout: add `--default-timeout=60`;
  2. route pip through the proxy (address from IT, or Windows Settings →
     Network & Internet → Proxy): add `--proxy http://PROXYHOST:PORT`
     (combinable with `--trusted-host …`);
  3. avoid the network entirely: the calendar wheel is vendored in `vendor\`
     (step 2), and any other blocked package can be browser-downloaded from
     pypi.org (its "Download files" page) and installed as a local file:
     `pip install path\to\file.whl`.
  Note GitHub *release* downloads come from `objects.githubusercontent.com`,
  not github.com — if that domain is blocked, use the vendored copy instead.
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
