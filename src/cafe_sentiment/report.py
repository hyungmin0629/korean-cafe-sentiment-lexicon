"""Build a self-contained offline owner report from an analysis directory.

The second streaming pass stores aggregates and bounded evidence samples rather
than every review. Excerpts stay in the same private output directory.
"""
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import date
from importlib.resources import files
from pathlib import Path

from .aggregate import Aggregator, period_key

THEMES = {
    "menu": [("맛·취향", r"맛|취향|입맛|풍미|고소|향긋"), ("식감·신선도", r"식감|촉촉|바삭|눅눅|딱딱|퍽퍽|신선|상한|부드"),
             ("단맛·산미", r"달|단맛|쓴맛|쓰다|산미|신맛"), ("메뉴 외관", r"예쁘|귀엽|귀여|깜찍"), ("메뉴 선택", r"선택|종류|다양|메뉴가 부족")],
    "service": [("응대·태도", r"친절|응대|무례|퉁명|말투|무시"), ("설명·요청", r"설명|요청|안내|배려"), ("주문 처리", r"주문|누락|실수")],
    "space": [("좌석·간격", r"좌석|의자|테이블|자리|간격"), ("소음·대화", r"소음|시끄|대화|음악"),
              ("분위기·인테리어", r"분위기|인테리어|아늑|고즈넉|쾌적|기분"), ("작업·편의", r"카공|공부|작업|와이파이|콘센트|충전")],
    "location": [("주차", r"주차"), ("찾아오는 길", r"찾기|역에서|접근|위치|입구|계단|대중교통")],
    "value": [("가격·가성비", r"가격|비싸|비쌈|저렴|가성비|돈값|돈이"), ("양·구성", r"양이|양이?\s|넉넉|충분")],
    "hygiene": [("청소·정리", r"청소|정리|먼지|쓰레기|깨끗|지저분"), ("식기·위생", r"식기|컵|설거지|위생|이물질"), ("화장실·냄새", r"화장실|냄새|악취")],
    "operation": [("대기·제공 시간", r"대기|웨이팅|기다|오래|빨리|줄"), ("혼잡", r"사람|붐비|붐빔|혼잡|정신"),
                  ("주문·픽업", r"주문|키오스크|픽업|결제"), ("영업·재고", r"영업|품절|재고|예약|휴무"), ("포장", r"포장")],
    "overall": [("재방문·추천", r"재방문|또 오|다시|추천|단골"), ("전반 경험", r"만족|실망|최고|최악|아깝|여긴")],
}
THEME_PATTERNS = {category: [(label, re.compile(pattern)) for label, pattern in entries] for category, entries in THEMES.items()}


def theme(category, evidence, label):
    text = evidence["expression"] + " " + evidence["matched_text"]
    return next((name for name, pattern in THEME_PATTERNS.get(category, []) if pattern.search(text)), label + " 평가")


def excerpt(record, category, direction):
    evidence = [item for item in record["evidence"] if item["category"] == category and item["polarity"] is not None
                and (item["polarity"] > 0 if direction == "positive" else item["polarity"] < 0)]
    first = evidence[0]
    text = record["normalized_text"]
    start = max(0, first["start"] - 60)
    end = min(len(text), max(first["end"] + 80, start + 220))
    end = min(end, start + 320)
    return {"review_id": record["review_id"], "source": record["source"], "date": record["review_date"],
            "label": record["categories"][category]["label"], "snippet": text[start:end],
            "leading_ellipsis": start > 0, "trailing_ellipsis": end < len(text),
            # Browser String.slice uses UTF-16 units; Python offsets use code points.
            "marks": [{"start": len(text[start:item["start"]].encode("utf-16-le")) // 2,
                       "end": len(text[start:min(item["end"], end)].encode("utf-16-le")) // 2,
                       "expression": item["expression"]} for item in evidence if start <= item["start"] < end]}


