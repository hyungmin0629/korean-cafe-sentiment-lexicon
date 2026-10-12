"""10k end-to-end CLI benchmark, with private synthetic files and JSONL output."""
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT / "outputs_private/benchmark_cli_v02"
    folder.mkdir(exist_ok=True)
    source = folder / "synthetic.10000.csv"
    if (folder / "result").exists():
        raise SystemExit("Benchmark result exists; preserve it")
    with source.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["review_id", "cafe_id", "source", "review_date", "text"])
        for index in range(10000):
            writer.writerow([str(index), f"synthetic_{index % 10}", "synthetic", f"2026-{index % 12 + 1:02d}-01",
                             "커피는맛있는데 직원은안친절해요. 주차장이 넓어요. 가격은 비싸요. 와이파이가 잘 돼요."])
    start = time.perf_counter()
    subprocess.run([sys.executable, str(ROOT / "run.py"), "--input", str(source), "--output", str(folder / "result")], check=True)
    elapsed = time.perf_counter() - start
    metadata = json.loads((folder / "result/run_metadata.json").read_text(encoding="utf-8"))
    report = {"version": metadata["version"], "reviews": 10000, "seconds": round(elapsed, 3),
              "reviews_per_second": round(10000 / elapsed, 1),
              "scope": "CLI subprocess startup + CSV input + ID deduplication + analysis + aggregation + all output files",
              "input": "Repeated authored short text, 10 cafes, 12 months; input generation excluded",
              "analyzed_rows": metadata["counts"]["analyzed_rows"],
              "output_bytes": sum(p.stat().st_size for p in (folder / "result").iterdir()),
              "lexicon_sha256": metadata["lexicon_sha256"], "rules_sha256": metadata["rules_sha256"]}
    (ROOT / "docs/benchmark_cli.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
