import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

try:
    import bs4
except ImportError:
    raise unittest.SkipTest("Requires optional requirements-naver.txt")

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load("guided_collection", ROOT / "tools/collect_naver_reviews.py")
crawler = load("guided_crawler", ROOT / "tools/crawl_naver_place.py")
URL = "https://map.naver.com/p/entry/place/1649277590"


class GuidedCollectionTests(unittest.TestCase):
    def test_missing_libraries_show_installation_before_prompting(self):
        stdout = io.StringIO()
        with patch.object(runner.importlib.util, "find_spec", return_value=None), patch("builtins.input", side_effect=AssertionError("Must not prompt")), redirect_stdout(stdout):
            result = runner.main([])
        self.assertEqual(result, 2)
        self.assertIn("requirements-naver.txt", stdout.getvalue())

    def test_invalid_url_creates_no_collection_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(runner, "ROOT", Path(folder)), patch.object(runner.importlib.util, "find_spec", return_value=True), patch.dict("sys.modules", {"crawl_naver_place": crawler}), redirect_stdout(io.StringIO()):
                result = runner.main(["--url", "https://example.com/place/123", "--cafe-name", "예제"])
            self.assertEqual(result, 2)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_blocked_guided_run_saves_diagnostic_and_does_not_offer_empty_upload(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(runner, "ROOT", Path(folder)), patch.object(runner.importlib.util, "find_spec", return_value=True), patch.dict("sys.modules", {"crawl_naver_place": crawler}), patch.object(crawler, "collect_browser", side_effect=crawler.CollectionStopped("robots_http_429")), redirect_stdout(stdout):
                result = runner.main(["--url", URL, "--cafe-name", "예제"])
            runs = list((Path(folder) / "data_private").iterdir())
            self.assertEqual(len(runs), 1)
            self.assertTrue((runs[0] / "collection_summary.txt").is_file())
        self.assertEqual(result, 1)
        self.assertIn("자동 요청을 제한", stdout.getvalue())
        self.assertIn("분석용 데이터가 아닙니다", stdout.getvalue())
        self.assertNotIn("분석할 파일:", stdout.getvalue())
