import csv
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cafe_sentiment import Analyzer
from cafe_sentiment.aggregate import Aggregator


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analyzer = Analyzer()

    def score(self, text, category):
        return self.analyzer.analyze(text)["categories"][category]

    def test_distinct_aspects(self):
        text = "커피는 맛있는데 직원이 불친절하고 주차가 어려워요."
        self.assertEqual(self.score(text, "menu")["score"], 100)
        self.assertEqual(self.score(text, "service")["score"], 0)
        self.assertEqual(self.score(text, "location")["score"], 25)

    def test_negation(self):
        self.assertEqual(self.score("커피가 맛있지 않아요", "menu")["label"], "negative")
        self.assertEqual(self.score("직원이 안 친절해요", "service")["label"], "negative")

    def test_revisit_phrase_not_split(self):
        self.assertEqual(self.score("다시 방문하고 싶어요", "overall")["label"], "positive")

    def test_development_variants(self):
        self.assertEqual(self.score("커피가 맛나지 않았어요", "menu")["label"], "negative")
        self.assertEqual(self.score("커피는 쏘쏘", "menu")["label"], "neutral")
        self.assertEqual(self.score("주차장이 넓어요", "location")["label"], "positive")

    def test_double_negation(self):
        self.assertEqual(self.score("직원이 불친절하지 않아요", "service")["polarity"], 1)

    def test_contextual_acidity(self):
        self.assertIsNone(self.score("산미가 있어요", "menu")["score"])
        self.assertEqual(self.score("산미가 있어서 제 취향에 잘 맞아요", "menu")["label"], "positive")
        self.assertEqual(self.score("산미가 너무 강해서 마시기 힘들어요", "menu")["label"], "negative")

    def test_mixed_and_neutral_are_different(self):
        mixed = self.score("커피는 맛있고 케이크는 맛없어요", "menu")
        self.assertEqual((mixed["score"], mixed["label"]), (50, "mixed"))
        self.assertEqual(self.score("메뉴가 보통이에요", "menu")["label"], "neutral")

    def test_unmentioned_is_not_neutral(self):
        score = self.score("커피는 맛있어요", "location")
        self.assertEqual((score["score"], score["mentioned"]), (None, False))

    def test_quotes_and_wishes_abstain(self):
        for text in ("직원이 친절하다고 해서 왔어요", "커피가 맛있으면 좋겠어요"):
            result = self.analyzer.analyze(text)
            self.assertTrue(result["needs_review"])
            self.assertTrue(all(v["score"] is None for v in result["categories"].values()))

    def test_longest_match_not_double_counted(self):
        score = self.score("분위기가 좋고 커피가 맛있어요", "space")
        self.assertEqual(score["evidence_count"], 1)
        self.assertEqual(score["polarity"], 2)

    def test_evidence_offsets(self):
        result = self.analyzer.analyze("커피는 맛있지 않아요. 직원은 친절해요")
        for item in result["evidence"]:
            self.assertEqual(result["normalized_text"][item["start"]:item["end"]], item["matched_text"])

    def test_menu_aliases(self):
        analyzer = Analyzer(aliases=ROOT / "configs/cafe_aliases.example.json")
        self.assertEqual(analyzer.analyze("나무라떼가 좋아요", "demo_a")["categories"]["menu"]["label"], "positive")

    def test_missing_month_and_missing_date(self):
        agg = Aggregator(self.analyzer.categories)
        row = {"cafe_id": "a"}
        for day in (date(2026, 1, 1), date(2026, 3, 31), None):
            agg.add(row, self.analyzer.analyze("커피는 맛있어요"), day)
        rows = list(agg.rows())
        feb = next(r for r in rows if r["period"] == "2026-02" and r["category"] == "menu")
        self.assertEqual((feb["total_reviews"], feb["score"]), (0, None))
        self.assertEqual(feb["cafe_missing_date_reviews"], 1)

    def test_equal_review_weight(self):
        agg = Aggregator(self.analyzer.categories, period="all")
        for text in ("커피 맛있어요. 케이크 맛있어요. 스콘 맛있어요", "커피 맛없어요"):
            agg.add({"cafe_id": "a"}, self.analyzer.analyze(text), None)
        row = next(r for r in agg.rows() if r["category"] == "menu")
        self.assertEqual(row["score"], 50)

    def test_cli_duplicates_dates_and_filters(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            source = temp / "input.csv"
            source.write_text("review_id,cafe_id,source,review_date,text\n"
                              "1,a,test,2026-01-01,커피 맛있어요\n"
                              "1,a,test,2026-01-01,커피 맛있어요\n"
                              "2,a,test,,커피 맛없어요\n"
                              "3,b,test,2026-13-01,직원 친절해요\n"
                              "4,b,test,2026-01-03,\n", encoding="utf-8")
            command = [sys.executable, str(ROOT / "run.py"), "--input", str(source),
                       "--output", str(temp / "out"), "--period", "all", "--start", "2026-01-01"]
            result = subprocess.run(command, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            metadata = json.loads((temp / "out/run_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["counts"]["analyzed_rows"], 3)
            self.assertEqual(metadata["counts"]["duplicate_id"], 1)
            with (temp / "out/summary.csv").open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            a = next(r for r in rows if r["cafe_id"] == "a" and r["category"] == "menu")
            self.assertEqual(a["score"], "100.0")
            self.assertTrue(all(r["score"] == "" for r in rows if r["cafe_id"] == "b"))
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
