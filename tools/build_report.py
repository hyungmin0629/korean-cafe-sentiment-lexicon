"""Generate an offline HTML report from existing analysis outputs."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cafe_sentiment.report import write_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--output")
    parser.add_argument("--examples", type=int, default=3)
    args = parser.parse_args()
    try:
        result = write_report(args.analysis, args.output, args.examples)
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
