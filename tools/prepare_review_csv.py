"""Convert a manually prepared two-column review CSV to the analyzer schema."""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

ALIASES = {"리뷰본문": "text", "리뷰작성일": "review_date", "text": "text", "review_date": "review_date"}
FIELDS = ["review_id", "cafe_id", "cafe_name", "review_date", "text", "source",
          "rating", "collected_at", "source_date_text"]


def normalize_date(value):
    if not value:
        return "", "missing_date"
    match = re.fullmatch(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})\.?", value)
    if not match:
        return "", "unrecognized_date"
    try:
        return date(*map(int, match.groups())).isoformat(), ""
    except ValueError:
        return "", "invalid_date"


def prepare(source_path, output, cafe_name, cafe_id=None, source="naver_place", place_url=""):
    source_path, output = Path(source_path), Path(output)
    cafe_name = cafe_name.strip()
    if not cafe_name or source not in ("naver_place", "synthetic"):
        raise ValueError("카페 이름과 출처를 확인해주세요.")
    cafe_id = (cafe_id or "cafe_" + hashlib.sha256(cafe_name.encode()).hexdigest()[:16]).strip()
    if not cafe_id:
        raise ValueError("카페 ID가 비어 있습니다.")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("출력은 새 폴더 또는 빈 폴더를 사용해주세요.")
    if not source_path.is_file():
        raise ValueError("입력 CSV를 찾을 수 없습니다.")
    records, issues, counts, occurrences = [], [], Counter(), Counter()
    with source_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, strict=True)
        headers = next(reader, [])
        mapped = [ALIASES.get(header.strip()) for header in headers]
        if len(mapped) != 2 or set(mapped) != {"text", "review_date"}:
            raise ValueError("첫 행은 리뷰본문,리뷰작성일 두 열이어야 합니다.")
        for number, values in enumerate(reader, 2):
            counts["input_rows"] += 1
            if not values or all(not value.strip() for value in values):
                counts["blank_rows_ignored"] += 1
                continue
            if len(values) != 2:
                raise ValueError(f"{number}번째 기록의 열 수가 다릅니다. CSV UTF-8로 다시 저장해주세요.")
            row = dict(zip(mapped, values))
            text, raw_date = row["text"], row["review_date"].strip()
            if not text.strip():
                raise ValueError(f"{number}번째 기록에 날짜만 있고 리뷰본문이 없습니다.")
            day, issue = normalize_date(raw_date)
            if issue:
                counts[issue] += 1
                issues.append({"record_number": number, "source_date_text": raw_date,
                               "issue": issue, "action": "date_unknown; whole-period analysis only"})
            identity = json.dumps([source, cafe_id, text, raw_date], ensure_ascii=False, separators=(",", ":"))
            digest = hashlib.sha256(identity.encode()).hexdigest()
            occurrences[digest] += 1
            if occurrences[digest] > 1:
                counts["identical_rows_retained"] += 1
                issues.append({"record_number": number, "source_date_text": raw_date,
                               "issue": "identical_row", "action": "retained; check accidental repeated copying"})
            records.append(dict(review_id=f"manual_{digest}_{occurrences[digest]}", cafe_id=cafe_id,
                                cafe_name=cafe_name, review_date=day, text=text, source=source,
                                rating="", collected_at="", source_date_text=raw_date))
    if not records:
        raise ValueError("리뷰본문이 비어 있습니다. 빈 양식에 실제 리뷰를 입력해주세요.")
    counts["prepared_rows"] = len(records)
    output.mkdir(parents=True, exist_ok=True)
    for name, rows, fields in [("reviews.csv", records, FIELDS),
                               ("preparation_issues.csv", issues, ["record_number", "source_date_text", "issue", "action"])]:
        with (output / name).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader(); writer.writerows(rows)
    metadata = dict(schema_version=1, method="user_prepared_csv; no crawling", source=source,
                    is_synthetic=source == "synthetic", cafe_id=cafe_id, cafe_name=cafe_name,
                    place_url=place_url, prepared_at=datetime.now().astimezone().isoformat(),
                    input_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(), counts=dict(counts),
                    review_date_basis="review written date; unknown dates left blank",
                    identity_scope="content/date occurrence within this input; not original platform review IDs")
    (output / "preparation_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser(description="본문·작성일 양식을 분석용 리뷰 CSV로 변환합니다.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cafe-name", required=True, help="카페명과 지점을 함께 입력")
    parser.add_argument("--cafe-id", help="같은 지점에 반복 사용하는 고정 ID")
    parser.add_argument("--source", choices=("naver_place", "synthetic"), default="naver_place")
    parser.add_argument("--place-url", default="", help="원본 매장 URL, 선택")
    args = parser.parse_args()
    try:
        result = prepare(args.input, args.output, args.cafe_name, args.cafe_id, args.source, args.place_url)
        print(json.dumps({"output": str(Path(args.output) / "reviews.csv"), "counts": result["counts"]}, ensure_ascii=False))
        return 0
    except (ValueError, OSError, UnicodeError, csv.Error) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
