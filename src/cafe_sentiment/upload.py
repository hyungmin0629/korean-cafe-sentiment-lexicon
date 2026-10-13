"""Validate uploaded CSV and normalize it without scoring or inferring dates."""
import csv
import hashlib
import io
import re
from collections import Counter
from datetime import date

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 20000
FIELDS = ["review_id", "cafe_id", "cafe_name", "source", "review_date", "text", "rating",
          "collected_at", "visit_date", "source_date_text", "source_url"]
ALIASES = {"리뷰본문": "text", "리뷰작성일": "review_date"}


class UploadError(ValueError):
    pass


def normalize_date(value):
    match = re.fullmatch(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})\.?", value.strip())
    if not match:
        return ""
    try:
        return date(*map(int, match.groups())).isoformat()
    except ValueError:
        return ""


def prepare_upload(text, cafe_name="", source="naver_place"):
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_BYTES:
        raise UploadError("CSV는 UTF-8 형식, 10MB 이하로 준비해주세요.")
    if "\x00" in text:
        raise UploadError("CSV에 읽을 수 없는 문자가 있습니다. CSV UTF-8로 다시 저장해주세요.")
    if not isinstance(cafe_name, str) or len(cafe_name) > 150:
        raise UploadError("카페 이름은 150자 이하로 입력해주세요.")
    cafe_name = cafe_name.strip()
    if source not in {"naver_place", "diningcode", "manual", "synthetic"}:
        raise UploadError("출처를 다시 선택해주세요.")
    reader = csv.reader(io.StringIO(text.lstrip("\ufeff"), newline=""), strict=True)
    try:
        original_headers = next(reader, [])
        headers = [ALIASES.get(name.strip(), name.strip()) for name in original_headers]
        if not headers or any(not name for name in headers) or len(set(headers)) != len(headers):
            raise UploadError("첫 행에 서로 다른 열 이름이 필요합니다. 빈 열 이름과 중복 열을 확인해주세요.")
        full = {"review_id", "cafe_id", "source", "text"}.issubset(headers)
        simple = set(headers) == {"text", "review_date"} and len(headers) == 2
        if not full and not simple:
            raise UploadError("크롤러 CSV(review_id,cafe_id,source,text) 또는 리뷰본문,리뷰작성일 두 열을 사용해주세요.")
        if simple and not cafe_name:
            raise UploadError("본문·작성일 두 열의 CSV에는 카페 이름과 지점을 입력해주세요.")
        generated_cafe = "cafe_" + hashlib.sha256(cafe_name.encode()).hexdigest()[:16]
        rows, issues, counts, seen, occurrences = [], [], Counter(), set(), Counter()
        def issue(number, kind, action, review_id=""):
            counts[kind] += 1
            issues.append({"record_number": number, "review_id": review_id, "issue": kind, "action": action})
        for number, values in enumerate(reader, 2):
            counts["input_rows"] += 1
            if counts["input_rows"] > MAX_ROWS:
                raise UploadError("한 파일은 20,000개 기록까지 처리합니다. 파일을 나누어 올려주세요.")
            if not values or all(not v.strip() for v in values):
                issue(number, "blank_rows", "row_skipped")
                continue
            if len(values) != len(headers):
                raise UploadError(f"{number}번째 기록의 열 수가 다릅니다. 쉼표와 따옴표를 확인해주세요.")
            raw = dict(zip(headers, values))
            row = {name: raw.get(name, "").strip() for name in FIELDS}
            # Preserve the body's internal spacing, commas, line breaks and emoji.
            row["text"] = raw["text"].strip()
            if len(row["text"]) > 20000:
                raise UploadError(f"{number}번째 기록의 본문이 20,000자를 넘습니다.")
            if simple:
                row.update(cafe_id=generated_cafe, cafe_name=cafe_name, source=source)
                identity = "\0".join([source, generated_cafe, row["text"], row["review_date"]])
                digest = hashlib.sha256(identity.encode()).hexdigest()
                occurrences[digest] += 1
                row["review_id"] = f"upload_{digest}_{occurrences[digest]}"
            if any(not row[name] for name in ("review_id", "cafe_id", "source", "text")):
                issue(number, "missing_required", "row_skipped", row["review_id"])
                continue
            identity = row["source"], row["cafe_id"], row["review_id"]
            if identity in seen:
                issue(number, "duplicate_id", "first_row_retained", row["review_id"])
                continue
            seen.add(identity)
            original_date = row["review_date"]
            row["review_date"] = normalize_date(original_date)
            if original_date and not row["source_date_text"]:
                row["source_date_text"] = original_date
            if not row["review_date"]:
                issue(number, "invalid_date" if original_date else "missing_date",
                      "excluded_from_date_based_summary", row["review_id"])
                counts["unknown_dates"] += 1
                if normalize_date(row["visit_date"]):
                    counts["visit_only"] += 1
            else:
                counts["dated_rows"] += 1
            rows.append(row)
    except csv.Error as exc:
        raise UploadError("CSV의 따옴표·열 구성이 올바르지 않습니다. CSV UTF-8로 다시 저장해주세요.") from exc
    if not rows:
        raise UploadError("분석할 리뷰 본문이 없습니다. 빈 행과 필수 정보를 확인해주세요.")
    cafes = {row["cafe_id"] for row in rows}
    if full and cafe_name:
        if len(cafes) != 1:
            raise UploadError("여러 카페가 있는 CSV는 카페 이름을 비워 기존 카페 정보를 사용해주세요.")
        for row in rows:
            row["cafe_name"] = cafe_name
    dates = sorted({row["review_date"] for row in rows if row["review_date"]})
    counts.update(accepted_rows=len(rows), excluded_rows=counts["input_rows"] - len(rows), cafe_count=len(cafes))
    preview = {"format": "crawler_csv" if full else "two_column_csv", "counts": dict(counts),
               "date_start": dates[0] if dates else None, "date_end": dates[-1] if dates else None,
               "month_count": len({value[:7] for value in dates}),
               "cafes": sorted({row["cafe_name"] or row["cafe_id"] for row in rows}),
               "sources": sorted({row["source"] for row in rows}),
               "ignored_columns": [name for name in headers if name not in FIELDS],
               "rows": [{key: row[key] for key in ("review_id", "cafe_name", "source", "review_date", "visit_date", "text")} for row in rows[:5]],
               "issue_examples": issues[:10]}
    return rows, issues, preview
