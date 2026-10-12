"""Collect public cafe reviews; no login, author profiles, or images requested.

Optional collection dependency: beautifulsoup4. Core analyzer uses stdlib only.
Cache is private. HTTP 403/429 stops collection rather than being retried.
"""
import argparse
import csv
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://www.diningcode.com"
UA = "CafeSentimentResearch/0.1 (user-requested local analysis)"
CAFES = [
    ("terarosa_gangneung", "테라로사 강릉본점", "wDkXSfj2qk2T"),
    ("onion_anguk", "어니언 안국점", "vVFyXDEBVFu0"),
    ("layered_anguk", "레이어드 안국점", "DUzvoAT8FEUU"),
]


def parse_reviews(html, cafe_id, cafe_name, url, collected_at):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for block in soup.select(".latter-graph[id^='div_review_']"):
        body = block.select_one(".review_contents")
        if not body:
            continue
        text = body.get_text("\n", strip=True)
        date_node = block.select_one(".point-detail .date")
        date_text = date_node.get_text(strip=True) if date_node else ""
        full = re.fullmatch(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", date_text)
        review_date = date(*(int(value) for value in full.groups())).isoformat() if full else ""
        rating = block.select_one(".total_score")
        rows.append({"review_id": block["id"].removeprefix("div_review_"),
                     "cafe_id": cafe_id, "cafe_name": cafe_name, "review_date": review_date,
                     "text": text, "source": "diningcode", "rating":
                     rating.get_text(strip=True).removesuffix("점") if rating else "",
                     "collected_at": collected_at, "source_url": url,
                     "source_date_text": date_text,
                     "date_status": "explicit_year" if full else "year_missing_or_unknown"})
    return soup, rows


def crawl(max_pages=25, delay=1.5):
    cache = ROOT / "data_private/crawl"
    cache.mkdir(parents=True, exist_ok=True)
    robot = urllib.robotparser.RobotFileParser()
    last_request = 0.0

    def request(url, payload=None):
        nonlocal last_request
        if not robot.can_fetch(UA, url):
            raise RuntimeError("robots.txt disallows: " + url)
        time.sleep(max(0, delay - (time.monotonic() - last_request)))
        headers = {"User-Agent": UA, "Referer": BASE + "/"}
        req = urllib.request.Request(url, data=urllib.parse.urlencode(payload).encode() if payload else None,
                                     headers=headers)
        last_request = time.monotonic()
        return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", errors="replace")

    robots_path = cache / "robots.txt"
    # The robots file itself is fetched before enforcing its public path rules.
    if not robots_path.exists():
        req = urllib.request.Request(BASE + "/robots.txt", headers={"User-Agent": UA})
        robots_path.write_bytes(urllib.request.urlopen(req, timeout=25).read())
    robot.parse(robots_path.read_text(encoding="utf-8").splitlines())
    collected_at = datetime.now(timezone(timedelta(hours=9))).isoformat()
    records, identities, manifest = [], set(), []
    failure = None
    for cafe_id, cafe_name, rid in CAFES:
        url = BASE + "/profile.php?rid=" + rid
        entry = {"cafe_id": cafe_id, "cafe_name": cafe_name, "url": url, "pages": 0,
                 "collected_reviews": 0, "sort": "DININGCODE", "status": "pending"}
        manifest.append(entry)
        try:
            for page in range(1, max_pages + 1):
                cache_file = cache / f"{cafe_id}_{page:03d}.html"
                if cache_file.exists():
                    html = cache_file.read_text(encoding="utf-8")
                else:
                    if page == 1:
                        html = request(url)
                    else:
                        html = request(BASE + "/2018/ajax/review.php", {
                            "mode": "LIST", "v_rid": rid, "page": page, "rows": "5",
                            "type": "rest", "start_id": first_id, "order": "DININGCODE"})
                    cache_file.write_text(html, encoding="utf-8")
                soup, rows = parse_reviews(html, cafe_id, cafe_name, url, collected_at)
                entry["pages"] += 1
                if page == 1:
                    node = soup.select_one("#hdn_first_review_id")
                    first_id = node.get("value", "") if node else ""
                    if not first_id:
                        meta = soup.select_one("#review-meta-data")
                        first_id = meta.get("data-first-id", "") if meta else ""
                    count = soup.select_one(".review-count")
                    entry["displayed_review_count"] = count.get_text(strip=True) if count else ""
                added = 0
                for row in rows:
                    identity = (cafe_id, row["review_id"])
                    if identity not in identities:
                        records.append(row)
                        identities.add(identity)
                        added += 1
                entry["collected_reviews"] += added
                print(json.dumps({"cafe": cafe_name, "page": page, "added": added,
                                  "total": entry["collected_reviews"]}, ensure_ascii=False), flush=True)
                if not rows or not added:
                    entry["status"] = "end_or_no_new_reviews"
                    break
                pages_node = soup.select_one("#hdn_pageT_review")
                if pages_node and page >= int(pages_node.get("value", 0)):
                    entry["status"] = "reached_last_page"
                    break
                entry["status"] = "page_limit"
        except (urllib.error.URLError, RuntimeError, ValueError) as error:
            entry["status"] = "stopped_on_error"
            failure = str(error)
            entry["error"] = failure
            break
        count_match = re.search(r"[0-9,]+", entry.get("displayed_review_count", ""))
        if count_match:
            displayed = int(count_match.group().replace(",", ""))
            entry["difference_from_displayed"] = displayed - entry["collected_reviews"]
            if entry["status"] == "reached_last_page" and displayed != entry["collected_reviews"]:
                entry["status"] = "reached_last_page_with_count_difference"
    output = ROOT / "data_private/reviews.diningcode.csv"
    fields = ["review_id", "cafe_id", "cafe_name", "review_date", "text", "source", "rating",
              "collected_at", "source_url", "source_date_text", "date_status"]
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    report = {"collected_at": collected_at, "total": len(records), "cafes": manifest,
              "max_pages": max_pages, "delay_seconds": delay, "error": failure,
              "missing_year": sum(not r["review_date"] for r in records),
              "robots_sha256": hashlib.sha256(robots_path.read_bytes()).hexdigest(),
              "sampling": "public default recommendation order, capped pages; not random",
              "publication": "raw reviews private; redistribution rights not established"}
    (ROOT / "data_private/crawl_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"total": len(records), "error": failure}, ensure_ascii=False), flush=True)
    return 1 if failure else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=25)
    parser.add_argument("--delay", type=float, default=1.5)
    args = parser.parse_args()
    if args.max_pages < 1 or args.delay < 1:
        parser.error("max-pages >= 1 and delay >= 1 required")
    raise SystemExit(crawl(args.max_pages, args.delay))
