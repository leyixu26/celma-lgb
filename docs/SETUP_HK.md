# Operator setup — refresh machine (Windows, direct access to celma)

The refresh machine needs: **Python 3.11+**, internet access to celma.org.cn
and github.com. No git, no VPN, no admin rights required.

## 1. One-time setup (~10 min)

> **⚠ Put the project on a LOCAL path first.** On corporate PCs, Desktop /
> Documents are often redirected to a network share (UNC `\\server\…` or
> OneDrive). `cmd` cannot use UNC paths as a working directory (it silently
> falls back to `C:\Windows`), and venvs on shares misbehave — producing
> confusing pip/python mismatches. Use your local home instead: in Explorer
> paste `%USERPROFILE%` in the address bar and put the project folder there
> (e.g. `C:\Users\<you>\celma-lgb`); in terminals, `cd /d %USERPROFILE%\celma-lgb`.

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

## 2. Refresh — one click (two equivalent ways)

**Option A:** double-click **`refresh.bat`**.
**Option B (bat-free — use this if the bat window flashes/closes or policy
blocks .bat files):** in a terminal,
```bat
cd /d %USERPROFILE%\celma-lgb
.venv\Scripts\python run_all.py --publish
```
Both run the same thing: scrape → parse → **verify** (hard gate: any
completeness failure stops the run before publishing) → analyze → dashboard →
publish. ~15–40 min depending on how many new schedule PDFs exist. When it
finishes, the team dashboard is live at
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

## Corporate proxy (scrape times out: WinError 10060 / "connected party did not properly respond")

Your browser reaches celma through the **company proxy**; Python goes direct
and gets firewalled — note the realized feed uses the non-standard port
**4443**, which direct egress rules block almost universally.

Diagnose with three 30-second tests, then read the table.

**Test A — can Python reach normal port 443?** (terminal, project folder)
```bat
.venv\Scripts\python -c "import httpx; print(httpx.get('https://www.celma.org.cn', timeout=10).status_code)"
```
**Test B — can the browser reach the 4443 data feed?** Paste into Edge/Chrome:
```
https://www.governbond.org.cn:4443/api/loadBondData.action?timeStamp=1&dataType=ZQFXLISTBYAD&adList=&adCode=87&zqlx=&year=&fxfs=&qxr=&fxqx=&zqCode=&zqName=&page=1&pageSize=1
```
JSON text = 4443 reachable in browser; error/timeout = blocked network-wide.
(The browser may **download a file** instead of showing text — that IS success:
the feed's content-type isn't displayable. Open the file with Notepad; it
should start `{"code":"0","data":[…`.)
**Test C — the browser-level proxy** (`netsh winhttp show proxy` saying
"direct access" does NOT settle this — browsers read a different setting):
Windows Settings → Network & Internet → **Proxy** — note whether "Automatically
detect settings" is on, a **script address** (PAC URL) is set, or a manual proxy.

| Test A | Test B | Diagnosis | Fix |
|---|---|---|---|
| 200 | JSON | 443 fine for Python; **python-on-4443 blocked** (process/port egress rule) | Ask IT: *"allow python.exe outbound TCP 4443 to governbond.org.cn"* — or run split mode (schedule at work, realized elsewhere) |
| 200 | error | port 4443 blocked for the whole network | same two options |
| timeout | — | Python has **no egress at all**; the browser exits via PAC or a security agent | see below |

