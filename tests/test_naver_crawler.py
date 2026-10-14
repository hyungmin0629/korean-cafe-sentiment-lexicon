import csv
import importlib.util
import io
import json
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

try:
    import bs4
except ImportError:
    raise unittest.SkipTest("Naver crawler tests require optional requirements-naver.txt")

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("naver_crawler", ROOT / "tools/crawl_naver_place.py")
crawler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crawler)
URL = "https://map.naver.com/p/search/test/place/1649277590?placePath=?bk_query=test"
SELECTORS = crawler.load_selectors(ROOT / "configs/naver_place_selectors.json")
FIXTURE = ROOT / "tests/fixtures/naver_reviews.synthetic.html"


class FakeTimeout(Exception):
    pass


class FakeLocator:
    def __init__(self, count=0):
        self.amount = count
        self.first = self
        self.last = self

    def count(self): return self.amount
    def nth(self, index): return self
    def locator(self, selector): return FakeLocator()
    def wait_for(self, **kwargs): pass
    def is_visible(self): return True
    def is_enabled(self): return True
    def evaluate(self, *args): return True
    def scroll_into_view_if_needed(self): pass
    def click(self): pass
    def get_attribute(self, name): return None


class FakePage:
    def __init__(self, htmls, status=200):
        self.htmls, self.index, self.status = htmls, 0, status
        self.url = crawler.canonical_url(URL)[0]
        self.clicked = 0

    def set_default_timeout(self, value): pass
    def on(self, event, callback): self.callback = callback
    def goto(self, url, **kwargs):
        self.callback(SimpleNamespace(url=url, status=self.status,
                                      request=SimpleNamespace(resource_type="document")))
        return SimpleNamespace(status=self.status)
    def content(self): return self.htmls[self.index]
    def locator(self, selector):
        if selector == SELECTORS["card"]:
            return FakeLocator(len(crawler.BeautifulSoup(self.content(), "html.parser").select(selector)))
        if selector == SELECTORS["load_more"]:
            return FakeLocator(int(self.index < len(self.htmls) - 1))
        return FakeLocator()
    def get_by_role(self, *args, **kwargs): return FakeLocator()
    def wait_for_function(self, *args, **kwargs):
        self.index += 1
        self.clicked += 1


def fake_runtime(page):
    browser = SimpleNamespace(new_context=lambda **kw: SimpleNamespace(new_page=lambda: page), closed=False)
    def close(): browser.closed = True
    browser.close = close
    class Runtime:
        def __enter__(self): return SimpleNamespace(chromium=SimpleNamespace(launch=lambda **kw: browser))
        def __exit__(self, *args): pass
    module = types.ModuleType("playwright.sync_api")
    module.sync_playwright, module.TimeoutError = Runtime, FakeTimeout
    return {"playwright": types.ModuleType("playwright"), "playwright.sync_api": module}, browser


