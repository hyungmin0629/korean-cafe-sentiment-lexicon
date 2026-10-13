import csv
import http.client
import io
import json
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cafe_sentiment.upload import UploadError, prepare_upload
from cafe_sentiment.web import AppState, make_handler


def csv_text(rows, headers=("review_id", "cafe_id", "cafe_name", "source", "review_date", "text", "visit_date")):
    handle = io.StringIO(newline="")
    writer = csv.writer(handle)
    writer.writerow(headers)
    writer.writerows(rows)
    return handle.getvalue()


class UploadValidationTests(unittest.TestCase):
    def test_full_csv_dedup_and_unknown_dates_do_not_use_visit_dates(self):
        text = csv_text([["1","a","카페","synthetic","2026-01-01","커피 맛있어요", ""],
                         ["1","a","카페","synthetic","2026-01-01","ID 중복 제외", ""],
                         ["2","a","카페","synthetic","","직원 친절해요", "2026-01-02"],
                         ["3","a","카페","synthetic","2026-02-29","커피 맛있어요", ""],
                         ["4","a","카페","synthetic","2026-03-01","", ""]])
        rows, issues, preview = prepare_upload(text)
        self.assertEqual(len(rows), 3)
        self.assertEqual(preview["counts"]["excluded_rows"], 2)
        self.assertEqual(preview["counts"]["unknown_dates"], 2)
        self.assertEqual(preview["counts"]["visit_only"], 1)
        self.assertEqual(rows[1]["review_date"], "")
        self.assertEqual(rows[1]["visit_date"], "2026-01-02")
        self.assertEqual(rows[2]["source_date_text"], "2026-02-29")

    def test_two_column_ids_keep_independent_identical_reviews(self):
        body = '커피는 "맛있어요", ☕\n공간은 넓어요.'
        text = csv_text([[body, "2024.2.29"], [body, "2024.2.29"], ["친절해요", "9.15"]], ("리뷰본문", "리뷰작성일"))
        rows, _, preview = prepare_upload(text, "예제 카페", "synthetic")
        self.assertEqual(len({row["review_id"] for row in rows}), 3)
        self.assertEqual(rows[0]["text"], body)
        self.assertEqual(rows[0]["review_date"], "2024-02-29")
        self.assertEqual(rows[2]["review_date"], "")
        self.assertEqual(rows[0]["source"], "synthetic")
        self.assertEqual(preview["format"], "two_column_csv")
        with self.assertRaises(UploadError): prepare_upload(text)

    def test_bad_headers_malformed_and_empty_input(self):
        for text in ("", "text,text\na,b", '리뷰본문,리뷰작성일\n"never closed',
                     "리뷰본문,리뷰작성일\n본문,2026-01-01,extra", "리뷰본문,리뷰작성일\n,2026-01-01", "junk\nhello"):
            with self.assertRaises(UploadError): prepare_upload(text, "예제")

    def test_multiple_cafes_preserve_identity_and_extra_columns_are_dropped(self):
        text = csv_text([["same","a","A","synthetic","2026-01-01","맛있어요","AUTHOR_SECRET"],
                         ["same","b","B","synthetic","2026-01-01","맛없어요","AUTHOR_SECRET"]],
                        ("review_id","cafe_id","cafe_name","source","review_date","text","nickname"))
        rows, _, preview = prepare_upload(text)
        self.assertEqual(len(rows), 2)
        self.assertEqual(preview["counts"]["cafe_count"], 2)
        self.assertEqual(preview["ignored_columns"], ["nickname"])
        self.assertNotIn("AUTHOR_SECRET", json.dumps(rows))
        with self.assertRaises(UploadError): prepare_upload(text, "단일 카페 이름")

    def test_limits_and_script_text_remain_data(self):
        text = csv_text([["<script>window.pwned=true</script>", "2026-01-01"]], ("text", "review_date"))
        rows, _, _ = prepare_upload(text, "예제", "synthetic")
        self.assertIn("<script>", rows[0]["text"])
        with patch("cafe_sentiment.upload.MAX_BYTES", 10):
            with self.assertRaises(UploadError): prepare_upload(text, "예제")
        with patch("cafe_sentiment.upload.MAX_ROWS", 1):
            with self.assertRaises(UploadError): prepare_upload(csv_text([["A",""],["B",""]], ("text","review_date")), "예제")


class UploadHTTPTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.state = AppState(self.folder.name, ROOT)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.state))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.folder.cleanup()

    def request(self, method, path, data=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        body = json.dumps(data, ensure_ascii=False).encode() if data is not None else None
        request_headers = {"Content-Type": "application/json"} if body is not None else {}
        request_headers.update(headers or {})
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def input_job(self):
        text = csv_text([["1","a","예제","synthetic","2026-01-01",'커피 "맛있어요", ☕',""],
                         ["2","a","예제","synthetic","2026-03-01","직원이 친절해요",""],
                         ["3","a","예제","synthetic","","공간이 넓어요","2026-03-02"]])
        status, _, data = self.request("POST", "/api/preview", {"csv": text, "filename": "my.csv"})
        self.assertEqual(status, 201)
        return json.loads(data)

    def test_http_upload_preview_report_and_private_file_boundaries(self):
        self.assertEqual(self.request("GET", "/")[0], 200)
        self.assertEqual(self.request("GET", "/assets/upload.js")[0], 200)
        status, _, sample = self.request("GET", "/api/sample")
        self.assertEqual(status, 200)
        self.assertEqual(len(prepare_upload(sample.decode("utf-8-sig"))[0]), 250)
        job = self.input_job()
        token = job["id"]
        status, _, _ = self.request("POST", f"/api/jobs/{token}/analyze", {"period":"month"})
        self.assertEqual(status, 202)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            status, _, result = self.request("GET", f"/api/jobs/{token}")
            done = json.loads(result)
            if done["status"] != "running": break
            time.sleep(.02)
        self.assertEqual(done["status"], "complete")
        self.assertEqual(done["included_rows"], 3)
        self.assertEqual(done["analysis_counts"]["analyzed_rows"], 3)
        self.assertEqual(done["analysis_counts"]["missing_date"], 1)
        status, headers, report = self.request("GET", done["report_url"])
        self.assertEqual(status, 200)
        self.assertIn(b'id="report-data"', report)
        status, headers, _ = self.request("GET", done["downloads"]["summary.csv"])
        self.assertEqual(status, 200)
        self.assertIn("attachment", headers["Content-Disposition"])
        for path in (f"/runs/{token}/job.json", f"/runs/{token}/result/../job.json", "/data_private/reviews.v03.csv", "/.env", "/runs/"):
            self.assertEqual(self.request("GET", path)[0], 404)
        self.assertEqual(self.request("POST", f"/api/jobs/{token}/analyze", {"period":"month"})[0], 202)
        self.assertEqual(self.request("POST", f"/api/jobs/{token}/analyze", {"period":"all"})[0], 400)

    def test_origin_host_content_type_and_malformed_payload(self):
        self.assertEqual(self.request("POST", "/api/preview", {}, {"Origin":"https://other.example"})[0], 403)
        self.assertEqual(self.request("GET", "/api/health", headers={"Host":"other.example"})[0], 403)
        self.assertEqual(self.request("POST", "/api/preview", {}, {"Content-Type":"text/plain"})[0], 415)
        self.assertEqual(self.request("POST", "/api/preview", {})[0], 400)
        self.assertEqual(self.request("POST", "/api/preview", {}, {"Origin":f"http://127.0.0.1:{self.port}"})[0], 400)

    def test_invalid_or_empty_date_range_does_not_start_job(self):
        job = self.input_job()
        for settings in ({"start":"2026-13-01"}, {"start":"2026-04-01","end":"2026-01-01"},
                         {"start":"2027-01-01","end":"2027-02-01"}):
            status, _, _ = self.request("POST", f'/api/jobs/{job["id"]}/analyze', settings)
            self.assertEqual(status, 400)
            self.assertEqual(self.state.get(job["id"])["status"], "ready")
        self.assertFalse((Path(self.folder.name)/job["id"]/"result").exists())


if __name__ == "__main__": unittest.main()