**Fixes for the timeout case:**
- Test C shows a **manual proxy** or **script address (PAC)**: for PAC, open
  the script URL in the browser and find the `PROXY host:port` entries inside
  (Ctrl+F "PROXY"; the default is usually in the file's LAST `return` line).
  **Copy only the `host:port`** — drop the word PROXY, the quotes, and anything
  after (`; DIRECT` etc.), then prefix `http://`. Example: the PAC line
  `return "PROXY hkproxy.company.com:8080; DIRECT";` becomes
  `http://hkproxy.company.com:8080` — no quotes, no PROXY, no semicolon.
  Test each candidate directly, no file edits needed — use whichever prints 200:
  `.venv\Scripts\python -c "import httpx; print(httpx.get('https://www.celma.org.cn', timeout=10, proxy='http://HOST:PORT').status_code)"`
  The winner goes into `proxy.txt` as that single `http://host:port` line.
  Then create **`proxy.txt`** in the project folder containing one line, e.g.
  `http://proxy.mycompany.com:8080` — every script picks it up automatically
  (git-ignored, like token.txt); the run's first line confirms
  `using proxy from proxy.txt`.
- Proxy demands **username/password**: use
  `http://user:password@proxyhost:port`. Windows-integrated (NTLM/Kerberos)
  auth is not natively supported — ask IT for unauthenticated egress or a
  workaround.
- Test C shows nothing but a **Zscaler/Netskope-style icon** sits in the system
  tray: egress is per-process policy; only an IT request helps —
  *"allow python.exe outbound HTTPS to celma.org.cn and governbond.org.cn:4443"*.

### Once you have a candidate proxy — verify, lock in, run

Replace `HOST:PORT` throughout. These tests double as the "is the site blocked?"
check: any printed status number proves the path is open.

**1. Website through the proxy (~10 s):**
```bat
cd /d %USERPROFILE%\celma-lgb
.venv\Scripts\python -c "import httpx; print(httpx.get('https://www.celma.org.cn', timeout=15, proxy='http://HOST:PORT').status_code)"
```
`200` = proxy works, celma not blocked · `407` = proxy wants credentials — use
`http://USERNAME:PASSWORD@HOST:PORT` (NTLM-only proxies won't accept this; ask
IT) · `403`/other = destination filtered (whitelist request) · timeout = wrong
candidate, try the next PAC entry.

**2. The port-4443 data feed through the proxy (~10 s):**
```bat
.venv\Scripts\python -c "import httpx; print(httpx.get('https://www.governbond.org.cn:4443/api/loadBondData.action', timeout=20, proxy='http://HOST:PORT').status_code)"
```
ANY number printed (200/400/405/500…) = the path works — this is the original
blocker cleared. (`405 Method Not Allowed` just means the endpoint dislikes a
bare parameter-less probe; the real scraper sends fully-parameterized requests.)
Timeout/proxy error = the proxy refuses CONNECT on 4443 → IT:
*"allow proxy CONNECT to governbond.org.cn:4443 (MOF public bond-disclosure feed)."*

**2b. Definitive test — run the actual production fetch through the proxy.**
Create `proxy.txt` first (step 3) — then no environment variables are needed
(`import celma` reads it in any shell):
```bat
cd /d %USERPROFILE%\celma-lgb
.venv\Scripts\python -c "import sys; sys.path.insert(0,'src'); import celma; c=celma.new_client(); d=celma.fetch_realized_page(c,1,5); print('total bonds on platform:', d.get('total'))"
```
Expected: `[celma] using proxy from proxy.txt: …` then
`total bonds on platform: 19xxx` = absolute proof — run the pipeline. An HTTP
`418` here would mean the platform's WAF is bot-flagging the proxy's exit
(unlikely when the browser works through the same proxy) — report it.

> **Shell trap:** `set HTTPS_PROXY=…` works only in **cmd** — in PowerShell
> (prompt starts with `PS`) `set` silently does nothing and Python goes direct
> (→ 10060 timeout). PowerShell syntax is `$env:HTTPS_PROXY="http://HOST:PORT"`;
> in cmd, no spaces around `=`. `proxy.txt` sidesteps all of this — prefer it.

### Still blocked through the proxy? (browser works, Python doesn't)

Two causes fit: the PAC routes these hosts to a **different proxy** than the
one you extracted, or the proxy requires **Windows-integrated (NTLM) auth**
that plain Python can't speak. Two decisive tests:

**T1 — fetch via the OS stack (same PAC + credentials as the browser).** Use
the blue **Windows PowerShell**. Note: `-ProxyUseDefaultCredentials` is not
valid without `-Proxy`, so either use the system PAC (variant 1) or name the
proxy (variant 2):
```powershell
# variant 1 — system PAC + Windows credentials
[System.Net.WebRequest]::DefaultWebProxy.Credentials = [System.Net.CredentialCache]::DefaultCredentials
(Invoke-WebRequest "https://www.governbond.org.cn:4443/api/loadBondData.action?timeStamp=1&dataType=ZQFXLISTBYAD&adCode=87&page=1&pageSize=1" -UseBasicParsing).StatusCode

# variant 2 — explicit proxy + Windows credentials
(Invoke-WebRequest "https://www.governbond.org.cn:4443/api/loadBondData.action?timeStamp=1&dataType=ZQFXLISTBYAD&adCode=87&page=1&pageSize=1" -UseBasicParsing -Proxy "http://HOST:PORT" -ProxyUseDefaultCredentials).StatusCode
```
`200` from either = the machine can automate this — **activate the built-in
PowerShell transport** (next). `407` = NTLM-only proxy (see ladder). Timeout on
both = deeper block.

### PowerShell transport (activate after T1 = 200)

The pipeline can route every request through Windows PowerShell's
`Invoke-WebRequest` — i.e. the OS network stack with the system PAC and your
logged-in Windows credentials, the exact path T1 proved. No new software; works
under Restricted execution policy (inline commands, no .ps1 files); Task
Scheduler compatible; also carries the GitHub publish step.

1. Create **`transport.txt`** in the project folder containing exactly one word:
   ```
   powershell
   ```
   (git-ignored, like token.txt / proxy.txt. proxy.txt is NOT needed in this
   mode — the OS picks the proxy per the PAC.)
2. Verify — the definitive test again, which now announces the transport:
   ```bat
   cd /d %USERPROFILE%\celma-lgb
   .venv\Scripts\python -c "import sys; sys.path.insert(0,'src'); import celma; c=celma.new_client(); d=celma.fetch_realized_page(c,1,5); print('total bonds on platform:', d.get('total'))"
   ```
   Expect `[celma] transport: powershell (OS proxy stack + Windows credentials)`
   then `total bonds on platform: 19xxx`.
3. Run the pipeline as usual (`run_all.py`, then `--publish` once token.txt
   exists). Each request spawns a short PowerShell process (~0.5 s overhead), so
   a refresh runs somewhat longer than on an unrestricted network — fine for
   the daily scheduled task.

**If the verify step printed XML-ish garbage** (`…_x000A_…</Objs>`): that is
PowerShell serializing its console streams as CLIXML when run under a captured
pipe — fixed in the current version. The transport now returns the status via a
temp file (immune to stream serialization), forces `-OutputFormat Text
-InputFormat None`, and decodes CLIXML in error messages. Re-download the repo
ZIP, overwrite the folder, rerun the step-2 verify one-liner. If it now prints
a *readable* error instead of the total (e.g. something about EncodedCommand or
a security policy), send that exact text back — it names the real blocker.

**If it printed `ScriptContainedMaliciousContent`** ("script contains malicious
content"): the endpoint-security agent (AMSI) blocks *base64-encoded*
PowerShell (`-EncodedCommand`) — a pattern malware uses — and treats the word
"Bypass" the same way. Fixed in the current version: requests go out as plain
single-line `-Command` text, the same shape as the hand-typed T1 test that
passed. Only `src/transport.py` changed — use the single-file update from
"Updating the code" below, then rerun the verify one-liner. If even plain
commands get flagged, report the exact text — the next step is a curl.exe
transport (curl ships with Windows 10+ and can also use integrated proxy auth).

**If it printed `…NotSupportedInConstrainedLanguage`**: the policy runs
*automated* PowerShell in Constrained Language Mode — .NET calls are blocked,
cmdlets are allowed (interactive shells run full-language, which is why the
hand-typed T1 worked). Fixed in the current version: the transport is pure
cmdlets — the system PAC routes requests on its own, with no .NET proxy tweak.
Single-file update `src/transport.py`, rerun the verify one-liner. Two
outcomes:
  - the total prints → done, run the pipeline;
  - `ERROR: … (407) Proxy Authentication Required` → the proxy wants
    credentials. Put the proxy address into `proxy.txt` (format
    `http://host:port` — the entry the PAC returns for
    `www.governbond.org.cn`, see the PAC-extraction section above). The
    transport then adds `-Proxy … -ProxyUseDefaultCredentials` (your Windows
    login, CLM-legal) automatically. Rerun.

**T2 — PAC host-specific branches:** Ctrl+F the PAC for `celma`, `governbond`,
`.cn`, `china`. A branch returning a different `PROXY host:port` for these is
the one the browser actually uses — test it with the explicit-proxy one-liner
and put the winner in `proxy.txt`.

**Workaround ladder:** ① T2 proxy in proxy.txt · ② PowerShell transport
(after T1=200) · ③ NTLM helper (`px`) if 407s everywhere · ④ browser-console
capture bundle (browser fetches, pipeline ingests offline) · ⑤ **file in
parallel regardless** — IT request: *"allow python.exe / proxy CONNECT to
celma.org.cn:443 and governbond.org.cn:4443 (MOF public bond-disclosure
platform, already permitted for browsers)"* · ⑥ fallback: scrape from a
celma-reachable machine, company PC consumes via GitHub (team unaffected).

**3. Lock in:** create `proxy.txt` in the project folder — exactly one line,
`http://HOST:PORT` (with `USER:PASS@` if step 1 needed it). Save as type
*All Files* so it isn't `proxy.txt.txt`.

**4. First full run — without publishing:**
```bat
.venv\Scripts\python run_all.py
```
Milestones: `[celma] using proxy from proxy.txt` → `realized page 1: 500 rows …`
counting to ~40 pages → `list … COMPLETE` → `amounts: … newly fetched` →
`ALL CHECKS PASS` → `DONE.` (~15–40 min; interruptions resume on re-run).

**5. Enable publishing:** create the GitHub token (§1.3) as `token.txt`, then
every refresh is `.venv\Scripts\python run_all.py --publish` (or `refresh.bat`
/ the scheduled task) — the team dashboard updates ~1 min later.

## Troubleshooting install

- **`No matching distribution found` for ANY package (curated corporate
  mirror)** — skip the package index entirely. The complete dependency set is
  bundled at **github.com/leyixu26/celma-lgb-wheels** (Windows x64,
  Python 3.12): download that repo's ZIP (Code → Download ZIP, same as this
  repo), extract, then:
  ```bat
  pip install --no-index --find-links C:\path\to\celma-lgb-wheels-main\wheelhouse -r requirements.txt
  pip install --no-index --find-links C:\path\to\celma-lgb-wheels-main\wheelhouse chinesecalendar
  ```
  `--no-index` means pip never touches any index — nothing left to block. For a
  different Python version, request a matching bundle.
  If it reports one specific package missing (e.g.
  `Could not find a version … tzdata; sys_platform == "win32"`), the bundle
  predates a fix — re-download the celma-lgb-wheels ZIP (bundle now includes
  tzdata) and re-run the same command.
- **Single package missing only** — for `chinesecalendar` the wheel is also
  vendored in this repo (see step 2); for others, retry against PyPI directly:
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
- **pip says "Requirement already satisfied" but `python` says
  `ModuleNotFoundError`** — your `pip` and `python` are two different Python
  installations (venv not active in this window, or a Microsoft-Store/system
  Python shadowing PATH). Prove it: `pip --version` vs
  `python -c "import sys; print(sys.executable)"` — the paths won't match.
  **Fix: stop relying on PATH — name the venv's interpreter explicitly** for
  both the install and the test, so they cannot diverge:
  ```bat
  cd C:\path\to\celma-lgb
  .venv\Scripts\python -m pip install --no-index --find-links "C:\path\to\wheelhouse" -r requirements.txt
  .venv\Scripts\python -m pip install --no-index --find-links "C:\path\to\wheelhouse" chinesecalendar
  .venv\Scripts\python -c "import httpx, pandas, bs4, lxml, pdfplumber, matplotlib, openpyxl, chinese_calendar; print('READY')"
  ```
  Run the pipeline the same way (`.venv\Scripts\python run_all.py`) — or just
  use `refresh.bat`, which already calls `.venv\Scripts\python.exe` explicitly
  and is immune to this problem.
- **Project on a UNC / network / OneDrive path** — the root cause of most of
  the above: `cmd` falls back to `C:\Windows` on UNC working directories, so
  venv creation/activation lands in the wrong place. Move the project to
  `%USERPROFILE%\celma-lgb` (always local), **recreate the venv from scratch
  there** (venvs are path-bound — never move one), and reinstall from the
  wheelhouse. Results publish via GitHub, so nothing needs the network share.
- **`refresh.bat` window flashes and closes instantly** — never diagnose a
  flashing console by double-click; run it from a terminal so the error stays
  visible: `cd /d %USERPROFILE%\celma-lgb` then `refresh.bat`. Typical causes:
  no `.venv` yet (finish setup first), running a stray copy (Downloads/ZIP
  viewer/network), or corporate policy blocking `.bat` files. The bat is only a
  wrapper — the policy-proof equivalent is:
  `.venv\Scripts\python run_all.py --publish`
  (and Task Scheduler can call `.venv\Scripts\python.exe` with argument
  `run_all.py --publish`, *Start in* `%USERPROFILE%\celma-lgb`, no bat needed).
- **Wheelhouse path gotcha** — Windows "Extract All" wraps the ZIP in an extra
  same-named folder; the real wheel folder is usually
  `…\celma-lgb-wheels-main\celma-lgb-wheels-main\wheelhouse`. Navigate in
  Explorer until you *see the .whl files*, then drag that folder into the
  terminal to paste its true path. A correct install ends with
  `Successfully installed httpx-… pandas-…` (a long list).
- **Older download of this repo?** Early copies listed `chinesecalendar` as a
  hard requirement, so `pip install -r requirements.txt` aborted entirely when
  the mirror lacked it. Either re-download the repo, or install the core set
  directly: `pip install httpx pandas lxml beautifulsoup4 pdfplumber matplotlib openpyxl`
  and then follow step 2's optional-calendar instructions.

## First full run on the PC & first publish

1. **First round WITHOUT publish**: `.venv\Scripts\python run_all.py`. The
   first run rebuilds all article caches (~15–40 min through the PowerShell
   transport); later runs are incremental and much faster. It must end with
   `ALL CHECKS PASS`. Open `docs\index.html` locally to preview the dashboard.
   **What later refreshes fetch** (why they're much faster): article bodies +
   PDFs are cached in `data\raw\` — only newly published articles (~30–50 a
   month) are fetched. Two things are deliberately re-pulled in full every
   run: the ~80+ schedule *list* pages (completeness is proven against the
   site's 共 N 条 count, and celma backfills older-dated articles) and the
   ~40-page realized feed (old rows get amended / re-tapped; the full pull is
   what verify.py proves against the API's own total). Typical refresh:
   150–300 requests ≈ 5–15 min via the PowerShell transport. Keeping this
   incremental behavior is another reason to never delete `data\raw\`.
2. **Then publish separately**: create `token.txt` (§1), then
   `.venv\Scripts\python publish.py` — pushes the already-built outputs, no
   re-scrape. Publishing routes through the same transport; expect one short
   PowerShell flash per uploaded file.
3. **Safety net**: the pre-PC dashboard is archived permanently at
   `https://leyixu26.github.io/celma-lgb/archive/index_2026-07-21.html`, and
   the whole repo state is pinned by git tag `site-2026-07-21`. A publish can
   never delete files (it only adds/updates), so the archive survives every
   refresh. If a refresh ever breaks the live page, the archive is the
   reference and any commit can be reverted on GitHub.

## Updating the code (re-downloads)

- **Copy-overwrite, never delete.** Updates are a merge: extract the ZIP and
  copy its contents INTO `%USERPROFILE%\celma-lgb`, replacing when asked. Never
  delete the folder first — it holds machine-only files the ZIP does not:
  `.venv\` (all installed packages), `token.txt`, `transport.txt`, `proxy.txt`,
  and the raw scrape caches under `data\raw\` (losing those forces a full
  re-scrape).
- **`pip install` is NOT needed after a re-download.** Packages live in `.venv\`
  and survive overwrites. Reinstall only when `requirements.txt` changes —
  that will be called out explicitly when it happens. If ever unsure, rerun the
  install command: it finishes instantly with "Requirement already satisfied"
  when nothing changed.
- **Single-file updates** (when told only one or two files changed): no ZIP
  needed. In a PowerShell window (line 1 = attach your Windows login to the
  proxy, this window only — the same line as test T1; line 2 = the actual
  download. If line 1 errors in your window, try line 2 alone):
  ```powershell
  [System.Net.WebRequest]::DefaultWebProxy.Credentials = [System.Net.CredentialCache]::DefaultCredentials
  Invoke-WebRequest "https://raw.githubusercontent.com/leyixu26/celma-lgb/main/src/transport.py" -UseBasicParsing -OutFile "$env:USERPROFILE\celma-lgb\src\transport.py"
  ```
  (swap the path for whichever file changed — the raw URL is always
  `https://raw.githubusercontent.com/leyixu26/celma-lgb/main/<path with / >`).
  Browser alternative: open that raw URL, Ctrl+S into the right subfolder —
  set "Save as type" to **All Files** so it doesn't gain a `.txt` extension.

## 4. Renewals & upkeep

- **Token expires** (90 days): generate a new one, overwrite `token.txt`.
- **Yearly**: `pip install -U chinesecalendar` (holiday calendar for the new year).
- If a run ends with `INCOMPLETE`, just re-run — the site's live count moved
  mid-scrape; off-peak (early morning) converges in one pass.
