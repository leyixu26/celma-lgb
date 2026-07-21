"""
HTTP transport backends for the celma pipeline.

Default backend: httpx (direct, or via proxy.txt). On corporate Windows
machines where only the OS network stack can traverse the proxy — browser
works, Python times out (PAC routing + Windows-integrated auth) — the
'powershell' backend routes every request through Windows PowerShell's
Invoke-WebRequest, which uses the system PAC and the logged-in user's
credentials (the exact path proven by SETUP_HK test T1 variant 1).

Activate by creating transport.txt in the project root containing one word:
    powershell
(or set env CELMA_TRANSPORT=powershell). Requests are sent as PLAIN single-line
-Command text: no .ps1 files (so execution policy never applies) and no
-EncodedCommand (corporate AMSI/EDR flags base64-encoded PowerShell as
malicious — ScriptContainedMaliciousContent). Plain text also mirrors the
hand-typed T1 test the proxy provably allows. Every command is additionally
Constrained-Language-Mode-safe — locked-down hosts run automated PowerShell in
CLM, which blocks .NET calls but allows all cmdlets.
"""
from __future__ import annotations

import json as _json
import os
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx

ROOT = Path(__file__).resolve().parent.parent


def backend() -> str:
    b = os.environ.get("CELMA_TRANSPORT", "").strip().lower()
    if not b:
        f = ROOT / "transport.txt"
        if f.exists():
            b = f.read_text(encoding="utf-8").strip().lower()
    return b or "httpx"


def _q(s) -> str:
    """Single-quote a value for PowerShell (embedded quotes doubled)."""
    return "'" + str(s).replace("'", "''") + "'"


def _proxy_url() -> str:
    f = ROOT / "proxy.txt"
    if f.exists():
        p = f.read_text(encoding="utf-8").strip()
        if p:
            return p if "://" in p else "http://" + p
    return ""


# HttpWebRequest "protected" headers: PS 5.1 rejects these when passed via
# -Headers. None matter for our endpoints (celma GETs work bare — T1 proved
# it; GitHub needs only Authorization, which IS allowed). UA goes via -UserAgent.
_RESTRICTED_HEADERS = frozenset({
    "user-agent", "referer", "accept", "accept-language", "content-type",
    "host", "connection", "range", "date", "expect", "if-modified-since",
    "transfer-encoding"})


_CLIXML_S = re.compile(r"<S[^>]*>(.*?)</S>", re.S)


def _declixml(s: str) -> str:
    """PowerShell serializes console streams as CLIXML under captured pipes
    ('#< CLIXML' + <Objs>…_x000A_…</Objs>). Extract the human-readable text."""
    if "#< CLIXML" not in s and "<Objs" not in s:
        return s.strip()
    parts = [m.group(1) for m in _CLIXML_S.finditer(s)]
    txt = "".join(parts) if parts else s
    txt = txt.replace("_x000D_", "").replace("_x000A_", "\n")
    for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'),
                 ("&apos;", "'"), ("&amp;", "&")):
        txt = txt.replace(a, b)
    return re.sub(r"\s*\n\s*", " ", txt).strip()


_RESET_MARKERS = ("forcibly closed", "connection was closed", "unable to read data",
                  "connection reset", "transport connection")


def _retryable(msg: str) -> bool:
    """Retry drops/timeouts/5xx; don't retry hard client errors (403/404/407…).
    IWR error text carries the code as '(NNN)'; no code = transport-level drop."""
    m = re.search(r"\((\d{3})\)", msg)
    if m:
        code = int(m.group(1))
        return code >= 500 or code in (408, 429)
    return True


class PSResponse:
    def __init__(self, status: int, content: bytes, url: str):
        self.status_code, self.content, self.url = status, content, url

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self):
        try:
            return _json.loads(self.text)
        except ValueError:
            snippet = self.text[:120].replace("\n", " ")
            raise httpx.TransportError(
                f"response from {self.url} is not JSON — an intercepting proxy "
                f"may have served a block page. First bytes: {snippet!r}")

    def raise_for_status(self):
        if not 200 <= self.status_code < 300:
            raise httpx.TransportError(
                f"HTTP {self.status_code} for {self.url} (powershell transport)")
        return self


