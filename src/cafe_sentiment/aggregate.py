from collections import Counter, defaultdict
from datetime import date


def period_key(day, period):
    if period == "all":
        return "all"
    if not day:
        return None
    if period == "quarter":
        return f"{day.year}-Q{(day.month - 1) // 3 + 1}"
    return f"{day.year}-{day.month:02d}"


def calendar_periods(start, end, period):
    if period == "all":
        return ["all"]
    keys = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        key = period_key(cursor, period)
        if key not in keys:
            keys.append(key)
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    return keys


class Aggregator:
    def __init__(self, category_labels, period="month", start=None, end=None, min_samples=10):
        self.labels = category_labels
        self.period = period
        self.start, self.end = start, end
        self.min_samples = min_samples
        self.groups = defaultdict(lambda: {
            "total": 0, "mentioned": Counter(), "labels": defaultdict(Counter),
            "sum": Counter(), "n": Counter(), "expressions": defaultdict(Counter),
        })
        self.cafes = {}
        self.missing_dates = Counter()
        self.days = {}
        self.excluded_by_range = 0

    def add(self, row, analysis, day):
        cafe = row["cafe_id"]
        if day and ((self.start and day < self.start) or (self.end and day > self.end)):
            self.excluded_by_range += 1
            return
        self.cafes.setdefault(cafe, row.get("cafe_name", ""))
        if day:
            low, high = self.days.get(cafe, (day, day))
            self.days[cafe] = min(low, day), max(high, day)
        else:
            self.missing_dates[cafe] += 1
        key = period_key(day, self.period)
        # Date filters require a known date even with --period all.
        if key is None or (day is None and (self.start or self.end)):
            return
        group = self.groups[cafe, key]
        group["total"] += 1
        for category, score in analysis["categories"].items():
            group["mentioned"][category] += score["mentioned"]
            if score["polarity"] is not None:
                group["sum"][category] += score["polarity"]
                group["n"][category] += 1
                group["labels"][category][score["label"]] += 1
        for item in analysis["evidence"]:
            if item["polarity"] is not None:
                group["expressions"][item["category"]][item["expression"]] += 1

    def rows(self):
        for cafe in sorted(self.cafes):
            bounds = self.days.get(cafe)
            if self.period == "all":
                periods = ["all"]
            elif bounds or (self.start and self.end):
                lower = self.start or bounds[0]
                upper = self.end or bounds[1]
                periods = calendar_periods(lower, upper, self.period)
            else:
                periods = ["undated"]
            for period in periods:
                group = self.groups[cafe, period]
                for category, label in self.labels.items():
                    n, mentioned = group["n"][category], group["mentioned"][category]
                    counts = group["labels"][category]
                    yield {
                        "cafe_id": cafe, "cafe_name": self.cafes[cafe], "period": period,
                        "category": category, "category_label": label,
                        "score": round(50 + 25 * group["sum"][category] / n, 2) if n else None,
                        "total_reviews": group["total"], "mentioned_reviews": mentioned,
                        "scored_reviews": n, "unscored_mentions": mentioned - n,
                        "mention_rate": round(mentioned / group["total"], 4) if group["total"] else None,
                        "scoring_rate": round(n / mentioned, 4) if mentioned else None,
                        **{f"{kind}_reviews": counts[kind] for kind in
                           ("positive", "negative", "neutral", "mixed")},
                        **{f"{kind}_rate": round(counts[kind] / n, 4) if n else None for kind in
                           ("positive", "negative", "neutral", "mixed")},
                        "sample_status": "평가 근거 없음" if not n else
                            "표본 부족" if n < self.min_samples else "집계 가능",
                        "cafe_missing_date_reviews": self.missing_dates[cafe],
                        "top_expressions": " | ".join(f"{term}({count})" for term, count in
                            group["expressions"][category].most_common(5)),
                    }
