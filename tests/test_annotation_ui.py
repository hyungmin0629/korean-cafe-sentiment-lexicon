import csv
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
builder=module("annotation_builder",ROOT/"tools/build_annotation_ui.py")
evaluator=module("annotation_evaluator",ROOT/"tools/evaluate.py")


class AnnotationTests(unittest.TestCase):
    def template(self,path,text="커피는 맛있어요",**changes):
        rows=[dict(source="synthetic",review_id="1",cafe_id="a",split="holdout",text=text,category=category,
                   gold_label="",evidence_text="",reviewer="",notes="") for category in builder.CATEGORIES]
        rows[0].update(changes)
        with path.open("w",encoding="utf-8-sig",newline="") as h:
            writer=csv.DictWriter(h,fieldnames=builder.FIELDS);writer.writeheader();writer.writerows(rows)
        return rows

    def test_only_original_text_and_blank_judgments_are_embedded(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"input.csv";self.template(source)
            model=builder.build_model(source)
            self.assertEqual((len(model["reviews"]),model["aspect_count"]),(1,8))
            self.assertTrue(model["prediction_blind"])
            self.assertNotIn("gold_label",model["reviews"][0])
            self.assertNotIn("predicted_label",model["reviews"][0])
            self.assertEqual(model["reviews"][0]["text_sha256"],hashlib.sha256("커피는 맛있어요".encode()).hexdigest())

    def test_prefilled_labels_and_provisional_notes_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"input.csv"
            for changes in ({"gold_label":"positive"},{"reviewer":"Codex"},{"notes":"likely positive"},{"evidence_text":"맛있어요"}):
                self.template(source,**changes)
                with self.assertRaises(ValueError):builder.build_model(source)

    def test_duplicate_missing_and_inconsistent_aspects_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"input.csv";rows=self.template(source)
            for invalid in (rows[:-1],rows+[rows[0]],rows[:1]+[rows[1]|{"text":"다른 원문"}]+rows[2:]):
                with source.open("w",encoding="utf-8-sig",newline="") as h:
                    writer=csv.DictWriter(h,fieldnames=builder.FIELDS);writer.writeheader();writer.writerows(invalid)
                with self.assertRaises(ValueError):builder.build_model(source)

    def test_script_injection_stays_data_and_overwrite_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"input.csv";text='커피 맛있어요 </script><img src=x onerror=alert(1)> __ANNOTATION_JS__'
            self.template(source,text=text);output=Path(folder)/"review.html"
            builder.write_ui(source,output,{"a":"</script><script>alert(1)</script>"})
            html=output.read_text(encoding="utf-8")
            payload=re.search(r'<script id="annotation-data" type="application/json">(.*?)</script>',html,re.S).group(1)
            self.assertNotIn("<",payload);self.assertEqual(json.loads(payload)["reviews"][0]["text"],text)
            self.assertNotIn("innerHTML",html)
            with self.assertRaises(ValueError):builder.write_ui(source,output)

    def test_hash_only_csv_matches_predictions_and_rejects_changed_text(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            prediction=folder/"predictions.jsonl"
            prediction.write_text(json.dumps({"source":"synthetic","cafe_id":"a","review_id":"1","original_text":"커피 맛있어요",
                "categories":{"menu":{"label":"positive"}}},ensure_ascii=False)+"\n",encoding="utf-8")
            annotation=folder/"annotations.csv"
            row=dict(source="synthetic",cafe_id="a",review_id="1",split="holdout",text="",category="menu",gold_label="positive",
                     reviewer="Example human fixture",input_text_sha256=hashlib.sha256("커피 맛있어요".encode()).hexdigest())
            def write():
                with annotation.open("w",encoding="utf-8-sig",newline="") as h:
                    writer=csv.DictWriter(h,fieldnames=list(row));writer.writeheader();writer.writerow(row)
            write()
            self.assertEqual(evaluator.evaluate(prediction,annotation,"synthetic")["overall"]["labeled_aspects"],1)
            row["input_text_sha256"]="0"*64;write()
            with self.assertRaisesRegex(ValueError,"hash differs"):evaluator.evaluate(prediction,annotation,"synthetic")


if __name__=="__main__":unittest.main()