class NaverCrawlerTests(unittest.TestCase):
    def parse(self, html=None):
        return crawler.extract_reviews(html or FIXTURE.read_text(encoding="utf-8"), SELECTORS,
                                       crawler.canonical_url(URL)[0], "자체 작성 예제", "2026-10-13T00:00:00Z", "synthetic")

    def test_map_search_and_entry_and_mobile_urls(self):
        expected = "https://m.place.naver.com/restaurant/1649277590/review/visitor"
        for value in (URL, "https://map.naver.com/p/entry/place/1649277590",
                      "https://m.place.naver.com/restaurant/1649277590/home"):
            self.assertEqual(crawler.canonical_url(value), (expected, "1649277590"))
        for value in ("http://map.naver.com/place/1", "https://map.naver.com.evil.com/place/1",
                      "https://user@map.naver.com/place/1", "https://map.naver.com/place/1extra",
                      "https://naver.me/test", "https://map.naver.com:443/place/1"):
            with self.assertRaises(ValueError): crawler.canonical_url(value)

    def test_dates_are_never_guessed_and_visit_is_separate(self):
        rows = self.parse()
        self.assertEqual(rows[0]["review_date"], "2026-09-01")
        self.assertEqual(rows[0]["visit_date"], "2026-08-30")
        self.assertEqual(rows[1]["visit_date"], "2026-09-02")
        self.assertEqual([row["review_date"] for row in rows[1:]], [""] * 4)
        self.assertEqual(rows[3]["source_date_text"], "2026.09.03")
        for value in ("9.2", "어제", "2026.02.29", "2026.13.01"):
            self.assertEqual(crawler.full_date(value), "")

    def test_body_controls_and_authors_excluded_independent_duplicates_kept(self):
        rows = self.parse()
        self.assertEqual(rows[0]["text"], '커피는 "맛있어요", ☕\n공간은 넓어요.')
        self.assertNotIn("EXCLUDED_AUTHOR", json.dumps(rows))
        self.assertEqual(len(rows), 5)
        self.assertEqual(len({row["review_id"] for row in rows}), 5)
        records = {}
        crawler.merge_rows(records, rows, 200)
        crawler.merge_rows(records, self.parse(), 200)
        self.assertEqual(len(records), 5)
        self.assertEqual(rows[3]["review_id_basis"], "content_date_occurrence")
        fallback = self.parse('<ul><li class="pui__X35jYm"><a class="pui__vn15t2">커피가 맛있어요.</a></li></ul>')
        self.assertEqual(len(fallback), 1)
        self.assertEqual(fallback[0]["text"], "커피가 맛있어요.")

    def test_http_restrictions_do_not_retry(self):
        for status in (403, 429, 503):
            calls = []
            def opener(request, **kwargs):
                calls.append(request.full_url)
                raise HTTPError(request.full_url, status, "blocked", {}, None)
            with self.assertRaisesRegex(crawler.CollectionStopped, f"robots_http_{status}"):
                crawler.check_robots(crawler.canonical_url(URL)[0], opener)
            self.assertEqual(len(calls), 1)

    def test_robots_rules_and_missing_file(self):
        class Response(io.BytesIO):
            status = 200
        def opener(request, **kwargs):
            return Response(b"User-agent: *\nDisallow: /restaurant/\n")
        with self.assertRaisesRegex(crawler.CollectionStopped, "robots_disallowed"):
            crawler.check_robots(crawler.canonical_url(URL)[0], opener)
        def missing(request, **kwargs):
            raise HTTPError(request.full_url, 404, "missing", {}, None)
        self.assertEqual(crawler.check_robots(crawler.canonical_url(URL)[0], missing)["status"], 404)

    def test_mock_browser_pagination_deduplicates_and_closes(self):
        full = FIXTURE.read_text(encoding="utf-8")
        soup = crawler.BeautifulSoup(full, "html.parser")
        cards = soup.select(SELECTORS["card"])
        first = "<ul>" + "".join(str(card) for card in cards[:2]) + "</ul>"
        page = FakePage([first, full])
        modules, browser = fake_runtime(page)
        args = SimpleNamespace(delay=1, headed=False, cafe_name="예제", max_pages=10, max_reviews=200)
        records, manifest = {}, {"collected_at": "2026-10-13T00:00:00Z"}
        with patch.dict(sys.modules, modules), patch.object(crawler, "check_robots", return_value={"crawl_delay": 3}), patch.object(crawler.time, "sleep") as sleep:
            reason = crawler.collect_browser(args, SELECTORS, page.url, records, manifest)
        self.assertEqual(reason, "no_load_more_control_visible")
        self.assertEqual(len(records), 5)
        self.assertEqual(page.clicked, 1)
        self.assertEqual(manifest["effective_delay_seconds"], 3)
        self.assertEqual(sleep.call_count, 2)
        sleep.assert_called_with(3)
        self.assertTrue(browser.closed)

    def test_mock_browser_page_429_stops_before_collection(self):
        page = FakePage([FIXTURE.read_text(encoding="utf-8")], status=429)
        modules, browser = fake_runtime(page)
        args = SimpleNamespace(delay=1, headed=False)
        records = {}
        with patch.dict(sys.modules, modules), patch.object(crawler, "check_robots", return_value={"crawl_delay": 0}), patch.object(crawler.time, "sleep"):
            with self.assertRaisesRegex(crawler.CollectionStopped, "page_http_429"):
                crawler.collect_browser(args, SELECTORS, page.url, records, {})
        self.assertEqual(records, {})
        self.assertEqual(page.clicked, 0)
        self.assertTrue(browser.closed)

    def test_offline_csv_to_report_and_output_protection(self):
        with tempfile.TemporaryDirectory() as folder:
            output, report = Path(folder) / "csv", Path(folder) / "report"
            arguments = ["--url", URL, "--cafe-name", "자체 작성 예제", "--output", str(output),
                         "--html", str(FIXTURE), "--synthetic", "--report-output", str(report)]
            with patch.object(crawler, "check_robots", side_effect=AssertionError("offline made network request")), redirect_stdout(io.StringIO()):
                self.assertEqual(crawler.main(arguments), 0)
            with (output / "reviews.csv").open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 5)
            self.assertTrue(all(row["source"] == "synthetic" for row in rows))
            self.assertTrue((report / "report.html").is_file())
            detail = [json.loads(line) for line in (report / "reviews.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(detail), 5)
            self.assertEqual(detail[0]["original_text"], rows[0]["text"])
            manifest = json.loads((output / "collection_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["written_date_count"], 1)
            self.assertEqual(manifest["written_date_unknown_count"], 4)
            self.assertEqual(manifest["visit_date_count"], 2)
            self.assertTrue(manifest["usable_for_analysis"])
            self.assertIn("월별 집계에서 제외", (output / "collection_summary.txt").read_text(encoding="utf-8-sig"))
            self.assertFalse(manifest["all_reviews_collected"])
            before = (output / "reviews.csv").read_bytes()
            self.assertEqual(crawler.main(arguments), 2)
            self.assertEqual((output / "reviews.csv").read_bytes(), before)

    def test_partial_failure_saves_records_without_report(self):
        def stopped(args, selectors, url, records, manifest):
            crawler.merge_rows(records, self.parse(), 200)
            raise crawler.CollectionStopped("page_http_429")
        with tempfile.TemporaryDirectory() as folder:
            output, report = Path(folder) / "csv", Path(folder) / "report"
            with patch.object(crawler, "collect_browser", side_effect=stopped), redirect_stdout(io.StringIO()):
                result = crawler.main(["--url", URL, "--cafe-name", "예제", "--output", str(output), "--report-output", str(report)])
            self.assertEqual(result, 1)
            self.assertFalse(report.exists())
            manifest = json.loads((output / "collection_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["review_count"], 5)
            self.assertEqual(manifest["status"], "stopped")
            self.assertTrue(manifest["usable_for_analysis"])

    def test_scroll_load_without_list_button_and_bounded_stop(self):
        class ScrollPage(FakePage):
            def locator(self, selector):
                if selector == SELECTORS["load_more"]:
                    return FakeLocator()
                return super().locator(selector)

            def wait_for_function(self, *args, **kwargs):
                if self.index == len(self.htmls) - 1:
                    raise FakeTimeout()
                self.index += 1

        full = FIXTURE.read_text(encoding="utf-8")
        soup = crawler.BeautifulSoup(full, "html.parser")
        first = "<ul>" + str(soup.select(SELECTORS["card"])[0]) + "</ul>"
        page = ScrollPage([first, full])
        modules, browser = fake_runtime(page)
        args = SimpleNamespace(delay=1, headed=False, cafe_name="예제", max_pages=3,
                               max_reviews=200, scroll_load=True)
        records, manifest = {}, {"collected_at": "2026-10-14T00:00:00Z"}
        with patch.dict(sys.modules, modules), patch.object(crawler, "check_robots", return_value={"crawl_delay": 0}), patch.object(crawler.time, "sleep"):
            reason = crawler.collect_browser(args, SELECTORS, page.url, records, manifest)
        self.assertEqual(reason, "scroll_did_not_increase_cards")
        self.assertEqual(len(records), 5)
        self.assertEqual(manifest["snapshots"], 2)
        self.assertEqual(manifest["load_actions"], ["review_list_scroll"] * 2)
        self.assertTrue(browser.closed)

    def test_scroll_response_429_stops_and_preserves_existing_sample(self):
        page = FakePage([FIXTURE.read_text(encoding="utf-8")])
        modules, browser = fake_runtime(page)
        def blocked(*args, **kwargs):
            page.callback(SimpleNamespace(url=page.url, status=429,
                                          request=SimpleNamespace(resource_type="fetch")))
            raise FakeTimeout()
        args = SimpleNamespace(delay=1, headed=False, cafe_name="예제", max_pages=3,
                               max_reviews=200, scroll_load=True)
        records = {}
        with patch.dict(sys.modules, modules), patch.object(crawler, "check_robots", return_value={"crawl_delay": 0}), patch.object(crawler.time, "sleep"), patch.object(page, "wait_for_function", side_effect=blocked):
            with self.assertRaisesRegex(crawler.CollectionStopped, "page_http_429"):
                crawler.collect_browser(args, SELECTORS, page.url, records, {"collected_at": "test"})
        self.assertEqual(len(records), 5)
        self.assertEqual(page.clicked, 0)
        self.assertTrue(browser.closed)

    def test_blocked_collection_explains_empty_csv_in_korean(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "csv"
            with patch.object(crawler, "collect_browser", side_effect=crawler.CollectionStopped("robots_http_429")), redirect_stdout(io.StringIO()):
                result = crawler.main(["--url", URL, "--cafe-name", "예제", "--output", str(output)])
            self.assertEqual(result, 1)
            summary = (output / "collection_summary.txt").read_text(encoding="utf-8-sig")
            self.assertIn("자동 요청을 제한", summary)
            self.assertIn("분석용 데이터가 아닙니다", summary)
            self.assertNotIn("CSV에", summary)

    def test_visit_only_summary_does_not_promise_time_series(self):
        manifest = {"cafe_name": "예제", "review_count": 3, "written_date_count": 0,
                    "visit_date_count": 2, "status": "collected_sample",
                    "stop_reason": "scroll_did_not_increase_cards"}
        summary = crawler.collection_summary(manifest)
        self.assertIn("시계열은 만들 수 없습니다", summary)
        self.assertIn("작성일로 바꾸지", summary)
        self.assertIn("전체 수집 완료", summary)

    def test_empty_unknown_html_is_failure_not_empty_success(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            html = folder / "unknown.html"
            html.write_text("<html>unrecognized</html>", encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                result = crawler.main(["--url", URL, "--cafe-name", "예제", "--output", str(folder / "output"), "--html", str(html)])
            self.assertEqual(result, 1)
            manifest = json.loads((folder / "output/collection_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["review_count"], 0)
            self.assertEqual(manifest["status"], "stopped")
            self.assertFalse(manifest["usable_for_analysis"])

    def test_current_dom_structure_and_korean_visit_date(self):
        rows = self.parse((ROOT / "tests/fixtures/naver_reviews.dom20261013.synthetic.html").read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["text"], "커피가 맛있어요.\n공간이 넓어요.")
        self.assertEqual(rows[0]["visit_date"], "2026-08-22")
        self.assertEqual(rows[1]["visit_date"], "2026-09-02")
        self.assertEqual(rows[2]["visit_date"], "")
        self.assertTrue(all(row["review_date"] == "" for row in rows))
        self.assertNotIn("영수증", rows[0]["source_date_text"])
        self.assertNotIn("1번째", rows[0]["source_date_text"])
        self.assertEqual(crawler.full_date("2026년 2월 29일"), "")

    def test_generic_photo_and_chart_more_are_not_candidates(self):
        page = FakePage([FIXTURE.read_text(encoding="utf-8")])
        with patch.object(page, "get_by_role", side_effect=AssertionError("Generic more must not be used")):
            self.assertIsNone(crawler.more_button(page, SELECTORS))
        for attributes in ({"href": "/restaurant/1649277590/photo"}, {"data-nlog-area": "plc_rrv.chartmore"}):
            button = FakeLocator(1)
            button.get_attribute = lambda name: attributes.get(name)
            with patch.object(page, "locator", return_value=button):
                self.assertIsNone(crawler.more_button(page, SELECTORS))

    def test_same_host_photo_redirect_is_stopped(self):
        page = FakePage([FIXTURE.read_text(encoding="utf-8")])
        page.url = "https://m.place.naver.com/restaurant/1649277590/photo"
        with self.assertRaisesRegex(crawler.CollectionStopped, "unexpected_non_review_page"):
            crawler.restriction(page, [])


if __name__ == "__main__":
    unittest.main()
