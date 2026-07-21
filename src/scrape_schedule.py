"""
Scrape the issuance SCHEDULE (发行安排): the article list, then each article's
planned amounts.

List completeness is proven, not assumed: pages are fetched concurrently (a
near-instant snapshot of the live list) and the pass repeats, unioning unique
article ids, until the count equals the site's own "共 N 条" total. The result
is recorded in data/raw/schedule_provenance.json (COMPLETE / INCOMPLETE).

Amounts: each article page (and its linked PDF, where the tables usually live)
is fetched once and its text cached to data/raw/schedule_articles/<id>.txt —
interrupted runs simply resume, and future refreshes only fetch new articles.

    python src/scrape_schedule.py                 # list + amounts
    python src/scrape_schedule.py --skip-amounts  # list only
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx
from bs4 import BeautifulSoup

from celma import (DATA_RAW, new_client, list_page_url, parse_list_html,
                   site_total, max_page, parse_schedule_amounts, pdf_links)

LIST_OUT = DATA_RAW / "schedule_list.jsonl"
AMOUNTS_OUT = DATA_RAW / "schedule_amounts.csv"
CACHE = DATA_RAW / "schedule_articles"
AMOUNT_FIELDS = ["new_general_yi", "new_special_yi", "refinance_yi"]


def scrape_list(workers: int, max_passes: int) -> list[dict]:
    from transport import backend
    if backend() == "powershell" and workers > 2:
        print("  [transport] powershell backend: capping list workers at 2 "
              "(sustained 6-way spawn bursts trip proxy/EDR throttling)")
        workers = 2
    client = new_client()
    by_id: dict[str, dict] = {}
    target, prev = None, -1
    err_pages: set[int] = set()
    for p in range(1, max_passes + 1):
        try:
            h1 = client.get(list_page_url(1)).text
        except httpx.HTTPError as e:
            sys.exit(f"FAILED on list page 1 ({type(e).__name__}: {e}) — is celma reachable?")
        target = site_total(h1) or target
        npages = max_page(h1)
        for row in parse_list_html(h1):
            by_id.setdefault(row["article_id"], row)
        # later passes retry only the pages that failed, not the whole sweep
        todo = sorted(err_pages) if (p > 1 and err_pages) else list(range(2, npages + 1))
        if p > 1 and err_pages:
            print(f"  pass {p}: refetching {len(todo)} previously failed pages")
        err_pages = set()
        done = 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(lambda pg: client.get(list_page_url(pg)).text, pg): pg
                    for pg in todo}
            for fut in as_completed(futs):
                try:
                    for row in parse_list_html(fut.result()):
                        by_id.setdefault(row["article_id"], row)
                except Exception as e:  # noqa: BLE001
                    err_pages.add(futs[fut])
                    print(f"  page {futs[fut]} error: {type(e).__name__}: {e}")
                done += 1
                if done % 20 == 0:
                    print(f"  … {done}/{len(todo)} list pages this pass "
                          f"({len(by_id)} unique so far)")
        got = len(by_id)
        tail = f" ({len(err_pages)} pages failed)" if err_pages else ""
        print(f"list pass {p}: {got} unique / {target} target{tail}")
        if (target and got >= target) or (got == prev and not err_pages):
            break
        prev = got
        time.sleep(1)
    client.close()
    rows = list(by_id.values())
    LIST_OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    status = "COMPLETE" if (target and len(rows) >= target) else "INCOMPLETE"
    (DATA_RAW / "schedule_provenance.json").write_text(json.dumps(
        {"site_total_tiao": target, "scraped_unique": len(rows), "status": status},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"list {status}: {len(rows)}/{target} -> {LIST_OUT}")
    return rows


def article_text(client: httpx.Client, row: dict) -> str:
    """Article HTML text + linked-PDF text, cached to disk (resumable)."""
    f = CACHE / f"{row['article_id']}.txt"
    if f.exists():
        return f.read_text(encoding="utf-8")
    soup = BeautifulSoup(client.get(row["url"]).text, "lxml")
    text = soup.get_text(" ", strip=True)
    for purl in pdf_links(soup)[:4]:
        pdf_bytes = client.get(purl).content   # fetch failures PROPAGATE: a
        # flaky-network article must not be cached without its PDF text, or the
        # amounts would be lost forever (cache hit skips refetching)
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                text += "\n[PDF] " + "\n".join((pg.extract_text() or "") for pg in pdf.pages)
        except Exception:  # noqa: BLE001
            pass                               # corrupt PDF: cache what we have
    tmp = f.with_suffix(".tmp")   # atomic: a Ctrl+C can never leave a truncated cache entry
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(f)
    return text


def scrape_amounts(rows: list[dict], delay: float) -> None:
    """Incremental: article_ids that already have figures in schedule_amounts.csv
    are reused without refetching; only new articles (and past misses) are fetched."""
    CACHE.mkdir(parents=True, exist_ok=True)
    prior: dict[str, dict] = {}
    if AMOUNTS_OUT.exists():
        with AMOUNTS_OUT.open(encoding="utf-8-sig") as f:
            for rec in csv.DictReader(f):
                vals = {k: float(rec[k]) for k in AMOUNT_FIELDS if rec.get(k) not in (None, "")}
                if vals:
                    prior[rec["article_id"]] = vals
    client = new_client()
    out, hits, fetched = [], 0, 0
    for i, r in enumerate(rows, 1):
        rec = {"article_id": r["article_id"]}
        if r["article_id"] in prior:
            rec.update(prior[r["article_id"]])
            hits += 1
        else:
            try:
                parsed = parse_schedule_amounts(article_text(client, r))
                rec.update(parsed)
                hits += bool(parsed)
                fetched += 1
                time.sleep(delay)
            except Exception as e:  # noqa: BLE001
                print(f"  {r['article_id']} error: {type(e).__name__}: {e}")
        out.append(rec)
        if i % 25 == 0:
            print(f"amounts: {i}/{len(rows)} ({hits} parsed, {fetched} newly fetched)")
    client.close()
    with AMOUNTS_OUT.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["article_id"] + AMOUNT_FIELDS)
        w.writeheader()
        w.writerows(out)
    print(f"amounts parsed for {hits}/{len(out)} schedules -> {AMOUNTS_OUT}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Scrape the 发行安排 schedule (list + planned amounts)")
    ap.add_argument("--skip-amounts", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-passes", type=int, default=10)
    ap.add_argument("--delay", type=float, default=0.3)
    args = ap.parse_args()
    rows = scrape_list(args.workers, args.max_passes)
    if not args.skip_amounts:
        scrape_amounts(rows, args.delay)


if __name__ == "__main__":
    main()
