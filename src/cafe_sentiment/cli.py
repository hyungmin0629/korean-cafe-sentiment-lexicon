import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from . import __version__
from .aggregate import Aggregator
from .score import Analyzer


def parse_date(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Expected YYYY-MM-DD: " + value)
    return date.fromisoformat(value)


def write_csv(path, rows, fieldnames=None):
    iterator = iter(rows)
    first = next(iterator, None)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames or list(first or {}))
        writer.writeheader()
        if first is not None:
            writer.writerow(first)
        writer.writerows(iterator)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(args):
    input_path, output = Path(args.input), Path(args.output)
    if not input_path.is_file():
        raise ValueError("Input file does not exist")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty; choose a new directory")
    start = parse_date(args.start) if args.start else None
    end = parse_date(args.end) if args.end else None
    if start and end and start > end:
        raise ValueError("Start date must not be after end date")
    if args.min_samples < 1:
        raise ValueError("min-samples must be positive")
    analyzer = Analyzer(args.lexicon, args.rules, args.aliases)
    aggregator = Aggregator(analyzer.categories, args.period, start, end, args.min_samples)
    counts, sources = Counter(), Counter()
    seen = set()
    output.mkdir(parents=True, exist_ok=True)
    error_fields = ["row_number", "review_id", "cafe_id", "issue", "action"]
    with input_path.open(encoding="utf-8-sig", newline="") as input_file, \
            (output / "reviews.jsonl").open("w", encoding="utf-8") as detail, \
            (output / "input_issues.csv").open("w", encoding="utf-8-sig", newline="") as issue_file:
        reader = csv.DictReader(input_file)
        missing = {"review_id", "cafe_id", "source", "text"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError("Missing CSV columns: " + ", ".join(sorted(missing)))
        issue_writer = csv.DictWriter(issue_file, fieldnames=error_fields)
        issue_writer.writeheader()

        def issue(row_number, row, kind, action):
            counts[kind] += 1
            issue_writer.writerow({"row_number": row_number, "review_id": row.get("review_id", ""),
                                   "cafe_id": row.get("cafe_id", ""), "issue": kind, "action": action})

        for row_number, raw in enumerate(reader, 2):
            counts["input_rows"] += 1
            row = {key: (value or "").strip() for key, value in raw.items() if key is not None}
            if None in raw:
                issue(row_number, row, "extra_columns", "row_skipped")
                continue
            if any(not row.get(key) for key in ("review_id", "cafe_id", "source", "text")):
                issue(row_number, row, "empty_required_field", "row_skipped")
                continue
            identity = (row["source"], row["cafe_id"], row["review_id"])
            if identity in seen:
                issue(row_number, row, "duplicate_id", "row_skipped")
                continue
            seen.add(identity)
            day = None
            if row.get("review_date"):
                try:
                    day = parse_date(row["review_date"])
                except ValueError:
                    issue(row_number, row, "invalid_date", "excluded_from_date_based_summary")
            else:
                issue(row_number, row, "missing_date", "excluded_from_date_based_summary")
            result = analyzer.analyze(row["text"], row["cafe_id"])
            aggregator.add(row, result, day)
            record = {"review_id": row["review_id"], "cafe_id": row["cafe_id"],
                      "cafe_name": row.get("cafe_name", ""), "source": row["source"],
                      "review_date": day.isoformat() if day else None,
                      "original_text": row["text"], "rating": row.get("rating", ""), **result}
            detail.write(json.dumps(record, ensure_ascii=False) + "\n")
            sources[row["source"]] += 1
            counts["analyzed_rows"] += 1
            counts["needs_review_rows"] += result["needs_review"]
            counts["scored_rows"] += any(s["polarity"] is not None for s in result["categories"].values())
    write_csv(output / "summary.csv", aggregator.rows())
    metadata = {"version": __version__, "lexicon_version": analyzer.lexicon["version"],
                "rules_version": analyzer.rules["version"], "lexicon_sha256": analyzer.lexicon_hash,
                "rules_sha256": analyzer.rules_hash, "aliases_sha256": analyzer.aliases_hash,
                "input_sha256": sha256(input_path), "counts": dict(counts), "sources": dict(sources),
                "period": args.period, "start": args.start, "end": args.end,
                "min_samples": args.min_samples, "excluded_by_range": aggregator.excluded_by_range,
                "missing_dates_by_cafe": dict(aggregator.missing_dates),
                "detail_scope": "all_valid_input_rows; summary applies date filters",
                "generated_at": datetime.now().astimezone().isoformat(),
                "lexicon_status": "candidate_not_human_validated"}
    (output / "run_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "counts": dict(counts)}, ensure_ascii=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description="카페 리뷰 기간별·항목별 감성 분석")
    parser.add_argument("--input", required=True, help="UTF-8 review CSV")
    parser.add_argument("--output", required=True, help="New or empty output directory")
    parser.add_argument("--period", choices=("month", "quarter", "all"), default="month")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--min-samples", type=int, default=10)
    parser.add_argument("--lexicon")
    parser.add_argument("--rules")
    parser.add_argument("--aliases")
    args = parser.parse_args(argv)
    try:
        run(args)
    except (ValueError, OSError, KeyError, re.error) as error:
        print("분석 실패: " + str(error), file=sys.stderr)
        return 2
    return 0
