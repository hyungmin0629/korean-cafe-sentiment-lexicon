"""Prepare fixed private data splits and a blind annotation sheet.

Holdout/application text is never used to add lexicon entries in this tool.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLITS = {"terarosa_gangneung": "development", "fritz_dohwa": "development",
          "onion_anguk": "validation", "layered_anguk": "holdout",
          "daelim_seongsu": "holdout", "narinamu": "application"}


def main():
    raw = []
    for name in ("reviews.diningcode.csv", "reviews.expansion.csv", "reviews.narinamu.csv"):
        raw.extend(csv.DictReader((ROOT / "data_private" / name).open(encoding="utf-8-sig", newline="")))
    identities = set()
    for row in raw:
        key = (row["source"], row["cafe_id"], row["review_id"])
        if key in identities:
            raise ValueError("Duplicate collection identity")
        identities.add(key)
    output = ROOT / "data_private/reviews.v02.csv"
    if output.exists():
        raise SystemExit("Fixed data exists; do not overwrite")
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(raw[0]))
        writer.writeheader()
        writer.writerows(raw)
    data = {"version": "0.2.0", "review_csv_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "lexicon_sha256": hashlib.sha256((ROOT / "lexicon/cafe_sentiment.json").read_bytes()).hexdigest(),
            "rules_sha256": hashlib.sha256((ROOT / "lexicon/context_rules.json").read_bytes()).hexdigest(),
            "cafes": [], "accuracy_status": "no_human_gold_labels",
            "selection": "All collected bodies analyzed; annotation sample uses identity SHA256 order, max 30 per cafe",
            "development_policy": "Only terarosa/fritz text inspected for this expansion; onion used earlier development, so not independent holdout"}
    for cafe_id, split in SPLITS.items():
        rows = [row for row in raw if row["cafe_id"] == cafe_id]
        body = [row for row in rows if row["text"].strip()]
        data["cafes"].append({"cafe_id": cafe_id, "cafe_name": rows[0]["cafe_name"], "split": split,
                              "collected": len(rows), "nonempty": len(body),
                              "undated_nonempty": sum(not row["review_date"] for row in body)})
    (ROOT / "docs/dataset.v02.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = ["source", "review_id", "cafe_id", "split", "text", "category", "gold_label", "evidence_text", "reviewer", "notes"]
    categories = json.loads((ROOT / "lexicon/context_rules.json").read_text(encoding="utf-8"))["category_labels"]
    with (ROOT / "data_private/annotations.v02.blank.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for cafe_id, split in SPLITS.items():
            rows = [row for row in raw if row["cafe_id"] == cafe_id and row["text"].strip()]
            rows.sort(key=lambda r: hashlib.sha256((r["source"] + cafe_id + r["review_id"]).encode()).hexdigest())
            for row in rows[:30]:
                for category in categories:
                    writer.writerow({key: row[key] for key in ("source", "review_id", "cafe_id", "text")} |
                                     {"split": split, "category": category})
    print(json.dumps({"collected": len(raw), "nonempty": sum(bool(r["text"].strip()) for r in raw),
                      "splits": data["cafes"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
