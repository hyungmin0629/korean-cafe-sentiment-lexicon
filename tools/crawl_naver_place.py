"""Collect visible Naver Place visitor reviews into the analyzer's CSV schema.

Run locally with a fresh, anonymous Playwright browser. Never bypass access
controls. HTML fixtures support offline parser and report testing.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
import time
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "CafeSentimentCollector/0.4 (+https://github.com/hyungmin0629/korean-cafe-sentiment-lexicon)"
FIELDS = ["review_id", "cafe_id", "cafe_name", "source", "review_date", "text",
          "rating", "collected_at", "source_url", "visit_date", "source_date_text",
          "date_status", "review_id_basis"]


class CollectionStopped(RuntimeError):
    pass


def canonical_url(value):
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port:
        raise ValueError("Use an HTTPS Naver Place URL without credentials or a port")
    if parsed.hostname == "map.naver.com":
        match = re.search(r"/place/(\d+)(?:/|$)", parsed.path)
    elif parsed.hostname in {"m.place.naver.com", "pcmap.place.naver.com"}:
        match = re.match(r"/(?:restaurant|place)/(\d+)(?:/|$)", parsed.path)
    else:
        match = None
    if not match:
        raise ValueError("Open a cafe's map/place URL containing /place/ID or /restaurant/ID")
    place_id = match.group(1)
    return f"https://m.place.naver.com/restaurant/{place_id}/review/visitor", place_id


def load_selectors(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    for name in ("card", "body", "written_date", "visit_date", "generic_date", "load_more", "expand_body"):
        if not isinstance(config.get(name), str) or not config[name].strip():
            raise ValueError(f"Missing CSS selector: {name}")
    # Validate syntax before opening a browser.
    soup = BeautifulSoup("<html></html>", "html.parser")
    for name in ("card", "body", "written_date", "visit_date", "generic_date", "load_more", "expand_body"):
        soup.select(config[name])
    return config


def check_robots(url, opener=urlopen):
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        with opener(Request(robots_url, headers={"User-Agent": USER_AGENT}), timeout=20) as response:
            status = response.status
            if status != 200:
                raise CollectionStopped(f"robots_http_{status}")
            body = response.read(1024 * 1024 + 1)
        if len(body) > 1024 * 1024:
            raise CollectionStopped("robots_response_too_large")
        if re.search(br"<(?:html|!doctype\s+html)\b", body, re.I):
            raise CollectionStopped("robots_returned_html_instead_of_rules")
        rules = RobotFileParser(robots_url)
        rules.parse(body.decode("utf-8", errors="replace").splitlines())
        if not rules.can_fetch(USER_AGENT, url):
            raise CollectionStopped("robots_disallowed")
        rate = rules.request_rate(USER_AGENT)
        return {"url": robots_url, "status": 200,
                "crawl_delay": max(rules.crawl_delay(USER_AGENT) or 0,
                                   rate.seconds / rate.requests if rate and rate.requests else 0)}
    except HTTPError as exc:
        # A missing robots file is distinct from a blocked/unavailable one.
        if exc.code == 404:
            return {"url": robots_url, "status": 404, "crawl_delay": 0}
        raise CollectionStopped(f"robots_http_{exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise CollectionStopped("robots_unavailable") from exc


def full_date(value):
    match = re.search(r"(?<!\d)(\d{4})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{1,2})(?!\d)", value)
    if not match:
        match = re.search(r"(?<!\d)(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", value)
    if not match:
        return ""
    try:
        return date(*map(int, match.groups())).isoformat()
    except ValueError:
        return ""


def date_text(node, attr):
    return str(node.get(attr) or node.get("datetime") or node.get_text(" ", strip=True)) if node else ""


def extract_reviews(html, selectors, url, cafe_name, collected_at, source="naver_place"):
    _, place_id = canonical_url(url)
    soup = BeautifulSoup(html, "html.parser")
    rows, occurrences = [], Counter()
    for card in soup.select(selectors["card"]):
        body = card.select_one(selectors["body"])
        if not body:
            continue
        for control in body.select("button, [data-pui-click-code='reviewmore'], [data-pui-click-code='rvshowmore']"):
            control.decompose()
        text = body.get_text("\n", strip=True).strip()
        if not text:
            continue
        written = date_text(card.select_one(selectors["written_date"]), "data-review-written-date")
        visited = date_text(card.select_one(selectors["visit_date"]), "data-review-visit-date")
        generic = [date_text(node, "datetime") for node in card.select(selectors["generic_date"])]
        generic = [value for value in generic if full_date(value) or re.search(
            r"\d{1,2}\s*[./-]\s*\d{1,2}|어제|오늘|그제|\d+\s*일\s*전", value)]
        for value in generic:
            if "작성" in value and not written:
                written = value
            elif "방문" in value and not visited:
                visited = value
        # Unlabelled dates do not establish whether this is a visit or writing date.
        raw_dates = " | ".join(dict.fromkeys(value for value in [written, visited, *generic] if value))
        review_date, visit_date = full_date(written), full_date(visited)
        native_id = card.get("data-review-id", "")
        if not native_id:
            link = card.select_one("a[href*='/my/review/']")
            if link:
                match = re.search(r"/my/review/([A-Za-z0-9_-]+)", link.get("href", ""))
                native_id = match.group(1) if match else ""
        if native_id:
            review_id, basis = f"naver_{place_id}_{native_id}", "source_review_id"
        else:
            digest = hashlib.sha256((text + "\0" + raw_dates).encode("utf-8")).hexdigest()[:24]
            occurrences[digest] += 1
            review_id, basis = f"naver_{place_id}_{digest}_{occurrences[digest]}", "content_date_occurrence"
        rows.append(dict(zip(FIELDS, [review_id, f"naver_{place_id}", cafe_name, source,
                         review_date, text, "", collected_at, url, visit_date, raw_dates,
                         "written_date_known" if review_date else "written_date_unknown", basis])))
    return rows


def merge_rows(records, rows, limit):
    for row in rows:
        if row["review_id"] in records or len(records) < limit:
            records[row["review_id"]] = row


def restriction(page, blocked):
    if blocked:
        raise CollectionStopped(blocked[0])
    host = urlparse(page.url).hostname or ""
    if host not in {"m.place.naver.com", "pcmap.place.naver.com"}:
        raise CollectionStopped("redirected_outside_place_or_login_required")
    if not re.match(r"/(?:restaurant|place)/\d+/review(?:/|$)", urlparse(page.url).path):
        raise CollectionStopped("unexpected_non_review_page")
    # Inspect access-control elements, not arbitrary review text mentioning login.
    if page.locator("input[name='captcha'], #captcha, iframe[src*='captcha']").count():
        raise CollectionStopped("captcha_required")


def more_button(page, selectors):
    # Generic '더보기' also names photo, keyword-chart, and body controls.
    # Use only the explicitly configured review-list control.
    group = page.locator(selectors["load_more"])
    for index in range(group.count()):
        button = group.nth(index)
        href = button.get_attribute("href") or ""
        area = button.get_attribute("data-nlog-area") or ""
        if (href and not href.startswith(("javascript:", "#"))) or re.search(r"imgmore|chartmore|photomore", area):
            continue
        if (button.is_visible() and button.is_enabled()
                and button.evaluate("(el, card) => !el.closest(card)", selectors["card"])):
            return button
    return None


def collect_browser(args, selectors, url, records, manifest):
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout
    except ImportError as exc:
        raise CollectionStopped("playwright_missing: install requirements-naver.txt and Chromium") from exc
    robots = check_robots(url)
    manifest["robots"] = robots
    delay = max(args.delay, robots["crawl_delay"])
    manifest["effective_delay_seconds"] = delay
    blocked = []
    with sync_playwright() as runtime:
        browser_options = {"headless": not args.headed}
        if getattr(args, "browser", "chromium") != "chromium":
            browser_options["channel"] = args.browser
        browser = runtime.chromium.launch(**browser_options)
        try:
            context = browser.new_context(user_agent=USER_AGENT, locale="ko-KR")
            page = context.new_page()
            page.set_default_timeout(15000)

            def on_response(response):
                host = urlparse(response.url).hostname or ""
                if (host == "naver.com" or host.endswith(".naver.com")) and (
                        response.request.resource_type in {"document", "xhr", "fetch"}) and response.status in {403, 429}:
                    blocked.append(f"page_http_{response.status}")

            page.on("response", on_response)
            time.sleep(delay)
            response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            restriction(page, blocked)
            if response and response.status >= 400:
                raise CollectionStopped(f"page_http_{response.status}")
            try:
                page.locator(selectors["card"]).first.wait_for(state="attached", timeout=15000)
            except BrowserTimeout as exc:
                restriction(page, blocked)
                raise CollectionStopped("review_layout_unrecognized_or_unavailable") from exc
            for page_number in range(1, args.max_pages + 1):
                restriction(page, blocked)
                # Expand only the body control, and never follow an external link.
                bodies = page.locator(selectors["card"]).locator(selectors["expand_body"])
                for index in range(min(bodies.count(), args.max_reviews)):
                    body = bodies.nth(index)
                    href = body.get_attribute("href") or ""
                    if body.is_visible() and body.inner_text().rstrip().endswith("더보기") and (
                            not href or href.startswith(("javascript:", "#"))):
                        time.sleep(delay)
                        restriction(page, blocked)
                        body.click()
                rows = extract_reviews(page.content(), selectors, url, args.cafe_name,
                                       manifest["collected_at"])
                restriction(page, blocked)
                previous = len(records)
                merge_rows(records, rows, args.max_reviews)
                manifest["snapshots"] = page_number
                if not records:
                    raise CollectionStopped("no_nonempty_review_bodies")
                if len(records) >= args.max_reviews:
                    return "max_reviews_reached"
                if page_number > 1 and len(records) == previous:
                    return "no_new_reviews"
                if page_number == args.max_pages:
                    return "max_pages_reached"
                button = more_button(page, selectors)
                if button is None and not getattr(args, "scroll_load", False):
                    return "no_load_more_control_visible"
                old_count = page.locator(selectors["card"]).count()
                time.sleep(delay)
                restriction(page, blocked)
                if button is not None:
                    button.scroll_into_view_if_needed()
                    restriction(page, blocked)
                    button.click()
                    method = "list_button"
                else:
                    # Scroll only the visible review list, including nested scroll containers.
                    # Do not follow photo/profile links or change sorting to recover a failure.
                    page.locator(selectors["card"]).last.evaluate(
                        "el => el.scrollIntoView({block: 'start', behavior: 'instant'})")
                    method = "review_list_scroll"
                manifest.setdefault("load_actions", []).append(method)
                try:
                    page.wait_for_function("({selector, count}) => document.querySelectorAll(selector).length > count",
                                           arg={"selector": selectors["card"], "count": old_count}, timeout=15000)
                except BrowserTimeout:
                    restriction(page, blocked)
                    return ("load_more_did_not_increase_cards" if button is not None
                            else "scroll_did_not_increase_cards")
                restriction(page, blocked)
        finally:
            browser.close()


def collection_summary(manifest):
    """Explain a result without leaking review bodies or claiming completeness."""
    reason = manifest.get("stop_reason", "unknown")
    count = manifest["review_count"]
    known = manifest["written_date_count"]
    lines = ["네이버 플레이스 리뷰 수집 결과", f"카페: {manifest['cafe_name']}",
             f"확보한 본문: {count}건", f"작성일 확인: {known}건",
             f"방문일 확인: {manifest['visit_date_count']}건 (작성일과 별도)",
             f"종료 상태: {manifest['status']}", f"종료 이유: {reason}", ""]
    if reason in {"robots_http_429", "page_http_429"}:
        lines += ["네이버가 자동 요청을 제한했습니다(429). 이번 실행은 중단됐습니다.",
                  "자동 재시도나 접근 제한 우회를 하지 않았습니다."]
    elif reason in {"robots_disallowed", "robots_http_403", "page_http_403"}:
        lines += ["해당 경로의 자동 접근이 허용되지 않거나 거절됐습니다."]
    elif reason.startswith("robots_"):
        lines += ["자동 접근 규칙을 확인하지 못해 수집을 중단했습니다."]
    elif "Executable doesn't exist" in reason:
        lines += ["수집용 Chromium이 없습니다. 아래 설치 후 새 실행을 시작하세요.",
                  "python -m playwright install chromium"]
    elif "distribution" in reason and "not found" in reason:
        lines += ["지정한 브라우저가 설치되어 있지 않습니다.",
                  "설치된 Chrome/Edge에 맞춰 --browser chrome 또는 --browser msedge를 선택하세요.",
                  "Chromium을 사용하려면 python -m playwright install chromium 후 --browser chromium을 선택하세요."]
    elif reason.startswith("playwright_missing"):
        lines += ["수집 라이브러리가 없습니다. 설치 안내를 확인하세요.",
                  "python -m pip install -r requirements-naver.txt",
                  "python -m playwright install chromium"]
    elif reason == "captcha_required":
        lines += ["인증 화면이 나타나 수집을 중단했습니다."]
    elif reason in {"review_layout_unrecognized_or_unavailable", "no_nonempty_review_bodies"}:
        lines += ["리뷰 본문을 찾지 못했습니다. URL과 선택자 설정을 확인하세요."]
    elif reason in {"scroll_did_not_increase_cards", "load_more_did_not_increase_cards",
                    "no_load_more_control_visible"}:
        lines += ["목록이 더 늘어나지 않아 현재 확보한 표본만 저장했습니다.",
                  "전체 수집 완료나 마지막 리뷰 도달을 확인한 결과가 아닙니다."]
    if count:
        if manifest["status"] == "stopped":
            lines += ["중단 전에 확보한 일부 본문은 CSV에 보존했습니다. 부분 수집 자료입니다."]
        lines += ["reviews.csv를 CSV 분석 화면에 올릴 수 있습니다."]
        if known == 0:
            lines += ["작성일을 확인한 리뷰가 없어 작성일 기준 시계열은 만들 수 없습니다.",
                      "방문일을 작성일로 바꾸지 않았습니다. 전체 기간 분석만 사용하세요."]
        elif known < count:
            lines += [f"작성일 미확인 {count - known}건은 월별 집계에서 제외됩니다."]
    else:
        lines += ["리뷰가 0건입니다. reviews.csv는 헤더만 있으며 분석용 데이터가 아닙니다.",
                  "보고서는 생성하지 않았습니다."]
    lines += ["", "범위: 제한된 표본이며 전체 수집을 보장하지 않습니다.",
              "실제 리뷰와 결과 파일은 비공개 폴더에 보관하세요."]
    return "\n".join(lines) + "\n"


def save_collection(output, records, manifest):
    with (output / "reviews.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records.values())
    manifest["review_count"] = len(records)
    manifest["written_date_count"] = sum(bool(row["review_date"]) for row in records.values())
    manifest["written_date_unknown_count"] = len(records) - manifest["written_date_count"]
    manifest["visit_date_count"] = sum(bool(row["visit_date"]) for row in records.values())
    manifest["usable_for_analysis"] = bool(records)
    manifest["fallback_id_count"] = sum(row["review_id_basis"] != "source_review_id" for row in records.values())
    (output / "collection_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "collection_summary.txt").write_text(collection_summary(manifest), encoding="utf-8-sig")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--cafe-name", required=True)
    parser.add_argument("--output", required=True, help="New or empty private directory")
    parser.add_argument("--report-output", help="Optional new/empty analyzer report directory")
    parser.add_argument("--max-reviews", type=int, default=200)
    parser.add_argument("--max-pages", type=int, default=20, help="Maximum DOM snapshots")
    parser.add_argument("--delay", type=float, default=2)
    parser.add_argument("--headed", action="store_true", help="Show browser; does not bypass restrictions")
    parser.add_argument("--browser", choices=["chromium", "chrome", "msedge"], default="chromium",
                        help="Bundled Chromium, or an installed browser with a fresh anonymous profile")
    parser.add_argument("--scroll-load", action="store_true", help="Try review-list scrolling when no list button is visible; live Naver behavior unverified")
    parser.add_argument("--selectors", default=str(ROOT / "configs/naver_place_selectors.json"))
    parser.add_argument("--html", help="Read locally saved rendered HTML without network")
    parser.add_argument("--synthetic", action="store_true", help="Label authored HTML fixture; requires --html")
    args = parser.parse_args(argv)
    try:
        if args.max_reviews < 1 or args.max_pages < 1 or args.delay < 1 or not args.cafe_name.strip():
            raise ValueError("Positive limits, nonempty cafe name, and delay >= 1 are required")
        if args.synthetic and not args.html:
            raise ValueError("--synthetic requires --html")
        url, place_id = canonical_url(args.url)
        selectors = load_selectors(args.selectors)
        output = Path(args.output)
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            raise ValueError("Choose a new or empty output directory")
        if args.report_output:
            report_output = Path(args.report_output)
            if report_output.resolve() == output.resolve() or (report_output.exists() and (
                    not report_output.is_dir() or any(report_output.iterdir()))):
                raise ValueError("Report output must be a separate new or empty directory")
        if args.html and not Path(args.html).is_file():
            raise ValueError("HTML file does not exist")
        output.mkdir(parents=True, exist_ok=True)
        records = {}
        manifest = {"source_url": url, "place_id": place_id, "cafe_name": args.cafe_name,
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "mode": "offline_html" if args.html else "live_browser",
                    "source": "synthetic" if args.synthetic else "naver_place",
                    "max_reviews": args.max_reviews, "max_snapshots": args.max_pages,
                    "requested_delay_seconds": args.delay, "snapshots": 0,
                    "scroll_load_enabled": args.scroll_load, "load_actions": [],
                    "browser": args.browser,
                    "selectors_sha256": hashlib.sha256(Path(args.selectors).read_bytes()).hexdigest(),
                    "all_reviews_collected": False, "date_basis": "written_only",
                    "ordering": "default_page_order; no sort change", "status": "running"}
        try:
            if args.html:
                rows = extract_reviews(Path(args.html).read_text(encoding="utf-8"), selectors, url,
                                       args.cafe_name, manifest["collected_at"], manifest["source"])
                if not rows:
                    raise CollectionStopped("review_layout_unrecognized_or_no_bodies")
                merge_rows(records, rows, args.max_reviews)
                manifest["snapshots"] = 1
                reason = "offline_html_parsed"
            else:
                reason = collect_browser(args, selectors, url, records, manifest)
            manifest.update(status="collected_sample", stop_reason=reason)
        except Exception as exc:
            # Persist previously collected rows on browser/network/layout failures.
            manifest.update(status="stopped", stop_reason=str(exc)[:500])
        save_collection(output, records, manifest)
        print(json.dumps({"status": manifest["status"], "reason": manifest["stop_reason"],
                          "reviews": len(records), "csv": str(output / "reviews.csv")}, ensure_ascii=False))
        if manifest["status"] == "stopped":
            return 1
        if args.report_output:
            sys.path.insert(0, str(ROOT / "src"))
            from cafe_sentiment.cli import main as analyze
            return analyze(["--input", str(output / "reviews.csv"), "--output", args.report_output])
        return 0
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
