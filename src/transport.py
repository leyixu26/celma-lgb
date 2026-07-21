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
(or set env CELMA_TRANSPORT=powershell). Requests are sent as inline
-EncodedCommand, which works even under Restricted execution policy — no .ps1
files are written or run.
"""
from __future__ import annotations

import base64
import json as _json
import os
import re
import subprocess
import tempfile
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


class PSResponse:
    def __init__(self, status: int, content: bytes, url: str):
        self.status_code, self.content, self.url = status, content, url

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self):
        return _json.loads(self.text)

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

    def __init__(self, headers=None, timeout=40, **_ignored):
        self.headers = dict(headers or {})
        self.timeout = int(timeout) if isinstance(timeout, (int, float)) else 40

    def request(self, method: str, url: str, params=None, json=None) -> PSResponse:
        if params:
            url = url + ("&" if "?" in url else "?") + urlencode(params)
        out = tempfile.NamedTemporaryFile(delete=False)
        out.close()
        sf = tempfile.NamedTemporaryFile(delete=False, suffix=".status")
        sf.close()
        body_path = None
        ua = self.headers.get("User-Agent")
        hdrs = {k: v for k, v in self.headers.items() if k.lower() != "user-agent"}

        # Status is written to a FILE, not stdout — PowerShell serializes stdout
        # as CLIXML under capture (…_x000A_…</Objs>), which corrupts any marker
        # parsed from it. Files are immune. Status code uses [int] (the enum
        # stringifies to "OK", not 200).
        lines = [
            "$ProgressPreference='SilentlyContinue'",
            "[System.Net.WebRequest]::DefaultWebProxy.Credentials="
            "[System.Net.CredentialCache]::DefaultCredentials",
            "$h=@{}",
        ]
        for k, v in hdrs.items():
            lines.append(f"$h[{_q(k)}]={_q(v)}")
        cmd = (f"$r=Invoke-WebRequest -Uri {_q(url)} -UseBasicParsing "
               f"-TimeoutSec {self.timeout} -OutFile {_q(out.name)} -PassThru "
               f"-Method {method}")
        if ua:
            cmd += f" -UserAgent {_q(ua)}"
        if hdrs:
            cmd += " -Headers $h"
        if json is not None:
            bf = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
            bf.write(_json.dumps(json).encode("utf-8"))
            bf.close()
            body_path = bf.name
            cmd += (f" -Body ([System.IO.File]::ReadAllText({_q(body_path)}))"
                    " -ContentType 'application/json; charset=utf-8'")
        w = "[System.IO.File]::WriteAllText"
        lines += [
            "try { " + cmd + f"; {w}({_q(sf.name)},('STATUS:'+[int]$r.StatusCode)) }}",
            "catch { $resp=$_.Exception.Response",
            f"  if ($resp -ne $null) {{ {w}({_q(sf.name)},('STATUS:'+[int]$resp.StatusCode)) }}",
            f"  else {{ {w}({_q(sf.name)},('ERROR:'+$_.Exception.Message)) }} }}",
        ]
        enc = base64.b64encode("\n".join(lines).encode("utf-16-le")).decode()
        try:
            p = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                 "Bypass", "-InputFormat", "None", "-OutputFormat", "Text",
                 "-EncodedCommand", enc],
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
