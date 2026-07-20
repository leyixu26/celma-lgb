"""
Scrape REALIZED issuance (发行结果) from the JSON feed into data/raw/realized_json/.

Completeness is self-checked: pagination continues until the record count equals
the API's own `total`, and page 1 (holding `total` + `sumCount`) is kept so
verify.py can prove the pull against the source's own figures.

    python src/scrape_realized.py            # full history (~40 pages, a few minutes)
Re-running refreshes everything (the feed is one consistent database, so a full
re-pull is the correct refresh, not an increment).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx

from celma import DATA_RAW, new_client, fetch_realized_page

OUT = DATA_RAW / "realized_json"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("page_*.json"):   # full refresh: clear the previous pull
        old.unlink()
    client = new_client()
    page, got, total = 1, 0, None
    while True:
        try:
            data = fetch_realized_page(client, page=page)
        except httpx.HTTPError as e:
            if page == 1:
                sys.exit(f"FAILED on page 1 ({type(e).__name__}: {e}) — is celma reachable from this network?")
            print(f"page {page} error ({type(e).__name__}); stopping — re-run to complete.")
            break
        (OUT / f"page_{page:04d}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        rows = data.get("data", []) or []
        total = int(data.get("total", 0) or 0)
        got += len(rows)
        print(f"page {page:>3}: {len(rows):>4} rows | {got}/{total}")
        if not rows or (total and got >= total):
            break
        page += 1
        time.sleep(0.5)
    client.close()
    status = "COMPLETE" if (total and got >= total) else "INCOMPLETE"
    (DATA_RAW / "realized_provenance.json").write_text(json.dumps(
        {"api_total": total, "rows_pulled": got, "pages": page, "status": status},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{status}: {got}/{total} records -> {OUT}/")


if __name__ == "__main__":
    main()
