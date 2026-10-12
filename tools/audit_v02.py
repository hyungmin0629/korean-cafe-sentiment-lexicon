"""Summarize execution coverage; never describe it as accuracy."""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "outputs_private/actual_all_v02"
    records = [json.loads(line) for line in (output / "reviews.jsonl").open(encoding="utf-8")]
    baseline = [json.loads(line) for line in (ROOT / "outputs_private/actual_all_v01/reviews.jsonl").open(encoding="utf-8")]
    dataset = json.loads((ROOT / "docs/dataset.v02.json").read_text(encoding="utf-8"))
    splits = {row["cafe_id"]: row["split"] for row in dataset["cafes"]}
    per_entry, scored_entry = Counter(), Counter()
    for record in records:
        if splits[record["cafe_id"]] != "development":
            continue
        per_entry.update({e["entry_id"] for e in record["evidence"]})
        scored_entry.update({e["entry_id"] for e in record["evidence"] if e["polarity"] is not None})
    lexicon = json.loads((ROOT / "lexicon/cafe_sentiment.json").read_text(encoding="utf-8"))
    with (ROOT / "lexicon/development_coverage.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["entry_id", "expression", "category", "polarity", "development_reviews_matched", "development_reviews_scored", "status"])
        writer.writeheader()
        for entry in lexicon["entries"]:
            writer.writerow({key: entry[key] for key in ("entry_id", "expression", "category", "polarity", "status")} |
                             {"development_reviews_matched": per_entry[entry["entry_id"]],
                              "development_reviews_scored": scored_entry[entry["entry_id"]]})
    cafes = []
    for cafe in dataset["cafes"]:
        selected = [record for record in records if record["cafe_id"] == cafe["cafe_id"]]
        cafes.append(cafe | {"scored_reviews": sum(any(c["score"] is not None for c in r["categories"].values()) for r in selected),
                            "needs_review": sum(r["needs_review"] for r in selected),
                            "category_scored_reviews": {key: sum(r["categories"][key]["score"] is not None for r in selected)
                                                        for key in selected[0]["categories"]}})
    old_ids = {(r["source"], r["cafe_id"], r["review_id"]) for r in baseline}
    same_input = [r for r in records if (r["source"], r["cafe_id"], r["review_id"]) in old_ids]
    def scored(rows):
        return sum(any(c["score"] is not None for c in r["categories"].values()) for r in rows)
    report = {"version": "0.2.0", "entries": len(lexicon["entries"]), "entries_by_category": dict(Counter(e["category"] for e in lexicon["entries"])),
              "development_reviews": sum(c["nonempty"] for c in cafes if c["split"] == "development"),
              "entries_observed_in_development": len(per_entry),
              "entries_unobserved_in_development": len(lexicon["entries"]) - len(per_entry),
              "observation_definition": "Selected expression evidence in development reviews; includes abstained evidence, not raw regex counts or human validation",
              "same_input_comparison": {"reviews": len(baseline), "v01_scored": scored(baseline), "v02_scored": scored(same_input)},
              "cafes": cafes, "interpretation": "Execution coverage only; no human ground truth or measured real-review accuracy"}
    (ROOT / "docs/coverage.v02.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = list(csv.DictReader((output / "summary.csv").open(encoding="utf-8-sig", newline="")))
    lines = ["# 확장 사전 파일럿 결과", "", "버전 0.2.0, 2026-10-12. 사람 정답 기반 정확도 평가 전입니다.", "",
             f"후보 표현 {report['entries']}개. 실제 본문 {len(records)}건 분석, 감성 근거가 하나 이상 있는 리뷰 {scored(records)}건.", "",
             f"개발 본문 {report['development_reviews']}건에서 선택 근거가 관찰된 후보 {len(per_entry)}개이며, 나머지는 아직 개발 표본에서 확인하지 못한 보완 가설입니다.", "",
             "## 전체 기간 결과", "", "| 카페 | 항목 | 점수 | 판정 리뷰 | 전체 본문 | 표본 상태 |", "|---|---|---:|---:|---:|---|"]
    for row in summary:
        lines.append(f"| {row['cafe_name']} | {row['category_label']} | {row['score'] or '—'} | {row['scored_reviews']} | {row['total_reviews']} | {row['sample_status']} |")
    lines += ["", "점수는 사전 근거의 감성지수이며 만족 고객 비율이나 검증된 카페 품질이 아닙니다. 기간·출처·언급 건수를 함께 해석해야 합니다.", "",
              "## 나리나무 적용", "", "다이닝코드 공개 본문 2건에 동일한 사전을 적용했습니다. 1건은 작성 연도가 없어 월별 분석에서 제외합니다. 메뉴를 제외한 항목의 근거가 없고 메뉴도 표본이 부족하여 운영 판단용 점수를 확정할 수 없습니다.", "",
              "## 후속 품질 검증", "", "`data_private/annotations.v02.blank.csv`는 사전 예측을 넣지 않은 사람 정답 입력 양식입니다. 레이어드·대림창고를 별도 평가 대상으로 유지합니다. 정답을 작성하면 `tools/evaluate.py`로 카테고리별 정밀도·재현율·F1, 보류로 놓친 감성, 혼동표를 계산할 수 있습니다.", ""]
    (output / "확장_분석보고서.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("entries", "entries_by_category", "entries_observed_in_development", "same_input_comparison")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
