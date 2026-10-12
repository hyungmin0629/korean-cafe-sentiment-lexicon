"""Validate authoritative CSV and synchronize public/package JSON resources."""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cafe_sentiment import __version__


def main():
    with (ROOT / "lexicon/cafe_sentiment.csv").open(encoding="utf-8-sig", newline="") as handle:
        entries = list(csv.DictReader(handle))
    seen = set()
    for entry in entries:
        entry["polarity"] = int(entry["polarity"])
        for field in ("variants", "target_terms"):
            entry[field] = json.loads(entry[field])
        if entry["entry_id"] in seen or entry["polarity"] not in (-2, -1, 0, 1, 2):
            raise ValueError("Duplicate ID or invalid polarity: " + entry["entry_id"])
        if entry["status"] not in ("candidate", "reviewed", "deprecated"):
            raise ValueError("Invalid status")
        re.compile(entry["pattern"])
        seen.add(entry["entry_id"])
    lexicon = {"version": __version__, "status": "candidate_not_human_validated", "entries": entries}
    resources = ROOT / "src/cafe_sentiment/resources"
    resources.mkdir(parents=True, exist_ok=True)
    data = json.dumps(lexicon, ensure_ascii=False, indent=2) + "\n"
    (ROOT / "lexicon/cafe_sentiment.json").write_text(data, encoding="utf-8")
    (resources / "cafe_sentiment.json").write_text(data, encoding="utf-8")
    rules = (ROOT / "lexicon/context_rules.json").read_text(encoding="utf-8")
    json.loads(rules)
    (resources / "context_rules.json").write_text(rules, encoding="utf-8")
    print(f"Validated/exported {len(entries)} entries")


if __name__ == "__main__":
    main()
