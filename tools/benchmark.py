"""Streaming synthetic core benchmark, excluding CSV/JSONL I/O."""
import ctypes
import json
import platform
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cafe_sentiment import Analyzer
from cafe_sentiment.aggregate import Aggregator


def peak_memory_mb():
    if sys.platform == "win32":
        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
                (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize",
                "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32")
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        function = ctypes.WinDLL("psapi").GetProcessMemoryInfo
        function.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)
        if function(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            return round(counters.PeakWorkingSetSize / 1024 / 1024, 2)
    return None


def main():
    analyzer = Analyzer()
    samples = ["커피는 맛있는데 직원이 불친절하고 주차가 어려워요.",
               "공간이 넓고 분위기가 좋아요. 가격은 비싸요.",
               "커피가 맛있지 않아요. 직원은 친절해요.",
               "컵은 더럽고 화장실은 깨끗해요."]
    results = []
    for n in (10000, 100000):
        agg = Aggregator(analyzer.categories, "month")
        start = time.perf_counter()
        for index in range(n):
            row = {"cafe_id": f"synthetic_{index % 10}"}
            agg.add(row, analyzer.analyze(samples[index % len(samples)]), date(2026, index % 12 + 1, 1))
        list(agg.rows())
        elapsed = time.perf_counter() - start
        result = {"reviews": n, "seconds": round(elapsed, 3),
                  "reviews_per_second": round(n / elapsed, 1), "process_peak_memory_mb": peak_memory_mb()}
        results.append(result)
        print(json.dumps(result), flush=True)
    report = {"python": platform.python_version(), "platform": platform.platform(),
              "version": "0.1.0", "input": "synthetic, four repeated short texts, 10 cafes, 12 months",
              "scope": "analyze + aggregate; excludes CSV input, duplicate-ID set and JSONL output",
              "memory": "process-wide Windows peak working set, includes both sequential runs",
              "results": results}
    (ROOT / "docs/benchmark.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