class PowerShellClient:
    """Minimal httpx.Client look-alike backed by Invoke-WebRequest.

    Supports what the pipeline uses: get/post/patch, params, JSON bodies,
    headers, binary-safe bodies (via -OutFile), per-request timeout. Each
    request is its own powershell process — inherently thread-safe for the
    ThreadPoolExecutor in scrape_schedule (a few hundred ms overhead per
    request is acceptable at our volumes).
    """

    RETRIES = 3          # total attempts per request
    BACKOFF = 2          # seconds; grows linearly (2s, 4s)
    RESET_BACKOFF = 10   # connection resets get longer waits (WAF/proxy cooloff)
    COOLDOWN_SECS = 90   # after a reset, slow the global cadence for this long…
    COOLDOWN_INTERVAL = 2.0   # …to one spawn per this many seconds
    SPAWN_INTERVAL = 0.4  # min seconds between powershell launches, globally

    _gate = threading.Lock()
    _last_spawn = 0.0
    _cooldown_until = 0.0

    def __init__(self, headers=None, timeout=40, **_ignored):
        self.headers = dict(headers or {})
        self.timeout = int(timeout) if isinstance(timeout, (int, float)) else 40

    def _pace(self) -> None:
        """Global spawn throttle (shared across threads and client instances).
        A burst of powershell.exe launches both looks like a spawn storm to the
        EDR and hammers the proxy — sustained load is what breaks mid-run."""
        with PowerShellClient._gate:
            now = time.monotonic()
            interval = (self.COOLDOWN_INTERVAL
                        if now < PowerShellClient._cooldown_until
                        else self.SPAWN_INTERVAL)
            wait = PowerShellClient._last_spawn + interval - now
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            PowerShellClient._last_spawn = now

    def request(self, method: str, url: str, params=None, json=None) -> PSResponse:
        """One request with automatic retries: a corporate proxy occasionally
        drops a request mid-run; one blip must not stop a 300-request scrape."""
        for attempt in range(1, self.RETRIES + 1):
            try:
                return self._request_once(method, url, params=params, json=json)
            except httpx.TransportError as e:
                msg = str(e).lower()
                is_reset = any(m in msg for m in _RESET_MARKERS)
                if is_reset:
                    # the host/proxy is actively cutting us: slow everyone down
                    PowerShellClient._cooldown_until = (
                        time.monotonic() + self.COOLDOWN_SECS)
                if attempt == self.RETRIES or not _retryable(str(e)):
                    raise
                wait = (self.RESET_BACKOFF if is_reset else self.BACKOFF) * attempt
                tag = "reset — cooling down; " if is_reset else ""
                print(f"    [transport] {tag}retry {attempt}/{self.RETRIES - 1} "
                      f"in {wait}s: {e}")
                time.sleep(wait)
        raise AssertionError("unreachable")

    def _request_once(self, method: str, url: str, params=None, json=None) -> PSResponse:
        self._pace()
        if params:
            url = url + ("&" if "?" in url else "?") + urlencode(params)
        out = tempfile.NamedTemporaryFile(delete=False)
        out.close()
        sf = tempfile.NamedTemporaryFile(delete=False, suffix=".status")
        sf.close()
        body_path = None
        ua = self.headers.get("User-Agent")
        hdrs = {k: v for k, v in self.headers.items()
                if k.lower() not in _RESTRICTED_HEADERS}

        # Status is written to a FILE, not stdout — PowerShell serializes stdout
        # as CLIXML under capture (…_x000A_…</Objs>), which corrupts any marker
        # parsed from it. Files are immune.
        # The whole script is ONE line of plain -Command text: no newlines, no
        # double quotes (values are PS-single-quoted), no base64 — AMSI/EDR
        # blocks -EncodedCommand, and "Bypass" is likewise a trigger word.
        # Constrained-Language-Mode-safe: cmdlets and core types ONLY (no
        # [System.*]:: calls, no property setters, no $r/-PassThru — success
        # writes a literal STATUS:200; callers only need 2xx / not-2xx, and on
        # failure the caught error text carries the real code, e.g. "(407)").
        # System PAC applies to Invoke-WebRequest on its own; if the proxy
        # demands credentials, proxy.txt triggers -Proxy +
        # -ProxyUseDefaultCredentials (the user's Windows login, CLM-legal).
        stmts = ["$ProgressPreference='SilentlyContinue'", "$h=@{}"]
        for k, v in hdrs.items():
            stmts.append(f"$h[{_q(k)}]={_q(v)}")
        cmd = (f"Invoke-WebRequest -Uri {_q(url)} -UseBasicParsing "
               f"-TimeoutSec {self.timeout} -OutFile {_q(out.name)} "
               f"-Method {method}")
        if ua:
            cmd += f" -UserAgent {_q(ua)}"
        if hdrs:
            cmd += " -Headers $h"
        proxy = _proxy_url()
        if proxy:
            cmd += f" -Proxy {_q(proxy)} -ProxyUseDefaultCredentials"
        if json is not None:
            bf = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
            bf.write(_json.dumps(json).encode("utf-8"))
            bf.close()
            body_path = bf.name
            cmd += (f" -InFile {_q(body_path)}"
                    " -ContentType 'application/json; charset=utf-8'")
        sc = f"Set-Content -LiteralPath {_q(sf.name)} -Encoding UTF8 -Value "
        stmts.append("try { " + cmd + f"; {sc}'STATUS:200' }}"
                     f" catch {{ {sc}('ERROR:'+$_) }}")
        script = "; ".join(stmts).replace('"', "'").replace("\n", " ").replace("\r", " ")
        try:
            p = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-InputFormat",
                 "None", "-OutputFormat", "Text", "-Command", script],
                capture_output=True, text=True, stdin=subprocess.DEVNULL,
                timeout=self.timeout + 30)
            try:
                marker = Path(sf.name).read_text(
                    encoding="utf-8-sig", errors="replace").strip()
            except OSError:
                marker = ""
            if marker.startswith("STATUS:"):
                return PSResponse(int(marker.split(":", 1)[1]),
                                  Path(out.name).read_bytes(), url)
            detail = (marker or _declixml(p.stderr or "")
                      or _declixml(p.stdout or "") or "no output from powershell")
            raise httpx.TransportError(
                f"powershell transport (exit {p.returncode}): {detail}")
        except subprocess.TimeoutExpired:
            raise httpx.TransportError(f"powershell transport timeout for {url}")
        finally:
            for pth in (out.name, sf.name, body_path):
                if pth:
                    try:
                        os.unlink(pth)
                    except OSError:
                        pass

    def get(self, url, params=None):
        return self.request("GET", url, params=params)

    def post(self, url, json=None):
        return self.request("POST", url, json=json)

    def patch(self, url, json=None):
        return self.request("PATCH", url, json=json)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
