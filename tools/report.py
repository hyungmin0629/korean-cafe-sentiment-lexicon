"""Create a private pilot report and unlabeled human annotation template."""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "outputs_private/actual_all_v01"
    summary = list(csv.DictReader((output / "summary.csv").open(encoding="utf-8-sig", newline="")))
    metadata = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "data_private/crawl_manifest.json").read_text(encoding="utf-8"))
    lines = ["# 카페 리뷰 감성분석 파일럿 결과", "", "분석일: 2026-10-12. 사전·규칙 버전 0.1.0.", "",
             "실제 다이닝코드 공개 리뷰에 사전 기반 분석을 실행한 결과입니다. 사람 정답 기반 정확도 검증 전이며, 아래 점수는 각 카페의 실제 품질을 확정하는 평가가 아닙니다.", "",
             f"수집 레코드 {manifest['total']}건, 본문 분석 {metadata['counts']['analyzed_rows']}건, "
             f"빈 필수값 제외 {metadata['counts'].get('empty_required_field', 0)}건. "
             f"분석 본문 중 작성일 미상 {sum(metadata['missing_dates_by_cafe'].values())}건.", "",
             "추천순으로 제공된 공개 목록을 수집했습니다. 페이지 끝까지 조회해도 화면 총건수와 수집 수가 다른 카페가 있으므로 완전 수집으로 간주하지 않습니다. 누락 수·상태는 수집 기록에 있습니다.", "",
             "## 전체 기간 항목별 결과", "",
             "| 카페 | 항목 | 점수 | 항목 언급 | 판정 가능 | 분석 리뷰 | 표본 상태 |",
             "|---|---|---:|---:|---:|---:|---|"]
    for row in summary:
        lines.append(f"| {row['cafe_name']} | {row['category_label']} | {row['score'] or '—'} | "
                     f"{row['mentioned_reviews']} | {row['scored_reviews']} | {row['total_reviews']} | {row['sample_status']} |")
    lines += ["", "점수는 0~100 감성지수이며 만족 고객 비율이 아닙니다. 근거 없는 점수는 빈값입니다. 10건 미만 표본 부족 표시는 임시 기준입니다. 항목별 판정 건수가 크게 달라 카페 순위로 해석하지 않습니다.", "",
              "## 기간 분석", "", "월별 결과는 `../actual_month_v01/summary.csv`에 있습니다. "
              "작성 연도가 표시되지 않은 리뷰는 원문 날짜 문자열을 보존하고 기간 분석에서 제외했습니다. "
              "리뷰가 없는 달은 0건·점수 없음으로 표시합니다.", "",
              "## 해석과 다음 검토", "", "메뉴와 공간은 다른 항목보다 분석 근거가 상대적으로 많습니다. "
              "친절·청결·입지·운영은 카페에 따라 근거가 적어, 실제 개선 우선순위를 결정하기 전에 관련 원문을 검토해야 합니다.", "",
              "테라로사 강릉본점은 사전 개발 자료로, 어니언 안국점은 개발 검토 자료로, 레이어드 안국점은 보류 평가 자료로 구분했습니다. "
              "이번에는 사람 정답이 없으므로 어느 카페에서도 정확도 수치를 계산하지 않았습니다. "
              "보류 카페의 원문을 보고 사전을 추가 수정하면 별도 평가 자료가 필요합니다.", "",
              "다음은 실제 리뷰 정답 작성, 정밀도·재현율·F1 평가, 나리나무 리뷰 테스트입니다. "
              "원문과 상세 결과는 비공개로 관리하고 공개 여부가 정해진 집계만 공개합니다.", ""]
    (output / "파일럿_분석보고서.md").write_text("\n".join(lines), encoding="utf-8")
    by_cafe = defaultdict(list)
    for line in (output / "reviews.jsonl").open(encoding="utf-8"):
        record = json.loads(line)
        by_cafe[record["cafe_id"]].append(record)
    dest = ROOT / "data_private/annotations.blank.csv"
    if not dest.exists():
        with dest.open("w", encoding="utf-8-sig", newline="") as handle:
            fields = ["review_id", "cafe_id", "split", "text", "category", "gold_label", "evidence_text", "reviewer", "notes"]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for cafe_id, records in sorted(by_cafe.items()):
                split = "holdout" if cafe_id == "layered_anguk" else "development"
                for record in sorted(records, key=lambda r: r["review_id"])[:30]:
                    for category in record["categories"]:
                        writer.writerow({"review_id": record["review_id"], "cafe_id": cafe_id,
                                         "split": split, "text": record["original_text"], "category": category})
    print(json.dumps({"report": str(output / "파일럿_분석보고서.md"), "annotation_template": str(dest)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
