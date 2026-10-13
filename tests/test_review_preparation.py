import csv
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("review_preparation", ROOT / "tools/prepare_review_csv.py")
preparation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preparation)


class PreparationTests(unittest.TestCase):
    def write(self, path, rows, headers=("리뷰본문", "리뷰작성일")):
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers); writer.writerows(rows)

    def read(self, output):
        with (output / "reviews.csv").open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_text_identity_and_calendar_dates_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder); source, output = folder / "input.csv", folder / "output"
            text = '커피는 "맛있어요", ☕\n공간은 넓어요.'
            self.write(source, [[text, "2024.2.29"], ["주차가 편해요", "2026/9/2"]])
            result = preparation.prepare(source, output, "예제 카페 합정", source="synthetic")
            rows = self.read(output)
            self.assertEqual(rows[0]["text"], text)
            self.assertEqual([row["review_date"] for row in rows], ["2024-02-29", "2026-09-02"])
            self.assertEqual(rows[0]["source_date_text"], "2024.2.29")
            self.assertTrue(result["is_synthetic"])
            self.assertTrue(all(row["review_id"] and row["cafe_id"] and not row["collected_at"] for row in rows))

    def test_unknown_invalid_and_partial_dates_never_gain_a_year(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder); source, output = folder / "input.csv", folder / "output"
            raw_dates = ["", "9.15", "어제", "2026-02-29", "2026-13-01"]
            self.write(source, [["커피가 좋아요", value] for value in raw_dates])
            result = preparation.prepare(source, output, "예제 카페")
            rows = self.read(output)
            self.assertEqual([row["source_date_text"] for row in rows], raw_dates)
            self.assertTrue(all(row["review_date"] == "" for row in rows))
            self.assertEqual(result["counts"]["missing_date"], 1)
            self.assertEqual(result["counts"]["unrecognized_date"], 2)
            self.assertEqual(result["counts"]["invalid_date"], 2)

    def test_identical_independent_rows_are_retained_with_stable_distinct_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder); source = folder / "input.csv"
            self.write(source, [["커피 맛있어요", "2026-09-01"]] * 2)
            for name in ("a", "b"):
                result = preparation.prepare(source, folder / name, "예제 카페", cafe_id="same_cafe")
                self.assertEqual(result["counts"]["identical_rows_retained"], 1)
            a, b = self.read(folder / "a"), self.read(folder / "b")
            self.assertEqual(a, b)
            self.assertEqual(len({row["review_id"] for row in a}), 2)

    def test_empty_or_malformed_input_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder); source, output = folder / "input.csv", folder / "output"
            for rows, headers in [([], ("리뷰본문", "리뷰작성일")),
                                  ([["", "2026-09-01"]], ("리뷰본문", "리뷰작성일")),
                                  ([["맛있어요", "2026-09-01", "extra"]], ("리뷰본문", "리뷰작성일")),
                                  ([], ("리뷰본문", "리뷰본문"))]:
                self.write(source, rows, headers)
                with self.assertRaises(ValueError): preparation.prepare(source, output, "예제 카페")
                self.assertFalse(output.exists())

    def test_existing_outputs_are_protected_and_blank_rows_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder); source, output = folder / "input.csv", folder / "output"
            self.write(source, [["", ""], ["좋아요", ""], []])
            result = preparation.prepare(source, output, "예제 카페")
            self.assertEqual(result["counts"]["blank_rows_ignored"], 2)
            before = (output / "reviews.csv").read_bytes()
            with self.assertRaises(ValueError): preparation.prepare(source, output, "예제 카페")
            self.assertEqual((output / "reviews.csv").read_bytes(), before)

    def test_prepared_example_runs_through_existing_report_pipeline(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            preparation.prepare(ROOT / "examples/review_input/리뷰입력_작성예제.synthetic.csv", folder / "prepared", "입력 예제", source="synthetic")
            result = subprocess.run([sys.executable, str(ROOT / "run.py"), "--input", str(folder / "prepared/reviews.csv"),
                                     "--output", str(folder / "report")], capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stderr)
            metadata = json.loads((folder / "report/run_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["counts"]["analyzed_rows"], 4)
            self.assertEqual(metadata["sources"], {"synthetic": 4})
            self.assertEqual(metadata["counts"]["missing_date"], 2)
            self.assertTrue((folder / "report/report.html").is_file())


if __name__ == "__main__": unittest.main()
