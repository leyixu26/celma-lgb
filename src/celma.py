"""
Shared library for the celma-lgb pipeline: constants, HTTP client, and parsers.

Source: celma.org.cn (中国地方政府债券信息公开平台) — the Ministry of Finance's sole
official disclosure window for local-government bonds. Two datasets:
  * SCHEDULE (发行安排):  forward monthly issuance plans, one article per
    issuer-month, planned amounts in the standard MOF tables
    (表2-1 再融资 / 表2-2 新增一般+新增专项, unit 亿元).
  * REALIZED (发行结果):  actual issuance, served by a JSON API.

Endpoints were identified by one-time network capture (2026-06); see
docs/METHODOLOGY.md §2 for the discovery record.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_CLEAN = ROOT / "data" / "clean"
OUTPUTS = ROOT / "outputs"
DOCS = ROOT / "docs"

# ---------------------------------------------------------------- endpoints
ARTICLE_BASE = "https://www.celma.org.cn"
DATA_SERVICE = "https://www.governbond.org.cn:4443"      # same platform, data host
LOAD_BOND_DATA = DATA_SERVICE + "/api/loadBondData.action"
SCHEDULE_CHANNEL = "192"                                  # 发行安排 tab id
SCHEDULE_COL = "dfzfxjh"                                  # article path segment

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def list_page_url(page: int) -> str:
    return f"{ARTICLE_BASE}/zqsclb_{page}.jhtml?ad_code=87&channelId={SCHEDULE_CHANNEL}"


def article_url(article_id) -> str:
    return f"{ARTICLE_BASE}/{SCHEDULE_COL}/{article_id}.jhtml"


def new_client(timeout: float = 40.0) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Referer": ARTICLE_BASE + "/",
                 "Accept-Language": "zh-CN,zh;q=0.9"},
        timeout=timeout, follow_redirects=True, trust_env=True)


def fetch_realized_page(client: httpx.Client, page: int = 1, page_size: int = 500) -> dict:
    """One page of the realized-issuance JSON feed (adCode 87 = whole country).
    Response: {code, data: [...], total, sumCount}."""
    params = {"timeStamp": int(time.time() * 1000), "dataType": "ZQFXLISTBYAD",
              "adList": "", "adCode": "87", "zqlx": "", "year": "", "fxfs": "",
              "qxr": "", "fxqx": "", "zqCode": "", "zqName": "",
              "page": page, "pageSize": page_size}
    r = client.get(LOAD_BOND_DATA, params=params)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- issuers (37)
ISSUERS = ["北京市", "天津市", "河北省", "山西省", "内蒙古自治区", "辽宁省", "大连市",
           "吉林省", "黑龙江省", "上海市", "江苏省", "浙江省", "宁波市", "安徽省",
           "福建省", "厦门市", "江西省", "山东省", "青岛市", "河南省", "湖北省",
           "湖南省", "广东省", "深圳市", "广西壮族自治区", "海南省", "重庆市",
           "四川省", "贵州省", "云南省", "西藏自治区", "陕西省", "甘肃省", "青海省",
           "宁夏回族自治区", "新疆维吾尔自治区", "新疆生产建设兵团"]
_ALIASES = {"内蒙古": "内蒙古自治区", "广西": "广西壮族自治区", "宁夏": "宁夏回族自治区",
            "西藏": "西藏自治区", "新疆兵团": "新疆生产建设兵团", "兵团": "新疆生产建设兵团",
            "新疆": "新疆维吾尔自治区"}


def canonicalize_issuer(text: str):
    """Canonical issuer name found in free text; longest names first so
    新疆生产建设兵团 wins over 新疆维吾尔自治区."""
    if not text:
        return None
    for name in sorted(ISSUERS, key=len, reverse=True):
        if name in text:
            return name
    if "兵团" in text:
        return "新疆生产建设兵团"
    for alias in sorted(_ALIASES, key=len, reverse=True):
        if alias in text:
            return _ALIASES[alias]
    return None


# ---------------------------------------------------------------- list parsing
_DATE = re.compile(r"(20\d{2})-(\d{1,2})-(\d{1,2})")
_TOTAL = re.compile(r"共\s*(\d+)\s*条")


def parse_list_html(html: str) -> list[dict]:
    """Rows of one schedule list page: {article_id, url, title, publish_date, issuer}."""
    soup = BeautifulSoup(html, "lxml")
    idre = re.compile(rf"/{SCHEDULE_COL}/(\d+)\.jhtml")
    rows = []
    for li in soup.find_all("li"):
        a = li.find("a", href=idre)
        if not a:
            continue
        m = idre.search(a.get("href", ""))
        if not m:
            continue
        title = (a.get("title") or a.get_text(strip=True) or "").strip()
        span = li.find("span")
        dm = (_DATE.search(span.get_text()) if span else None) or _DATE.search(li.get_text(" ", strip=True))
        pub = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}" if dm else None
        rows.append({"article_id": m.group(1), "url": article_url(m.group(1)),
                     "title": title, "publish_date": pub, "issuer": canonicalize_issuer(title)})
    return rows


def site_total(html: str):
    """The list's own record count ('共 N 条') — the completeness target."""
    m = _TOTAL.search(html)
    return int(m.group(1)) if m else None


def max_page(html: str) -> int:
    n = [int(x) for x in re.findall(r"zqsclb_(\d+)\.jhtml", html)]
    return max(n) if n else 1


# ---------------------------------------------------------------- title parsing
_YEAR = re.compile(r"(20\d{2})年")
_MONTH = re.compile(r"(\d{1,2})\s*月")
_QUARTER = re.compile(r"([一二三四1-4])\s*季度")


def enrich_schedule_row(r: dict) -> dict:
    """Derive plan_year / plan_month / plan_period / plan_type from the title,
    e.g. '2026年07月安徽省债券发行安排公开' -> 2026-07, monthly."""
    t = r.get("title", "") or ""
    yr = _YEAR.search(t)
    pm = None
    for mm in _MONTH.finditer(t):
        v = int(mm.group(1))
        if 1 <= v <= 12:
            pm = v
            break
    py = int(yr.group(1)) if yr else None
    return {**r, "plan_year": py, "plan_month": pm,
            "plan_type": "monthly" if pm else ("quarterly" if _QUARTER.search(t) else "annual/other"),
            "plan_period": f"{py}-{pm:02d}" if (py and pm) else None}


# ---------------------------------------------------------------- schedule amounts
def parse_schedule_amounts(text: str) -> dict:
    """Planned amounts from a schedule document's text (HTML body or PDF).
    Standard MOF layout: 表2-1 再融资债券计划发行规模, 表2-2 新增一般/新增专项.
    Returns {} when the document doesn't follow the standard tables."""
    out = {}
    m = re.search(r"新增一般债券\s*新增专项债券[\s\S]{0,40}?\d+\s*月\s+([\d.]+)\s+([\d.]+)", text)
    if m:
        out["new_general_yi"] = float(m.group(1))
        out["new_special_yi"] = float(m.group(2))
    r = re.search(r"再融资债券计划发行规模[\s\S]{0,40}?\d+\s*月\s+([\d.]+)", text)
    if r:
        out["refinance_yi"] = float(r.group(1))
    return out


def pdf_links(soup: BeautifulSoup) -> list[str]:
    out = []
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if h.lower().endswith(".pdf") or any(k in h.lower() for k in ("attach", "/file", "download")):
            out.append(h if h.startswith("http") else ARTICLE_BASE + (h if h.startswith("/") else "/" + h))
    return list(dict.fromkeys(out))
