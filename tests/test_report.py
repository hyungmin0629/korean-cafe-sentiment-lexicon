import csv
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cafe_sentiment.report import build_model, write_report


class ReportTests(unittest.TestCase):
    def run_input(self, folder, rows, *args):
        source = folder / "input.csv"
        with source.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["review_id", "cafe_id", "cafe_name", "source", "review_date", "text"])
            writer.writeheader()
            writer.writerows(rows)
        output = folder / "out"
        result = subprocess.run([sys.executable,str(ROOT / "run.py"),"--input",str(source),"--output",str(output),"--period","month",*args],capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        return output

    def rows(self):
        base = {"cafe_id":"a","cafe_name":"예제","source":"synthetic"}
        return [base | {"review_id":"1","review_date":"2026-01-01","text":"커피 맛있어요"},
                base | {"review_id":"2","review_date":"2026-03-01","text":"커피 맛없어요"},
                base | {"review_id":"3","review_date":"","text":"커피 맛있어요"}]

    def test_dates_gaps_and_missing_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self.run_input(Path(directory),self.rows())
            model = build_model(output)
            cafe = model["cafes"][0]
            self.assertEqual(cafe["periods"]["all"]["stats"]["total"],3)
            self.assertEqual(cafe["periods"]["2026-02"]["categories"]["menu"]["score"],None)
            self.assertEqual(cafe["periods"]["2026-02"]["categories"]["menu"]["scored_reviews"],0)
            self.assertEqual(cafe["missing_dates"],1)
            self.assertEqual(cafe["periods"]["all"]["categories"]["menu"]["sample_status"],"표본 부족")
            # Month range is reconstructed from review-level sums, not a mean of month scores.
            rows = [cafe["periods"][month]["categories"]["menu"] for month in ("2026-01","2026-03")]
            self.assertEqual(50+25*sum(row["polarity_sum"] for row in rows)/sum(row["scored_reviews"] for row in rows),50)
            self.assertTrue((output / "report.html").is_file())

    def test_filters_and_excerpt_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            output=self.run_input(Path(directory),self.rows(),"--start","2026-03-01","--report-examples","0")
            model=build_model(output,0)
            self.assertEqual(model["cafes"][0]["periods"]["all"]["stats"]["total"],1)
            self.assertEqual(model["cafes"][0]["periods"]["all"]["categories"]["menu"]["score"],0)
            self.assertEqual(model["cafes"][0]["periods"]["all"]["categories"]["menu"]["examples"]["negative"],[])

    def test_script_injection_and_placeholder_text_are_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            rows=self.rows()[:1]
            rows[0]["text"]="커피 맛있어요 </script><img src=x onerror=alert(1)> __REPORT_JS__"
            rows[0]["cafe_name"]="</script><script>alert(1)</script>"
            output=self.run_input(Path(directory),rows)
            html=(output / "report.html").read_text(encoding="utf-8")
            payload=re.search(r'<script id="report-data" type="application/json">(.*?)</script>',html,re.S).group(1)
            data=json.loads(payload)
            self.assertEqual(data["cafes"][0]["name"],rows[0]["cafe_name"])
            self.assertNotIn("<",payload)
            self.assertNotIn("<img src=x",html)
            self.assertNotIn("innerHTML",html)

    def test_themes_count_unique_reviews_and_samples_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            rows=self.rows()[:1]*12
            rows=[row | {"review_id":str(i),"review_date":f"2026-01-{i+1:02d}","text":"커피 맛있어요. 빵 맛있어요"} for i,row in enumerate(rows)]
            output=self.run_input(Path(directory),rows)
            menu=build_model(output)["cafes"][0]["periods"]["all"]["categories"]["menu"]
            self.assertEqual(menu["themes"]["positive"][0]["reviews"],12)
            self.assertEqual(len(menu["examples"]["positive"]),3)
            self.assertEqual(menu["examples"]["positive"][0]["date"],"2026-01-12")
            self.assertEqual(menu["sample_status"],"집계 가능")
            with self.assertRaises(ValueError):
                write_report(output)

    def test_optional_report_and_empty_input(self):
        with tempfile.TemporaryDirectory() as directory:
            output=self.run_input(Path(directory),[],"--no-report")
            self.assertFalse((output / "report.html").exists())
            self.assertEqual(build_model(output)["cafes"],[])

    def test_emoji_before_evidence_preserves_browser_highlight(self):
        with tempfile.TemporaryDirectory() as directory:
            rows=self.rows()[:1]
            rows[0]["text"]="곰돌이🐻🧸 커피는 맛있어요"
            output=self.run_input(Path(directory),rows)
            example=build_model(output)["cafes"][0]["periods"]["all"]["categories"]["menu"]["examples"]["positive"][0]
            mark=example["marks"][0]
            browser_slice=example["snippet"].encode("utf-16-le")[mark["start"]*2:mark["end"]*2].decode("utf-16-le")
            self.assertEqual(browser_slice,"맛있")
