import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("evaluate", Path(__file__).resolve().parents[1] / "tools/evaluate.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EvaluationTests(unittest.TestCase):
    def test_abstention_is_false_negative(self):
        result = module.metrics([("positive", "positive"), ("positive", "unscored"),
                                 ("unscored", "positive"), ("negative", "negative")])
        self.assertEqual(result["accuracy"], 0.5)
        self.assertEqual(result["classes"]["positive"]["precision"], 0.5)
        self.assertEqual(result["classes"]["positive"]["recall"], 0.5)
        self.assertEqual(result["abstentions_on_opinions"], 1)

    def test_mixed_is_not_neutral(self):
        result = module.metrics([("mixed", "neutral"), ("neutral", "neutral")])
        self.assertEqual(result["classes"]["mixed"]["recall"], 0)
        self.assertEqual(result["classes"]["neutral"]["precision"], 0.5)