def read_records(path):
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def build_model(directory, example_limit=3):
    directory = Path(directory)
    metadata = json.loads((directory / "run_metadata.json").read_text(encoding="utf-8"))
    labels = {}
    with (directory / "summary.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            labels[row["category"]] = row["category_label"]
    if not labels:
        labels = json.loads(files("cafe_sentiment").joinpath("resources/context_rules.json").read_text(encoding="utf-8"))["category_labels"]
    start = date.fromisoformat(metadata["start"]) if metadata.get("start") else None
    end = date.fromisoformat(metadata["end"]) if metadata.get("end") else None
    minimum = metadata["min_samples"]
    all_agg, month_agg = (Aggregator(labels, period, start, end, minimum) for period in ("all", "month"))
    stats = defaultdict(Counter)
    sources = defaultdict(Counter)
    themes = defaultdict(Counter)
    examples = defaultdict(list)
    dates = {}
    for record in read_records(directory / "reviews.jsonl"):
        day = date.fromisoformat(record["review_date"]) if record["review_date"] else None
        all_agg.add(record, record, day)
        month_agg.add(record, record, day)
        if day and ((start and day < start) or (end and day > end)):
            continue
        if not day and (start or end):
            continue
        cafe = record["cafe_id"]
        if day:
            low, high = dates.get(cafe, (day, day))
            dates[cafe] = min(low, day), max(high, day)
        periods = ["all"] + ([period_key(day, "month")] if day else [])
        for period in periods:
            key = (cafe, period)
            stats[key]["total"] += 1
            stats[key]["dated"] += day is not None
            stats[key]["scored"] += any(s["score"] is not None for s in record["categories"].values())
            stats[key]["needs_review"] += record["needs_review"]
            sources[key][record["source"]] += 1
        review_themes = set()
        for item in record["evidence"]:
            if item["polarity"] in (None, 0) or item["category"] is None:
                continue
            category = item["category"]
            direction = "positive" if item["polarity"] > 0 else "negative"
            review_themes.add((category, direction, theme(category, item, labels[category])))
        for period in periods:
            for category, direction, name in review_themes:
                themes[cafe, period, category, direction][name] += 1
            for category in labels:
                for direction in ("positive", "negative"):
                    if not any(cat == category and kind == direction for cat, kind, _ in review_themes):
                        continue
                    pool = examples[cafe, period, category, direction]
                    pool.append(excerpt(record, category, direction))
                    pool.sort(key=lambda sample: (sample["date"] or "", sample["source"], sample["review_id"]), reverse=True)
                    del pool[example_limit:]
    summaries = list(all_agg.rows()) + list(month_agg.rows())
    cafes = []
    for cafe_id, name in sorted(all_agg.cafes.items()):
        periods = {}
        for row in summaries:
            if row["cafe_id"] != cafe_id:
                continue
            key = row["period"]
            bucket = periods.setdefault(key, {"stats": dict(stats[cafe_id, key]), "sources": dict(sources[cafe_id, key]), "categories": {}})
            category = row["category"]
            aggregate = all_agg if key == "all" else month_agg
            bucket["categories"][category] = row | {
                "polarity_sum": aggregate.groups[cafe_id, key]["sum"][category],
                "themes": {direction: [{"name": term, "reviews": count} for term, count in themes[cafe_id, key, category, direction].most_common(8)]
                           for direction in ("positive", "negative")},
                "examples": {direction: examples[cafe_id, key, category, direction] for direction in ("positive", "negative")}}
        bounds = dates.get(cafe_id)
        cafes.append({"id": cafe_id, "name": name or cafe_id, "periods": periods,
                      "date_start": bounds[0].isoformat() if bounds else None, "date_end": bounds[1].isoformat() if bounds else None,
                      "missing_dates": all_agg.missing_dates[cafe_id]})
    return {"schema_version": 1, "mark_offset_unit": "utf16_code_units", "version": metadata["version"], "generated_at": metadata["generated_at"],
            "min_samples": minimum, "category_labels": labels, "cafes": cafes,
            "input_counts": metadata["counts"], "source_period": metadata["period"],
            "start": metadata.get("start"), "end": metadata.get("end"),
            "input_sha256": metadata["input_sha256"], "lexicon_sha256": metadata["lexicon_sha256"],
            "rules_sha256": metadata["rules_sha256"], "example_limit": example_limit,
            "is_synthetic": set(metadata["sources"]) == {"synthetic"},
            "quality_status": "candidate_not_human_validated"}


def write_report(directory, destination=None, example_limit=3):
    if not 0 <= example_limit <= 10:
        raise ValueError("report examples must be between 0 and 10")
    model = build_model(directory, example_limit)
    resources = files("cafe_sentiment").joinpath("resources")
    template = resources.joinpath("report.html").read_text(encoding="utf-8")
    payload = json.dumps(model, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    html = template.replace("__REPORT_CSS__", resources.joinpath("report.css").read_text(encoding="utf-8"))
    html = html.replace("__REPORT_TRENDS_JS__", resources.joinpath("report-trends.js").read_text(encoding="utf-8"))
    html = html.replace("__REPORT_JS__", resources.joinpath("report.js").read_text(encoding="utf-8"))
    html = html.replace("__REPORT_DATA__", payload)
    destination = Path(destination) if destination else Path(directory) / "report.html"
    if destination.exists():
        raise ValueError("Report exists; choose a new destination")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")
    return {"path": str(destination), "bytes": destination.stat().st_size, "cafes": len(model["cafes"]),
            "contains_review_excerpts": example_limit > 0, "example_limit_per_period_direction": example_limit}
