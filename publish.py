"""
Publish refreshed data to GitHub as ONE commit via the REST API — no git
required on this machine. Auth: a fine-grained personal access token with
Contents read/write on this repository, in the GITHUB_TOKEN environment
variable (or a token.txt next to this file, git-ignored).

    python publish.py
"""
from __future__ import annotations

import base64
import os
import sys
from datetime import date
from pathlib import Path

import httpx

OWNER, REPO, BRANCH = "leyixu26", "celma-lgb", "main"
ROOT = Path(__file__).resolve().parent
PUBLISH = ["data/clean", "outputs", "docs", "VERIFICATION.md"]
API = f"https://api.github.com/repos/{OWNER}/{REPO}"


def token() -> str:
    t = os.environ.get("GITHUB_TOKEN", "").strip()
    if not t and (ROOT / "token.txt").exists():
        t = (ROOT / "token.txt").read_text(encoding="utf-8").strip()
    if not t:
        sys.exit("No token: set GITHUB_TOKEN or create token.txt (see docs/SETUP_HK.md).")
    return t


def collect() -> list[Path]:
    files: list[Path] = []
    for spec in PUBLISH:
        p = ROOT / spec
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files += [f for f in sorted(p.rglob("*")) if f.is_file()]
    return files


def make_client():
    sys.path.insert(0, str(ROOT / "src"))
    from transport import backend, PowerShellClient
    headers = {"Authorization": f"Bearer {token()}",
               "Accept": "application/vnd.github+json"}
    if backend() == "powershell":
        print("publish: powershell transport (OS proxy stack)")
        return PowerShellClient(headers=headers, timeout=120)
    return httpx.Client(headers=headers, timeout=120, follow_redirects=True)


def main() -> None:
    c = make_client()
    head = c.get(f"{API}/git/ref/heads/{BRANCH}")
    head.raise_for_status()
    base_commit = head.json()["object"]["sha"]
    base_tree = c.get(f"{API}/git/commits/{base_commit}").json()["tree"]["sha"]

    files = collect()
    tree = []
    for f in files:
        blob = c.post(f"{API}/git/blobs", json={
            "content": base64.b64encode(f.read_bytes()).decode(), "encoding": "base64"})
        blob.raise_for_status()
        tree.append({"path": str(f.relative_to(ROOT)).replace(os.sep, "/"),
                     "mode": "100644", "type": "blob", "sha": blob.json()["sha"]})
        print(f"  blob {f.relative_to(ROOT)}")
    new_tree = c.post(f"{API}/git/trees", json={"base_tree": base_tree, "tree": tree})
    new_tree.raise_for_status()
    commit = c.post(f"{API}/git/commits", json={
        "message": f"data refresh {date.today()}",
        "tree": new_tree.json()["sha"], "parents": [base_commit]})
    commit.raise_for_status()
    sha = commit.json()["sha"]
    upd = c.patch(f"{API}/git/refs/heads/{BRANCH}", json={"sha": sha})
    upd.raise_for_status()
    print(f"\npushed {len(files)} files as {sha[:10]} -> https://github.com/{OWNER}/{REPO}")
    print(f"dashboard: https://{OWNER}.github.io/{REPO}/  (Pages redeploys in ~1 min)")


if __name__ == "__main__":
    main()
