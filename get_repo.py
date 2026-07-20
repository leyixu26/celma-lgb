"""
Download this repository (code + data) onto any machine with Python + internet —
no git and no login needed (the repo is public).

    python get_repo.py           # downloads and extracts into ./celma-lgb/
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import urllib.request

URL = "https://api.github.com/repos/leyixu26/celma-lgb/zipball/main"


def main() -> None:
    print("downloading …")
    data = urllib.request.urlopen(URL, timeout=120).read()
    z = zipfile.ZipFile(io.BytesIO(data))
    root = z.namelist()[0].split("/")[0]
    dest = Path("celma-lgb")
    for name in z.namelist():
        rel = name[len(root) + 1:]
        if not rel:
            continue
        target = dest / rel
        if name.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(name))
    print(f"extracted to ./{dest}/ — open {dest}/docs/index.html or see README.md")


if __name__ == "__main__":
    main()
