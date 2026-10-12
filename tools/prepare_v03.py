"""Freeze input roles and blank independent human labels for v0.3."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLES = {"terarosa_gangneung":"development", "fritz_dohwa":"development",
         "onion_anguk":"validation", "layered_anguk":"development_audit",
         "daelim_seongsu":"development_audit", "narinamu":"application",
         "momos_oncheonjang":"holdout", "anthracite_hapjeong":"holdout"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    records=[]
    for name in ("reviews.v02.csv", "reviews.holdout_v03.csv"):
        with (ROOT / "data_private" / name).open(encoding="utf-8-sig",newline="") as handle:
            records.extend(csv.DictReader(handle))
    keys={(r["source"],r["cafe_id"],r["review_id"]) for r in records}
    if len(keys)!=len(records):
        raise ValueError("Duplicate input identity")
    destination=ROOT / "data_private/reviews.v03.csv"
    if destination.exists():
        raise SystemExit("Fixed v0.3 inputs already exist")
    with destination.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(records[0]))
        writer.writeheader(); writer.writerows(records)
    report={"version":"0.3.0", "input_sha256":digest(destination),
            "lexicon_sha256":digest(ROOT / "lexicon/cafe_sentiment.json"),
            "rules_sha256":digest(ROOT / "lexicon/context_rules.json"), "cafes":[],
            "policy":"v0.2 audit cafes now development references; new cafe text not used for classifier changes",
            "accuracy_status":"no_human_gold_labels"}
    for cafe_id,role in ROLES.items():
        rows=[r for r in records if r["cafe_id"]==cafe_id]
        nonempty=[r for r in rows if r["text"].strip()]
        report["cafes"].append({"cafe_id":cafe_id,"cafe_name":rows[0]["cafe_name"],"role":role,
                               "collected":len(rows),"nonempty":len(nonempty),
                               "undated_nonempty":sum(not r["review_date"] for r in nonempty)})
    (ROOT / "docs/dataset.v03.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    labels=json.loads((ROOT / "lexicon/context_rules.json").read_text(encoding="utf-8"))["category_labels"]
    fields=["source","review_id","cafe_id","split","text","category","gold_label","evidence_text","reviewer","notes"]
    with (ROOT / "data_private/annotations.v03.holdout.blank.csv").open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
        for cafe_id,role in ROLES.items():
            if role!="holdout":continue
            rows=[r for r in records if r["cafe_id"]==cafe_id and r["text"].strip()]
            rows.sort(key=lambda r:hashlib.sha256((r["source"]+cafe_id+r["review_id"]).encode()).hexdigest())
            for row in rows[:30]:
                for category in labels:
                    writer.writerow({key:row[key] for key in ("source","review_id","cafe_id","text")} |
                                     {"split":"holdout","category":category})
    print(json.dumps({"collected":len(records),"nonempty":sum(bool(r['text'].strip()) for r in records),"roles":report['cafes']},ensure_ascii=False))


if __name__=="__main__":main()
