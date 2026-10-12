"""Idempotent authored corrections from development error types, not human approval."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCHES = {
    "비싸다": (r"비[싸싼쌌쌈]", ["비쌈"]),
    "재방문 의사가 있다": (r"재방문\s*의사[가은는]*\s*(?:있|[oO][kK]|ㅇㅋ)", ["재방문 의사 OK"]),
    "재방문 의사 없다": (r"재방문\s*의사[가은는]*\s*(?:없|[xX]|[nN][oO])", ["재방문 의사 X", "재방문 의사 NO"]),
    "가격이 좀 있다": (r"(?:가격대[이가은는]*\s*(?:(?:좀|약간|조금|꽤)\s*)?있|가격[이가은는]*\s*(?:좀|약간|조금|꽤)\s*있)", ["가격대가 있다"]),
}
ADDITIONS = [
    ("메뉴 외관이 귀엽다", r"(?:(?:귀여운|깜찍한)\s*(?:케이크|케익|스콘|쿠키|빵|디저트)|(?:케이크|케익|스콘|쿠키|빵|디저트)[이가은는도]*\s*(?:귀[엽여]|깜찍))", "menu", 1, []),
    ("사람이 너무 많다", r"사람[이가은는]*\s*너무\s*많", "operation", -1, []),
    ("너무 붐비다", r"(?:너무|핵)\s*붐[비빔]", "operation", -1, []),
    ("분위기가 기분 좋다", r"기분\s*좋", "space", 1, ["분위기", "공간", "인테리어", "뷰"]),
    ("다른 곳을 고르겠다", r"(?:굳이\s*)?(?:여긴|여기는)\s*아닌\s*걸로", "overall", -1, []),
]


def main():
    path = ROOT / "lexicon/cafe_sentiment.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields, entries = reader.fieldnames, list(reader)
    lookup = {entry["expression"]: entry for entry in entries}
    for expression, (pattern, variants) in PATCHES.items():
        entry = lookup[expression]
        entry["pattern"] = r"(?<![가-힣])(?:" + pattern + ")"
        entry["variants"] = json.dumps(variants, ensure_ascii=False)
        entry["notes"] = "v0.3 개발 오류 유형 보완. 사람 검증 전."
    for entry in entries:
        entry["pattern"] = entry["pattern"].replace("가격[", "가격대?[")
        entry["pattern"] = entry["pattern"].replace("나[오왔]", "나[오왔와]")
    index = max(int(entry["entry_id"].removeprefix("CAFE")) for entry in entries)
    for expression, pattern, category, polarity, terms in ADDITIONS:
        if expression in lookup:
            continue
        index += 1
        entry = {"entry_id": f"CAFE{index:04d}", "expression": expression, "variants": "[]",
                 "pattern": r"(?<![가-힣])(?:" + pattern + ")", "category": category, "subcategory": "",
                 "polarity": str(polarity), "match_type": "regex", "target_terms": json.dumps(terms, ensure_ascii=False),
                 "context_rule_id": "default", "provenance": "authored_by_codex_error_type_2026-10-12",
                 "status": "candidate", "notes": "개발 오류 유형 보완 가설. 사람 검증 전."}
        entries.append(entry)
        lookup[expression] = entry
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(entries)
    rules_path = ROOT / "lexicon/context_rules.json"
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    rules["version"] = "0.3.0"
    rules["abstain_patterns"]["uncertain"] = r"^(?:어|아)?\s*보[이여입였]|^(?:한지|할지|은지|는지|을지|ㄹ지)\s*모르"
    rules["negation_suffix"] = r"^(?:하)?(?:지|지는|지도|진)\s*않[가-힣]*|^(?:하)?지\s*못[가-힣]*"
    rules["intensifier_prefix"] = r"(?:정말|매우|엄청|너무|진짜|아주|짱|넘)\s*$"
    rules_path.write_text(json.dumps(rules, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Candidate entries: {len(entries)}")


if __name__ == "__main__":
    main()
